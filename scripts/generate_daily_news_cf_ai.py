#!/usr/bin/env python3
import html
import json
import os
import re
import smtplib
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path

HK_TZ = timezone(timedelta(hours=8))
TODAY = datetime.now(HK_TZ).strftime("%Y-%m-%d")
GENERATED_AT = datetime.now(HK_TZ).isoformat(timespec="seconds")

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
BRIEFS_DIR = DATA_DIR / "briefs"
INDEX_PATH = DATA_DIR / "index.json"
BRIEF_PATH = BRIEFS_DIR / f"{TODAY}.json"
USER_AGENT = "Mozilla/5.0 (compatible; TinyDreamNewsRadar/1.0; +https://news.tinydreamlab.com/)"

SOURCE_URLS = [
    ("Wallstreetcn", "https://wallstreetcn.com/"),
    ("Reuters Markets", "https://www.reuters.com/markets/"),
    ("Reuters Technology", "https://www.reuters.com/technology/"),
    ("CNBC Markets", "https://www.cnbc.com/markets/"),
    ("CNBC Technology", "https://www.cnbc.com/technology/"),
    ("TechCrunch AI", "https://techcrunch.com/category/artificial-intelligence/"),
    ("TechCrunch Startups", "https://techcrunch.com/category/startups/"),
    ("Caixin", "https://www.caixin.com/"),
    ("LatePost", "https://www.latepost.com/"),
]

REQUIRED_BRIEF_FIELDS = ["date", "title", "deck", "daily_summary_zh", "market_focus", "hot_topics", "categories", "items", "sources", "generated_at"]
REQUIRED_HOT_TOPIC_FIELDS = ["rank", "topic", "heat_score", "heat_label", "source_count", "main_sources", "item_ids", "one_line_reason", "reporter_angle"]
REQUIRED_ITEM_FIELDS = ["id", "date", "title_original", "title_zh", "source", "url", "published_at", "category", "themes", "summary_zh", "key_facts", "market_impact", "reporter_angle", "importance_score", "heat_score", "source_count", "sources_reporting_same_topic", "position_signal", "time_horizon", "tracking_value"]


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def env_required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        fail(f"Missing required environment variable: {name}")
    return value


def fetch_url(url: str) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            raw = response.read(1_500_000)
            charset = response.headers.get_content_charset() or "utf-8"
            return response.status, raw.decode(charset, errors="replace")
    except Exception as exc:
        return 0, f"FETCH_ERROR: {exc}"


def clean_text(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value or "")
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def absolute_url(base_url: str, href: str) -> str:
    return urllib.parse.urljoin(base_url, html.unescape((href or "").strip()))


def extract_candidates(source_name: str, url: str, body: str) -> list[dict]:
    candidates = []
    seen = set()
    for title in re.findall(r"<title[^>]*>(.*?)</title>", body, flags=re.I | re.S):
        text = clean_text(title)
        if 12 <= len(text) <= 180 and text not in seen:
            seen.add(text)
            candidates.append({"source": source_name, "title": text, "url": url})

    anchor_pattern = re.compile(r"<a\s+[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", re.I | re.S)
    for href, label in anchor_pattern.findall(body):
        text = clean_text(label)
        if not (18 <= len(text) <= 180):
            continue
        lower = text.lower()
        if any(skip in lower for skip in ["subscribe", "sign in", "cookie", "privacy", "terms"]):
            continue
        link = absolute_url(url, href)
        key = (text, link)
        if key in seen:
            continue
        seen.add(key)
        candidates.append({"source": source_name, "title": text, "url": link})
        if len(candidates) >= 30:
            break
    return candidates


def collect_news_candidates() -> tuple[list[dict], list[dict]]:
    all_candidates = []
    sources = []
    for source_name, url in SOURCE_URLS:
        status, body = fetch_url(url)
        access = "Full" if status == 200 else "Blocked"
        sources.append({"name": source_name, "url": url, "access": access})
        if status == 200:
            all_candidates.extend(extract_candidates(source_name, url, body))

    keywords = re.compile(r"fed|fomc|inflation|cpi|pce|jobs|treasury|yield|dollar|oil|gold|nvidia|amd|tsmc|semiconductor|chip|ai|artificial intelligence|cloud|apple|tesla|microsoft|google|meta|amazon|\u806f\u5132|\u901a\u8139|\u975e\u8fb2|\u9ec3\u91d1|\u539f\u6cb9|\u4eba\u5de5\u667a\u80fd|\u534a\u5c0e\u9ad4|\u82af\u7247|\u6676\u7247", re.I)
    filtered = [item for item in all_candidates if keywords.search(item["title"])]
    if len(filtered) < 20:
        filtered = all_candidates[:80]
    return filtered[:100], sources


def strip_code_fence(text: str) -> str:
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def sanitize_json_text(text: str) -> str:
    text = re.sub(r"\\u(?![0-9a-fA-F]{4})", r"\\\\u", text)
    text = re.sub(r"\\(?![\"\\/bfnrtu])", r"\\\\", text)
    return text


def extract_json(text: str) -> dict:
    text = strip_code_fence(text)
    candidates = [text]
    match = re.search(r"\{.*\}", text, flags=re.S)
    if match and match.group(0) != text:
        candidates.append(match.group(0))
    for candidate in candidates:
        for attempt in [candidate, sanitize_json_text(candidate)]:
            try:
                return json.loads(attempt)
            except json.JSONDecodeError:
                continue
    raise json.JSONDecodeError("Cloudflare AI did not return parseable JSON", text, 0)


def call_cloudflare_ai(candidates: list[dict], sources: list[dict]) -> dict:
    account_id = env_required("CLOUDFLARE_ACCOUNT_ID")
    api_token = env_required("CLOUDFLARE_API_TOKEN")
    model = os.environ.get("CF_AI_MODEL", "@cf/meta/llama-3.1-8b-instruct").strip()

    prompt = {
        "task": "Create a Traditional Chinese website-ready daily international finance and technology news brief. Output strict JSON only. Use real Traditional Chinese characters, not Unicode escape placeholders like \\uXXXX.",
        "date": TODAY,
        "schema_rules": [
            "Return only one JSON object, no markdown.",
            "hot_topics must have 3 to 5 entries and every item_ids value must exist in items[].id.",
            "items must have at least 6 entries and every item must include the required website fields.",
            "categories[].item_ids must exist in items[].id.",
            "Do not give personalized investment advice.",
        ],
        "required_item_fields": REQUIRED_ITEM_FIELDS,
        "required_hot_topic_fields": REQUIRED_HOT_TOPIC_FIELDS,
        "sources": sources,
        "candidate_headlines": candidates[:80],
    }

    payload = {
        "messages": [
            {"role": "system", "content": "You output strict JSON only. No markdown. Use Traditional Chinese characters directly."},
            {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
        ],
        "max_tokens": 6000,
        "temperature": 0.1,
    }

    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        error = exc.read().decode("utf-8", errors="replace")
        fail(f"Cloudflare Workers AI HTTP {exc.code}: {error}")

    data = json.loads(raw)
    if not data.get("success", False):
        fail(f"Cloudflare Workers AI failed: {raw}")

    result = data.get("result", {})
    text = result.get("response") or result.get("text") or result.get("content")
    if not text:
        fail(f"Cloudflare Workers AI response missing text: {raw[:1000]}")
    return extract_json(text)


def normalize_brief(brief: dict, sources: list[dict]) -> dict:
    brief["date"] = TODAY
    brief["generated_at"] = brief.get("generated_at") or GENERATED_AT
    brief.setdefault("sources", sources)
    brief.setdefault("email_body_zh", brief.get("daily_summary_zh", ""))
    return brief


def validate_brief(brief: dict) -> None:
    for field in REQUIRED_BRIEF_FIELDS:
        if field not in brief:
            fail(f"Brief missing required field: {field}")
    if brief["date"] != TODAY:
        fail(f"Brief date {brief['date']} does not match {TODAY}")

    items = brief.get("items")
    if not isinstance(items, list) or len(items) < 6:
        fail("items must contain at least 6 entries.")
    item_ids = set()
    for item in items:
        for field in REQUIRED_ITEM_FIELDS:
            if field not in item:
                fail(f"Item missing required field {field}: {item.get('id')}")
        if item["id"] in item_ids:
            fail(f"Duplicate item id: {item['id']}")
        item_ids.add(item["id"])

    hot_topics = brief.get("hot_topics")
    if not isinstance(hot_topics, list) or not (3 <= len(hot_topics) <= 5):
        fail("hot_topics must contain 3 to 5 entries.")
    for topic in hot_topics:
        for field in REQUIRED_HOT_TOPIC_FIELDS:
            if field not in topic:
                fail(f"Hot topic missing required field {field}: {topic}")
        refs = topic.get("item_ids")
        if not isinstance(refs, list) or not refs:
            fail(f"Hot topic has empty item_ids: {topic.get('topic')}")
        for item_id in refs:
            if item_id not in item_ids:
                fail(f"Hot topic item_id not found in items: {item_id}")

    for category in brief.get("categories", []):
        refs = category.get("item_ids", [])
        if not isinstance(refs, list):
            fail(f"Category item_ids must be a list: {category.get('name')}")
        for item_id in refs:
            if item_id not in item_ids:
                fail(f"Category item_id not found in items: {item_id}")


def build_index_entry(brief: dict) -> dict:
    top_themes = []
    for item in brief.get("items", []):
        for theme in item.get("themes", []):
            if theme not in top_themes:
                top_themes.append(theme)
            if len(top_themes) >= 5:
                break
        if len(top_themes) >= 5:
            break
    return {
        "date": brief["date"],
        "title": brief["title"],
        "summary": brief["deck"],
        "top_themes": top_themes,
        "hot_topic_count": len(brief.get("hot_topics", [])),
        "item_count": len(brief.get("items", [])),
        "generated_at": brief["generated_at"],
    }


def update_index(brief: dict) -> dict:
    if INDEX_PATH.exists():
        index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    else:
        index = {"latest_date": TODAY, "briefs": []}
    entry = build_index_entry(brief)
    briefs = [b for b in index.get("briefs", []) if b.get("date") != TODAY]
    briefs.append(entry)
    briefs.sort(key=lambda row: row.get("date", ""), reverse=True)
    return {"latest_date": TODAY, "briefs": briefs}


def build_fallback_brief(candidates: list[dict], sources: list[dict], error: str) -> dict:
    usable = [item for item in candidates if item.get("title") and item.get("url")]
    if not usable:
        usable = [{"source": source["name"], "title": source["name"], "url": source["url"]} for source in sources]
    while len(usable) < 6:
        usable.append(usable[len(usable) % max(1, len(usable))])

    category_defs = [
        ("\u570b\u969b\u8ca1\u7d93\u8207\u5e02\u5834", "global-finance-markets"),
        ("AI\u8207\u79d1\u6280\u7522\u696d", "ai-technology-industry"),
        ("\u4e2d\u570b\u79d1\u6280\u8207\u653f\u7b56", "china-tech-policy"),
    ]
    items = []
    for idx, candidate in enumerate(usable[:6], start=1):
        category_name, _ = category_defs[(idx - 1) % len(category_defs)]
        source_name = candidate.get("source") or "Public source"
        title = clean_text(candidate.get("title") or source_name)
        items.append({
            "id": f"{TODAY}-fallback-{idx:03d}",
            "date": TODAY,
            "title_original": title,
            "title_zh": title,
            "source": source_name,
            "url": candidate.get("url") or "https://news.tinydreamlab.com/",
            "published_at": GENERATED_AT,
            "category": category_name,
            "themes": [category_name],
            "summary_zh": "\u9019\u689d\u65b0\u805e\u7531\u81ea\u52d5\u4fdd\u5e95\u6a21\u5f0f\u6839\u64da\u516c\u958b\u6a19\u984c\u548c\u9023\u7d50\u7522\u751f\u3002\u539f\u59cb AI JSON \u56de\u8986\u683c\u5f0f\u672a\u80fd\u901a\u904e\u9a57\u8b49\uff0c\u56e0\u6b64\u672c\u7cfb\u7d71\u5148\u4fdd\u7559\u53ef\u8ffd\u8e64\u7684\u65b0\u805e\u5165\u53e3\u3002",
            "key_facts": ["\u4f86\u6e90\u9801\u9762\u51fa\u73fe\u76f8\u95dc\u6a19\u984c\u6216\u9023\u7d50\u3002", "\u9700\u4eba\u624b\u6216\u4e0b\u4e00\u8f2a\u81ea\u52d5\u6458\u8981\u9032\u4e00\u6b65\u88dc\u5145\u5167\u5bb9\u3002"],
            "market_impact": "\u9700\u5f8c\u7e8c\u8ddf\u9032\u3002",
            "reporter_angle": "\u53ef\u5f9e\u539f\u6587\u9023\u7d50\u6838\u5be6\u4e8b\u5be6\u548c\u5e02\u5834\u5f71\u97ff\u3002",
            "importance_score": max(5, 9 - idx),
            "heat_score": max(50, 82 - idx * 4),
            "source_count": 1,
            "sources_reporting_same_topic": [source_name],
            "position_signal": "fallback headline candidate",
            "time_horizon": "short_term",
            "tracking_value": "\u9700\u8ffd\u8e64\u539f\u6587\u66f4\u65b0\u8207\u76f8\u95dc\u5831\u9053\u3002",
        })

    hot_topics = []
    for rank, item in enumerate(items[:3], start=1):
        hot_topics.append({
            "rank": rank,
            "topic": item["title_zh"][:60],
            "heat_score": item["heat_score"],
            "heat_label": "High" if item["heat_score"] >= 75 else "Medium",
            "source_count": 1,
            "main_sources": [item["source"]],
            "item_ids": [item["id"]],
            "one_line_reason": "\u81ea\u52d5\u4fdd\u5e95\u6a21\u5f0f\u9078\u51fa\u7684\u9ad8\u512a\u5148\u7d1a\u65b0\u805e\u5165\u53e3\u3002",
            "reporter_angle": item["reporter_angle"],
        })

    categories = []
    for category_name, slug in category_defs:
        refs = [item["id"] for item in items if item["category"] == category_name]
        if refs:
            categories.append({"name": category_name, "slug": slug, "item_ids": refs})

    return {
        "date": TODAY,
        "title": "\u6bcf\u65e5\u570b\u969b\u8ca1\u7d93\u8207\u79d1\u6280\u65b0\u805e\u6458\u8981",
        "deck": "\u4eca\u65e5\u6458\u8981\u7531\u81ea\u52d5\u4fdd\u5e95\u6a21\u5f0f\u7522\u751f\uff0c\u4fdd\u7559\u65b0\u805e\u6a19\u984c\u3001\u4f86\u6e90\u548c\u539f\u6587\u9023\u7d50\u3002",
        "daily_summary_zh": "\u672c\u6b21 Cloudflare Workers AI \u56de\u8986\u672a\u80fd\u901a\u904e JSON \u9a57\u8b49\u3002\u7cfb\u7d71\u5df2\u555f\u7528\u4fdd\u5e95\u6a21\u5f0f\uff0c\u6839\u64da\u5df2\u6293\u53d6\u7684\u516c\u958b\u65b0\u805e\u6a19\u984c\u548c\u9023\u7d50\u7522\u751f\u53ef\u4f9b\u7db2\u7ad9\u986f\u793a\u7684\u7d50\u69cb\u5316\u6458\u8981\u3002",
        "market_focus": ["\u570b\u969b\u8ca1\u7d93\u8207\u5e02\u5834", "AI\u8207\u79d1\u6280\u7522\u696d", "\u539f\u6587\u9023\u7d50\u8ffd\u8e64"],
        "hot_topics": hot_topics,
        "categories": categories,
        "items": items,
        "sources": sources,
        "generated_at": GENERATED_AT,
        "email_body_zh": "\u4eca\u65e5\u81ea\u52d5\u65b0\u805e\u6458\u8981\u555f\u7528\u4fdd\u5e95\u6a21\u5f0f\u3002\n\n\u539f\u56e0\uff1aCloudflare Workers AI \u56de\u8986\u7684 JSON \u683c\u5f0f\u672a\u80fd\u901a\u904e\u7cfb\u7d71\u9a57\u8b49\u3002\n\n" + str(error)[:500],
    }


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def send_email(brief: dict) -> None:
    email_to = os.environ.get("EMAIL_TO", "").strip()
    smtp_user = os.environ.get("GMAIL_SMTP_USER", "").strip()
    smtp_password = os.environ.get("GMAIL_APP_PASSWORD", "").strip()
    if not (email_to and smtp_user and smtp_password):
        print("Email secrets not fully set; skipping email send.")
        return
    body = (brief.get("email_body_zh") or brief.get("daily_summary_zh", "")) + "\n\n\u7db2\u7ad9\uff1ahttps://news.tinydreamlab.com/\n"
    message = EmailMessage()
    message["From"] = smtp_user
    message["To"] = email_to
    message["Subject"] = f"\u6bcf\u65e5\u8ca1\u7d93\u79d1\u6280\u65b0\u805e\u96f7\u9054 | {TODAY}"
    message.set_content(body)
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context, timeout=60) as server:
        server.login(smtp_user, smtp_password)
        server.send_message(message)
    print("Email sent.")


def main() -> None:
    candidates, sources = collect_news_candidates()
    if len(candidates) < 10:
        print(f"Warning: only collected {len(candidates)} candidate headlines.")

    try:
        brief = call_cloudflare_ai(candidates, sources)
        brief = normalize_brief(brief, sources)
        validate_brief(brief)
    except Exception as exc:
        print(f"Warning: AI brief generation failed; using fallback brief. Reason: {exc}")
        brief = build_fallback_brief(candidates, sources, str(exc))
        validate_brief(brief)

    index = update_index(brief)
    write_json(BRIEF_PATH, brief)
    write_json(INDEX_PATH, index)
    json.loads(BRIEF_PATH.read_text(encoding="utf-8"))
    json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    send_email(brief)
    print(f"Generated {BRIEF_PATH}")
    print(f"Updated {INDEX_PATH}")


if __name__ == "__main__":
    main()
