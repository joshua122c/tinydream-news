#!/usr/bin/env python3
import html
import json
import os
import re
import smtplib
import ssl
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path

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

SOURCE_CONFIGS = [
    {"name": "Reuters Markets", "url": "https://www.reuters.com/markets/", "kind": "page", "tier": 1, "max_items": 10},
    {"name": "Reuters Technology", "url": "https://www.reuters.com/technology/", "kind": "page", "tier": 1, "max_items": 8},
    {"name": "CNBC Top News", "url": "https://www.cnbc.com/id/100003114/device/rss/rss.html", "kind": "rss", "tier": 1, "max_items": 10},
    {"name": "CNBC Markets", "url": "https://www.cnbc.com/markets/", "kind": "page", "tier": 1, "max_items": 8},
    {"name": "CNBC Technology", "url": "https://www.cnbc.com/technology/", "kind": "page", "tier": 1, "max_items": 8},
    {"name": "WSJ Markets", "url": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml", "kind": "rss", "tier": 1, "max_items": 8},
    {"name": "WSJ Technology", "url": "https://feeds.a.dj.com/rss/RSSWSJD.xml", "kind": "rss", "tier": 1, "max_items": 6},
    {"name": "MarketWatch Top Stories", "url": "https://feeds.content.dowjones.io/public/rss/mw_topstories", "kind": "rss", "tier": 2, "max_items": 8},
    {"name": "TechCrunch AI", "url": "https://techcrunch.com/category/artificial-intelligence/", "kind": "page", "tier": 2, "max_items": 6},
    {"name": "TechCrunch Startups", "url": "https://techcrunch.com/category/startups/", "kind": "page", "tier": 2, "max_items": 5},
    {"name": "Wallstreetcn", "url": "https://wallstreetcn.com/", "kind": "page", "tier": 3, "max_items": 3},
    {"name": "Caixin", "url": "https://www.caixin.com/", "kind": "page", "tier": 3, "max_items": 3},
    {"name": "LatePost", "url": "https://www.latepost.com/", "kind": "page", "tier": 3, "max_items": 3},
]

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
REQUIRED_ITEM_FIELDS = ["id", "date", "title_original", "title_zh", "source", "url", "published_at", "category", "themes", "summary_zh", "key_facts", "market_impact", "reporter_angle", "importance_score", "heat_score", "source_count", "sources_reporting_same_topic", "position_signal", "time_horizon", "tracking_value"]

BAD_READER_PHRASES = [
    "這條消息被列入",
    "追蹤清單",
    "公開新聞標題",
    "保留可追蹤",
    "JSON",
    "fallback",
    "保底模式",
]


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


def clean_text(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value or "")
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


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
        if not title_match:
            continue
        title = clean_text(title_match.group(1))
        link = clean_text(link_match.group(1)) if link_match else url
        if not (12 <= len(title) <= 180):
            continue
        candidates.append({
            "source": source_name,
            "title": title,
            "url": absolute_url(url, link),
            "published_at_hint": clean_text(date_match.group(1)) if date_match else "",
        })
        if len(candidates) >= 30:
            break
    return candidates


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
    return labels.get(source_name, source_name or "主要來源")


def infer_category(title: str) -> str:
    text = title.lower()
    if re.search(r"nvidia|amd|tsmc|intel|broadcom|semiconductor|chip|chips|晶片|半導體", text):
        return "半導體與供應鏈"
    if re.search(r"\bai\b|artificial intelligence|openai|cloud|data center|datacenter|software|平台|人工智能|雲端", text):
        return "科技、AI與平台"
    if re.search(r"fed|fomc|inflation|cpi|pce|yield|treasury|jobs|rates|producer prices|recession|通脹|利率|美債|就業", text):
        return "全球市場與宏觀"
    if re.search(r"earnings|deal|merger|ipo|stock|shares|profit|revenue|buyback|財報|併購|上市|股份", text):
        return "企業、財報與交易"
    if re.search(r"oil|gas|gold|silver|dollar|yen|euro|commodity|crude|能源|黃金|美元|外匯|商品", text):
        return "能源、外匯與商品"
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
        ("iran-oil", r"iran|kharg|oil|crude"),
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


def collect_news_candidates() -> tuple[list[dict], list[dict]]:
    all_candidates = []
    sources = []
    for config in SOURCE_CONFIGS:
        status, body = fetch_url(config["url"])
        sources.append({
            "name": config["name"],
            "url": config["url"],
            "access": "Full" if status == 200 else "Blocked",
            "tier": config.get("tier", 3),
        })
        if status != 200:
            continue
        extracted = extract_rss_candidates(config["name"], config["url"], body) if config["kind"] == "rss" else extract_page_candidates(config["name"], config["url"], body)
        for candidate in extracted[: config.get("max_items", 8)]:
            candidate["source_tier"] = config.get("tier", 3)
            candidate["category"] = infer_category(candidate.get("title", ""))
            candidate["score"] = headline_score(candidate)
            all_candidates.append(candidate)

    keywords = re.compile(r"fed|inflation|treasury|yield|dollar|oil|gold|nvidia|amd|tsmc|semiconductor|chip|ai|artificial intelligence|cloud|apple|tesla|microsoft|google|meta|amazon|ipo|earnings|通脹|利率|半導體|人工智能|黃金|美元", re.I)
    filtered = [item for item in all_candidates if keywords.search(item["title"])]
    if len(filtered) < 24:
        filtered = all_candidates
    filtered.sort(key=lambda item: item.get("score", 0), reverse=True)

    deduped = []
    seen_titles = set()
    cluster_counts = {}
    category_counts = {}
    for item in filtered:
        key = re.sub(r"[^a-z0-9\u3400-\u9fff]+", "", item["title"].lower())[:90]
        if not key or key in seen_titles:
            continue
        cluster = cluster_key(item["title"])
        category = item.get("category") or "全球市場與宏觀"
        if cluster_counts.get(cluster, 0) >= 2:
            continue
        if category_counts.get(category, 0) >= 5:
            continue
        seen_titles.add(key)
        cluster_counts[cluster] = cluster_counts.get(cluster, 0) + 1
        category_counts[category] = category_counts.get(category, 0) + 1
        deduped.append(item)
        if len(deduped) >= 48:
            break
    return deduped, sources


def keyword_headline(title: str, category: str) -> str:
    text = f"{title} {category}".lower()
    company_match = re.search(r"\b(Nvidia|Apple|Microsoft|Google|Alphabet|Amazon|Meta|Tesla|Oracle|SpaceX|OpenAI|AMD|TSMC|Intel|Broadcom)\b", title, re.I)
    company = company_match.group(1) if company_match else ""
    if re.search(r"gold|silver|bullion", text):
        return "金價受壓，避險與通脹交易出現重新定價"
    if re.search(r"treasury|yield|fed|rates|inflation|cpi|producer prices|jobs", text):
        return "利率與通脹預期牽動美債和股市走向"
    if re.search(r"oil|crude|gas|commodity|dollar|yen|euro", text):
        return "能源、外匯與商品價格成為市場焦點"
    if re.search(r"ai|artificial intelligence|chip|semiconductor|data center|cloud", text):
        prefix = f"{company} 帶動" if company else "AI 與半導體"
        return f"{prefix}投資熱潮延續，估值與供應鏈受關注"
    if re.search(r"earnings|shares|stock|ipo|deal|merger|revenue|profit", text):
        prefix = f"{company} 消息" if company else "企業消息"
        return f"{prefix}牽動投資者對盈利與估值的判斷"
    if re.search(r"china|asia|japan|hong kong|taiwan", text):
        return "中國及亞洲市場消息影響區內風險情緒"
    return "重要財經與科技消息值得今日追蹤"


def headline_to_zh(title: str, category: str) -> str:
    title = clean_text(title)
    if has_cjk(title) and not looks_mostly_english(title):
        return title

    patterns = [
        (r"SpaceX raising \$75 billion.*IPO.*Nasdaq.*", "SpaceX 擬透過破紀錄 IPO 集資 750 億美元，市場等待 Nasdaq 首日表現"),
        (r"SpaceX cuts retail IPO allocation.*", "SpaceX 調低散戶 IPO 配售比例，上市分配安排受關注"),
        (r"Warren questions SpaceX IPO oversight.*", "美國議員質疑 SpaceX IPO 監管安排，交易所審查受關注"),
        (r"SpaceX IPO won.*bull market.*", "SpaceX IPO 未必終結牛市，但投資者憂慮上市後估值壓力"),
        (r"SpaceX soon-to-be millionaires.*", "SpaceX 上市或製造新一批富豪，財富效應帶動高端消費想像"),
        (r"Jim Cramer warns SpaceX.*", "市場名嘴警告 SpaceX 上市後估值可能升至難以持續水平"),
        (r"Trump claims Iran war settled.*", "特朗普稱伊朗衝突接近落實協議，市場觀察地緣風險降溫"),
        (r"Trump picks former SEC Chairman.*", "特朗普提名前 SEC 主席出任國家情報總監，監管與政策人事受關注"),
        (r"What energy insiders.*oil prices.*Iran deal.*", "華府能源人士評估油價與伊朗協議前景"),
        (r"Analysis: Trump said he loves inflation.*", "特朗普通脹言論引發對 Fed 主席人選和政策路徑的討論"),
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
    if re.search(r"nvidia|ai|artificial intelligence|cloud|data center", text):
        themes.append("AI投資熱潮")
    if re.search(r"semiconductor|chip|tsmc|amd|intel", text):
        themes.append("半導體供應鏈")
    if re.search(r"gold|oil|dollar|yen|commodity", text):
        themes.append("商品與外匯")
    if re.search(r"earnings|shares|stock|ipo|deal", text):
        themes.append("企業與資本市場")
    return list(dict.fromkeys(themes))[:4]


def editorial_summary(title_zh: str, original_title: str, category: str, source: str) -> str:
    text = f"{title_zh} {original_title} {category}".lower()
    if category == "全球市場與宏觀":
        return "這則消息反映宏觀數據、利率預期和資金流向仍是今日市場主線。投資者需要留意美債收益率、美元和股市估值如何回應，因為同一組數據可能同時改變風險胃納和科技股定價。"
    if category == "科技、AI與平台":
        return "科技板塊的焦點仍集中在 AI 應用、雲端平台和算力投入。相關消息不只影響單一公司股價，也會牽動投資者對軟件、基建和資料中心需求的中期判斷。"
    if category == "半導體與供應鏈":
        return "半導體消息繼續是 AI 產業鏈的關鍵觀察點。晶片需求、供應鏈交付和資本開支預期，會直接影響市場對硬件公司和上游供應商的估值。"
    if category == "企業、財報與交易":
        return "企業消息反映投資者正在重新衡量盈利能見度、現金流和估值水平。若事件涉及融資、併購或上市預期，後續仍要觀察市場是否把個別消息擴散到同業板塊。"
    if category == "能源、外匯與商品":
        if re.search(r"gold|黃金|金價", text):
            return "金價走勢顯示避險需求與實質利率之間出現拉扯。即使通脹憂慮存在，若美元或債息偏強，黃金仍可能面對資金流出和短線拋壓。"
        if re.search(r"oil|crude|原油|能源", text):
            return "能源價格變化會影響通脹預期、企業成本和地緣風險定價。市場接下來會關注供應消息是否轉化為更廣泛的商品價格壓力。"
        return "商品和外匯市場正在重新反映通脹、利率和避險需求。這類價格變化往往會快速傳導到股市板塊輪動和企業成本預期。"
    if category == "中國與亞洲觀察":
        return "亞洲市場消息反映區內政策、需求和供應鏈仍有變化。這類新聞需要與全球資金流和科技產業鏈一併觀察，才能判斷影響是否只限本地市場。"
    return "這則新聞涉及今日國際財經與科技市場的重要變化。投資者可先掌握事件方向，再透過原文連結核對細節和後續發展。"


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
    title_zh = headline_to_zh(original_title, category)
    source = source_label(candidate.get("source", ""))
    heat_score = max(52, min(94, int(candidate.get("score", 70)) - idx))
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
        "summary_zh": editorial_summary(title_zh, original_title, category, source),
        "key_facts": [
            f"原文來源：{source}",
            f"題材分類：{category}",
            "網站保留原文連結，方便進一步核對細節。",
        ],
        "market_impact": market_impact(category),
        "reporter_angle": tracking_value(category),
        "importance_score": max(5, min(10, 11 - idx // 2)),
        "heat_score": heat_score,
        "source_count": 1,
        "sources_reporting_same_topic": [source],
        "position_signal": "ranked headline",
        "time_horizon": "short_term",
        "tracking_value": tracking_value(category),
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


def build_brief(candidates: list[dict], sources: list[dict]) -> dict:
    usable = candidates[:12]
    if not usable:
        usable = [{"source": source["name"], "title": source["name"], "url": source["url"], "category": "全球市場與宏觀", "score": 60} for source in sources]
    while len(usable) < 12:
        usable.append(usable[len(usable) % max(1, len(usable))])

    items = [build_item(candidate, idx) for idx, candidate in enumerate(usable[:12], start=1)]
    categories = []
    for name, slug in CATEGORY_TAXONOMY:
        refs = [item["id"] for item in items if item["category"] == name]
        if refs:
            categories.append({"name": name, "slug": slug, "item_ids": refs})

    hot_topics = []
    for rank, item in enumerate(items[:5], start=1):
        hot_topics.append({
            "rank": rank,
            "topic": item["title_zh"],
            "heat_score": item["heat_score"],
            "heat_label": "High" if item["heat_score"] >= 75 else "Medium",
            "source_count": item["source_count"],
            "main_sources": [item["source"]],
            "item_ids": [item["id"]],
            "one_line_reason": hot_topic_reason(item),
            "reporter_angle": item["reporter_angle"],
        })

    top_categories = list(dict.fromkeys(item["category"] for item in items[:8]))[:4]
    daily_summary = "今日國際財經與科技新聞以" + "、".join(top_categories) + "為主線。市場焦點集中於利率與通脹預期、AI 和半導體投資熱度、主要企業消息，以及能源與外匯價格變化。讀者可先掌握焦點主題，再按分類打開原文深入閱讀。"

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
    if not isinstance(items, list) or len(items) < 10:
        fail("items must contain at least 10 entries.")
    item_ids = set()
    for item in items:
        for field in REQUIRED_ITEM_FIELDS:
            if field not in item:
                fail(f"Item missing required field {field}: {item.get('id')}")
        if item["id"] in item_ids:
            fail(f"Duplicate item id: {item['id']}")
        item_ids.add(item["id"])
        if not has_cjk(item["title_zh"]) or looks_mostly_english(item["title_zh"]):
            fail(f"title_zh is not acceptable Traditional Chinese: {item['title_zh']}")
        if any(phrase in item["summary_zh"] for phrase in BAD_READER_PHRASES):
            fail(f"summary_zh contains bad phrase: {item['id']}")

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
