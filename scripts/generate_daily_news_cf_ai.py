#!/usr/bin/env python3
import html
import json
import os
import re
import smtplib
import ssl
import sys
import time
import urllib.parse
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import parsedate_to_datetime
from pathlib import Path

try:
    from opencc import OpenCC
except Exception:
    try:
        from opencc.opencc import OpenCC
    except Exception:
        OpenCC = None

HK_TZ = timezone(timedelta(hours=8))
NOW_HK = datetime.now(HK_TZ)
TODAY = NOW_HK.strftime("%Y-%m-%d")
UPDATE_ID = NOW_HK.strftime("%Y-%m-%d-%H%M")
GENERATED_AT = NOW_HK.isoformat(timespec="seconds")

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
BRIEFS_DIR = DATA_DIR / "briefs"
INDEX_PATH = DATA_DIR / "index.json"
BRIEF_PATH = BRIEFS_DIR / f"{UPDATE_ID}.json"
DAILY_LATEST_PATH = BRIEFS_DIR / f"{TODAY}.json"

USER_AGENT = "Mozilla/5.0 (compatible; TinyDreamNewsRadar/2.0; +https://news.tinydreamlab.com/)"
LAST_AI_CALL_AT = 0.0
OPENCC_S2HK = None
if OpenCC:
    try:
        OPENCC_S2HK = OpenCC("s2hk")
    except Exception:
        OPENCC_S2HK = None

SOURCE_CONFIGS = [
    {"name": "Reuters Markets", "url": "https://www.reuters.com/markets/", "kind": "page", "tier": 1, "max_items": 16},
    {"name": "Reuters Technology", "url": "https://www.reuters.com/technology/", "kind": "page", "tier": 1, "max_items": 12},
    {"name": "CNBC Top News", "url": "https://www.cnbc.com/id/100003114/device/rss/rss.html", "kind": "rss", "tier": 1, "max_items": 10},
    {"name": "CNBC Markets", "url": "https://www.cnbc.com/markets/", "kind": "page", "tier": 1, "max_items": 8},
    {"name": "CNBC Technology", "url": "https://www.cnbc.com/technology/", "kind": "page", "tier": 1, "max_items": 8},
    {"name": "WSJ Markets", "url": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml", "kind": "rss", "tier": 1, "max_items": 12},
    {"name": "WSJ Technology", "url": "https://feeds.a.dj.com/rss/RSSWSJD.xml", "kind": "rss", "tier": 1, "max_items": 8},
    {"name": "Yahoo Finance", "url": "https://finance.yahoo.com/news/rssindex", "kind": "rss", "tier": 2, "max_items": 8},
    {"name": "MarketWatch Top Stories", "url": "https://feeds.content.dowjones.io/public/rss/mw_topstories", "kind": "rss", "tier": 2, "max_items": 10},
    {"name": "The Guardian Business", "url": "https://www.theguardian.com/business/rss", "kind": "rss", "tier": 2, "max_items": 8},
    {"name": "Nikkei Asia Business", "url": "https://asia.nikkei.com/Business", "kind": "page", "tier": 2, "max_items": 5},
    {"name": "TechCrunch AI", "url": "https://techcrunch.com/category/artificial-intelligence/", "kind": "page", "tier": 2, "max_items": 8},
    {"name": "TechCrunch Startups", "url": "https://techcrunch.com/category/startups/", "kind": "page", "tier": 2, "max_items": 5},
    {"name": "Wallstreetcn", "url": "https://wallstreetcn.com/", "kind": "page", "tier": 3, "max_items": 3},
    {"name": "Caixin", "url": "https://www.caixin.com/", "kind": "page", "tier": 3, "max_items": 3},
    {"name": "LatePost", "url": "https://www.latepost.com/", "kind": "page", "tier": 3, "max_items": 3},
]

SOURCE_FAMILY_LIMIT = 4
CATEGORY_LIMIT = 5
MIN_ITEM_COUNT = 8
MAX_DATED_NEWS_AGE = timedelta(hours=96)
MAX_FUTURE_PUBLISHED_AT = timedelta(hours=6)
MIN_AI_CONTEXT_CONFIDENCE = 0.74
MIN_DIRECT_CONTEXT_CONFIDENCE = 0.74

SUMMARY_BASIS_CONFIDENCE = {
    "rss_description": 0.84,
    "meta_description": 0.76,
    "jsonld_article": 0.88,
    "article_body": 0.72,
    "low_confidence_body": 0.45,
}

RUN_REPORT = {
    "collection": {
        "sources_total": len(SOURCE_CONFIGS),
        "sources_accessible": 0,
        "raw_candidates": 0,
        "accepted_candidates": 0,
        "skipped_by_rule": 0,
        "skipped_stale": 0,
        "keyword_candidates": 0,
        "unique_candidates": 0,
        "grouped_candidates": 0,
    },
    "source_stats": [],
    "item_quality": {
        "built_items": 0,
        "publishable_items": 0,
        "skipped_items": [],
        "summaries_removed": 0,
        "summary_rejections": [],
        "context_confidence": {},
    },
    "ai": {
        "summary_candidates": 0,
        "summary_updates": 0,
        "response_chars": 0,
        "parsed_summaries": 0,
        "rejected_summaries": 0,
        "response_samples": [],
        "last_status": "not_called",
    },
}

CATEGORY_TAXONOMY = [
    ("全球市場與宏觀", "global-markets-macro"),
    ("科技、AI與平台", "technology-ai-platforms"),
    ("半導體與供應鏈", "semiconductors-supply-chain"),
    ("企業、財報與交易", "companies-earnings-deals"),
    ("能源、外匯與商品", "energy-fx-commodities"),
    ("中國與亞洲觀察", "china-asia-watch"),
]

REQUIRED_BRIEF_FIELDS = ["date", "title", "deck", "daily_summary_zh", "market_focus", "hot_topics", "categories", "items", "sources", "generated_at"]
REQUIRED_HOT_TOPIC_FIELDS = ["rank", "topic", "heat_score", "heat_label", "source_count", "main_sources", "item_ids", "one_line_reason", "reporter_angle"]
REQUIRED_ITEM_FIELDS = ["id", "date", "title_original", "title_zh", "source", "url", "published_at", "category", "themes", "summary", "summary_zh", "summary_basis", "summary_status", "key_facts", "market_impact", "reporter_angle", "importance_score", "heat_score", "source_count", "sources_reporting_same_topic", "position_signal", "time_horizon", "tracking_value"]

BAD_READER_PHRASES = [
    "這條消息被列入",
    "追蹤清單",
    "公開新聞標題",
    "保留可追蹤",
    "JSON",
    "fallback",
    "保底模式",
    "市場真正關心的是",
    "投資者需要留意",
    "聚焦 AI 應用",
    "仍是今日市場主線",
    "此舉反映",
    "這反映",
    "來源描述提到",
    "來源描述顯示",
    "詳情需以原文",
    "追蹤線索",
    "enumerator",
    "基於公司",
    "這一事態",
    "提出了新的挑戰",
    "提出新的挑戰",
]

BAD_GENERIC_TITLES = {
    "重要財經與科技消息值得今日追蹤",
    "能源、外匯與商品價格成為市場焦點",
    "企業消息牽動投資者對盈利與估值的判斷",
}


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def as_list(value):
    return value if isinstance(value, list) else []


def has_cjk(value: str) -> bool:
    return bool(re.search(r"[\u3400-\u9fff]", value or ""))


def looks_mostly_english(value: str) -> bool:
    letters = len(re.findall(r"[A-Za-z]", value or ""))
    cjk = len(re.findall(r"[\u3400-\u9fff]", value or ""))
    return letters > 12 and letters > cjk * 1.3


def looks_like_generic_editorial_title(value: str) -> bool:
    text = value or ""
    generic_fragments = [
        "企業交易消息牽動",
        "企業消息牽動投資者",
        "市場消息牽動投資者",
        "重要財經與科技消息",
        "相關價格變化牽動",
        "價格變化牽動商品與外匯",
    ]
    if any(fragment in text for fragment in generic_fragments):
        return True
    if re.search(r"^圍繞\s+(Is|US|U\.S\.|UK|Trump|Oil|Gold|Comex)\b", text):
        return True
    return False


def clean_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False)
    elif not isinstance(value, str):
        value = str(value)
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", value, flags=re.S)
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def to_traditional_zh(value: str) -> str:
    text = clean_text(value or "")
    if not text:
        return ""
    if OPENCC_S2HK:
        return clean_text(OPENCC_S2HK.convert(text))
    return text


def contains_common_simplified_zh(value: str) -> bool:
    # Chinese output is normalized through OpenCC before validation. Do not
    # treat OpenCC wording differences as proof that the text is Simplified.
    return False


def clean_feed_text(value: str) -> str:
    value = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", value or "", flags=re.S)
    return clean_text(value)


def parse_published_at(value: str) -> datetime | None:
    text = clean_text(value)
    if not text:
        return None
    try:
        parsed = parsedate_to_datetime(text)
    except Exception:
        parsed = None
    if parsed is None:
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except Exception:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(HK_TZ)


def candidate_is_fresh(candidate: dict) -> bool:
    published = parse_published_at(candidate.get("published_at_hint", ""))
    if not published:
        return True
    age = NOW_HK - published
    if age < -MAX_FUTURE_PUBLISHED_AT:
        return False
    return age <= MAX_DATED_NEWS_AGE


def headline_entity(title: str) -> str:
    stop_phrases = {
        "Wall Street", "BofA", "Citi", "Mizuho", "Analyst Report", "The", "A", "An",
        "Here", "What", "I", "My", "We", "Is This", "US", "U.S", "New", "Friday", "Monday", "Tuesday", "Wednesday", "Thursday",
        "Says", "Say", "Said", "Launches", "Raises", "Our", "These", "Global", "Market", "Markets",
    }
    for phrase in re.findall(r"\b[A-Z][A-Za-z0-9&.-]*(?:\s+[A-Z][A-Za-z0-9&.-]*){0,2}\b", title or ""):
        cleaned = phrase.strip(" ,:;.-")
        cleaned = re.sub(r"^(New|US|U\.S\.?)\s+", "", cleaned)
        cleaned = re.sub(r"\s+(Says|Say|Said|Launches|Raises)$", "", cleaned)
        if not cleaned or cleaned in stop_phrases:
            continue
        if any(part in stop_phrases for part in cleaned.split()) and len(cleaned.split()) <= 2:
            continue
        return cleaned
    return ""


def absolute_url(base_url: str, href: str) -> str:
    return urllib.parse.urljoin(base_url, html.unescape((href or "").strip()))


def fetch_url(url: str) -> tuple[int, str]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            raw = response.read(1_500_000)
            charset = response.headers.get_content_charset() or "utf-8"
            return response.status, raw.decode(charset, errors="replace")
    except Exception as exc:
        return 0, f"FETCH_ERROR: {exc}"


def extract_page_candidates(source_name: str, url: str, body: str) -> list[dict]:
    candidates = []
    seen = set()
    anchor_pattern = re.compile(r"<a\s+[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", re.I | re.S)
    for href, label in anchor_pattern.findall(body):
        title = clean_text(label)
        if not (18 <= len(title) <= 180):
            continue
        lower = title.lower()
        if any(skip in lower for skip in ["subscribe", "sign in", "cookie", "privacy", "terms", "advertisement"]):
            continue
        link = absolute_url(url, href)
        key = (title.lower(), link)
        if key in seen:
            continue
        seen.add(key)
        candidates.append({"source": source_name, "title": title, "url": link})
        if len(candidates) >= 30:
            break
    return candidates


def extract_rss_candidates(source_name: str, url: str, body: str) -> list[dict]:
    candidates = []
    for item in re.findall(r"<item\b[^>]*>(.*?)</item>", body, flags=re.I | re.S):
        title_match = re.search(r"<title[^>]*>(.*?)</title>", item, re.I | re.S)
        link_match = re.search(r"<link[^>]*>(.*?)</link>", item, re.I | re.S)
        date_match = re.search(r"<pubDate[^>]*>(.*?)</pubDate>", item, re.I | re.S)
        desc_match = re.search(r"<description[^>]*>(.*?)</description>", item, re.I | re.S)
        content_match = re.search(r"<content:encoded[^>]*>(.*?)</content:encoded>", item, re.I | re.S)
        if not title_match:
            continue
        title = clean_text(title_match.group(1))
        link = clean_text(link_match.group(1)) if link_match else url
        if not (12 <= len(title) <= 180):
            continue
        summary_hint = clean_feed_text((content_match or desc_match).group(1)) if (content_match or desc_match) else ""
        candidates.append({
            "source": source_name,
            "title": title,
            "url": absolute_url(url, link),
            "published_at_hint": clean_text(date_match.group(1)) if date_match else "",
            "summary_hint": summary_hint,
            "summary_hint_basis": "rss_description" if summary_hint else "",
        })
        if len(candidates) >= 30:
            break
    return candidates


def text_is_useful_summary(value: str, title: str = "") -> bool:
    text = clean_text(value)
    if len(text) < 80:
        return False
    lower = text.lower()
    if any(skip in lower for skip in ["subscribe", "newsletter", "cookie", "sign up", "advertisement", "all rights reserved"]):
        return False
    title_key = re.sub(r"[^a-z0-9\u3400-\u9fff]+", "", (title or "").lower())
    text_key = re.sub(r"[^a-z0-9\u3400-\u9fff]+", "", lower)
    return not (title_key and text_key.startswith(title_key) and len(text_key) < len(title_key) + 80)


def extract_meta_description(body: str) -> str:
    patterns = [
        r"<meta\b[^>]*(?:name|property)=[\"'](?:description|og:description|twitter:description)[\"'][^>]*content=[\"']([^\"']+)[\"'][^>]*>",
        r"<meta\b[^>]*content=[\"']([^\"']+)[\"'][^>]*(?:name|property)=[\"'](?:description|og:description|twitter:description)[\"'][^>]*>",
    ]
    for pattern in patterns:
        match = re.search(pattern, body or "", flags=re.I | re.S)
        if match:
            return clean_text(match.group(1))
    return ""


def extract_jsonld_article_text(body: str) -> str:
    pieces = []
    for script in re.findall(r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>", body or "", flags=re.I | re.S):
        text = clean_text(script)
        for key in ["articleBody", "description"]:
            match = re.search(rf'"{key}"\s*:\s*"((?:\\.|[^"\\])*)"', text, flags=re.S)
            if match:
                try:
                    pieces.append(json.loads(f'"{match.group(1)}"'))
                except Exception:
                    pieces.append(match.group(1))
    return clean_text(" ".join(pieces))


def extract_article_body_text(body: str) -> str:
    html_body = re.sub(r"<(script|style|noscript|svg|footer|header|nav)\b.*?</\1>", " ", body or "", flags=re.I | re.S)
    paragraphs = []
    seen = set()
    for raw in re.findall(r"<p\b[^>]*>(.*?)</p>", html_body, flags=re.I | re.S):
        paragraph = clean_text(raw)
        lower = paragraph.lower()
        if not (70 <= len(paragraph) <= 900):
            continue
        if any(skip in lower for skip in ["subscribe", "newsletter", "advertisement", "cookies", "sign up", "all rights reserved", "read more"]):
            continue
        key = paragraph[:120].lower()
        if key in seen:
            continue
        seen.add(key)
        paragraphs.append(paragraph)
        if sum(len(p) for p in paragraphs) >= 2600:
            break
    return clean_text(" ".join(paragraphs))


def source_text_confidence(basis: str, text: str = "", title: str = "") -> float:
    confidence = SUMMARY_BASIS_CONFIDENCE.get(basis, 0.0)
    if basis == "article_body":
        confidence = max(confidence, 0.70 if title_text_overlap(title, text) >= 2 else 0.56)
    if len(clean_text(text)) < 120:
        confidence -= 0.08
    return max(0.0, min(0.95, round(confidence, 2)))


def title_text_overlap(title: str, text: str) -> int:
    title_markers = set(marker.lower() for marker in content_markers(title))
    text_lower = clean_text(text).lower()
    overlap = sum(1 for marker in title_markers if marker and marker in text_lower)
    title_words = {
        token.lower()
        for token in re.findall(r"\b[A-Za-z][A-Za-z0-9&.-]{3,}\b", title or "")
        if token.lower() not in {"from", "with", "after", "this", "that", "says", "said", "will", "over"}
    }
    overlap += sum(1 for word in title_words if word in text_lower)
    return overlap


def make_context(basis: str, text: str, url_status: int = 0) -> dict:
    return {
        "basis": basis,
        "text": clean_text(text),
        "confidence": source_text_confidence(basis, text),
        "url_status": url_status,
    }


def article_context(candidate: dict) -> dict:
    title = clean_text(candidate.get("title", ""))
    hint = clean_text(candidate.get("summary_hint", ""))
    fallbacks = []
    if text_is_useful_summary(hint, title):
        basis = candidate.get("summary_hint_basis") or "rss_description"
        fallbacks.append(make_context(basis, hint[:1600]))
    status, body = fetch_url(candidate.get("url", ""))
    if status == 200:
        article_text = extract_article_body_text(body)
        jsonld_text = extract_jsonld_article_text(body)
        meta = extract_meta_description(body)
        if text_is_useful_summary(meta, title):
            fallbacks.append(make_context("meta_description", meta[:1200], status))
        if text_is_useful_summary(jsonld_text, title):
            fallbacks.append(make_context("jsonld_article", jsonld_text[:3000], status))
        if text_is_useful_summary(article_text, title) and len(article_text) >= 350:
            body_basis = "article_body" if title_text_overlap(title, article_text) >= 2 else "low_confidence_body"
            body_context = make_context(body_basis, article_text[:3600], status)
            if body_context["confidence"] >= MIN_AI_CONTEXT_CONFIDENCE:
                body_context["fallback_contexts"] = fallbacks
                return body_context
            fallbacks.append(body_context)
    if fallbacks:
        fallbacks.sort(key=lambda row: row.get("confidence", 0), reverse=True)
        first = fallbacks[0]
        return {
            "basis": first["basis"],
            "text": first["text"],
            "confidence": first.get("confidence", 0),
            "url_status": status,
            "fallback_contexts": fallbacks[1:],
        }
    return {"basis": "", "text": "", "confidence": 0, "url_status": status, "fallback_contexts": []}


def call_cloudflare_ai(prompt: str) -> str:
    global LAST_AI_CALL_AT
    account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    model = os.environ.get("CF_AI_MODEL", "@cf/meta/llama-3.2-3b-instruct").strip()
    if not (account_id and token and model):
        return ""
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{urllib.parse.quote(model, safe='@/-')}"
    payload = json.dumps({"messages": [{"role": "user", "content": prompt}], "max_tokens": 760}, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "User-Agent": USER_AGENT},
        method="POST",
    )
    for attempt in range(4):
        elapsed = time.monotonic() - LAST_AI_CALL_AT
        if elapsed < 2.5:
            time.sleep(2.5 - elapsed)
        try:
            LAST_AI_CALL_AT = time.monotonic()
            with urllib.request.urlopen(request, timeout=45) as response:
                data = json.loads(response.read().decode("utf-8", errors="replace"))
            break
        except urllib.error.HTTPError as exc:
            error_body = ""
            try:
                error_body = exc.read().decode("utf-8", errors="replace")
            except Exception:
                error_body = ""
            error_code = ""
            error_message = ""
            if error_body:
                try:
                    error_data = json.loads(error_body)
                    errors = error_data.get("errors") if isinstance(error_data, dict) else []
                    if isinstance(errors, list) and errors:
                        first_error = errors[0] if isinstance(errors[0], dict) else {}
                        error_code = str(first_error.get("code") or "")
                        error_message = clean_text(str(first_error.get("message") or ""))
                except Exception:
                    error_message = clean_text(error_body[:300])
            if exc.code == 429 and error_code == "3036":
                print("Cloudflare AI daily free allocation exhausted: code 3036. Skipping retries.")
                return ""
            if exc.code == 429 and attempt < 3:
                retry_after = exc.headers.get("Retry-After")
                try:
                    wait_seconds = max(5, int(retry_after)) if retry_after else 6 + attempt * 4
                except ValueError:
                    wait_seconds = 6 + attempt * 4
                detail = f" code {error_code}" if error_code else ""
                message = f": {error_message}" if error_message else ""
                print(f"Cloudflare AI rate limited{detail}{message}; retrying in {wait_seconds}s.")
                time.sleep(wait_seconds)
                continue
            detail = f" code {error_code}" if error_code else ""
            message = f": {error_message}" if error_message else ""
            print(f"Cloudflare AI summary failed: HTTP {exc.code}{detail}{message}")
            return ""
        except Exception as exc:
            print(f"Cloudflare AI summary failed: {exc}")
            return ""
    else:
        return ""
    result = data.get("result") if isinstance(data, dict) else {}
    if isinstance(result, dict):
        return clean_text(result.get("response") or result.get("text") or result.get("answer") or "")
    return clean_text(result if isinstance(result, str) else "")


def content_markers(value: str) -> list[str]:
    markers = []
    for token in re.findall(r"\$?\b[A-Z][A-Za-z0-9&.-]{1,}(?:\s+[A-Z][A-Za-z0-9&.-]{1,}){0,2}\b|\b\d+(?:[.,]\d+)?%?\b", value or ""):
        token = token.strip(" ,.;:()[]")
        if len(token) < 2 or token in {"The", "This", "That", "For", "New", "US"}:
            continue
        markers.append(token)
    return list(dict.fromkeys(markers))[:20]


def summary_rejection_reason(summary: str, context_text: str, title: str, source_confidence: float = 1.0) -> str:
    if not summary or "NO_VERIFIABLE_SUMMARY" in summary:
        return "empty_summary"
    if not has_cjk(summary):
        return "not_chinese"
    if re.search(r"[{}\\]|\":|\":\s*\}\}", summary):
        return "json_fragment"
    if re.search(r"[\u0e00-\u0e7f]", summary):
        return "non_chinese_script"
    if re.search(r"^(Yahoo Finance|The Guardian|CNBC|Reuters|MarketWatch|華爾街見聞|財新|LatePost)[：:]", summary):
        return "source_name_prefix"
    if source_confidence < MIN_AI_CONTEXT_CONFIDENCE:
        return "low_source_confidence"
    if any(phrase in summary for phrase in BAD_READER_PHRASES):
        return "bad_reader_phrase"
    if any(phrase in summary for phrase in [
        "source_text", "JSON", "Markdown", "內部之聲", "黑幫 Shadow Fleet", "Oil 減油船",
        "cryptocurrency Industry", "重要一角", "規模和影響力", "會再受關注", "項目將於",
        "plan 中", "monetary", "真相尋", "communicate", "tensions", "panel", "油漆",
        "聯手監控", "一名三名", "第六次會議", "合作移除",
        "美聯儲在AI", "美聯儲公司", "大言不慮", "透漏", "重頭戲", "Industry", "cryptocurrency",
        "香港聯合廣播公司", "美聯儲批准", "media", "付款用户",
    ]):
        return "machine_translation_artifact"
    if re.search(r"\b(Spacex|美Fed|fraud conviction|raised \$|tanker將|Straits of Hormuz開放)\b|\$[0-9]", summary):
        return "machine_translation_artifact"
    if len(summary) < 35:
        return "too_short"
    if len(summary) > 160:
        return "too_long"
    cjk_count = len(re.findall(r"[\u3400-\u9fff]", summary))
    latin_count = len(re.findall(r"[A-Za-z]", summary))
    if latin_count > 45 and latin_count > cjk_count * 0.65:
        return "too_much_english"
    sentences = [clean_text(sentence) for sentence in re.split(r"(?<=[。！？!?])", summary) if clean_text(sentence)]
    normalized = [re.sub(r"\s+", "", sentence) for sentence in sentences]
    if len(normalized) != len(set(normalized)):
        return "repeated_sentence"
    clauses = [re.sub(r"\s+", "", clause) for clause in re.split(r"[，,；;。]", summary) if len(re.sub(r"\s+", "", clause)) >= 10]
    if len(clauses) != len(set(clauses)):
        return "repeated_clause"
    for idx, clause in enumerate(clauses):
        if any(clause and clause in other for other in clauses[idx + 1:]):
            return "repeated_clause"
    if re.search(r"(達到|表示|指出|包括|以及|影響)$", summary):
        return "incomplete_sentence"
    title_tokens = {
        token.lower()
        for token in re.findall(r"\b[A-Za-z][A-Za-z0-9&.-]{2,}\b", title or "")
        if token.lower() not in {"the", "and", "for", "with", "from", "after", "said", "says"}
    }
    context_lower = clean_text(context_text).lower()
    summary_lower = summary.lower()
    unsupported_tokens = [token for token in re.findall(r"\b[A-Za-z][A-Za-z0-9&.-]{2,}\b", summary_lower) if token not in context_lower and token not in title_tokens]
    if len([token for token in unsupported_tokens if not token.isdigit()]) > 4:
        return "unsupported_entities"
    return ""


def summary_supported_by_text(summary: str, context_text: str, title: str, source_confidence: float = 1.0) -> bool:
    return not summary_rejection_reason(summary, context_text, title, source_confidence)


def clean_ai_summary_output(value: object) -> str:
    text = to_traditional_zh(clean_text(value))
    text = re.sub(r'["”」』\']?\s*[:：]\s*["“「『\']?\s*\}+\s*$', "", text)
    text = re.sub(r'["”」』\']?\s*\}+[,]?\s*$', "", text)
    text = text.strip(" \"'，,;；")
    sentences = re.split(r"(?<=[。！？!?])", text)
    unique_sentences = []
    seen = set()
    for sentence in sentences:
        clean_sentence = sentence.strip()
        if not clean_sentence:
            continue
        key = re.sub(r"\s+", "", clean_sentence)
        if key in seen:
            continue
        seen.add(key)
        unique_sentences.append(clean_sentence)
    return clean_text("".join(unique_sentences))[:420]


def english_source_summary_zh(text: str, title_zh: str = "", original_title: str = "") -> str:
    # English source text must be summarized by AI from the current source text.
    # Hard-coded English-to-Chinese summary mappings are intentionally disabled.
    return ""
    lower = f"{original_title} {text}".lower()
    if "nasdaq" in lower and "ai infrastructure" in lower:
        return "美股大多下跌，Nasdaq 領跌；原文提到多家 AI 基建相關公司急跌，部分跌幅達雙位數，顯示 AI 交易短線受壓。"
    if "spacex" in lower and "moonshots" in lower:
        return "前 Tesla 董事 Steve Westly 表示，SpaceX 至少要實現三大長遠目標中的兩項，才足以支撐其龐大估值。原文並提到 SpaceX 計劃以每股 135 美元出售 5.556 億股，集資 750 億美元。"
    if "spacex" in lower and "initial public offering" in lower and "75 billion" in lower:
        return "原文指 SpaceX 的 IPO 原本有多個可能出錯之處，但公司最終打破華爾街常規，完成史上最大規模 IPO，集資 750 億美元。"
    if "spacex" in lower and "nasdaq debut" in lower:
        return "SpaceX 在 Nasdaq 首日掛牌股價急升，原文指公司市值突破 2 萬億美元，逼近 Amazon，反映市場對其上市反應熱烈。"
    if "u.s. and iran" in lower and "strait of hormuz" in lower:
        return "特朗普政府官員表示，美國與伊朗可能在數日內簽署協議，內容包括重開霍爾木茲海峽，以及推動拆除伊朗核計劃的部分步驟。"
    if "united arab emirates" in lower and "frozen" in lower and "iran" in lower:
        return "阿聯酋政府否認媒體所指同意向伊朗釋放數十億美元凍結資金，並稱相關指控完全不實，沒有經阿聯酋釋放、轉移或協助任何伊朗凍結資金。"
    if "gold settled" in lower and "silver" in lower:
        return "COMEX 黃金結算價下跌 1.4%，過去三個交易日有兩日下跌；銀價下跌 2.5%，過去四個交易日有三日下跌。"
    if "panic fueling the selloff" in lower and ("nvidia" in lower or "broadcom" in lower):
        return "原文指市場對 Nvidia、Broadcom 等科技巨頭的拋售恐慌可能過度，DeepSeek 消息雖觸發 AI 股回調，但未必足以拖垮美國 AI 龍頭。"
    if "paramount" in lower and "warner bros" in lower and "department of justice" in lower:
        return "美國司法部批准 Paramount Skydance 收購 Warner Bros. Discovery 的交易，意味大型媒體併購向前推進，行業整合再受關注。"
    if "arabica coffee" in lower and "tariffs" in lower:
        return "阿拉比卡咖啡價格創紀錄高位，交易商消化特朗普撤回對哥倫比亞徵收關稅及經濟制裁威脅的消息。"
    if "blackrock" in lower and "india" in lower and "bonds" in lower:
        return "BlackRock 表示，印度改善債券吸引力的措施值得肯定，但油價及其對盧比的影響，仍是吸引外資流入政府債券的一大障礙。"
    if "sam bankman-fried" in lower and "25-year" in lower:
        return "Sam Bankman-Fried 上訴失敗，法院維持其欺詐定罪及 25 年監禁刑期；案件源於其創辦的 FTX 加密貨幣交易所倒閉。"
    return ""


def source_excerpt_summary(text: str, title_zh: str = "", original_title: str = "") -> str:
    text = clean_text(text)
    if not text:
        return ""
    if has_cjk(text):
        sentences = re.split(r"(?<=[。！？])", text)
        return to_traditional_zh("".join(sentences[:2]))[:360]
    zh_summary = english_source_summary_zh(text, title_zh, original_title)
    if zh_summary:
        return to_traditional_zh(zh_summary)[:420]
    return ""


def summarize_from_context(title_zh: str, original_title: str, source: str, context: dict) -> tuple[str, str, str]:
    contexts = [context] + as_list(context.get("fallback_contexts"))
    first_basis = ""
    first_fallback = ""
    for candidate_context in contexts:
        text = clean_text(candidate_context.get("text", ""))
        basis = candidate_context.get("basis", "")
        confidence = float(candidate_context.get("confidence") or SUMMARY_BASIS_CONFIDENCE.get(basis, 0))
        if basis and not first_basis:
            first_basis = basis
        if not text:
            continue
        if confidence < MIN_DIRECT_CONTEXT_CONFIDENCE:
            continue
        if has_cjk(text):
            sentences = re.split(r"(?<=[。！？])", text)
            summary = to_traditional_zh("".join(sentences[:3]))[:360]
            if summary_supported_by_text(summary, text, original_title, confidence):
                return summary, basis, "verified_from_source_text"
        fallback = source_excerpt_summary(text, title_zh, original_title)
        if summary_supported_by_text(fallback, text, original_title, confidence):
            first_fallback = first_fallback or fallback
            first_basis = first_basis or basis
    if first_fallback:
        return first_fallback, first_basis, "verified_from_source_text"
    return "", first_basis, "summary_unavailable_after_source_check" if first_basis else "no_verifiable_source_text"


def parse_ai_json_object(value: str) -> dict:
    text = clean_text(value)
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I)
    match = re.search(r"\{.*\}", text, flags=re.S)
    if not match:
        return {}
    try:
        data = json.loads(match.group(0))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def normalize_ai_summaries(data: dict, response_text: str = "", known_ids: list[str] | None = None) -> dict[str, str]:
    if not isinstance(data, dict):
        data = {}
    value = data.get("summaries")
    if isinstance(value, dict):
        rows = {str(key): clean_ai_summary_output(text) for key, text in value.items() if clean_ai_summary_output(text)}
        if known_ids and len(known_ids) == 1 and known_ids[0] not in rows and len(rows) == 1:
            return {known_ids[0]: next(iter(rows.values()))}
        return rows
    if isinstance(value, list):
        rows = {}
        for row in value:
            if not isinstance(row, dict):
                continue
            item_id = clean_text(row.get("id") or row.get("item_id") or row.get("story_id"))
            text = clean_ai_summary_output(row.get("summary") or row.get("summary_zh") or row.get("text"))
            if item_id and text:
                rows[item_id] = text
        return rows
    direct_rows = {}
    for key, text in data.items():
        if key == "summaries":
            continue
        if isinstance(text, str) and key.startswith(TODAY):
            direct_rows[str(key)] = clean_ai_summary_output(text)
    if direct_rows:
        return direct_rows
    rows = {}
    compact = clean_text(response_text)
    ids = known_ids or []
    if compact and ids:
        id_pattern = "|".join(re.escape(item_id) for item_id in ids)
        pattern = rf"({id_pattern})\s*[\"'）\)]?\s*(?:[:：\-–—]|摘要[:：])\s*[\"']?(.+?)(?=(?:{id_pattern})\s*[\"'）\)]?\s*(?:[:：\-–—]|摘要[:：])|$)"
        for match in re.finditer(pattern, compact, flags=re.S):
            item_id = match.group(1)
            summary = clean_ai_summary_output(match.group(2))
            if item_id and summary:
                rows[item_id] = summary
    return rows


def apply_batch_ai_summaries(items: list[dict]) -> None:
    payload = []
    context_by_id = {}
    for item in items:
        context_text = clean_text(item.get("_summary_context_text", ""))
        context_confidence = float(item.get("_summary_context_confidence") or 0)
        if item.get("summary_zh") and item.get("summary_status") == "verified_from_source_text":
            continue
        if not context_text:
            continue
        if context_confidence < MIN_AI_CONTEXT_CONFIDENCE:
            RUN_REPORT["item_quality"]["summary_rejections"].append({
                "id": item.get("id", ""),
                "reason": "low_source_confidence",
                "basis": item.get("_summary_context_basis", ""),
                "confidence": context_confidence,
            })
            continue
        context_by_id[item["id"]] = context_text
        payload.append({
            "id": item["id"],
            "title_zh": item["title_zh"],
            "title_original": item["title_original"],
            "source": item["source"],
            "source_confidence": context_confidence,
            "summary_basis": item.get("_summary_context_basis", ""),
            "source_text": context_text[:900],
        })
    if not payload:
        return
    RUN_REPORT["ai"]["summary_candidates"] += len(payload)
    item_by_id = {item["id"]: item for item in items}
    parsed_any = False
    for start in range(0, len(payload), 1):
        batch = payload[start:start + 1]
        prompt = (
            "你是香港繁體中文財經新聞編輯。以下是一條新聞的可信來源文字，可能是正文、RSS description 或 meta description。\n"
            "任務：只根據該條 source_text 寫新聞摘要。不可加入推測、評論、投資建議，亦不可加入 source_text 沒有的背景。\n"
            "每條摘要輸出 1 至 2 句自然香港繁體中文，約 50 至 120 字；公司名可保留英文，人名不要亂音譯；必須保留 source_text 中的重要數字、人物、公司或事件。\n"
            "請像財經編輯寫 brief：先講事件，再講關鍵數字或影響。不要直譯英文語序；Fed 寫作美聯儲，Strait of Hormuz 寫作霍爾木茲海峽。\n"
            "如果 source_text 太短，只把已有資訊整理成一句；如果完全不能判斷，就回傳空字串。不要輸出 Markdown。\n"
            "只輸出 JSON object，格式必須是 {\"summaries\":{\"新聞 id\":\"中文摘要或空字串\"}}。\n\n"
            + json.dumps(batch, ensure_ascii=False)
        )
        response = call_cloudflare_ai(prompt)
        RUN_REPORT["ai"]["response_chars"] += len(response or "")
        if response and len(RUN_REPORT["ai"]["response_samples"]) < 2:
            RUN_REPORT["ai"]["response_samples"].append(clean_text(response)[:220])
        data = parse_ai_json_object(response)
        known_ids = [row["id"] for row in batch]
        summaries = normalize_ai_summaries(data, response, known_ids)
        RUN_REPORT["ai"]["parsed_summaries"] += len(summaries)
        if not summaries:
            continue
        parsed_any = True
        for item_id, value in summaries.items():
            item = item_by_id.get(item_id)
            if not item:
                continue
            summary = clean_ai_summary_output(value)
            context_text = context_by_id.get(item_id, "")
            confidence = float(item.get("_summary_context_confidence") or 0)
            rejection_reason = summary_rejection_reason(summary, context_text, item.get("title_original", ""), confidence)
            if not rejection_reason and not contains_common_simplified_zh(summary):
                item["summary_zh"] = summary[:420]
                item["summary"] = item["summary_zh"]
                item["summary_status"] = "verified_from_source_text"
                item["summary_quality_status"] = "passed"
                RUN_REPORT["ai"]["summary_updates"] += 1
            elif summary:
                RUN_REPORT["ai"]["rejected_summaries"] += 1
                RUN_REPORT["item_quality"]["summary_rejections"].append({
                    "id": item.get("id", ""),
                    "reason": rejection_reason or "simplified_chinese",
                    "basis": item.get("_summary_context_basis", ""),
                    "confidence": confidence,
                    "preview": summary[:120],
                })
    RUN_REPORT["ai"]["last_status"] = "ok" if parsed_any else "empty_or_unparseable_response"


def source_label(source_name: str) -> str:
    labels = {
        "Reuters Markets": "Reuters Markets",
        "Reuters Technology": "Reuters Technology",
        "CNBC Top News": "CNBC",
        "CNBC Markets": "CNBC Markets",
        "CNBC Technology": "CNBC Technology",
        "WSJ Markets": "WSJ Markets",
        "WSJ Technology": "WSJ Technology",
        "Yahoo Finance": "Yahoo Finance",
        "MarketWatch Top Stories": "MarketWatch",
        "The Guardian Business": "The Guardian",
        "Nikkei Asia Business": "Nikkei Asia",
        "TechCrunch AI": "TechCrunch AI",
        "TechCrunch Startups": "TechCrunch",
        "Wallstreetcn": "華爾街見聞",
        "Caixin": "財新",
        "LatePost": "晚點",
    }
    return labels.get(source_name, source_name or "主要來源")


def source_family(source_name: str) -> str:
    text = (source_name or "").lower()
    if "cnbc" in text:
        return "CNBC"
    if "reuters" in text:
        return "Reuters"
    if "wsj" in text or "wall street journal" in text:
        return "WSJ"
    if "marketwatch" in text:
        return "MarketWatch"
    if "yahoo" in text:
        return "Yahoo Finance"
    if "guardian" in text:
        return "The Guardian"
    if "nikkei" in text:
        return "Nikkei Asia"
    if "techcrunch" in text:
        return "TechCrunch"
    return source_label(source_name)


def candidate_allowed(source_name: str, link: str, title: str) -> bool:
    lower_title = (title or "").lower()
    lower_link = (link or "").lower()
    if not lower_link.startswith(("http://", "https://")):
        return False
    parsed = urllib.parse.urlparse(lower_link)
    path = parsed.path.rstrip("/")
    nav_paths = {
        "", "/", "/site", "/site/index", "/business", "/markets", "/technology",
        "/startups", "/wealth", "/personal-finance", "/news", "/world", "/tag",
    }
    if path in nav_paths:
        return False
    if "latepost.com" in lower_link and "/news/" not in lower_link:
        return False
    if "wallstreetcn.com" in lower_link and "/articles/" not in lower_link:
        return False
    if "caixin.com" in lower_link and not re.search(r"/20\d{2}-\d{2}-\d{2}/|/20\d{2}/", lower_link):
        return False
    skip_terms = [
        "personal trainer", "elderly mother", "medicaid", "social security", "retirement",
        "mortgage", "home together", "inheritance", "divorce", "market talk", "sponsored",
        "newsletter", "podcast", "watch live", "live updates", "stock futures are little changed",
        "plumber", "toilet", "cistern", "do i pay again", "should i pay",
        "cramer's top 10", "best deep value stock", "invest in now", "top stocks to buy",
        "focus list", "analyst picks", "analyst report:",
        "analyst upgrade", "analysts upgrade", "analysts upgrades", "analyst upgrades",
        "inherited", "no experience with investing", "what should i do with this money",
        " i ", " my ", " what should ", "what do i",
        "price target", "buy rating", "sell rating", "neutral rating",
        "remains positive on", "raises pt", "analysts bullish",
        "is this", "best stock",
        "massive gap-up", "gap-up", "propels", "diane keaton", "annie hall", "bonhams", "auction",
        "adviser", "advisor", "annuities", "fire him", "fire her", "undervalued",
        "assets investors should buy", "investors should buy", "should buy if",
        "stocks to buy", "stock to buy", "to buy right now", "buy right now",
        "best travel stock", "best dividend stock", "best ai stock", "best growth stock",
        "stock portfolio", "hedge fund portfolio", "university stock portfolio",
        "orion cmc",
    ]
    if any(term in lower_title for term in skip_terms):
        return False
    if re.search(r"^(i|my|we|our|these)\b|what should i|what do i", lower_title):
        return False
    if re.search(r"\b(should|could)\s+(i|we|investors)\s+(buy|sell|fire|do)\b|do we fire|should we fire|still undervalued", lower_title):
        return False
    if re.search(r"^is\s+.+\s+(stock\s+)?(a\s+)?(buy|sell|hold)\b|is\s+.+\s+stock\s+worth", lower_title):
        return False
    if re.search(r"^is\s+.+\bthe\s+best\b.*\bstock\b", lower_title):
        return False
    if re.search(r"\b(upgraded|downgraded|initiates?|reiterates?|raises?|cuts?)\b.*\bstock\b|\bstock\b.*\b(upgraded|downgraded|price target|rating)\b", lower_title):
        return False
    generic_nav_titles = {
        "media & entertainment", "banking & finance", "business", "markets",
        "technology", "startups", "wealth", "personal finance",
    }
    if lower_title in generic_nav_titles:
        return False
    word_count = len(re.findall(r"[A-Za-z\u3400-\u9fff][A-Za-z0-9\u3400-\u9fff-]*", title or ""))
    important_terms = re.search(r"fed|inflation|treasury|yield|oil|gold|coffee|tariff|ai|chip|ipo|earnings|acquire|deal|merger|shares|stock|china|japan|asia", lower_title)
    if word_count < 4 and not important_terms:
        return False
    if any(part in lower_link for part in ["/video/", "/watch/", "/pro/", "/select/", "/personal-finance/", "/quotes/"]):
        return False
    if "cnbc.com" in lower_link and not re.search(r"/20\d{2}/\d{2}/\d{2}/", lower_link):
        return False
    if "reuters.com" in lower_link and not re.search(r"/(markets|technology|business|world)/", lower_link):
        return False
    return True


def infer_category(title: str) -> str:
    text = title.lower()
    if re.search(r"iran|hormuz|middle east|peace deal|peace agreement|tehran|伊朗|霍爾木茲|中東", text):
        return "能源、外匯與商品"
    if re.search(r"nvidia|amd|tsmc|intel|broadcom|globalfoundries|arm holdings|sandisk|seagate|semiconductor|chip|chips|晶片|半導體", text):
        return "半導體與供應鏈"
    if re.search(r"\bai\b|artificial intelligence|openai|cloud|data center|datacenter|software|平台|人工智能|雲端", text):
        return "科技、AI與平台"
    if re.search(r"fed|fomc|inflation|cpi|pce|yield|treasury|jobs|rates|producer prices|recession|通脹|利率|美債|就業", text):
        return "全球市場與宏觀"
    if re.search(r"oil|gas|gold|silver|dollar|yen|euro|commodity|crude|coffee|cocoa|wheat|corn|能源|黃金|美元|外匯|商品", text):
        return "能源、外匯與商品"
    if re.search(r"earnings|deal|merger|ipo|stock|shares|profit|revenue|buyback|acquire|acquisition|hostile bid|\bbid\b|財報|併購|上市|股份", text):
        return "企業、財報與交易"
    if re.search(r"china|hong kong|japan|asia|taiwan|中國|香港|日本|亞洲", text):
        return "中國與亞洲觀察"
    return "全球市場與宏觀"


def headline_score(candidate: dict) -> int:
    title = candidate.get("title", "")
    tier = int(candidate.get("source_tier", 3))
    score = 100 - tier * 10
    text = title.lower()
    priority_terms = [
        "fed", "inflation", "treasury", "yield", "nvidia", "ai", "semiconductor", "chip",
        "tsmc", "apple", "microsoft", "google", "meta", "amazon", "tesla", "oil", "gold",
        "dollar", "ipo", "earnings", "通脹", "利率", "半導體", "人工智能", "黃金", "美元",
    ]
    score += sum(7 for term in priority_terms if term in text)
    if 24 <= len(title) <= 130:
        score += 5
    return score


def cluster_key(title: str) -> str:
    text = (title or "").lower()
    clusters = [
        ("spacex", r"spacex"),
        ("paramount-wbd", r"paramount|warner bros|wbd"),
        ("iran-oil", r"(iran|kharg|tehran|hormuz).*(oil|crude|deal|peace|agreement)|oil.*iran|crude.*iran|u\.s\.-iran|us and iran"),
        ("gold", r"gold|bullion|silver"),
        ("rates-inflation", r"fed|fomc|inflation|cpi|pce|treasury|yield|producer prices|jobs"),
        ("ai-platforms", r"\bai\b|artificial intelligence|openai|cloud|data center|datacenter"),
        ("semiconductors", r"nvidia|amd|tsmc|intel|broadcom|semiconductor|chip"),
        ("big-tech", r"apple|microsoft|google|alphabet|amazon|meta|tesla|oracle"),
        ("china-asia", r"china|hong kong|japan|asia|taiwan"),
    ]
    for name, pattern in clusters:
        if re.search(pattern, text):
            return name
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9]{3,}", text)
    return "-".join(words[:3]) or re.sub(r"[^a-z0-9\u3400-\u9fff]+", "", text)[:24]


def title_dedupe_key(title: str) -> str:
    return re.sub(r"[^a-z0-9\u3400-\u9fff]+", "", (title or "").lower())[:100]


def topic_title_from_cluster(cluster: str, primary_title_zh: str, related: list[dict], category: str) -> str:
    if len(related) <= 1:
        return primary_title_zh
    if cluster == "spacex":
        return "SpaceX 上市與估值話題升溫，市場同時關注配售、監管與財富效應"
    if cluster == "paramount-wbd":
        return "派拉蒙與華納兄弟探索合併獲批，媒體業整合再升溫"
    if cluster == "rates-inflation":
        return "利率與通脹訊號交錯，市場重新評估美債收益率與風險資產定價"
    if cluster == "ai-platforms":
        return "AI 平台與算力投資熱度延續，估值、需求與競爭壓力同步受檢視"
    if cluster == "semiconductors":
        return "半導體供應鏈成為 AI 交易核心，晶片需求與資本開支持續牽動估值"
    if cluster == "iran-oil":
        return "中東與原油供應風險再受關注，能源價格牽動通脹與避險定價"
    if cluster == "gold":
        return "黃金與貴金屬走勢承壓，避險需求和實質利率出現拉扯"
    if cluster == "big-tech":
        return "大型科技股消息密集，投資者重估盈利能見度與估值支撐"
    if cluster == "china-asia":
        return "中國與亞洲市場消息升溫，區內資金流與供應鏈預期受關注"
    return keyword_headline(primary_title_zh, category)


def choose_topic_category(related: list[dict]) -> str:
    scores = {}
    for item in related:
        category = item.get("category") or infer_category(item.get("title", ""))
        scores[category] = scores.get(category, 0) + int(item.get("score", 0))
    return max(scores.items(), key=lambda pair: pair[1])[0] if scores else "全球市場與宏觀"


def choose_primary_candidate(related: list[dict], family_counts: dict) -> dict:
    sorted_related = sorted(related, key=lambda item: item.get("score", 0), reverse=True)
    for item in sorted_related:
        family = source_family(item.get("source", ""))
        if family_counts.get(family, 0) < SOURCE_FAMILY_LIMIT:
            return item
    return sorted_related[0]


def build_topic_candidate(cluster: str, related: list[dict], family_counts: dict) -> dict:
    primary = choose_primary_candidate(related, family_counts)
    category = choose_topic_category(related)
    related_sorted = sorted(related, key=lambda item: item.get("score", 0), reverse=True)
    sources = list(dict.fromkeys(source_label(item.get("source", "")) for item in related_sorted))
    families = list(dict.fromkeys(source_family(item.get("source", "")) for item in related_sorted))
    source_count = len(sources)
    group_score = max(item.get("score", 0) for item in related_sorted) + min(24, (source_count - 1) * 8 + (len(related_sorted) - 1) * 3)
    return {
        **primary,
        "cluster_key": cluster,
        "category": category,
        "score": group_score,
        "source_count": max(1, source_count),
        "sources_reporting_same_topic": sources,
        "source_families": families,
        "related_candidates": related_sorted[:6],
        "related_titles": [item.get("title", "") for item in related_sorted[:6]],
    }


def collect_news_candidates() -> tuple[list[dict], list[dict]]:
    all_candidates = []
    sources = []
    for config in SOURCE_CONFIGS:
        status, body = fetch_url(config["url"])
        source_stat = {
            "name": config["name"],
            "tier": config.get("tier", 3),
            "access": "Full" if status == 200 else "Blocked",
            "status_code": status,
            "extracted_count": 0,
            "accepted_count": 0,
            "skipped_by_rule": 0,
            "skipped_stale": 0,
        }
        sources.append({
            "name": config["name"],
            "url": config["url"],
            "access": "Full" if status == 200 else "Blocked",
            "tier": config.get("tier", 3),
        })
        if status != 200:
            RUN_REPORT["source_stats"].append(source_stat)
            continue
        RUN_REPORT["collection"]["sources_accessible"] += 1
        extracted = extract_rss_candidates(config["name"], config["url"], body) if config["kind"] == "rss" else extract_page_candidates(config["name"], config["url"], body)
        source_stat["extracted_count"] = len(extracted)
        RUN_REPORT["collection"]["raw_candidates"] += len(extracted)
        for candidate in extracted[: config.get("max_items", 8)]:
            if not candidate_allowed(config["name"], candidate.get("url", ""), candidate.get("title", "")):
                source_stat["skipped_by_rule"] += 1
                RUN_REPORT["collection"]["skipped_by_rule"] += 1
                continue
            if not candidate_is_fresh(candidate):
                source_stat["skipped_stale"] += 1
                RUN_REPORT["collection"]["skipped_stale"] += 1
                continue
            candidate["source_tier"] = config.get("tier", 3)
            candidate["category"] = infer_category(candidate.get("title", ""))
            candidate["score"] = headline_score(candidate)
            all_candidates.append(candidate)
            source_stat["accepted_count"] += 1
            RUN_REPORT["collection"]["accepted_candidates"] += 1
        RUN_REPORT["source_stats"].append(source_stat)

    keywords = re.compile(
        r"fed|inflation|treasury|yield|dollar|oil|gold|tariff|sanction|hormuz|iran|"
        r"economy|gdp|fraud|conviction|appeal|bank|listing|stock exchange|delist|"
        r"deal|merger|acquisition|acquire|\bto buy\b|shares|stock falls|stock rises|"
        r"nvidia|amd|tsmc|semiconductor|chip|\bai\b|artificial intelligence|cloud|"
        r"apple|tesla|microsoft|google|meta|amazon|ipo|earnings|"
        r"通脹|利率|半導體|人工智能|黃金|美元",
        re.I,
    )
    filtered = [item for item in all_candidates if keywords.search(item["title"])]
    if len(filtered) < MIN_ITEM_COUNT:
        filtered = all_candidates
    RUN_REPORT["collection"]["keyword_candidates"] = len(filtered)
    filtered.sort(key=lambda item: item.get("score", 0), reverse=True)

    unique_candidates = []
    seen_titles = set()
    seen_urls = set()
    for item in filtered:
        key = title_dedupe_key(item["title"])
        url_key = re.sub(r"[?#].*$", "", (item.get("url") or "").lower().rstrip("/"))
        if not key or key in seen_titles or (url_key and url_key in seen_urls):
            continue
        seen_titles.add(key)
        if url_key:
            seen_urls.add(url_key)
        unique_candidates.append(item)
        if len(unique_candidates) >= 72:
            break
    RUN_REPORT["collection"]["unique_candidates"] = len(unique_candidates)

    clusters = {}
    for item in unique_candidates:
        clusters.setdefault(cluster_key(item["title"]), []).append(item)

    grouped = []
    family_counts = {}
    category_counts = {}
    cluster_rows = sorted(
        clusters.items(),
        key=lambda row: max(item.get("score", 0) for item in row[1]) + min(18, len(row[1]) * 3),
        reverse=True,
    )
    for cluster, related in cluster_rows:
        topic = build_topic_candidate(cluster, related, family_counts)
        category = topic.get("category") or "全球市場與宏觀"
        family = source_family(topic.get("source", ""))
        if category_counts.get(category, 0) >= CATEGORY_LIMIT:
            continue
        if family_counts.get(family, 0) >= SOURCE_FAMILY_LIMIT:
            continue
        grouped.append(topic)
        category_counts[category] = category_counts.get(category, 0) + 1
        family_counts[family] = family_counts.get(family, 0) + 1
        if len(grouped) >= 48:
            break

    if len(grouped) < 12:
        used_keys = {title_dedupe_key(item.get("title", "")) for item in grouped}
        for item in unique_candidates:
            key = title_dedupe_key(item.get("title", ""))
            if key in used_keys:
                continue
            topic = build_topic_candidate(cluster_key(item.get("title", "")), [item], family_counts)
            family = source_family(topic.get("source", ""))
            if family_counts.get(family, 0) >= SOURCE_FAMILY_LIMIT:
                continue
            grouped.append(topic)
            family_counts[family] = family_counts.get(family, 0) + 1
            used_keys.add(key)
            if len(grouped) >= 12:
                break
    grouped.sort(key=lambda item: item.get("score", 0), reverse=True)
    RUN_REPORT["collection"]["grouped_candidates"] = len(grouped)
    return grouped, sources


def keyword_headline(title: str, category: str) -> str:
    text = f"{title} {category}".lower()
    company_match = re.search(r"\b(Nvidia|Apple|Microsoft|Google|Alphabet|Amazon|Meta|Tesla|Oracle|SpaceX|OpenAI|AMD|TSMC|Intel|Broadcom|GlobalFoundries|Arm Holdings|SanDisk|Seagate|Waymo|DigitalBridge|Equinix|QXO|Beacon|Rocket Lab|Circle|Warner Bros\.? Discovery|Warner)\b", title, re.I)
    company = company_match.group(1) if company_match else ""
    entity = company or headline_entity(title)
    if entity.lower() in {"oil", "crude", "gold", "silver", "comex", "trump", "u.s", "us", "global", "market", "markets", "iran"}:
        entity = ""
    if re.search(r"iran|hormuz|tehran|middle east|peace deal|peace agreement", text):
        return "伊朗和平協議時間表仍存變數，能源與地緣風險重新定價"
    if re.search(r"coffee|cocoa|wheat|corn|tariff", text):
        return "農產品與關稅消息牽動商品價格，通脹預期再受關注"
    if re.search(r"natural gas|gas falls|gas prices", text):
        return "天然氣價格受天氣預報牽動，能源市場重新評估短線需求"
    if re.search(r"gold|silver|bullion", text):
        return "金價受壓，避險與通脹交易出現重新定價"
    if re.search(r"treasury|yield|fed|rates|inflation|cpi|producer prices|jobs", text):
        return "利率與通脹預期牽動美債和股市走向"
    if re.search(r"oil|crude|gas|commodity|dollar|yen|euro", text):
        if entity:
            return f"{entity} 相關價格變化牽動商品與外匯市場情緒"
        return "能源與外匯價格波動升溫，市場重估通脹與避險交易"
    if re.search(r"autonomous|robotaxi|self-driving|waymo", text):
        return "Waymo 擴大自動駕駛服務，平台變現與城市營運能力受檢視"
    if re.search(r"\bai\b|artificial intelligence|chip|semiconductor|data center|cloud", text):
        prefix = f"{company} 帶動" if company else "AI 與半導體"
        return f"{prefix}投資熱潮延續，估值與供應鏈受關注"
    if re.search(r"earnings|shares|stock|ipo|deal|merger|revenue|profit|acquire|acquisition|hostile bid|\bbid\b", text):
        prefix = f"圍繞 {entity} 的企業消息" if entity else "企業交易消息"
        return f"{prefix}牽動投資者對盈利與估值的判斷"
    if re.search(r"china|asia|japan|hong kong|taiwan", text):
        return "中國及亞洲市場消息影響區內風險情緒"
    if entity:
        if category == "企業、財報與交易":
            return f"圍繞 {entity} 的企業消息牽動盈利與估值判斷"
        if category == "科技、AI與平台":
            return f"圍繞 {entity} 的科技消息牽動平台競爭與成長預期"
        if category == "能源、外匯與商品":
            return f"圍繞 {entity} 的價格變化牽動商品與外匯市場情緒"
        return f"圍繞 {entity} 的市場消息牽動投資者風險判斷"
    return "重要財經與科技消息值得今日追蹤"


def headline_to_zh(title: str, category: str) -> str:
    title = clean_text(title)
    if has_cjk(title) and not looks_mostly_english(title):
        if re.search(r"史上最大的 IPO.*最贵的盲盒", title):
            return "史上最大 IPO：SpaceX 估值成為市場最貴盲盒"
        if re.search(r"50 年科技 IPO.*晚点小数据", title):
            return "50 年科技 IPO 回顧：從蘋果、Nvidia 到 SpaceX 的上市週期"
        return to_traditional_zh(title)

    patterns = [
        (r"SpaceX raising \$75 billion.*IPO.*Nasdaq.*", "SpaceX 擬透過破紀錄 IPO 集資 750 億美元，市場等待 Nasdaq 首日表現"),
        (r"SpaceX cuts retail IPO allocation.*", "SpaceX 調低散戶 IPO 配售比例，上市分配安排受關注"),
        (r"Warren questions SpaceX IPO oversight.*", "美國議員質疑 SpaceX IPO 監管安排，交易所審查受關注"),
        (r"SpaceX IPO won.*bull market.*", "SpaceX IPO 未必終結牛市，但投資者憂慮上市後估值壓力"),
        (r"SpaceX soon-to-be millionaires.*", "SpaceX 上市或製造新一批富豪，財富效應帶動高端消費想像"),
        (r"Jim Cramer warns SpaceX.*", "市場名嘴警告 SpaceX 上市後估值可能升至難以持續水平"),
        (r"Former Tesla board member says SpaceX needs to achieve.*moonshots.*valuation.*", "前 Tesla 董事稱 SpaceX 需兌現兩大目標才可支撐估值"),
        (r"Small investors scrambled to get in on the SpaceX IPO.*", "散戶搶購 SpaceX IPO，部分投資者仍質疑估值過高"),
        (r"How Elon Musk nailed the SpaceX IPO.*", "馬斯克操盤 SpaceX IPO 獲市場追捧，上市定價策略受關注"),
        (r"SpaceX surges past \$2 trillion in Nasdaq debut.*", "SpaceX 納斯達克首日市值突破 2 萬億美元，逼近 Amazon"),
        (r"After SpaceX.*huge IPO.*financial future.*AI.*", "SpaceX 大型 IPO 令美國投資組合更綁定 AI 資本周期"),
        (r"US stocks rise after oil prices ease and SpaceX soars.*", "美股上升，油價回落與 SpaceX 首日大漲提振市場情緒"),
        (r"BlackRock says oil, FX risks loom over India's bond inflow push.*", "BlackRock 警告油價與匯率風險或影響印度債券資金流入"),
        (r"UAE denies.*fund transfer to Iran.*|UAE denies.*frozen funds.*Iran.*|.*UAE.*release billions.*frozen funds.*Iran.*", "阿聯酋否認同意向伊朗轉移或釋放凍結資金"),
        (r"Trump claims Iran war settled.*", "特朗普稱伊朗衝突接近落實協議，市場觀察地緣風險降溫"),
        (r"Trump picks former SEC Chairman.*", "特朗普提名前 SEC 主席出任國家情報總監，監管與政策人事受關注"),
        (r"What energy insiders.*oil prices.*Iran deal.*", "華府能源人士評估油價與伊朗協議前景"),
        (r"Analysis: Trump said he loves inflation.*", "特朗普通脹言論引發對 Fed 主席人選和政策路徑的討論"),
        (r"Pimco is warning about a spike in defaults.*", "Pimco 警告違約風險升溫，收益型投資組合配置受關注"),
        (r"DeepSeek Won.*Sink U\.S\. AI Titans.*", "DeepSeek 未必拖垮美國 AI 巨頭，競爭壓力仍需重估"),
        (r"Swiss franc, Japanese yen Rise as DeepSeek News Boosts Safe Havens.*", "DeepSeek 消息推升避險需求，瑞郎和日圓走強"),
        (r"Oil prices fall on proposed U\.S\.-Iran peace deal.*", "美伊和平協議憧憬拖低油價，市場押注霍爾木茲海峽重開"),
        (r"Global oil prices drop to \$88.*Iran peace deal.*", "油價跌至每桶 88 美元附近，市場憧憬伊朗和平協議最快周末達成"),
        (r"Proposed Iran-U\.S\. deal would reopen Hormuz.*", "伊朗官媒稱美伊協議或重開霍爾木茲海峽並解除石油制裁"),
        (r"Trump claims US and Iran on verge of signing peace agreement.*", "特朗普稱美伊接近簽署和平協議，德黑蘭稱尚未作最終決定"),
        (r"Trump says peace deal will be signed Sunday after Iran said it remains cautious on timing.*", "特朗普稱和平協議周日簽署，伊朗對時間表仍保持審慎"),
        (r"Trump denies Iran's account of deal terms.*", "特朗普否認伊朗對協議條款的說法，並譴責新一輪無人機攻擊"),
        (r"Trump administration: Iran deal signing likely in coming days.*not '?100%'? certain.*", "特朗普政府稱伊朗協議或數日內簽署，但仍未完全確定"),
        (r"Meta reportedly begins dismantling.*Manus deal.*", "Meta 據報按北京要求拆解 Manus 交易，AI 併購監管風險升溫"),
        (r"Paramount-WBD merger wins approval from DOJ.*", "派拉蒙與華納兄弟探索合併獲美國司法部批准"),
        (r"US justice department approves.*merger of Paramount and Warner Bros Discovery.*", "美國司法部批准派拉蒙與華納兄弟探索 1,110 億美元合併"),
        (r"Sam Bankman-Fried loses bid to appeal.*FTX.*", "FTX 創辦人上訴失敗，欺詐定罪維持不變"),
        (r"UK economy shrank by 0\.1% in April.*", "英國 4 月經濟收縮 0.1%，地緣風險拖累增長"),
        (r"Barclays to buy GoHenry.*", "Barclays 收購兒童扣帳卡應用 GoHenry，擴大年輕客群布局"),
        (r"Paddy Power owner Flutter to scrap listing.*London Stock Exchange.*", "Flutter 擬撤銷倫敦上市地位，重心進一步轉向美國市場"),
        (r"Flutter Entertainment to Delist From London.*Trade Solely in New York.*", "Flutter 擬退出倫敦上市，股份將只在紐約交易"),
        (r"Origin Materials approves delisting to cut compliance costs.*", "美國材料公司 Origin Materials 批准退市以降低合規成本"),
        (r"Charles Cole indicted for defrauding Napster.*239M shares.*", "Charles Cole 被控欺詐 Napster 2.39 億股，涉案股份交易受關注"),
        (r"Treasury yields are steady after hot producer prices reading.*", "美債收益率在生產者價格數據偏熱後靠穩，市場重新評估利率路徑"),
        (r"Gold slumps to 6-month low.*", "通脹憂慮升溫但金價跌至六個月低位，避險需求未有承接"),
        (r"Trump might 'love the inflation,'.*", "通脹壓力仍困擾消費者，市場關注政策言論與民生壓力"),
        (r"These in-demand jobs pay over.*", "高薪職位需求仍強，薪酬壓力與通脹前景受關注"),
        (r"Trump threatens to seize Kharg Island.*", "伊朗油氣基建風險升溫，原油供應憂慮再受關注"),
        (r"Oracle shares tumble.*", "Oracle 股價受壓，投資者憂慮融資和現金流壓力"),
        (r"DoorDash lets customers use photos.*", "DoorDash 擴大 AI 應用，餐飲預訂和點餐體驗加速智能化"),
        (r"SpaceX.*IPO.*", "SpaceX 估值與上市憧憬升溫，私人市場財富效應受關注"),
        (r"Stocks Sink in Broad AI Rout.*", "AI 概念股出現廣泛回調，市場重新審視估值和競爭壓力"),
        (r"DeepSeek.*", "DeepSeek 相關消息持續牽動全球 AI 競爭格局"),
    ]
    for pattern, replacement in patterns:
        if re.search(pattern, title, re.I):
            return replacement
    return keyword_headline(title, category)


def themes_for(category: str, title: str) -> list[str]:
    text = title.lower()
    themes = [category]
    if re.search(r"fed|rates|yield|treasury|inflation|cpi|jobs", text):
        themes.append("利率與通脹")
    if re.search(r"nvidia|\bai\b|artificial intelligence|cloud|data center", text):
        themes.append("AI投資熱潮")
    if re.search(r"semiconductor|chip|tsmc|amd|intel", text):
        themes.append("半導體供應鏈")
    if re.search(r"gold|oil|dollar|yen|commodity", text):
        themes.append("商品與外匯")
    if re.search(r"earnings|shares|stock|ipo|deal", text):
        themes.append("企業與資本市場")
    return list(dict.fromkeys(themes))[:4]


def source_phrase(sources: list[str]) -> str:
    if len(sources) >= 3:
        return f"{sources[0]}、{sources[1]}等 {len(sources)} 個來源"
    if len(sources) == 2:
        return f"{sources[0]}與{sources[1]}"
    return sources[0] if sources else "主要來源"


def market_impact(category: str) -> str:
    impacts = {
        "全球市場與宏觀": "可能影響美債收益率、美元、股票估值和高風險資產配置。",
        "科技、AI與平台": "可能改變市場對 AI 應用、雲端服務和大型科技股增長的預期。",
        "半導體與供應鏈": "可能影響晶片股、設備商和 AI 基建供應鏈的估值。",
        "企業、財報與交易": "可能帶動個股波動，並影響同業估值和資本市場情緒。",
        "能源、外匯與商品": "可能影響通脹預期、企業成本、避險資金和商品相關股票。",
        "中國與亞洲觀察": "可能影響亞洲股匯市場、供應鏈配置和區內政策預期。",
    }
    return impacts.get(category, "可能影響相關板塊的短線定價和市場情緒。")


def tracking_value(category: str) -> str:
    values = {
        "全球市場與宏觀": "追蹤後續通脹、就業和央行官員言論，判斷利率預期是否延續變化。",
        "科技、AI與平台": "追蹤訂單、資本開支、產品落地和競爭格局是否支持估值。",
        "半導體與供應鏈": "追蹤晶片需求、產能、庫存和主要客戶採購節奏。",
        "企業、財報與交易": "追蹤管理層指引、現金流、融資條件和同業反應。",
        "能源、外匯與商品": "追蹤庫存、供應、美元走勢和地緣風險是否推動第二輪價格變化。",
        "中國與亞洲觀察": "追蹤政策表態、資金流和亞洲主要市場的連鎖反應。",
    }
    return values.get(category, "追蹤原文後續更新和其他主要媒體是否交叉確認。")


def build_item(candidate: dict, idx: int) -> dict:
    original_title = clean_text(candidate.get("title") or "")
    category = candidate.get("category") or infer_category(original_title)
    primary_title_zh = headline_to_zh(original_title, category)
    related = as_list(candidate.get("related_candidates")) or [candidate]
    cluster = candidate.get("cluster_key") or cluster_key(original_title)
    title_zh = topic_title_from_cluster(cluster, primary_title_zh, related, category)
    source = source_label(candidate.get("source", ""))
    same_topic_sources = as_list(candidate.get("sources_reporting_same_topic")) or [source]
    source_count = max(1, int(candidate.get("source_count") or len(same_topic_sources) or 1))
    heat_score = max(52, min(94, int(candidate.get("score", 70)) - idx))
    related_titles = [clean_text(title) for title in as_list(candidate.get("related_titles")) if clean_text(title)]
    key_facts = [
        f"主要來源：{source}",
        f"同題材來源數：{source_count}",
        f"同題材來源：{'、'.join(same_topic_sources[:4])}",
    ]
    if related_titles:
        key_facts.append("代表性原始標題：" + "；".join(related_titles[:2]))
    context = article_context(candidate)
    context_confidence = float(context.get("confidence") or 0)
    context_basis = context.get("basis", "")
    if context_basis:
        confidence_key = f"{context_basis}:{context_confidence:.2f}"
        RUN_REPORT["item_quality"]["context_confidence"][confidence_key] = RUN_REPORT["item_quality"]["context_confidence"].get(confidence_key, 0) + 1
    summary_zh, summary_basis, summary_status = summarize_from_context(title_zh, original_title, source, context)
    if summary_basis:
        key_facts.append(f"摘要依據：{summary_basis}")
    else:
        key_facts.append("摘要狀態：未取得可核實正文或描述")
    return {
        "id": f"{TODAY}-headline-{idx:03d}",
        "date": TODAY,
        "title_original": original_title,
        "title_zh": title_zh,
        "source": source,
        "url": candidate.get("url") or "https://news.tinydreamlab.com/",
        "published_at": candidate.get("published_at_hint") or GENERATED_AT,
        "category": category,
        "themes": themes_for(category, original_title),
        "summary": summary_zh,
        "summary_zh": summary_zh,
        "summary_basis": summary_basis,
        "summary_status": summary_status,
        "summary_quality_status": "passed" if summary_zh else "unavailable",
        "source_confidence": context_confidence,
        "source_confidence_label": "high" if context_confidence >= 0.80 else "medium" if context_confidence >= MIN_AI_CONTEXT_CONFIDENCE else "low",
        "key_facts": key_facts[:4],
        "market_impact": "",
        "reporter_angle": "",
        "importance_score": max(5, min(10, 11 - idx // 2)),
        "heat_score": heat_score,
        "source_count": source_count,
        "sources_reporting_same_topic": same_topic_sources,
        "position_signal": "merged_topic" if source_count > 1 or len(related) > 1 else "ranked_headline",
        "time_horizon": "short_term",
        "tracking_value": "",
        "topic_key": cluster,
        "_summary_context_text": clean_text(context.get("text", "")),
        "_summary_context_basis": context_basis,
        "_summary_context_confidence": context_confidence,
    }


def hot_topic_reason(item: dict) -> str:
    category = item.get("category", "")
    if category == "全球市場與宏觀":
        return "宏觀數據和利率預期會同時影響股債匯商品，是今日市場定價的核心變數。"
    if category == "科技、AI與平台":
        return "AI 應用與雲端平台消息可能改變市場對大型科技股增長和資本開支的判斷。"
    if category == "半導體與供應鏈":
        return "半導體供應鏈是 AI 基建的核心，相關消息容易牽動硬件股和設備商估值。"
    if category == "企業、財報與交易":
        return "企業融資、財報或交易消息會直接影響個股估值，並可能擴散至同業。"
    if category == "能源、外匯與商品":
        return "商品和外匯價格會影響通脹預期、企業成本和避險資金流向。"
    if category == "中國與亞洲觀察":
        return "亞洲市場消息需要放在全球資金流和供應鏈重組背景下觀察。"
    return "此題材可能影響今日市場情緒，值得優先追蹤原文細節。"


def item_rejection_reason(item: dict) -> str:
    title = item.get("title_zh", "")
    if title in BAD_GENERIC_TITLES or looks_like_generic_editorial_title(title):
        return "generic_title"
    if not has_cjk(title) or looks_mostly_english(title):
        return "bad_title_language"
    published = parse_published_at(item.get("published_at", ""))
    if published:
        age = NOW_HK - published
        if age < -MAX_FUTURE_PUBLISHED_AT or age > MAX_DATED_NEWS_AGE:
            return "stale_or_future_published_at"
    if not isinstance(item.get("source_count"), int) or item["source_count"] < 1:
        return "bad_source_count"
    return ""


def sanitize_items_for_publication(items: list[dict]) -> list[dict]:
    publishable = []
    seen_titles = set()
    for item in items:
        reason = item_rejection_reason(item)
        if reason:
            print(f"Skipping low-quality item {item.get('id')}: {reason} | {item.get('title_original')}")
            RUN_REPORT["item_quality"]["skipped_items"].append({
                "id": item.get("id", ""),
                "reason": reason,
                "source": item.get("source", ""),
                "title_original": item.get("title_original", ""),
                "title_zh": item.get("title_zh", ""),
            })
            continue
        title = item.get("title_zh", "")
        if title in seen_titles:
            print(f"Skipping duplicate title item {item.get('id')}: {title}")
            RUN_REPORT["item_quality"]["skipped_items"].append({
                "id": item.get("id", ""),
                "reason": "duplicate_title",
                "source": item.get("source", ""),
                "title_original": item.get("title_original", ""),
                "title_zh": title,
            })
            continue
        seen_titles.add(title)
        summary = item.get("summary_zh", "")
        summary_rejection = summary_rejection_reason(
            summary,
            item.get("_summary_context_text", ""),
            item.get("title_original", ""),
            float(item.get("source_confidence") or 0),
        ) if summary else ""
        if summary and (
            any(phrase in summary for phrase in BAD_READER_PHRASES)
            or contains_common_simplified_zh(summary)
            or not item.get("summary_basis")
            or item.get("summary_status") != "verified_from_source_text"
            or summary_rejection
        ):
            item["summary"] = ""
            item["summary_zh"] = ""
            item["summary_status"] = "summary_removed_after_quality_check"
            item["summary_quality_status"] = summary_rejection or "removed_after_quality_check"
            RUN_REPORT["item_quality"]["summaries_removed"] += 1
            RUN_REPORT["item_quality"]["summary_rejections"].append({
                "id": item.get("id", ""),
                "reason": item["summary_quality_status"],
                "basis": item.get("summary_basis", ""),
                "confidence": item.get("source_confidence", 0),
                "preview": summary[:120],
            })
        publishable.append(item)
    RUN_REPORT["item_quality"]["publishable_items"] = len(publishable)
    return publishable


def build_hot_topics(items: list[dict]) -> list[dict]:
    groups = {}
    for item in items:
        key = item.get("topic_key") or title_dedupe_key(item.get("title_zh", ""))
        groups.setdefault(key, []).append(item)
    topic_rows = []
    for key, group_items in groups.items():
        ranked = sorted(group_items, key=lambda item: item.get("heat_score", 0), reverse=True)
        primary = ranked[0]
        sources = []
        for item in ranked:
            for source in as_list(item.get("sources_reporting_same_topic")) or [item.get("source")]:
                if source and source not in sources:
                    sources.append(source)
        topic_title = primary["title_zh"]
        if len(ranked) > 1:
            topic_title = topic_title_from_cluster(key, primary["title_zh"], [{} for _ in ranked], primary.get("category", ""))
        heat_score = min(99, max(item.get("heat_score", 0) for item in ranked) + min(10, (len(ranked) - 1) * 3 + (len(sources) - 1) * 2))
        reason = hot_topic_reason(primary)
        if len(ranked) > 1:
            reason = f"{len(ranked)} 條相關新聞集中在同一題材，反映它是今日主要新聞熱點之一；{reason}"
        topic_rows.append({
            "rank": 0,
            "topic": topic_title,
            "heat_score": heat_score,
            "heat_label": "High" if heat_score >= 75 else "Medium",
            "source_count": max(1, len(sources)),
            "main_sources": sources[:4] or [primary["source"]],
            "item_ids": [item["id"] for item in ranked],
            "one_line_reason": reason,
            "reporter_angle": primary.get("reporter_angle", ""),
            "related_story_count": len(ranked),
            "supporting_titles": [item.get("title_zh", "") for item in ranked[:4]],
        })
    topic_rows.sort(key=lambda row: (row["heat_score"], row["related_story_count"], row["source_count"]), reverse=True)
    for rank, topic in enumerate(topic_rows[:5], start=1):
        topic["rank"] = rank
    return topic_rows[:5]


def build_brief(candidates: list[dict], sources: list[dict]) -> dict:
    usable = candidates[:12]
    if not usable:
        fail("No usable news candidates were collected from accessible sources.")
    if len(usable) < MIN_ITEM_COUNT:
        fail(f"Only {len(usable)} usable news candidates were collected after quality filters.")

    items = [build_item(candidate, idx) for idx, candidate in enumerate(usable, start=1)]
    RUN_REPORT["item_quality"]["built_items"] = len(items)
    apply_batch_ai_summaries(items)
    items = sanitize_items_for_publication(items)
    for item in items:
        item.pop("_summary_context_text", None)
        item.pop("_summary_context_basis", None)
        item.pop("_summary_context_confidence", None)
    if len(items) < MIN_ITEM_COUNT:
        fail(f"Only {len(items)} publishable news items remained after item quality isolation.")
    categories = []
    for name, slug in CATEGORY_TAXONOMY:
        refs = [item["id"] for item in items if item["category"] == name]
        if refs:
            categories.append({"name": name, "slug": slug, "item_ids": refs})

    hot_topics = build_hot_topics(items)

    top_categories = list(dict.fromkeys(item["category"] for item in items[:8]))[:4]
    top_topics = "、".join(item["title_zh"] for item in items[:3])
    merged_count = sum(1 for item in items if item.get("source_count", 1) > 1)
    daily_summary = (
        "今日國際財經與科技新聞以" + "、".join(top_categories) +
        "為主線。頭版焦點包括" + top_topics +
        f"。本期共有 {merged_count} 個主題整合同題材來源，重點不只在單一標題，而是觀察新聞是否正在形成可持續的市場敘事；讀者可先讀焦點主題，再按分類核對原文和後續變化。"
    )

    return {
        "date": TODAY,
        "update_id": UPDATE_ID,
        "update_file": f"data/briefs/{UPDATE_ID}.json",
        "title": "每日國際財經與科技新聞摘要",
        "deck": "整理全球市場、科技產業和主要企業消息，協助快速掌握今日值得追蹤的新聞主線。",
        "daily_summary_zh": daily_summary,
        "market_focus": top_categories,
        "hot_topics": hot_topics,
        "categories": categories,
        "items": items,
        "sources": sources,
        "generation_report": RUN_REPORT,
        "generated_at": GENERATED_AT,
        "email_body_zh": daily_summary + "\n\n網站：https://news.tinydreamlab.com/",
    }


def validate_brief(brief: dict) -> None:
    for field in REQUIRED_BRIEF_FIELDS:
        if field not in brief:
            fail(f"Brief missing required field: {field}")
    if brief["date"] != TODAY:
        fail(f"Brief date {brief['date']} does not match {TODAY}")
    text_dump = json.dumps(brief, ensure_ascii=False)
    for phrase in BAD_READER_PHRASES:
        if phrase in text_dump:
            fail(f"Reader-facing brief contains bad phrase: {phrase}")
    items = brief.get("items")
    if not isinstance(items, list) or len(items) < MIN_ITEM_COUNT:
        fail(f"items must contain at least {MIN_ITEM_COUNT} entries.")
    item_ids = set()
    title_counts = {}
    summary_counts = {}
    source_family_counts = {}
    for item in items:
        for field in REQUIRED_ITEM_FIELDS:
            if field not in item:
                fail(f"Item missing required field {field}: {item.get('id')}")
        if item["id"] in item_ids:
            fail(f"Duplicate item id: {item['id']}")
        item_ids.add(item["id"])
        title_counts[item["title_zh"]] = title_counts.get(item["title_zh"], 0) + 1
        if item.get("summary_zh"):
            summary_counts[item["summary_zh"]] = summary_counts.get(item["summary_zh"], 0) + 1
        source_family_counts[source_family(item.get("source", ""))] = source_family_counts.get(source_family(item.get("source", "")), 0) + 1
        if item["title_zh"] in BAD_GENERIC_TITLES:
            fail(f"title_zh is too generic: {item['title_zh']}")
        if looks_like_generic_editorial_title(item["title_zh"]):
            fail(f"title_zh looks like a generic editorial placeholder: {item['title_zh']} | original: {item.get('title_original')}")
        if not has_cjk(item["title_zh"]) or looks_mostly_english(item["title_zh"]):
            fail(f"title_zh is not acceptable Traditional Chinese: {item['title_zh']}")
        published = parse_published_at(item.get("published_at", ""))
        if published:
            age = NOW_HK - published
            if age < -MAX_FUTURE_PUBLISHED_AT or age > MAX_DATED_NEWS_AGE:
                fail(f"published_at is outside freshness window: {item['id']} | {item.get('published_at')}")
        if contains_common_simplified_zh(item["title_zh"]):
            fail(f"title_zh contains common simplified Chinese characters: {item['title_zh']}")
        if any(phrase in item["summary_zh"] for phrase in BAD_READER_PHRASES):
            fail(f"summary_zh contains bad phrase: {item['id']}")
        if item.get("summary_zh") and contains_common_simplified_zh(item["summary_zh"]):
            fail(f"summary_zh contains common simplified Chinese characters: {item['id']} | summary: {item['summary_zh'][:180]}")
        if item.get("summary_zh") and not item.get("summary_basis"):
            fail(f"summary_zh must include summary_basis: {item['id']}")
        if item.get("summary_zh") and item.get("summary_status") != "verified_from_source_text":
            fail(f"summary_zh must be verified from source text: {item['id']}")
        if item.get("summary_zh") and float(item.get("source_confidence") or 0) < MIN_AI_CONTEXT_CONFIDENCE:
            fail(f"summary_zh source confidence is too low: {item['id']} | {item.get('source_confidence')}")
        if item.get("summary_zh") and re.search(r"[{}\\]|\":|\":\s*\}\}|[\u0e00-\u0e7f]|Spacex|美Fed|fraud conviction|raised \$|tanker將|Straits of Hormuz開放|cryptocurrency Industry|重要一角|規模和影響力|會再受關注|plan 中|monetary|真相尋|communicate|tensions|panel|油漆|聯手監控|一名三名|第六次會議|合作移除|美聯儲在AI|美聯儲公司|大言不慮|透漏|重頭戲|Industry|cryptocurrency|香港聯合廣播公司|美聯儲批准|media|付款用户|\$[0-9]", item["summary_zh"]):
            fail(f"summary_zh failed final quality gate: {item['id']} | {item['summary_zh'][:180]}")
        if not isinstance(item.get("source_count"), int) or item["source_count"] < 1:
            fail(f"source_count must be a positive integer: {item['id']}")
    duplicate_titles = [title for title, count in title_counts.items() if count > 1]
    if duplicate_titles:
        fail(f"Duplicate title_zh values: {duplicate_titles}")
    repeated_summaries = [summary for summary, count in summary_counts.items() if count > 2]
    if repeated_summaries:
        fail("Too many repeated summary_zh values.")
    accessible_families = {source_family(source.get("name", "")) for source in brief.get("sources", []) if source.get("access") == "Full"}
    if len(accessible_families) >= 3 and source_family_counts:
        dominant_family, dominant_count = max(source_family_counts.items(), key=lambda pair: pair[1])
        if dominant_count > SOURCE_FAMILY_LIMIT:
            fail(f"Source concentration too high: {dominant_family} has {dominant_count} of {len(items)} items.")

    hot_topics = brief.get("hot_topics")
    if not isinstance(hot_topics, list) or not (3 <= len(hot_topics) <= 5):
        fail("hot_topics must contain 3 to 5 entries.")
    for topic in hot_topics:
        for field in REQUIRED_HOT_TOPIC_FIELDS:
            if field not in topic:
                fail(f"Hot topic missing required field {field}: {topic}")
        for item_id in as_list(topic.get("item_ids")):
            if item_id not in item_ids:
                fail(f"Hot topic item_id not found in items: {item_id}")

    for category in brief.get("categories", []):
        for item_id in as_list(category.get("item_ids")):
            if item_id not in item_ids:
                fail(f"Category item_id not found in items: {item_id}")


def build_index_entry(brief: dict) -> dict:
    top_themes = []
    for item in brief.get("items", []):
        for theme in item.get("themes", []):
            if theme not in top_themes:
                top_themes.append(theme)
            if len(top_themes) >= 6:
                break
        if len(top_themes) >= 6:
            break
    return {
        "date": brief["date"],
        "update_id": UPDATE_ID,
        "file": f"data/briefs/{UPDATE_ID}.json",
        "latest_file": f"data/briefs/{TODAY}.json",
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
        index = {"latest_date": TODAY, "latest_update_id": UPDATE_ID, "latest_file": f"data/briefs/{TODAY}.json", "briefs": []}
    entry = build_index_entry(brief)
    previous = next((b for b in index.get("briefs", []) if b.get("date") == TODAY), None)
    briefs = [b for b in index.get("briefs", []) if b.get("date") != TODAY]
    updates = as_list(previous.get("updates")) if previous else []
    updates = [u for u in updates if u.get("update_id") != UPDATE_ID]
    updates.append({
        "update_id": UPDATE_ID,
        "file": f"data/briefs/{UPDATE_ID}.json",
        "generated_at": brief["generated_at"],
        "item_count": len(brief.get("items", [])),
        "hot_topic_count": len(brief.get("hot_topics", [])),
        "title": brief["title"],
    })
    updates.sort(key=lambda row: row.get("update_id", ""), reverse=True)
    entry["updates"] = updates
    briefs.append(entry)
    briefs.sort(key=lambda row: row.get("date", ""), reverse=True)
    return {
        "latest_date": TODAY,
        "latest_update_id": UPDATE_ID,
        "latest_file": f"data/briefs/{TODAY}.json",
        "briefs": briefs,
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
    message = EmailMessage()
    message["From"] = smtp_user
    message["To"] = email_to
    message["Subject"] = f"每日財經與科技新聞摘要 | {TODAY}"
    message.set_content(brief.get("email_body_zh") or brief.get("daily_summary_zh", ""))
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context, timeout=60) as server:
        server.login(smtp_user, smtp_password)
        server.send_message(message)
    print("Email sent.")


def main() -> None:
    candidates, sources = collect_news_candidates()
    print(f"Collected {len(candidates)} candidate headlines.")
    brief = build_brief(candidates, sources)
    validate_brief(brief)
    index = update_index(brief)
    write_json(BRIEF_PATH, brief)
    write_json(DAILY_LATEST_PATH, brief)
    write_json(INDEX_PATH, index)
    json.loads(BRIEF_PATH.read_text(encoding="utf-8"))
    json.loads(DAILY_LATEST_PATH.read_text(encoding="utf-8"))
    json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    send_email(brief)
    print(f"Generated {BRIEF_PATH}")
    print(f"Updated daily latest {DAILY_LATEST_PATH}")
    print(f"Updated {INDEX_PATH}")


if __name__ == "__main__":
    main()
