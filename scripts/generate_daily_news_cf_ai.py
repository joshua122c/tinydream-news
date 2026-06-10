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

TC_REPLACEMENTS = {
    "\u4e2d\u56fd": "\u4e2d\u570b",
    "\u7f8e\u56fd": "\u7f8e\u570b",
    "\u56fd\u9645": "\u570b\u969b",
    "\u8d22\u7ecf": "\u8ca1\u7d93",
    "\u79d1\u6280\u4ea7\u4e1a": "\u79d1\u6280\u7522\u696d",
    "\u4e92\u8054\u7f51": "\u4e92\u806f\u7db2",
    "\u8ba1\u7b97\u673a": "\u8a08\u7b97\u6a5f",
    "\u4f9b\u5e94\u94fe": "\u4f9b\u61c9\u93c8",
    "\u4f9b\u5e94": "\u4f9b\u61c9",
    "\u6269\u5f20": "\u64f4\u5f35",
    "\u6da8\u4ef7": "\u6f32\u50f9",
    "\u540c\u6bd4": "\u6309\u5e74",
    "\u534a\u5bfc\u4f53": "\u534a\u5c0e\u9ad4",
    "\u82af\u7247": "\u6676\u7247",
    "\u5b58\u50a8": "\u5132\u5b58",
    "\u6d01\u51c0\u5ba4": "\u6f54\u6de8\u5ba4",
    "\u8138\u5b50": "\u8116\u5b50",
    "\u810f": "\u81df",
    "\u9a71\u52a8": "\u9a45\u52d5",
    "\u70e7\u94b1": "\u71d2\u9322",
    "\u5f3a\u5ea6": "\u5f37\u5ea6",
    "\u5df2\u8d85": "\u5df2\u8d85",
    "\u6298\u65e7": "\u6298\u820a",
    "\u5c06\u662f": "\u5c07\u662f",
    "\u672a\u6765": "\u672a\u4f86",
    "\u7126\u70b9": "\u7126\u9ede",
    "\u521a\u521a": "\u525b\u525b",
    "\u4fdd\u5e95\u6a21\u5f0f": "\u5099\u7528\u6574\u7406",
    "\u81ea\u52d5\u4fdd\u5e95\u6a21\u5f0f": "\u81ea\u52d5\u6574\u7406\u6a21\u5f0f",
    "Cloudflare Workers AI \u56de\u8986\u672a\u80fd\u901a\u904e JSON \u9a57\u8b49": "\u4eca\u65e5\u6458\u8981\u5df2\u6839\u64da\u516c\u958b\u65b0\u805e\u6a19\u984c\u3001\u4f86\u6e90\u548c\u539f\u6587\u9023\u7d50\u6574\u7406",
    "\u539f\u59cb AI JSON \u56de\u8986\u683c\u5f0f\u672a\u80fd\u901a\u904e\u9a57\u8b49": "\u4eca\u65e5\u5148\u4fdd\u7559\u53ef\u8ffd\u8e64\u7684\u65b0\u805e\u5165\u53e3",
}

TC_CHARS = str.maketrans({
    "\u4e0e": "\u8207", "\u4e1a": "\u696d", "\u4e1c": "\u6771", "\u4e2a": "\u500b",
    "\u4e3a": "\u70ba", "\u4e50": "\u6a02", "\u4e70": "\u8cb7", "\u4e91": "\u96f2",
    "\u4ea7": "\u7522", "\u4ece": "\u5f9e", "\u4eec": "\u5011", "\u4ef7": "\u50f9",
    "\u4f20": "\u50b3", "\u4f53": "\u9ad4", "\u50a8": "\u5132", "\u5173": "\u95dc",
    "\u5174": "\u8208", "\u519b": "\u8ecd", "\u51b3": "\u6c7a", "\u51c0": "\u6de8",
    "\u5219": "\u5247", "\u521a": "\u525b", "\u521b": "\u5275", "\u522b": "\u5225",
    "\u529e": "\u8fa6", "\u52a1": "\u52d9", "\u52a8": "\u52d5", "\u52bf": "\u52e2",
    "\u533a": "\u5340", "\u534e": "\u83ef", "\u5355": "\u55ae", "\u538b": "\u58d3",
    "\u53c2": "\u53c3", "\u53cc": "\u96d9", "\u53d1": "\u767c", "\u53d8": "\u8b8a",
    "\u540e": "\u5f8c", "\u542f": "\u555f", "\u5458": "\u54e1", "\u54cd": "\u97ff",
    "\u56e2": "\u5718", "\u56f4": "\u570d", "\u56fd": "\u570b", "\u56fe": "\u5716",
    "\u573a": "\u5834", "\u5757": "\u584a", "\u575a": "\u5805", "\u5904": "\u8655",
    "\u5907": "\u5099", "\u5934": "\u982d", "\u5956": "\u734e", "\u5b66": "\u5b78",
    "\u5b9e": "\u5be6", "\u5ba1": "\u5be9", "\u5bf9": "\u5c0d", "\u5bfc": "\u5c0e",
    "\u5c06": "\u5c07", "\u5c42": "\u5c64", "\u5c81": "\u6b72", "\u5e08": "\u5e2b",
    "\u5e26": "\u5e36", "\u5e93": "\u5eab", "\u5e94": "\u61c9", "\u5e9f": "\u5ee2",
    "\u5f00": "\u958b", "\u5f20": "\u5f35", "\u5f3a": "\u5f37", "\u5f52": "\u6b78",
    "\u5f53": "\u7576", "\u5f55": "\u9304", "\u603b": "\u7e3d", "\u6076": "\u60e1",
    "\u60ca": "\u9a5a", "\u60e8": "\u6158", "\u60ef": "\u6163", "\u613f": "\u9858",
    "\u6218": "\u6230", "\u6267": "\u57f7", "\u6269": "\u64f4", "\u62a4": "\u8b77",
    "\u62a5": "\u5831", "\u62c5": "\u64d4", "\u62df": "\u64ec", "\u62e5": "\u64c1",
    "\u62e9": "\u64c7", "\u6325": "\u63ee", "\u6323": "\u6399", "\u6324": "\u64e0",
    "\u6362": "\u63db", "\u636e": "\u64da", "\u6446": "\u64fa", "\u6447": "\u6416",
    "\u6570": "\u6578", "\u65e0": "\u7121", "\u65e7": "\u820a", "\u65f6": "\u6642",
    "\u663e": "\u986f", "\u672f": "\u8853", "\u673a": "\u6a5f", "\u6743": "\u6b0a",
    "\u6765": "\u4f86", "\u6781": "\u6975", "\u6784": "\u69cb", "\u6807": "\u6a19",
    "\u680f": "\u6b04", "\u6811": "\u6a39", "\u6837": "\u6a23", "\u6863": "\u6a94",
    "\u68c0": "\u6aa2", "\u697c": "\u6a13", "\u6b27": "\u6b50", "\u6b8b": "\u6b98",
    "\u6c14": "\u6c23", "\u6c47": "\u532f", "\u6c49": "\u6f22", "\u6ca1": "\u6c92",
    "\u6cfd": "\u6fa4", "\u6d01": "\u6f54", "\u6d4b": "\u6e2c", "\u6d4e": "\u6fdf",
    "\u6d53": "\u6fc3", "\u6da8": "\u6f32", "\u6e10": "\u6f38", "\u6e29": "\u6eab",
    "\u6e7e": "\u7063", "\u6ee1": "\u6eff", "\u6eda": "\u6efe", "\u706f": "\u71c8",
    "\u7075": "\u9748", "\u70b9": "\u9ede", "\u70e7": "\u71d2", "\u70ed": "\u71b1",
    "\u7231": "\u611b", "\u72ec": "\u7368", "\u73af": "\u74b0", "\u73b0": "\u73fe",
    "\u7535": "\u96fb", "\u753b": "\u756b", "\u76d1": "\u76e3", "\u76d8": "\u76e4",
    "\u7740": "\u8457", "\u77ff": "\u7926", "\u7801": "\u78bc", "\u786e": "\u78ba",
    "\u793c": "\u79ae", "\u79bb": "\u96e2", "\u79cd": "\u7a2e", "\u79ef": "\u7a4d",
    "\u79f0": "\u7a31", "\u7a0e": "\u7a05", "\u7a33": "\u7a69", "\u7b14": "\u7b46",
    "\u7b7e": "\u7c3d", "\u7b80": "\u7c21", "\u7c7b": "\u985e", "\u7d27": "\u7dca",
    "\u7ebf": "\u7dda", "\u7ecf": "\u7d93", "\u7ed3": "\u7d50", "\u7edf": "\u7d71",
    "\u7ee7": "\u7e7c", "\u7eed": "\u7e8c", "\u7f16": "\u7de8", "\u7f51": "\u7db2",
    "\u7f57": "\u7f85", "\u804c": "\u8077", "\u8054": "\u806f", "\u80dc": "\u52dd",
    "\u8111": "\u8166", "\u8138": "\u81c9", "\u8282": "\u7bc0", "\u836f": "\u85e5",
    "\u83b7": "\u7372", "\u8425": "\u71df", "\u84dd": "\u85cd", "\u8651": "\u616e",
    "\u867d": "\u96d6", "\u8865": "\u88dc", "\u89c1": "\u898b", "\u89c2": "\u89c0",
    "\u89c4": "\u898f", "\u89c6": "\u8996", "\u8ba1": "\u8a08", "\u8ba4": "\u8a8d",
    "\u8ba8": "\u8a0e", "\u8ba9": "\u8b93", "\u8bad": "\u8a13", "\u8bae": "\u8b70",
    "\u8baf": "\u8a0a", "\u8bb0": "\u8a18", "\u8bb2": "\u8b1b", "\u8bbe": "\u8a2d",
    "\u8bc1": "\u8b49", "\u8bc4": "\u8a55", "\u8bc6": "\u8b58", "\u8bd1": "\u8b6f",
    "\u8bd5": "\u8a66", "\u8bdd": "\u8a71", "\u8be6": "\u8a73", "\u8bed": "\u8a9e",
    "\u8bf4": "\u8aaa", "\u8bf7": "\u8acb", "\u8bfb": "\u8b80", "\u8c03": "\u8abf",
    "\u8c08": "\u8ac7", "\u8c22": "\u8b1d", "\u8d22": "\u8ca1", "\u8d23": "\u8cac",
    "\u8d25": "\u6557", "\u8d27": "\u8ca8", "\u8d28": "\u8cea", "\u8d2d": "\u8cfc",
    "\u8d35": "\u8cb4", "\u8d37": "\u8cb8", "\u8d39": "\u8cbb", "\u8d44": "\u8cc7",
    "\u8d4f": "\u8cde", "\u8d5a": "\u8cfa", "\u8d5b": "\u8cfd", "\u8d5e": "\u8d0a",
    "\u8d8b": "\u8da8", "\u8dc3": "\u8e8d", "\u8e2a": "\u8e64", "\u8f66": "\u8eca",
    "\u8f68": "\u8ecc", "\u8f6c": "\u8f49", "\u8f6e": "\u8f2a", "\u8f7b": "\u8f15",
    "\u8f7d": "\u8f09", "\u8f83": "\u8f03", "\u8f91": "\u8f2f", "\u8f93": "\u8f38",
    "\u8fbe": "\u9054", "\u8fc7": "\u904e", "\u8fd0": "\u904b", "\u8fd8": "\u9084",
    "\u8fd9": "\u9019", "\u8fdb": "\u9032", "\u8fde": "\u9023", "\u9009": "\u9078",
    "\u903b": "\u908f", "\u9057": "\u907a", "\u90ae": "\u90f5", "\u90bb": "\u9130",
    "\u91ca": "\u91cb", "\u91cc": "\u88e1", "\u94c1": "\u9435", "\u94fe": "\u93c8",
    "\u9500": "\u92b7", "\u9519": "\u932f", "\u952e": "\u9375", "\u957f": "\u9577",
    "\u95e8": "\u9580", "\u95ee": "\u554f", "\u95f4": "\u9593", "\u95fb": "\u805e",
    "\u961f": "\u968a", "\u9633": "\u967d", "\u9635": "\u9663", "\u9645": "\u969b",
    "\u9646": "\u9678", "\u9648": "\u9673", "\u9669": "\u96aa", "\u968f": "\u96a8",
    "\u96be": "\u96e3", "\u9759": "\u975c", "\u97e9": "\u97d3", "\u9875": "\u9801",
    "\u9879": "\u9805", "\u987a": "\u9806", "\u987b": "\u9808", "\u987e": "\u9867",
    "\u9884": "\u9810", "\u9886": "\u9818", "\u9891": "\u983b", "\u9898": "\u984c",
    "\u989d": "\u984d", "\u98ce": "\u98a8", "\u98de": "\u98db", "\u9a71": "\u9a45",
    "\u9a8c": "\u9a57", "\u9ec4": "\u9ec3", "\u9f99": "\u9f8d",
})


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def env_required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        fail(f"Missing required environment variable: {name}")
    return value


def to_traditional_text(value: str) -> str:
    if not isinstance(value, str):
        return value
    for src, dst in TC_REPLACEMENTS.items():
        value = value.replace(src, dst)
    return value.translate(TC_CHARS)


def to_traditional(value):
    if isinstance(value, str):
        return to_traditional_text(value)
    if isinstance(value, list):
        return [to_traditional(item) for item in value]
    if isinstance(value, dict):
        return {key: to_traditional(item) for key, item in value.items()}
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
    value = re.sub(r"\s+", " ", value).strip()
    return to_traditional_text(value)


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
        sources.append({"name": source_name, "url": url, "access": "Full" if status == 200 else "Blocked"})
        if status == 200:
            all_candidates.extend(extract_candidates(source_name, url, body))

    keyword_pattern = re.compile(
        r"fed|fomc|inflation|cpi|pce|jobs|treasury|yield|dollar|oil|gold|"
        r"nvidia|amd|tsmc|semiconductor|chip|ai|artificial intelligence|cloud|apple|tesla|microsoft|google|meta|amazon|"
        r"\u806f\u5132|\u901a\u8139|\u975e\u8fb2|\u9ec3\u91d1|\u539f\u6cb9|\u4eba\u5de5\u667a\u80fd|\u534a\u5c0e\u9ad4|\u6676\u7247|\u4e2d\u570b",
        re.I,
    )
    filtered = [item for item in all_candidates if keyword_pattern.search(item["title"])]
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
    text = text.replace("\ufeff", "")
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
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


def ai_request(account_id: str, api_token: str, model: str, messages: list[dict], max_tokens: int = 7000) -> str:
    payload = {"messages": messages, "max_tokens": max_tokens, "temperature": 0.0}
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
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
    return text


def build_prompt(candidates: list[dict], sources: list[dict]) -> str:
    schema = {
        "date": TODAY,
        "title": "\u6bcf\u65e5\u570b\u969b\u8ca1\u7d93\u8207\u79d1\u6280\u65b0\u805e\u6458\u8981",
        "deck": "\u7e41\u9ad4\u4e2d\u6587\u5c0e\u8a9e",
        "daily_summary_zh": "\u7e41\u9ad4\u4e2d\u6587\u6bcf\u65e5\u7e3d\u7d50",
        "market_focus": ["\u570b\u969b\u8ca1\u7d93", "AI\u8207\u79d1\u6280\u7522\u696d", "\u534a\u5c0e\u9ad4"],
        "hot_topics": [{
            "rank": 1,
            "topic": "\u7e41\u9ad4\u4e2d\u6587\u7126\u9ede\u6a19\u984c",
            "heat_score": 80,
            "heat_label": "High",
            "source_count": 2,
            "main_sources": ["Reuters", "CNBC"],
            "item_ids": [f"{TODAY}-topic-001"],
            "one_line_reason": "\u7e41\u9ad4\u4e2d\u6587\u4e0a\u699c\u539f\u56e0",
            "reporter_angle": "\u7e41\u9ad4\u4e2d\u6587\u63a1\u8a2a\u6216\u8ffd\u8e64\u89d2\u5ea6",
        }],
        "categories": [{"name": "AI\u8207\u79d1\u6280\u7522\u696d", "slug": "ai-technology-industry", "item_ids": [f"{TODAY}-topic-001"]}],
        "items": [{
            "id": f"{TODAY}-topic-001",
            "date": TODAY,
            "title_original": "Original headline",
            "title_zh": "\u7e41\u9ad4\u4e2d\u6587\u6a19\u984c",
            "source": "Reuters",
            "url": "https://example.com/article",
            "published_at": GENERATED_AT,
            "category": "AI\u8207\u79d1\u6280\u7522\u696d",
            "themes": ["AI\u57fa\u5efa", "\u534a\u5c0e\u9ad4"],
            "summary_zh": "\u7e41\u9ad4\u4e2d\u6587\u6458\u8981\u3002",
            "key_facts": ["\u7e41\u9ad4\u4e2d\u6587\u91cd\u9ede\u4e00", "\u7e41\u9ad4\u4e2d\u6587\u91cd\u9ede\u4e8c"],
            "market_impact": "\u7e41\u9ad4\u4e2d\u6587\u5e02\u5834\u5f71\u97ff",
            "reporter_angle": "\u7e41\u9ad4\u4e2d\u6587\u8ffd\u8e64\u89d2\u5ea6",
            "importance_score": 8,
            "heat_score": 75,
            "source_count": 2,
            "sources_reporting_same_topic": ["Reuters", "CNBC"],
            "position_signal": "headline cluster",
            "time_horizon": "short_term",
            "tracking_value": "\u7e41\u9ad4\u4e2d\u6587\u8ffd\u8e64\u50f9\u503c",
        }],
        "sources": sources,
        "generated_at": GENERATED_AT,
        "email_body_zh": "\u7e41\u9ad4\u4e2d\u6587 email \u6458\u8981",
    }
    task = {
        "task": "Create a website-ready daily international finance and technology news brief.",
        "date": TODAY,
        "language": "Traditional Chinese only for all reader-facing Chinese fields.",
        "output_rules": [
            "Return one valid JSON object only. No markdown. No comments.",
            "Use real Traditional Chinese characters directly. Do not output Unicode escape sequences.",
            "Do not mention JSON validation, fallback mode, automation, prompt, model, or internal errors in reader-facing fields.",
            "hot_topics must contain 3 to 5 entries.",
            "items must contain 6 to 12 entries.",
            "Every hot_topics[].item_ids and categories[].item_ids value must exist in items[].id.",
            "Do not give personalized investment advice.",
        ],
        "required_item_fields": REQUIRED_ITEM_FIELDS,
        "required_hot_topic_fields": REQUIRED_HOT_TOPIC_FIELDS,
        "schema_example": schema,
        "sources": sources,
        "candidate_headlines": candidates[:80],
    }
    return json.dumps(task, ensure_ascii=False, indent=2)


def call_cloudflare_ai(candidates: list[dict], sources: list[dict]) -> dict:
    account_id = env_required("CLOUDFLARE_ACCOUNT_ID")
    api_token = env_required("CLOUDFLARE_API_TOKEN")
    model = os.environ.get("CF_AI_MODEL", "@cf/meta/llama-3.1-8b-instruct").strip()
    system = "You are a careful news editor. Output strict valid JSON only, using Traditional Chinese for reader-facing fields."
    text = ai_request(account_id, api_token, model, [{"role": "system", "content": system}, {"role": "user", "content": build_prompt(candidates, sources)}])
    try:
        return extract_json(text)
    except json.JSONDecodeError:
        repair_prompt = (
            "Repair the following response into one valid JSON object that matches the requested schema. "
            "Output JSON only. Use Traditional Chinese for reader-facing fields. Remove markdown and invalid escape sequences.\n\n"
            + text[:24000]
        )
        repaired = ai_request(account_id, api_token, model, [{"role": "system", "content": system}, {"role": "user", "content": repair_prompt}], max_tokens=7000)
        return extract_json(repaired)


def normalize_brief(brief: dict, sources: list[dict]) -> dict:
    brief = to_traditional(brief)
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

    text_dump = json.dumps(brief, ensure_ascii=False)
    forbidden = ["\u4fdd\u5e95\u6a21\u5f0f", "JSON \u9a57\u8b49", "JSON\u9a8c\u8bc1", "\u672a\u80fd\u901a\u904e", "\u672a\u80fd\u901a\u8fc7", "fallback mode"]
    for phrase in forbidden:
        if phrase in text_dump:
            fail(f"Reader-facing brief contains internal phrase: {phrase}")

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
    return to_traditional({"latest_date": TODAY, "briefs": briefs})


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
            "id": f"{TODAY}-headline-{idx:03d}",
            "date": TODAY,
            "title_original": title,
            "title_zh": title,
            "source": source_name,
            "url": candidate.get("url") or "https://news.tinydreamlab.com/",
            "published_at": GENERATED_AT,
            "category": category_name,
            "themes": [category_name],
            "summary_zh": "\u9019\u689d\u65b0\u805e\u6839\u64da\u516c\u958b\u6a19\u984c\u3001\u4f86\u6e90\u548c\u539f\u6587\u9023\u7d50\u6574\u7406\uff0c\u4fdd\u7559\u53ef\u8ffd\u8e64\u7684\u65b0\u805e\u5165\u53e3\uff0c\u65b9\u4fbf\u5feb\u901f\u700f\u89bd\u548c\u5f8c\u7e8c\u67e5\u8b49\u3002",
            "key_facts": ["\u4f86\u6e90\u9801\u9762\u51fa\u73fe\u76f8\u95dc\u6a19\u984c\u6216\u9023\u7d50\u3002", "\u53ef\u5f9e\u539f\u6587\u9023\u7d50\u7e7c\u7e8c\u6838\u5be6\u7d30\u7bc0\u548c\u5e02\u5834\u5f71\u97ff\u3002"],
            "market_impact": "\u503c\u5f97\u5f8c\u7e8c\u8ffd\u8e64\u5176\u5c0d\u5e02\u5834\u60c5\u7dd2\u3001\u76f8\u95dc\u80a1\u4efd\u6216\u7522\u696d\u93c8\u7684\u5f71\u97ff\u3002",
            "reporter_angle": "\u53ef\u5f9e\u539f\u6587\u9023\u7d50\u6838\u5be6\u4e8b\u5be6\uff0c\u4e26\u8ffd\u8e64\u5f8c\u7e8c\u662f\u5426\u6709\u66f4\u591a\u4f86\u6e90\u5831\u9053\u540c\u4e00\u4e3b\u984c\u3002",
            "importance_score": max(5, 9 - idx),
            "heat_score": max(50, 82 - idx * 4),
            "source_count": 1,
            "sources_reporting_same_topic": [source_name],
            "position_signal": "headline candidate",
            "time_horizon": "short_term",
            "tracking_value": "\u9700\u8981\u8ffd\u8e64\u539f\u6587\u66f4\u65b0\u8207\u76f8\u95dc\u5831\u9053\u3002",
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
            "one_line_reason": "\u6839\u64da\u4f86\u6e90\u548c\u984c\u6750\u71b1\u5ea6\u9078\u51fa\u7684\u9ad8\u512a\u5148\u7d1a\u65b0\u805e\u5165\u53e3\u3002",
            "reporter_angle": item["reporter_angle"],
        })

    categories = []
    for category_name, slug in category_defs:
        refs = [item["id"] for item in items if item["category"] == category_name]
        if refs:
            categories.append({"name": category_name, "slug": slug, "item_ids": refs})

    brief = {
        "date": TODAY,
        "title": "\u6bcf\u65e5\u570b\u969b\u8ca1\u7d93\u8207\u79d1\u6280\u65b0\u805e\u6458\u8981",
        "deck": "\u4eca\u65e5\u6458\u8981\u5df2\u66f4\u65b0\uff0c\u6574\u7406\u516c\u958b\u65b0\u805e\u6a19\u984c\u3001\u4f86\u6e90\u548c\u539f\u6587\u9023\u7d50\u3002",
        "daily_summary_zh": "\u4eca\u65e5\u65b0\u805e\u6458\u8981\u5df2\u6839\u64da\u5df2\u6293\u53d6\u7684\u516c\u958b\u65b0\u805e\u6a19\u984c\u3001\u4f86\u6e90\u548c\u539f\u6587\u9023\u7d50\u6574\u7406\uff0c\u4f9b\u5feb\u901f\u700f\u89bd\u548c\u5f8c\u7e8c\u8ffd\u8e64\u3002",
        "market_focus": ["\u570b\u969b\u8ca1\u7d93\u8207\u5e02\u5834", "AI\u8207\u79d1\u6280\u7522\u696d", "\u539f\u6587\u9023\u7d50\u8ffd\u8e64"],
        "hot_topics": hot_topics,
        "categories": categories,
        "items": items,
        "sources": sources,
        "generated_at": GENERATED_AT,
        "email_body_zh": "\u4eca\u65e5\u65b0\u805e\u6458\u8981\u5df2\u66f4\u65b0\u3002\u7db2\u7ad9\u5df2\u6574\u7406\u516c\u958b\u65b0\u805e\u6a19\u984c\u3001\u4f86\u6e90\u548c\u539f\u6587\u9023\u7d50\uff0c\u65b9\u4fbf\u5feb\u901f\u700f\u89bd\u548c\u5f8c\u7e8c\u8ffd\u8e64\u3002\n\n\u7db2\u7ad9\uff1ahttps://news.tinydreamlab.com/",
    }
    print(f"Warning: generated reader-safe headline brief. Internal reason: {error}")
    return to_traditional(brief)


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(to_traditional(data), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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
    try:
        brief = call_cloudflare_ai(candidates, sources)
        brief = normalize_brief(brief, sources)
        validate_brief(brief)
    except Exception as exc:
        print(f"Warning: AI brief generation failed; using reader-safe headline brief. Reason: {exc}")
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
