#!/usr/bin/env python3
import json
import os
import re
import smtplib
import ssl
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta
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


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def env_required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        fail(f"Missing required environment variable: {name}")
    return value


def extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            raise
        return json.loads(match.group(0))


def call_openai() -> dict:
    api_key = env_required("OPENAI_API_KEY")
    model = os.environ.get("OPENAI_MODEL", "gpt-5").strip() or "gpt-5"

    prompt = f"""
今天日期是 {TODAY}，時區是 Asia/Hong_Kong。

請掃描並比較以下 V1 來源池的今日或最近 24-48 小時可讀新聞：
1. 華爾街見聞 Wallstreetcn
2. Reuters
3. CNBC
4. TechCrunch
5. 財新 Caixin 或晚點 LatePost

不要以任何單一媒體為主。請把多個來源中相同或高度相關的新聞聚合成 topic clusters，
發掘國際財經、金融市場、AI、半導體、科技產業、中國科技/政策的重點。

使用者關注清單：
- 國際宏觀與央行
- 美債、美元、人民幣、黃金、原油等大類資產
- 美股與全球科技龍頭
- AI 算力與半導體產業鏈
- AI 應用與科技趨勢
- 中國與港股科技
- 中國宏觀與政策
- 地緣政治與政策風險

重點公司/主題：
Fed, CPI, PCE, nonfarm payrolls, Treasury yields, USD, gold, oil,
Nvidia, Microsoft, Google, Meta, Apple, Tesla, Amazon, Broadcom, Marvell, AMD, TSMC,
AI infrastructure, HBM, optical modules, CPO, data centers, Agentic AI, enterprise AI,
Huawei, Tencent, Alibaba, Meituan, Xiaomi, Baidu, BYD.

請只輸出合法 JSON，不要輸出 markdown，不要加解釋文字。

JSON 需要符合以下 schema：
{{
  "date": "{TODAY}",
  "title": "繁體中文標題",
  "deck": "繁體中文簡短導語",
  "daily_summary_zh": "繁體中文每日總結",
  "market_focus": ["焦點1", "焦點2", "焦點3"],
  "hot_topics": [
    {{
      "rank": 1,
      "topic": "焦點主題",
      "heat_score": 88,
      "heat_label": "High",
      "source_count": 4,
      "main_sources": ["Reuters", "CNBC"],
      "item_ids": ["{TODAY}-reuters-example-001"],
      "one_line_reason": "上榜原因",
      "reporter_angle": "記者可跟進角度"
    }}
  ],
  "categories": [
    {{
      "name": "AI算力與半導體",
      "slug": "ai-compute-semiconductors",
      "item_ids": ["{TODAY}-reuters-example-001"]
    }}
  ],
  "items": [
    {{
      "id": "{TODAY}-source-topic-001",
      "date": "{TODAY}",
      "title_original": "Original headline",
      "title_zh": "繁體中文標題",
      "source": "Reuters",
      "url": "https://example.com/article",
      "published_at": "{GENERATED_AT}",
      "category": "國際宏觀與央行",
      "themes": ["Fed policy", "AI infrastructure"],
      "summary_zh": "繁體中文摘要",
      "key_facts": ["事實1", "事實2"],
      "market_impact": "市場影響",
      "reporter_angle": "記者可跟進角度",
      "importance_score": 8,
      "heat_score": 75,
      "source_count": 3,
      "sources_reporting_same_topic": ["Reuters", "CNBC"],
      "position_signal": "top story / market-wide signal / Partial / Full / Blocked",
      "time_horizon": "short_term",
      "tracking_value": "追蹤價值"
    }}
  ],
  "sources": [
    {{
      "name": "Reuters",
      "url": "https://www.reuters.com/",
      "access": "Full"
    }}
  ],
  "generated_at": "{GENERATED_AT}",
  "email_body_zh": "1000至1600字繁體中文 email 正文，包含：今日一句話結論、重大提醒如有、市場方向儀表板、今日焦點新聞榜、國際財經重點3條、科技趨勢重點5條、多來源熱點判斷、今日最重要市場主線、記者可跟進角度、需要連續追蹤題目、原文連結。"
}}

要求：
- hot_topics 必須有 3 至 5 個。
- items 至少 6 條。
- 每個 hot_topics[].item_ids 不可為空。
- 每個 hot_topics[].item_ids 必須存在於 items[].id。
- categories[].item_ids 也必須存在於 items[].id。
- heat_score 0-100；75-100 High，50-74 Medium，低於50 Low。
- importance_score 1-10。
- 每個 item 的 themes 使用 2 至 6 個穩定標籤。
- 若來源全文不可讀，請在 sources 或 position_signal 標示 Partial 或 Blocked。
- 不提供個人化投資建議。
"""

    payload = {
        "model": model,
        "reasoning": {"effort": "low"},
        "tools": [
            {
                "type": "web_search",
                "filters": {
                    "allowed_domains": [
                        "wallstreetcn.com",
                        "reuters.com",
                        "cnbc.com",
                        "techcrunch.com",
                        "caixin.com",
                        "latepost.com",
                    ]
                },
            }
        ],
        "tool_choice": "auto",
        "input": prompt,
    }

    req = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=600) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        fail(f"OpenAI API HTTP {exc.code}: {error_body}")

    data = json.loads(body)
    output_text = data.get("output_text")
    if not output_text:
        parts = []
        for item in data.get("output", []):
            if item.get("type") != "message":
                continue
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    parts.append(content.get("text", ""))
        output_text = "\n".join(parts).strip()

    if not output_text:
        fail("OpenAI response did not contain output_text.")

    return extract_json(output_text)


def validate_brief(brief: dict) -> None:
    for field in REQUIRED_BRIEF_FIELDS:
        if field not in brief:
            fail(f"Brief missing required field: {field}")

    if brief["date"] != TODAY:
        fail(f"Brief date {brief['date']} does not match today {TODAY}")

    items = brief.get("items")
    if not isinstance(items, list) or not items:
        fail("Brief items must be a non-empty list.")

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
        item_refs = topic.get("item_ids")
        if not isinstance(item_refs, list) or not item_refs:
            fail(f"Hot topic has empty item_ids: {topic.get('topic')}")
        for item_id in item_refs:
            if item_id not in item_ids:
                fail(f"Hot topic item_id not found in items: {item_id}")

    for category in brief.get("categories", []):
        for item_id in category.get("item_ids", []):
            if item_id not in item_ids:
                fail(f"Category item_id not found in items: {item_id}")


def build_index_entry(brief: dict) -> dict:
    themes = []
    for topic in brief.get("hot_topics", [])[:5]:
        for source_theme in topic.get("main_sources", []):
            if source_theme not in themes:
                themes.append(source_theme)
    if len(themes) < 3:
        for item in brief.get("items", []):
            for theme in item.get("themes", []):
                if theme not in themes:
                    themes.append(theme)
                if len(themes) >= 5:
                    break
            if len(themes) >= 5:
                break

    return {
        "date": brief["date"],
        "title": brief["title"],
        "summary": brief["deck"],
        "top_themes": themes[:5],
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
    briefs.sort(key=lambda item: item.get("date", ""), reverse=True)

    index["latest_date"] = TODAY
    index["briefs"] = briefs
    return index


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def send_email(brief: dict) -> None:
    email_to = env_required("EMAIL_TO")
    smtp_user = env_required("GMAIL_SMTP_USER")
    smtp_password = env_required("GMAIL_APP_PASSWORD")

    subject = f"每日財經科技新聞雷達 | {TODAY}"
    body = brief.get("email_body_zh") or brief.get("daily_summary_zh", "")
    body += "\n\n網站：https://news.tinydreamlab.com/\n"

    message = EmailMessage()
    message["From"] = smtp_user
    message["To"] = email_to
    message["Subject"] = subject
    message.set_content(body)

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context, timeout=60) as server:
        server.login(smtp_user, smtp_password)
        server.send_message(message)


def main() -> None:
    brief = call_openai()
    brief["date"] = TODAY
    brief["generated_at"] = brief.get("generated_at") or GENERATED_AT
    validate_brief(brief)

    index = update_index(brief)

    write_json(BRIEF_PATH, brief)
    write_json(INDEX_PATH, index)

    # Re-read to ensure the files are valid UTF-8 JSON.
    json.loads(BRIEF_PATH.read_text(encoding="utf-8"))
    json.loads(INDEX_PATH.read_text(encoding="utf-8"))

    send_email(brief)
    print(f"Generated {BRIEF_PATH}")
    print(f"Updated {INDEX_PATH}")
    print("Email sent.")


if __name__ == "__main__":
    main()
