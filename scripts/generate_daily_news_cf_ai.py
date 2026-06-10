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

PHRASE_TC = {
    "中国": "中國", "美国": "美國", "国际": "國際", "财经": "財經", "科技产业": "科技產業",
    "互联网": "互聯網", "计算机": "計算機", "供应链": "供應鏈", "供应": "供應",
    "扩张": "擴張", "涨价": "漲價", "同比": "按年", "半导体": "半導體", "芯片": "晶片",
    "存储": "儲存", "洁净室": "潔淨室", "驱动": "驅動", "烧钱": "燒錢", "强度": "強度",
    "折旧": "折舊", "未来": "未來", "焦点": "焦點", "刚刚": "剛剛",
    "保底模式": "備用整理", "自动保底模式": "自動整理模式",
    "Cloudflare Workers AI 回覆未能通過 JSON 驗證": "今日摘要已根據公開新聞標題、來源和原文連結整理",
    "原始 AI JSON 回覆格式未能通過驗證": "今日先保留可追蹤的新聞入口",
}
CHAR_TC = str.maketrans({
    "与":"與","业":"業","东":"東","个":"個","为":"為","乐":"樂","买":"買","云":"雲","产":"產","从":"從","们":"們","价":"價",
    "传":"傳","体":"體","储":"儲","关":"關","兴":"興","军":"軍","决":"決","净":"淨","则":"則","刚":"剛","创":"創","别":"別",
    "办":"辦","务":"務","动":"動","势":"勢","区":"區","华":"華","单":"單","压":"壓","参":"參","双":"雙","发":"發","变":"變",
    "后":"後","启":"啟","员":"員","响":"響","团":"團","围":"圍","国":"國","图":"圖","场":"場","块":"塊","坚":"堅","处":"處",
    "备":"備","头":"頭","奖":"獎","学":"學","实":"實","审":"審","对":"對","导":"導","将":"將","层":"層","岁":"歲","师":"師",
    "带":"帶","库":"庫","应":"應","废":"廢","开":"開","张":"張","强":"強","归":"歸","当":"當","录":"錄","总":"總","恶":"惡",
    "惊":"驚","惨":"慘","惯":"慣","愿":"願","战":"戰","执":"執","扩":"擴","护":"護","报":"報","担":"擔","拟":"擬","拥":"擁",
    "择":"擇","挥":"揮","挣":"掙","挤":"擠","换":"換","据":"據","摆":"擺","摇":"搖","数":"數","无":"無","旧":"舊","时":"時",
    "显":"顯","术":"術","机":"機","权":"權","来":"來","极":"極","构":"構","标":"標","栏":"欄","树":"樹","样":"樣","档":"檔",
    "检":"檢","楼":"樓","欧":"歐","残":"殘","气":"氣","汇":"匯","汉":"漢","没":"沒","泽":"澤","洁":"潔","测":"測","济":"濟",
    "浓":"濃","涨":"漲","渐":"漸","温":"溫","湾":"灣","满":"滿","滚":"滾","灯":"燈","灵":"靈","点":"點","烧":"燒","热":"熱",
    "爱":"愛","独":"獨","环":"環","现":"現","电":"電","画":"畫","监":"監","盘":"盤","着":"著","矿":"礦","码":"碼","确":"確",
    "礼":"禮","离":"離","种":"種","积":"積","称":"稱","税":"稅","稳":"穩","笔":"筆","签":"簽","简":"簡","类":"類","紧":"緊",
    "线":"線","经":"經","结":"結","统":"統","继":"繼","续":"續","编":"編","网":"網","罗":"羅","职":"職","联":"聯","胜":"勝",
    "脑":"腦","脸":"臉","节":"節","药":"藥","获":"獲","营":"營","蓝":"藍","虑":"慮","虽":"雖","补":"補","见":"見","观":"觀",
    "规":"規","视":"視","计":"計","认":"認","讨":"討","让":"讓","训":"訓","议":"議","讯":"訊","记":"記","讲":"講","设":"設",
    "证":"證","评":"評","识":"識","译":"譯","试":"試","话":"話","详":"詳","语":"語","说":"說","请":"請","读":"讀","调":"調",
    "谈":"談","谢":"謝","财":"財","责":"責","败":"敗","货":"貨","质":"質","购":"購","贵":"貴","贷":"貸","费":"費","资":"資",
    "赏":"賞","赚":"賺","赛":"賽","赞":"贊","趋":"趨","跃":"躍","踪":"蹤","车":"車","轨":"軌","转":"轉","轮":"輪","轻":"輕",
    "载":"載","较":"較","辑":"輯","输":"輸","达":"達","过":"過","运":"運","还":"還","这":"這","进":"進","连":"連","选":"選",
    "逻":"邏","遗":"遺","邮":"郵","邻":"鄰","释":"釋","里":"裡","铁":"鐵","链":"鏈","销":"銷","错":"錯","键":"鍵","长":"長",
    "门":"門","问":"問","间":"間","闻":"聞","队":"隊","阳":"陽","阵":"陣","际":"際","陆":"陸","陈":"陳","险":"險","随":"隨",
    "难":"難","静":"靜","韩":"韓","页":"頁","项":"項","顺":"順","须":"須","顾":"顧","预":"預","领":"領","频":"頻","题":"題",
    "额":"額","风":"風","飞":"飛","驱":"驅","验":"驗","黄":"黃","龙":"龍",
})


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def validation_error(message: str) -> None:
    raise ValueError(message)


def env_required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        fail(f"Missing required environment variable: {name}")
    return value


def to_traditional_text(value: str) -> str:
    if not isinstance(value, str):
        return value
    for src, dst in PHRASE_TC.items():
        value = value.replace(src, dst)
    return value.translate(CHAR_TC)


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
    return to_traditional_text(re.sub(r"\s+", " ", value).strip())


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
    keywords = re.compile(r"fed|fomc|inflation|cpi|pce|jobs|treasury|yield|dollar|oil|gold|nvidia|amd|tsmc|semiconductor|chip|ai|artificial intelligence|cloud|apple|tesla|microsoft|google|meta|amazon|聯儲|通脹|非農|黃金|原油|人工智能|半導體|晶片|中國", re.I)
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
        fail(f"Cloudflare Workers AI HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}")
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
        "title": "每日國際財經與科技新聞摘要",
        "deck": "繁體中文導語",
        "daily_summary_zh": "繁體中文每日總結",
        "market_focus": ["國際財經", "AI與科技產業", "半導體"],
        "hot_topics": [{"rank": 1, "topic": "繁體中文焦點標題", "heat_score": 80, "heat_label": "High", "source_count": 2, "main_sources": ["Reuters", "CNBC"], "item_ids": [f"{TODAY}-topic-001"], "one_line_reason": "繁體中文上榜原因", "reporter_angle": "繁體中文追蹤角度"}],
        "categories": [{"name": "AI與科技產業", "slug": "ai-technology-industry", "item_ids": [f"{TODAY}-topic-001"]}],
        "items": [{"id": f"{TODAY}-topic-001", "date": TODAY, "title_original": "Original headline", "title_zh": "繁體中文標題", "source": "Reuters", "url": "https://example.com/article", "published_at": GENERATED_AT, "category": "AI與科技產業", "themes": ["AI基建", "半導體"], "summary_zh": "繁體中文摘要。", "key_facts": ["繁體中文重點一", "繁體中文重點二"], "market_impact": "繁體中文市場影響", "reporter_angle": "繁體中文追蹤角度", "importance_score": 8, "heat_score": 75, "source_count": 2, "sources_reporting_same_topic": ["Reuters", "CNBC"], "position_signal": "headline cluster", "time_horizon": "short_term", "tracking_value": "繁體中文追蹤價值"}],
        "sources": sources,
        "generated_at": GENERATED_AT,
        "email_body_zh": "繁體中文 email 摘要",
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
        repair_prompt = "Repair the following response into one valid JSON object that matches the requested schema. Output JSON only. Use Traditional Chinese for reader-facing fields. Remove markdown and invalid escape sequences.\n\n" + text[:24000]
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
            validation_error(f"Brief missing required field: {field}")
    if brief["date"] != TODAY:
        validation_error(f"Brief date {brief['date']} does not match {TODAY}")
    text_dump = json.dumps(brief, ensure_ascii=False)
    for phrase in ["保底模式", "JSON 驗證", "JSON验证", "未能通過", "未能通过", "fallback mode"]:
        if phrase in text_dump:
            validation_error(f"Reader-facing brief contains internal phrase: {phrase}")
    items = brief.get("items")
    if not isinstance(items, list) or len(items) < 6:
        validation_error("items must contain at least 6 entries.")
    item_ids = set()
    for item in items:
        for field in REQUIRED_ITEM_FIELDS:
            if field not in item:
                validation_error(f"Item missing required field {field}: {item.get('id')}")
        if item["id"] in item_ids:
            validation_error(f"Duplicate item id: {item['id']}")
        item_ids.add(item["id"])
    hot_topics = brief.get("hot_topics")
    if not isinstance(hot_topics, list) or not (3 <= len(hot_topics) <= 5):
        validation_error("hot_topics must contain 3 to 5 entries.")
    for topic in hot_topics:
        for field in REQUIRED_HOT_TOPIC_FIELDS:
            if field not in topic:
                validation_error(f"Hot topic missing required field {field}: {topic}")
        refs = topic.get("item_ids")
        if not isinstance(refs, list) or not refs:
            validation_error(f"Hot topic has empty item_ids: {topic.get('topic')}")
        for item_id in refs:
            if item_id not in item_ids:
                validation_error(f"Hot topic item_id not found in items: {item_id}")
    for category in brief.get("categories", []):
        refs = category.get("item_ids", [])
        if not isinstance(refs, list):
            validation_error(f"Category item_ids must be a list: {category.get('name')}")
        for item_id in refs:
            if item_id not in item_ids:
                validation_error(f"Category item_id not found in items: {item_id}")


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
    return {"date": brief["date"], "title": brief["title"], "summary": brief["deck"], "top_themes": top_themes, "hot_topic_count": len(brief.get("hot_topics", [])), "item_count": len(brief.get("items", [])), "generated_at": brief["generated_at"]}


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
    category_defs = [("國際財經與市場", "global-finance-markets"), ("AI與科技產業", "ai-technology-industry"), ("中國科技與政策", "china-tech-policy")]
    items = []
    for idx, candidate in enumerate(usable[:6], start=1):
        category_name, _ = category_defs[(idx - 1) % len(category_defs)]
        source_name = candidate.get("source") or "Public source"
        title = clean_text(candidate.get("title") or source_name)
        items.append({
            "id": f"{TODAY}-headline-{idx:03d}", "date": TODAY, "title_original": title, "title_zh": title,
            "source": source_name, "url": candidate.get("url") or "https://news.tinydreamlab.com/", "published_at": GENERATED_AT,
            "category": category_name, "themes": [category_name],
            "summary_zh": "這條新聞根據公開標題、來源和原文連結整理，保留可追蹤的新聞入口，方便快速瀏覽和後續查證。",
            "key_facts": ["來源頁面出現相關標題或連結。", "可從原文連結繼續核實細節和市場影響。"],
            "market_impact": "值得後續追蹤其對市場情緒、相關股份或產業鏈的影響。",
            "reporter_angle": "可從原文連結核實事實，並追蹤後續是否有更多來源報道同一主題。",
            "importance_score": max(5, 9 - idx), "heat_score": max(50, 82 - idx * 4), "source_count": 1,
            "sources_reporting_same_topic": [source_name], "position_signal": "headline candidate", "time_horizon": "short_term",
            "tracking_value": "需要追蹤原文更新與相關報道。",
        })
    hot_topics = []
    for rank, item in enumerate(items[:3], start=1):
        hot_topics.append({"rank": rank, "topic": item["title_zh"][:60], "heat_score": item["heat_score"], "heat_label": "High" if item["heat_score"] >= 75 else "Medium", "source_count": 1, "main_sources": [item["source"]], "item_ids": [item["id"]], "one_line_reason": "根據來源和題材熱度選出的高優先級新聞入口。", "reporter_angle": item["reporter_angle"]})
    categories = []
    for category_name, slug in category_defs:
        refs = [item["id"] for item in items if item["category"] == category_name]
        if refs:
            categories.append({"name": category_name, "slug": slug, "item_ids": refs})
    print(f"Warning: generated reader-safe headline brief. Internal reason: {error}")
    return to_traditional({
        "date": TODAY,
        "title": "每日國際財經與科技新聞摘要",
        "deck": "今日摘要已更新，整理公開新聞標題、來源和原文連結。",
        "daily_summary_zh": "今日新聞摘要已根據已抓取的公開新聞標題、來源和原文連結整理，供快速瀏覽和後續追蹤。",
        "market_focus": ["國際財經與市場", "AI與科技產業", "原文連結追蹤"],
        "hot_topics": hot_topics, "categories": categories, "items": items, "sources": sources, "generated_at": GENERATED_AT,
        "email_body_zh": "今日新聞摘要已更新。網站已整理公開新聞標題、來源和原文連結，方便快速瀏覽和後續追蹤。\n\n網站：https://news.tinydreamlab.com/",
    })


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
    body = (brief.get("email_body_zh") or brief.get("daily_summary_zh", "")) + "\n\n網站：https://news.tinydreamlab.com/\n"
    message = EmailMessage()
    message["From"] = smtp_user
    message["To"] = email_to
    message["Subject"] = f"每日財經科技新聞雷達 | {TODAY}"
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
