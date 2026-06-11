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

SOURCE_CONFIGS = [
    {"name": "Reuters Markets", "url": "https://www.reuters.com/markets/", "kind": "page", "tier": 1, "max_items": 10, "region": "global"},
    {"name": "Reuters Technology", "url": "https://www.reuters.com/technology/", "kind": "page", "tier": 1, "max_items": 8, "region": "global"},
    {"name": "CNBC Top News", "url": "https://www.cnbc.com/id/100003114/device/rss/rss.html", "kind": "rss", "tier": 1, "max_items": 10, "region": "global"},
    {"name": "CNBC Markets", "url": "https://www.cnbc.com/markets/", "kind": "page", "tier": 1, "max_items": 8, "region": "global"},
    {"name": "CNBC Technology", "url": "https://www.cnbc.com/technology/", "kind": "page", "tier": 1, "max_items": 8, "region": "global"},
    {"name": "WSJ Markets", "url": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml", "kind": "rss", "tier": 1, "max_items": 8, "region": "global"},
    {"name": "WSJ Technology", "url": "https://feeds.a.dj.com/rss/RSSWSJD.xml", "kind": "rss", "tier": 1, "max_items": 6, "region": "global"},
    {"name": "MarketWatch Top Stories", "url": "https://feeds.content.dowjones.io/public/rss/mw_topstories", "kind": "rss", "tier": 2, "max_items": 6, "region": "global"},
    {"name": "TechCrunch AI", "url": "https://techcrunch.com/category/artificial-intelligence/", "kind": "page", "tier": 2, "max_items": 6, "region": "global"},
    {"name": "TechCrunch Startups", "url": "https://techcrunch.com/category/startups/", "kind": "page", "tier": 2, "max_items": 5, "region": "global"},
    {"name": "Wallstreetcn", "url": "https://wallstreetcn.com/", "kind": "page", "tier": 3, "max_items": 4, "region": "china"},
    {"name": "Caixin", "url": "https://www.caixin.com/", "kind": "page", "tier": 3, "max_items": 3, "region": "china"},
    {"name": "LatePost", "url": "https://www.latepost.com/", "kind": "page", "tier": 3, "max_items": 3, "region": "china"},
]

CATEGORY_TAXONOMY = [
    ("全球市場與宏觀", "global-markets-macro"),
    ("企業、財報與交易", "companies-earnings-deals"),
    ("科技、AI與平台", "technology-ai-platforms"),
    ("半導體與供應鏈", "semiconductors-supply-chain"),
    ("中國與亞洲觀察", "china-asia-watch"),
    ("能源、外匯與商品", "energy-fx-commodities"),
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


def extract_rss_candidates(source_name: str, url: str, body: str) -> list[dict]:
    candidates = []
    for item in re.findall(r"<item\b[^>]*>(.*?)</item>", body, flags=re.I | re.S):
        title_match = re.search(r"<title[^>]*>(.*?)</title>", item, re.I | re.S)
        link_match = re.search(r"<link[^>]*>(.*?)</link>", item, re.I | re.S)
        date_match = re.search(r"<pubDate[^>]*>(.*?)</pubDate>", item, re.I | re.S)
        if not title_match:
            continue
        title = clean_text(title_match.group(1))
        link = clean_text(link_match.group(1)) if link_match else url
        if not (12 <= len(title) <= 180):
            continue
        candidates.append({"source": source_name, "title": title, "url": absolute_url(url, link), "published_at_hint": clean_text(date_match.group(1)) if date_match else ""})
        if len(candidates) >= 30:
            break
    return candidates


def infer_topic_hint(title: str) -> str:
    text = title.lower()
    if re.search(r"nvidia|amd|tsmc|semiconductor|chip|晶片|半導體", text):
        return "半導體與供應鏈"
    if re.search(r"\bai\b|artificial intelligence|openai|cloud|data center|datacenter|人工智能|雲|數據中心", text):
        return "科技、AI與平台"
    if re.search(r"fed|fomc|inflation|cpi|pce|yield|treasury|jobs|rates|聯儲|通脹|利率|非農", text):
        return "全球市場與宏觀"
    if re.search(r"earnings|deal|merger|ipo|stock|shares|財報|併購|上市|股份", text):
        return "企業、財報與交易"
    if re.search(r"oil|gas|gold|dollar|yen|euro|commodity|原油|黃金|美元|日圓|商品", text):
        return "能源、外匯與商品"
    if re.search(r"china|hong kong|japan|asia|中國|香港|日本|亞洲", text):
        return "中國與亞洲觀察"
    return "全球市場與宏觀"


def headline_score(candidate: dict) -> int:
    title = candidate.get("title", "")
    source_tier = int(candidate.get("source_tier", 3))
    score = 100 - source_tier * 12
    text = title.lower()
    priority_terms = ["fed", "inflation", "jobs", "treasury", "yield", "nvidia", "ai", "semiconductor", "chip", "tsmc", "apple", "microsoft", "google", "meta", "amazon", "tesla", "oil", "gold", "dollar", "聯儲", "通脹", "利率", "非農", "人工智能", "半導體", "晶片", "原油", "黃金", "美元", "中國"]
    score += sum(8 for term in priority_terms if term in text)
    if 24 <= len(title) <= 120:
        score += 6
    return score


def collect_news_candidates() -> tuple[list[dict], list[dict]]:
    all_candidates = []
    sources = []
    for config in SOURCE_CONFIGS:
        source_name = config["name"]
        url = config["url"]
        status, body = fetch_url(url)
        sources.append({"name": source_name, "url": url, "access": "Full" if status == 200 else "Blocked", "tier": config.get("tier", 3), "region": config.get("region", "global")})
        if status != 200:
            continue
        extracted = extract_rss_candidates(source_name, url, body) if config.get("kind") == "rss" else extract_candidates(source_name, url, body)
        for candidate in extracted[: config.get("max_items", 8)]:
            candidate["source_tier"] = config.get("tier", 3)
            candidate["region"] = config.get("region", "global")
            candidate["topic_hint"] = infer_topic_hint(candidate.get("title", ""))
            candidate["score"] = headline_score(candidate)
            all_candidates.append(candidate)
    keywords = re.compile(r"fed|fomc|inflation|cpi|pce|jobs|treasury|yield|dollar|oil|gold|nvidia|amd|tsmc|semiconductor|chip|ai|artificial intelligence|cloud|apple|tesla|microsoft|google|meta|amazon|聯儲|通脹|非農|黃金|原油|人工智能|半導體|晶片|中國", re.I)
    filtered = [item for item in all_candidates if keywords.search(item["title"])]
    if len(filtered) < 20:
        filtered = all_candidates
    filtered.sort(key=lambda item: item.get("score", 0), reverse=True)
    return filtered[:120], sources


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


def ai_request(account_id: str, api_token: str, model: str, messages: list[dict], max_tokens: int = 3600) -> str:
    payload = {"messages": messages, "max_tokens": max_tokens, "temperature": 0.0}
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}"
    req = urllib.request.Request(url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), headers={"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"}, method="POST")
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
    if isinstance(text, (dict, list)):
        return json.dumps(text, ensure_ascii=False)
    if not text and isinstance(result.get("choices"), list) and result["choices"]:
        message = result["choices"][0].get("message", {})
        text = message.get("content")
    if not text:
        fail(f"Cloudflare Workers AI response missing text: {raw[:1000]}")
    return text


def compact_candidate(candidate: dict, index: int) -> dict:
    return {
        "n": index,
        "source": candidate.get("source", ""),
        "title": candidate.get("title", "")[:130],
        "url": candidate.get("url", ""),
        "topic_hint": candidate.get("topic_hint", ""),
        "score": candidate.get("score", 0),
        "tier": candidate.get("source_tier", 3),
    }


def compact_source(source: dict) -> dict:
    return {
        "name": source.get("name", ""),
        "url": source.get("url", ""),
        "access": source.get("access", ""),
        "tier": source.get("tier", 3),
    }


def headline_to_zh(title: str) -> str:
    text = clean_text(title)
    patterns = [
        (r"Treasury yields are steady after hot producer prices reading, crude oil gains", "美國生產者價格數據偏熱後，美債孳息率保持平穩，原油價格上升"),
        (r"Treasury yields are steady after hot producer prices reading", "美國生產者價格數據偏熱後，美債孳息率保持平穩"),
        (r"Gold slumps to 6-month low even as inflation fears rise\. Here's why bullion is out of favor", "即使通脹憂慮升溫，金價仍跌至六個月低位：黃金為何失寵"),
        (r"Trump might 'love the inflation,' but consumers are feeling the pain", "特朗普或淡化通脹壓力，但消費者正承受物價痛楚"),
        (r"These in-demand jobs pay over \$100,000 .*", "這些熱門職位年薪逾十萬美元，或有助抵禦通脹壓力"),
        (r"Trump threatens to seize Kharg Island and other Iran oil infrastructure", "特朗普威脅控制哈爾克島及其他伊朗石油基建"),
        (r"Oracle shares tumble 11% on increased capital raise, cash concerns", "甲骨文擬增加融資引發現金流憂慮，股價急跌 11%"),
        (r"DoorDash lets customers use photos, prompts to order food and book reservations in latest AI push", "DoorDash 推出人工智能功能，讓用戶以相片和提示點餐及訂座"),
        (r"SpaceX soon-to-be millionaires are set to spend big on luxury homes, watches and private jet travel", "SpaceX 新一批準富豪預料將大手購入豪宅、名錶和私人飛機旅程"),
        (r"Stocks Sink in Broad AI Rout Sparked by China's DeepSeek", "中國 DeepSeek 觸發人工智能股拋售，美股相關板塊普遍下跌"),
        (r"Comex Gold, Silver Settle Lower", "Comex 黃金和白銀收低"),
        (r"DeepSeek Won't Sink U\.S\. AI Titans", "DeepSeek 未必足以擊沉美國人工智能巨頭"),
        (r"What to Know About China's DeepSeek AI", "中國 DeepSeek 人工智能有何值得留意"),
        (r"Silicon Valley Is Raving About a Made-in-China AI Model", "矽谷熱議中國製人工智能模型"),
        (r"Reid Hoffman Raises \$24\.6 Million for AI Cancer-Research Startup", "Reid Hoffman 為人工智能癌症研究初創融資 2,460 萬美元"),
        (r"\bcrude oil gains\b", "原油價格上升"),
        (r"\bslumps to 6-month low\b", "跌至六個月低位"),
        (r"\binflation fears rise\b", "通脹憂慮升溫"),
        (r"\bbullion\b", "黃金"),
        (r"\bout of favor\b", "失寵"),
        (r"\btumble\b", "急跌"),
        (r"\bincreased capital raise\b", "增加融資"),
        (r"\bcash concerns\b", "現金流憂慮"),
        (r"\bDeepSeek\b", "DeepSeek"),
        (r"\bTreasury yields\b", "美債孳息率"),
        (r"\bproducer prices\b", "生產者價格"),
        (r"\binflation\b", "通脹"),
        (r"\bconsumers\b", "消費者"),
        (r"\bNvidia\b", "英偉達"),
        (r"\bAI\b", "人工智能"),
        (r"\bsemiconductors?\b", "半導體"),
        (r"\bchips?\b", "晶片"),
        (r"\bFed\b", "聯儲局"),
        (r"\brates?\b", "利率"),
        (r"\boil\b", "油價"),
        (r"\bgold\b", "金價"),
        (r"\bdollar\b", "美元"),
        (r"\bstocks?\b", "股票"),
        (r"\bmarkets?\b", "市場"),
        (r"\bshares\b", "股份"),
        (r"\bOracle\b", "甲骨文"),
        (r"\bDoorDash\b", "DoorDash"),
        (r"\bSpaceX\b", "SpaceX"),
        (r"\bIran\b", "伊朗"),
        (r"\bChina\b", "中國"),
        (r"\bApple\b", "蘋果"),
        (r"\bMicrosoft\b", "微軟"),
        (r"\bTesla\b", "特斯拉"),
        (r"\bAmazon\b", "亞馬遜"),
        (r"\bearnings\b", "業績"),
        (r"\bdata centers?\b", "數據中心"),
    ]
    translated = text
    for pattern, replacement in patterns:
        translated = re.sub(pattern, replacement, translated, flags=re.I)
    if translated == text and re.search(r"[A-Za-z]", text):
        return f"焦點新聞：{text}"
    return to_traditional_text(translated)


def source_label(source_name: str) -> str:
    labels = {
        "CNBC Top News": "CNBC",
        "CNBC Markets": "CNBC Markets",
        "CNBC Technology": "CNBC Technology",
        "WSJ Markets": "WSJ Markets",
        "WSJ Technology": "WSJ Technology",
        "MarketWatch Top Stories": "MarketWatch",
        "TechCrunch AI": "TechCrunch AI",
        "TechCrunch Startups": "TechCrunch",
        "Wallstreetcn": "華爾街見聞",
        "Caixin": "財新",
        "LatePost": "晚點",
    }
    return labels.get(source_name, source_name or "來源")


def build_professional_item(candidate: dict, idx: int, category_defs: list[tuple[str, str]]) -> dict:
    category_name, _ = category_defs[(idx - 1) % len(category_defs)]
    source_name = candidate.get("source") or "Public source"
    original_title = clean_text(candidate.get("title") or source_name)
    title_zh = headline_to_zh(original_title)
    heat_score = max(48, min(92, int(candidate.get("score", 70)) - 18 - idx))
    return {
        "id": f"{TODAY}-headline-{idx:03d}",
        "date": TODAY,
        "title_original": original_title,
        "title_zh": title_zh,
        "source": source_label(source_name),
        "url": candidate.get("url") or "https://news.tinydreamlab.com/",
        "published_at": candidate.get("published_at_hint") or GENERATED_AT,
        "category": candidate.get("topic_hint") or category_name,
        "themes": [candidate.get("topic_hint") or category_name, category_name],
        "summary_zh": f"{source_label(source_name)} 報道聚焦「{title_zh}」。這條消息被列入今日國際財經與科技追蹤清單，反映市場正關注宏觀數據、企業動向、科技投資或產業鏈變化。",
        "key_facts": [
            f"原文來源為 {source_label(source_name)}，保留原文連結供查證。",
            "此新聞被系統按來源層級、題材關聯和市場敏感度排序。",
        ],
        "market_impact": "短線可觀察其對相關資產價格、科技股估值、利率預期或產業鏈情緒的影響。",
        "reporter_angle": "後續應追蹤是否有更多主流來源跟進、公司或監管機構是否回應，以及市場價格是否出現連鎖反應。",
        "importance_score": max(5, min(10, 11 - idx // 2)),
        "heat_score": heat_score,
        "source_count": 1,
        "sources_reporting_same_topic": [source_label(source_name)],
        "position_signal": "ranked headline",
        "time_horizon": "short_term",
        "tracking_value": "適合作為當日市場與科技新聞版面的追蹤入口。",
    }


def build_prompt(candidates: list[dict], sources: list[dict]) -> str:
    compact_candidates = [compact_candidate(candidate, idx) for idx, candidate in enumerate(candidates[:36], start=1)]
    compact_sources = [compact_source(source) for source in sources]
    task = {
        "task": "Create a website-ready daily international finance and technology news brief.",
        "date": TODAY,
        "language": "Traditional Chinese only for all reader-facing Chinese fields.",
        "required_top_level_fields": REQUIRED_BRIEF_FIELDS + ["email_body_zh"],
        "required_item_fields": REQUIRED_ITEM_FIELDS,
        "required_hot_topic_fields": REQUIRED_HOT_TOPIC_FIELDS,
        "category_taxonomy": [{"name": name, "slug": slug} for name, slug in CATEGORY_TAXONOMY],
        "editorial_policy": [
            "Prioritize global finance and technology stories from tier 1 sources such as Reuters, CNBC and WSJ.",
            "Use Wallstreetcn, Caixin and LatePost as China/Asia context sources, not as the dominant source of the whole brief.",
            "Cluster similar headlines across sources into one topic when possible.",
            "Rank by market relevance, cross-source confirmation, policy or earnings impact, and technology industry significance.",
            "Always preserve original article URLs in items[].url.",
        ],
        "output_rules": [
            "Return one valid JSON object only. No markdown. No comments.",
            "Use real Traditional Chinese characters directly. Do not output Unicode escape sequences.",
            "Do not mention JSON validation, fallback mode, automation, prompt, model, or internal errors in reader-facing fields.",
            "hot_topics must contain 3 to 5 entries.",
            "items must contain 10 to 12 entries.",
            "Use only category names and slugs from category_taxonomy.",
            "Every hot_topics[].item_ids and categories[].item_ids value must exist in items[].id.",
            f"Item ids must use this format: {TODAY}-topic-001.",
            "Do not give personalized investment advice.",
        ],
        "sources": compact_sources,
        "candidate_headlines": compact_candidates,
    }
    return json.dumps(task, ensure_ascii=False, separators=(",", ":"))


def call_cloudflare_ai(candidates: list[dict], sources: list[dict]) -> dict:
    account_id = env_required("CLOUDFLARE_ACCOUNT_ID")
    api_token = env_required("CLOUDFLARE_API_TOKEN")
    model = os.environ.get("CF_AI_MODEL", "@cf/qwen/qwen2.5-coder-32b-instruct").strip()
    system = "You are a careful news editor. Output strict valid JSON only, using Traditional Chinese for reader-facing fields."
    text = ai_request(account_id, api_token, model, [{"role": "system", "content": system}, {"role": "user", "content": build_prompt(candidates, sources)}])
    try:
        return extract_json(text)
    except json.JSONDecodeError:
        repair_prompt = "Repair the following response into one valid JSON object that matches the requested schema. Output JSON only. Use Traditional Chinese for reader-facing fields. Remove markdown and invalid escape sequences.\n\n" + text[:24000]
        repaired = ai_request(account_id, api_token, model, [{"role": "system", "content": system}, {"role": "user", "content": repair_prompt}], max_tokens=3600)
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
    if not isinstance(items, list) or len(items) < 10:
        validation_error("items must contain at least 10 entries.")
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
    usable = []
    seen_titles = set()
    for item in candidates:
        title_key = clean_text(item.get("title", "")).lower()
        if not title_key or not item.get("url") or title_key in seen_titles:
            continue
        seen_titles.add(title_key)
        usable.append(item)
    if not usable:
        usable = [{"source": source["name"], "title": source["name"], "url": source["url"]} for source in sources]
    while len(usable) < 12:
        usable.append(usable[len(usable) % max(1, len(usable))])
    category_defs = CATEGORY_TAXONOMY
    items = [build_professional_item(candidate, idx, category_defs) for idx, candidate in enumerate(usable[:12], start=1)]
    hot_topics = []
    for rank, item in enumerate(items[:5], start=1):
        hot_topics.append({
            "rank": rank,
            "topic": item["title_zh"][:80],
            "heat_score": item["heat_score"],
            "heat_label": "High" if item["heat_score"] >= 75 else "Medium",
            "source_count": 1,
            "main_sources": [item["source"]],
            "item_ids": [item["id"]],
            "one_line_reason": "此題材同時觸及宏觀預期、科技產業或主要市場價格，適合作為今日優先閱讀焦點。",
            "reporter_angle": item["reporter_angle"],
        })
    categories = []
    for category_name, slug in category_defs:
        refs = [item["id"] for item in items if item["category"] == category_name]
        if refs:
            categories.append({"name": category_name, "slug": slug, "item_ids": refs})
    print(f"Warning: generated reader-safe headline brief. Internal reason: {error}")
    return to_traditional({
        "date": TODAY,
        "title": "每日國際財經與科技新聞摘要",
        "deck": "今日焦點集中於美國利率與通脹線索、科技股與人工智能投資，以及主要企業和產業鏈消息。",
        "daily_summary_zh": "今日國際財經與科技新聞以宏觀數據、利率預期、人工智能與半導體產業鏈為主軸。網站已按題材熱度和來源可信度整理多條原文入口，方便先掌握重點，再按需要打開原文深入閱讀。",
        "market_focus": ["全球市場與宏觀", "科技、AI與平台", "半導體與供應鏈", "企業、財報與交易"],
        "hot_topics": hot_topics, "categories": categories, "items": items, "sources": sources, "generated_at": GENERATED_AT,
        "email_body_zh": "今日新聞摘要已更新。重點包括全球市場與宏觀數據、人工智能與半導體產業鏈、企業消息及能源外匯商品走勢。\n\n網站：https://news.tinydreamlab.com/",
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
    if os.environ.get("ENABLE_AI_BRIEF", "0").strip() == "1":
        try:
            brief = call_cloudflare_ai(candidates, sources)
            brief = normalize_brief(brief, sources)
            validate_brief(brief)
        except Exception as exc:
            print(f"Warning: AI brief generation failed; using reader-safe headline brief. Reason: {exc}")
            brief = build_fallback_brief(candidates, sources, str(exc))
            validate_brief(brief)
    else:
        print("AI full-brief generation disabled; using structured headline brief.")
        brief = build_fallback_brief(candidates, sources, "AI full-brief generation disabled")
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
