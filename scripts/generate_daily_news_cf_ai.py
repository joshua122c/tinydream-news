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

REQUIRED_BRIEF_FIELDS = [
    "date",
    "title",
    "deck",
    "daily_summary_zh",
    "market_focus",
    "hot_topics",
    "categories",
    "items",
    "sources",
    "generated_at",
]

REQUIRED_HOT_TOPIC_FIELDS = [
    "rank",
    "topic",
    "heat_score",
    "heat_label",
    "source_count",
    "main_sources",
    "item_ids",
    "one_line_reason",
    "reporter_angle",
]

REQUIRED_ITEM_FIELDS = [
    "id",
    "date",
    "title_original",
    "title_zh",
    "source",
    "url",
    "published_at",
    "category",
    "themes",
    "summary_zh",
    "key_facts",
    "market_impact",
    "reporter_angle",
    "importance_score",
    "heat_score",
    "source_count",
    "sources_reporting_same_topic",
    "position_signal",
    "time_horizon",
    "tracking_value",
]


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
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def absolute_url(base_url: str, href: str) -> str:
    return urllib.parse.urljoin(base_url, html.unescape(href.strip()))


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

    keyword_pattern = re.compile(
        r"(fed|fomc|inflation|cpi|pce|jobs|payroll|treasury|yield|dollar|oil|gold|"
        r"nvidia|amd|broadcom|marvell|tsmc|semiconductor|chip|ai|artificial intelligence|"
        r"agent|datacenter|data center|cloud|apple|tesla|microsoft|google|meta|amazon|"
        r"\u7f8e\u806f\u5132|\u806f\u5132|\u901a\u8139|\u975e\u8fb2|\u7f8e\u50b5|\u7f8e\u5143|\u9ec3\u91d1|\u539f\u6cb9|\u4eba\u5de5\u667a\u80fd|\u534a\u5c0e\u9ad4|\u82af\u7247|\u6676\u7247|\u7b97\u529b|"
        r"\u83ef\u70ba|\u9a30\u8a0a|\u963f\u91cc|\u7f8e\u5718|\u5c0f\u7c73|\u767e\u5ea6|\u6bd4\u4e9e\u8fea)",
        re.I,
    )
    filtered = [item for item in all_candidates if keyword_pattern.search(item["title"])]
    if len(filtered) < 20:
        filtered = all_candidates[:80]
    return filtered[:100], sources


def sanitize_json_text(text: str) -> str:
    text = re.sub(r"\\u(?![0-9a-fA-F]{4})", r"\\\\u", text)
    text = re.sub(r"\\(?![\"\\/bfnrtu])", r"\\\\", text)
    return text


def load_json_with_repair(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        repaired = sanitize_json_text(text)
        if repaired != text:
            try:
                print("Warning: repaired invalid JSON escape sequences from AI output.")
                return json.loads(repaired)
            except json.JSONDecodeError:
                pass
        start = max(0, exc.pos - 300)
        end = min(len(text), exc.pos + 300)
        preview = text[start:end].encode("unicode_escape", errors="replace").decode("ascii")
        print(f"Cloudflare AI JSON parse failed near char {exc.pos}: {preview}", file=sys.stderr)
        raise


def extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return load_json_with_repair(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            raise
        return load_json_with_repair(match.group(0))


def call_cloudflare_ai(candidates: list[dict], sources: list[dict]) -> dict:
    account_id = env_required("CLOUDFLARE_ACCOUNT_ID")
    api_token = env_required("CLOUDFLARE_API_TOKEN")
    model = os.environ.get("CF_AI_MODEL", "@cf/meta/llama-3.1-8b-instruct").strip()

    candidates_json = json.dumps(candidates, ensure_ascii=False, indent=2)
    sources_json = json.dumps(sources, ensure_ascii=False, indent=2)

    prompt = f"""
\u4eca\u5929\u65e5\u671f\u662f {TODAY}\uff0c\u6642\u5340\u662f Asia/Hong_Kong\u3002

\u4f60\u662f\u4e00\u540d\u8ca1\u7d93/\u79d1\u6280\u65b0\u805e\u7de8\u8f2f\u3002\u4ee5\u4e0b\u662f\u5f9e\u591a\u500b\u4f86\u6e90\u6293\u53d6\u5230\u7684\u5019\u9078\u65b0\u805e\u6a19\u984c\u548c\u9023\u7d50\u3002
\u8acb\u4e0d\u8981\u4ee5\u4efb\u4f55\u55ae\u4e00\u4f86\u6e90\u70ba\u4e3b\uff0c\u8acb\u6839\u64da\u5019\u9078\u65b0\u805e\u505a topic clustering\uff0c\u627e\u51fa\u570b\u969b\u8ca1\u7d93\u3001\u91d1\u878d\u5e02\u5834\u3001AI\u3001\u534a\u5c0e\u9ad4\u3001\u79d1\u6280\u7522\u696d\u3001\u4e2d\u570b\u79d1\u6280/\u653f\u7b56\u7684\u4eca\u65e5\u7126\u9ede\u3002

\u4f86\u6e90\u72c0\u614b\uff1a
{sources_json}

\u5019\u9078\u65b0\u805e\uff1a
{candidates_json}

\u8acb\u53ea\u8f38\u51fa\u5408\u6cd5 JSON\uff0c\u4e0d\u8981\u8f38\u51fa markdown\uff0c\u4e0d\u8981\u52a0\u89e3\u91cb\u6587\u5b57\u3002

JSON schema:
{{
  "date": "{TODAY}",
  "title": "\u7e41\u9ad4\u4e2d\u6587\u6a19\u984c",
  "deck": "\u7e41\u9ad4\u4e2d\u6587\u5c0e\u8a9e",
  "daily_summary_zh": "\u7e41\u9ad4\u4e2d\u6587\u6bcf\u65e5\u7e3d\u7d50",
  "market_focus": ["\u7126\u9ede1", "\u7126\u9ede2", "\u7126\u9ede3"],
  "hot_topics": [
    {{
      "rank": 1,
      "topic": "\u7126\u9ede\u4e3b\u984c",
      "heat_score": 80,
      "heat_label": "High",
      "source_count": 3,
      "main_sources": ["Reuters", "CNBC"],
      "item_ids": ["{TODAY}-source-topic-001"],
      "one_line_reason": "\u4e0a\u699c\u539f\u56e0",
      "reporter_angle": "\u8a18\u8005\u53ef\u8ddf\u9032\u89d2\u5ea6"
    }}
  ],
  "categories": [
    {{
      "name": "AI\u7b97\u529b\u8207\u534a\u5c0e\u9ad4",
      "slug": "ai-compute-semiconductors",
      "item_ids": ["{TODAY}-source-topic-001"]
    }}
  ],
  "items": [
    {{
      "id": "{TODAY}-source-topic-001",
      "date": "{TODAY}",
      "title_original": "Original headline",
      "title_zh": "\u7e41\u9ad4\u4e2d\u6587\u6a19\u984c",
      "source": "Reuters",
      "url": "https://example.com/article",
      "published_at": "{GENERATED_AT}",
      "category": "\u570b\u969b\u5b8f\u89c0\u8207\u592e\u884c",
      "themes": ["Fed policy", "AI infrastructure"],
      "summary_zh": "\u7e41\u9ad4\u4e2d\u6587\u6458\u8981\u3002\u82e5\u53ea\u8b80\u5230\u6a19\u984c\uff0c\u8acb\u660e\u78ba\u8aaa\u9019\u662f\u6839\u64da\u6a19\u984c\u548c\u4f86\u6e90\u4e0a\u4e0b\u6587\u7684\u6458\u8981\u3002",
      "key_facts": ["\u4e8b\u5be61", "\u4e8b\u5be62"],
      "market_impact": "\u5e02\u5834\u5f71\u97ff",
      "reporter_angle": "\u8a18\u8005\u53ef\u8ddf\u9032\u89d2\u5ea6",
      "importance_score": 8,
      "heat_score": 75,
      "source_count": 3,
      "sources_reporting_same_topic": ["Reuters", "CNBC"],
      "position_signal": "headline cluster",
      "time_horizon": "short_term",
      "tracking_value": "\u8ffd\u8e64\u50f9\u503c"
    }}
  ],
  "sources": [
    {{
      "name": "Reuters Markets",
      "url": "https://www.reuters.com/markets/",
      "access": "Full"
    }}
  ],
  "generated_at": "{GENERATED_AT}",
  "email_body_zh": "1000\u81f31600\u5b57\u7e41\u9ad4\u4e2d\u6587 email \u6b63\u6587\uff0c\u5305\u542b\u4eca\u65e5\u4e00\u53e5\u8a71\u7d50\u8ad6\u3001\u7126\u9ede\u65b0\u805e\u699c\u3001\u8ca1\u7d93\u8207\u79d1\u6280\u91cd\u9ede\u3001\u8a18\u8005\u53ef\u8ddf\u9032\u89d2\u5ea6\u548c\u539f\u6587\u9023\u7d50\u3002"
}}

\u8981\u6c42\uff1a
- hot_topics \u5fc5\u9808\u6709 3 \u81f3 5 \u500b\u3002
- items \u81f3\u5c11 6 \u689d\uff0c\u6700\u591a 12 \u689d\u3002
- \u6bcf\u500b hot_topics[].item_ids \u4e0d\u53ef\u70ba\u7a7a\u3002
- \u6bcf\u500b hot_topics[].item_ids \u5fc5\u9808\u5b58\u5728\u65bc items[].id\u3002
- categories[].item_ids \u5fc5\u9808\u5b58\u5728\u65bc items[].id\u3002
- \u4e0d\u53ef\u6709 duplicate item id\u3002
- \u4f7f\u7528\u7e41\u9ad4\u4e2d\u6587\u3002
- heat_score 0-100\uff0c75-100 High\uff0c50-74 Medium\uff0c\u4f4e\u65bc50 Low\u3002
- importance_score 1-10\u3002
- \u4e0d\u63d0\u4f9b\u500b\u4eba\u5316\u6295\u8cc7\u5efa\u8b70\u3002
"""

    payload = {
        "messages": [
            {
                "role": "system",
                "content": "You output strict JSON only. No markdown.",
            },
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 6000,
        "temperature": 0.2,
    }

    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        },
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
    if not text and isinstance(result.get("tool_calls"), list):
        text = json.dumps(result, ensure_ascii=False)
    if not text:
        fail(f"Cloudflare Workers AI response missing text: {raw[:1000]}")
    return extract_json(text)


def normalize_brief(brief: dict, sources: list[dict]) -> dict:
    brief["date"] = TODAY
    brief["generated_at"] = brief.get("generated_at") or GENERATED_AT
    if not brief.get("sources"):
        brief["sources"] = sources
    if "email_body_zh" not in brief:
        brief["email_body_zh"] = brief.get("daily_summary_zh", "")
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

    body = brief.get("email_body_zh") or brief.get("daily_summary_zh", "")
    body += "\n\n\u7db2\u7ad9\uff1ahttps://news.tinydreamlab.com/\n"

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

    brief = call_cloudflare_ai(candidates, sources)
    brief = normalize_brief(brief, sources)
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
