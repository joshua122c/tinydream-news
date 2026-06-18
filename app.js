const app = document.querySelector("#app");

const state = {
  index: null,
  brief: null,
  briefs: new Map(),
  categorySlug: "all",
  query: "",
  globalQuery: "",
};

const UI = {
  latestBrief: "最新每日摘要",
  readFullBrief: "閱讀完整摘要",
  hotTopics: "焦點主題",
  newsItems: "新聞項目",
  categories: "分類",
  sources: "來源",
  dailyOverview: "今日總覽",
  focusRanking: "今日焦點",
  relatedNews: "相關新聞",
  categoryNews: "分類新聞",
  originalSources: "原文來源",
  hotTags: "熱門標籤",
  formalTags: "正式標籤",
  marketImpact: "市場影響",
  trackingValue: "追蹤價值",
  readSource: "閱讀原文",
  search: "搜尋",
  clear: "清除",
  all: "全部",
  archive: "Archive",
  viewDailyBrief: "查看當日摘要",
  topics: "Topics",
};

const escapeHtml = (value = "") =>
  String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

const headlineHtml = (value = "") =>
  escapeHtml(value).replace(/([\u3400-\u9fff])/g, "$1<wbr>");

const asList = (value) => (Array.isArray(value) ? value : []);
const linkFor = (path) => path;
const dataPath = (path) => {
  const separator = path.includes("?") ? "&" : "?";
  return `/${path}${separator}v=${Date.now()}`;
};

function hasCjk(value = "") {
  return /[\u3400-\u9fff]/.test(String(value));
}

function looksMostlyEnglish(value = "") {
  const text = String(value || "");
  const letters = (text.match(/[A-Za-z]/g) || []).length;
  const cjk = (text.match(/[\u3400-\u9fff]/g) || []).length;
  return letters > 12 && letters > cjk * 1.3;
}

function keywordHeadline(title = "", category = "") {
  const text = `${title} ${category}`.toLowerCase();
  const company = title.match(/\b(Nvidia|Apple|Microsoft|Google|Alphabet|Amazon|Meta|Tesla|Oracle|SpaceX|OpenAI|AMD|TSMC|Intel|Broadcom)\b/i)?.[1];
  if (/gold|silver|bullion/.test(text)) return "金價受壓，避險與通脹交易出現重新定價";
  if (/treasury|yield|fed|rates|inflation|cpi|producer prices|jobs/.test(text)) return "利率與通脹預期牽動美債和股市走向";
  if (/oil|crude|gas|commodity|dollar|yen|euro/.test(text)) return "能源、外匯與商品價格成為市場焦點";
  if (/\bai\b|artificial intelligence|chip|semiconductor|data center|cloud/.test(text)) return `${company ? `${company} 帶動` : "AI 與半導體"}投資熱潮延續，估值與供應鏈受關注`;
  if (/earnings|shares|stock|ipo|deal|merger|revenue|profit/.test(text)) return `${company ? `${company} 消息` : "企業消息"}牽動投資者對盈利與估值的判斷`;
  if (/china|asia|japan|hong kong/.test(text)) return "中國及亞洲市場消息影響區內風險情緒";
  return "重要財經與科技消息值得今日追蹤";
}

function displayTitle(item) {
  const zh = item?.title_zh || "";
  if (hasCjk(zh) && !looksMostlyEnglish(zh)) return zh;
  return keywordHeadline(item?.title_original || zh, item?.category || "");
}

const TITLE_LIMITS = {
  lead: 58,
  card: 38,
  desk: 34,
  list: 28,
  brief: 44,
  morning: 20,
  editorialLead: 28,
  editorialCard: 34,
  default: 52,
};

function shortenHeadline(value = "", variant = "default") {
  const max = TITLE_LIMITS[variant] || TITLE_LIMITS.default;
  const text = String(value || "").trim();
  if (text.length <= max) return text;
  const clauses = text.split(/[，；：:。]/).map((part) => part.trim()).filter(Boolean);
  const firstClause = clauses[0] || "";
  if (firstClause.length >= 12 && firstClause.length <= max) return firstClause;
  return `${text.slice(0, Math.max(12, max - 1)).trim()}…`;
}

function storyTitle(item, variant = "default") {
  return shortenHeadline(displayTitle(item), variant);
}

function cleanEditorialHeadline(value = "") {
  return String(value || "")
    .replace(/[!！]+/g, "")
    .replace(/接下來[^。；;，,]*?(關注|留意)[^。；;，,]*/g, "")
    .replace(/這幾件事[^。；;，,]*/g, "")
    .replace(/值得高度關注/g, "受關注")
    .replace(/\s+/g, " ")
    .replace(/\s*([，。；：])\s*/g, "$1")
    .trim();
}

function splitEditorialClauses(value = "") {
  return cleanEditorialHeadline(value)
    .split(/[，,；;：:。]/)
    .map((part) => part.trim())
    .filter((part) => part.length >= 3);
}

function compactEditorialText(value = "", variant = "editorialCard") {
  const max = TITLE_LIMITS[variant] || TITLE_LIMITS.editorialCard;
  const text = cleanEditorialHeadline(value);
  if (Array.from(text).length <= max) return text;
  const clauses = splitEditorialClauses(text);
  const useful = clauses.find((part) => Array.from(part).length >= 8 && Array.from(part).length <= max);
  if (useful) return useful;
  return `${Array.from(text).slice(0, Math.max(10, max - 1)).join("").trim()}…`;
}

function editorialHeadlineParts(item, variant = "card") {
  const raw = cleanEditorialHeadline(displayTitle(item));
  const maxVariant = variant === "lead" ? "editorialLead" : "editorialCard";
  const company = raw.match(/\b(Nvidia|Apple|Microsoft|Google|Alphabet|Amazon|Meta|Tesla|Oracle|SpaceX|OpenAI|AMD|TSMC|Intel|Broadcom|DeepSeek)\b/i)?.[1];
  const clauses = splitEditorialClauses(raw);
  const valuation = clauses.find((part) => /估值|市值|valuation/i.test(part));
  const listing = /上市|IPO|掛牌/i.test(raw);
  let headline = "";

  if (company && valuation) {
    headline = listing ? `${company} 上市後${valuation.replace(new RegExp(company, "i"), "").trim()}` : `${company} ${valuation}`;
  } else if (company && clauses.length > 1) {
    headline = `${company} ${clauses.find((part) => !new RegExp(company, "i").test(part)) || clauses[0]}`;
  } else {
    headline = clauses.find((part) => Array.from(part).length >= 8) || raw;
  }

  headline = compactEditorialText(headline, maxVariant);
  const summaryFirst = displaySummary(item).split(/[。；;]/).map((part) => part.trim()).find((part) => part && !headline.includes(part.slice(0, 8)));
  const dekSource = clauses.filter((part) => !headline.includes(part.slice(0, 6))).slice(0, 2).join("，") || summaryFirst || editorialTakeaway(item) || "";
  return {
    headline,
    dek: compactEditorialText(dekSource, variant === "lead" ? "brief" : "card"),
  };
}

function isWeakSummary(value = "") {
  const text = String(value || "");
  return (
    !text.trim() ||
    text.includes("這條消息被列入") ||
    text.includes("追蹤清單") ||
    text.includes("公開新聞標題") ||
    text.includes("保留可追蹤") ||
    text.includes("根據來源和題材熱度")
  );
}

function displaySummary(item) {
  if (!isWeakSummary(item?.summary_zh)) return item.summary_zh;
  if (!isWeakSummary(item?.summary)) return item.summary;
  return "";
}

function editorialTakeaway(item) {
  const candidates = [item?.editorial_takeaway, item?.reporter_angle, item?.market_impact, item?.tracking_value]
    .map((value) => String(value || "").trim())
    .filter(Boolean);
  return candidates.find((value) => value.length >= 12 && !isWeakSummary(value)) || "";
}

function editorialNoteBlock(item) {
  const note = editorialTakeaway(item);
  return note ? `<p class="story-takeaway"><span>Why it matters</span>${escapeHtml(note)}</p>` : "";
}

function summaryBlock(item, options = {}) {
  const summary = displaySummary(item);
  if (summary) {
    return `<p class="story-summary">${escapeHtml(summary)}</p>${options.takeaway ? editorialNoteBlock(item) : ""}`;
  }
  return options.showMissing ? `<p class="story-summary missing">未取得足夠可核實來源文字，暫不撰寫摘要。</p>` : "";
}

function detailBoxes(item) {
  const impact = item?.market_impact || "";
  const tracking = item?.tracking_value || "";
  if (!impact && !tracking) return "";
  return `<div class="two-col">${impact ? `<div class="detail-box"><strong>${UI.marketImpact}</strong>${escapeHtml(impact)}</div>` : ""}${tracking ? `<div class="detail-box"><strong>${UI.trackingValue}</strong>${escapeHtml(tracking)}</div>` : ""}</div>`;
}

function sourceSignal(item) {
  const count = Number(item?.source_count || 1);
  const sources = asList(item?.sources_reporting_same_topic);
  if (count <= 1) return `<span>${escapeHtml(item?.source || "主要來源")}</span>`;
  const label = `${count} 個來源`;
  const detail = sources.slice(0, 3).join("、");
  return `<span class="source-signal" title="${escapeHtml(detail)}">${escapeHtml(label)}</span>`;
}

function heatLabel(score = 0, explicit) {
  if (explicit) return explicit;
  if (score >= 75) return "High";
  if (score >= 50) return "Medium";
  return "Low";
}

function heatClass(label = "") {
  const normalized = String(label).toLowerCase();
  if (normalized.includes("high")) return "high";
  if (normalized.includes("medium")) return "medium";
  return "low";
}

async function readJson(path) {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) throw new Error(`${path} returned ${response.status}`);
  return response.json();
}

async function boot() {
  try {
    state.index = await readJson(dataPath("data/index.json"));
    const latestDate = state.index.latest_date || state.index.briefs?.[0]?.date;
    const latestFile = state.index.latest_file || `data/briefs/${latestDate}.json`;
    state.brief = await readJson(dataPath(latestFile));
    cacheBrief(state.brief);
    bindNavigation();
    render();
  } catch (error) {
    app.innerHTML = `<section class="error"><p class="eyebrow">資料載入失敗</p><h1>未能讀取新聞摘要</h1><p>${escapeHtml(error.message)}</p></section>`;
  }
}

function bindNavigation() {
  document.body.addEventListener("click", (event) => {
    const link = event.target.closest("[data-link]");
    if (!link) return;
    const url = new URL(link.href);
    if (url.origin !== location.origin) return;
    event.preventDefault();
    const target = url.hash ? url.hash.slice(1) : url.pathname;
    history.pushState({}, "", target);
    render();
  });

  window.addEventListener("popstate", render);

  const form = document.querySelector("#global-search-form");
  const input = document.querySelector("#global-search-input");
  if (input) input.placeholder = "搜尋 Nvidia、Fed、AI、半導體...";
  form?.addEventListener("submit", (event) => {
    event.preventDefault();
    navigateToSearch(input.value.trim());
  });
  input?.addEventListener("input", () => {
    state.globalQuery = input.value.trim();
  });
}

function route() {
  const [path] = `${location.pathname}${location.search}`.split("?");
  const parts = path.split("/").filter(Boolean);
  if (parts[0] === "archive") return { name: "archive" };
  if (parts[0] === "search") return { name: "search", query: getSearchQuery() };
  if (parts[0] === "topics" && parts[1]) return { name: "topic", slug: parts[1] };
  if (parts[0] === "topics") return { name: "topics" };
  if (parts[0] === "briefs" && parts[1]) return { name: "brief", date: parts[1] };
  return { name: "home" };
}

function getSearchQuery() {
  return new URLSearchParams(location.search).get("q") || "";
}

function navigateToSearch(query) {
  history.pushState({}, "", `/search?q=${encodeURIComponent(query || "")}`);
  render();
}

function cacheBrief(brief) {
  if (!brief) return;
  state.briefs.set(brief.date, brief);
  if (brief.update_id) state.briefs.set(brief.update_id, brief);
}

async function ensureArchiveBriefs() {
  const jobs = asList(state.index.briefs).map(async (day) => {
    const id = day.update_id || day.date;
    if (state.briefs.has(id) || state.briefs.has(day.date)) return;
    const file = day.latest_file || day.file || `data/briefs/${day.date}.json`;
    try {
      const brief = await readJson(dataPath(file));
      cacheBrief(brief);
    } catch (error) {
      console.warn("Archive brief load failed", file, error);
    }
  });
  await Promise.all(jobs);
}

function briefMetaFor(id) {
  for (const day of asList(state.index.briefs)) {
    if (day.date === id) return { file: day.latest_file || `data/briefs/${day.date}.json` };
    const update = asList(day.updates).find((entry) => entry.update_id === id);
    if (update) return { file: update.file };
  }
  return null;
}

async function loadBrief(id) {
  if (state.briefs.has(id)) return state.briefs.get(id);
  const meta = briefMetaFor(id);
  if (!meta?.file) return null;
  const brief = await readJson(dataPath(meta.file));
  cacheBrief(brief);
  return brief;
}

async function render() {
  const current = route();
  state.categorySlug = "all";
  state.query = "";
  if (current.name === "archive") return renderArchive();
  if (current.name === "search") return renderSearch(current.query);
  if (current.name === "topics") return renderTopics();
  if (current.name === "topic") return renderTopic(current.slug);
  return renderBrief(current.name === "brief" ? current.date : state.brief.update_id || state.brief.date, current.name === "home");
}

async function renderBrief(id, isHome = false) {
  const brief = await loadBrief(id);
  if (!brief) {
    app.innerHTML = `<section class="error"><p class="eyebrow">找不到摘要</p><h1>${escapeHtml(id)}</h1><p>Archive 內暫時未找到這個版本。</p></section>`;
    return;
  }
  state.brief = brief;
  app.innerHTML = isHome
    ? homePage(brief)
    : `${hero(brief, false)}${latestTicker(brief)}<div class="edition-layout"><main>${summarySection(brief)}${frontPageSection(brief)}${topicSections(brief)}${categoriesSection(brief)}${sourcesSection(brief)}</main>${tagsSidebar(brief)}</div>`;
  if (document.querySelector("#category-panel")) bindCategoryControls(brief);
  if (document.querySelector("[data-workspace]")) bindWorkspaceControls(brief);
  bindItemJumpControls();
}

function formatTime(value) {
  if (!value) return "";
  return new Date(value).toLocaleString("zh-HK", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function sortedNewsItems(brief) {
  return asList(brief.items).slice().sort((a, b) => (b.heat_score || 0) - (a.heat_score || 0));
}

function storyTime(item, brief) {
  const date = new Date(item?.published_at || brief?.generated_at || "");
  if (!Number.isNaN(date.getTime())) return formatTime(date.toISOString());
  return brief?.date || "今日";
}

function primaryTopic(item) {
  return asList(item?.themes)[0] || item?.category || "News";
}

function storyMeta(item, brief) {
  return `<div class="story-meta"><span>${escapeHtml(item.source || "Source")}</span><span>${escapeHtml(storyTime(item, brief))}</span><span>${escapeHtml(primaryTopic(item))}</span></div>`;
}

function storyTopicKey(item) {
  const explicit = item?.topic_key || asList(item?.themes)[0] || item?.category || "";
  const title = displayTitle(item).toLowerCase().replace(/[^\w\u3400-\u9fff]+/g, "").slice(0, 18);
  return `${explicit}-${title}`.toLowerCase();
}

function editorialHomeLayout(brief) {
  const sorted = sortedNewsItems(brief);
  const usedIds = new Set();
  const usedTopics = new Set();
  const markUsed = (item) => {
    if (!item) return;
    usedIds.add(item.id);
    usedTopics.add(storyTopicKey(item));
  };
  const lead = sorted.find((item) => displaySummary(item)) || sorted[0];
  markUsed(lead);

  const take = (predicate, limit, options = {}) => {
    const chosen = [];
    for (const item of sorted) {
      if (!item || usedIds.has(item.id) || !predicate(item)) continue;
      const topic = storyTopicKey(item);
      if (options.uniqueTopic && usedTopics.has(topic)) continue;
      chosen.push(item);
      markUsed(item);
      if (chosen.length >= limit) break;
    }
    return chosen;
  };

  const markets = take((item) => matchesDesk(item, MARKET_PATTERNS), 3, { uniqueTopic: true });
  const technology = take((item) => matchesDesk(item, TECHNOLOGY_PATTERNS), 3, { uniqueTopic: true });
  const topStories = take(() => true, 4, { uniqueTopic: true });
  const latest = sorted
    .filter((item) => item?.id && !usedIds.has(item.id))
    .sort((a, b) => new Date(b.published_at || brief.generated_at || 0) - new Date(a.published_at || brief.generated_at || 0))
    .slice(0, 6);

  return { lead, topStories, markets, technology, latest };
}

function morningBullets(brief, layout = editorialHomeLayout(brief)) {
  const summary = String(brief.daily_summary_zh || brief.deck || "").trim();
  const sentences = summary
    .split(/(?<=[。！？；;])\s*/)
    .map((item) => item.trim())
    .filter((item) => item.length >= 14)
    .slice(0, 2);
  const storyBullets = [layout.lead, ...layout.topStories, ...layout.markets, ...layout.technology]
    .filter(Boolean)
    .map((item) => displaySummary(item) || editorialTakeaway(item) || storyTitle(item, "brief"))
    .filter(Boolean);
  return [...sentences, ...storyBullets].slice(0, 5);
}

function homePage(brief) {
  const layout = editorialHomeLayout(brief);
  return `<section class="home-front">
    ${homeLeadSection(brief, layout.lead)}
    ${morningBriefSection(brief, layout)}
    <div class="home-layout">
      <main class="home-main">
        ${topNewsThemesSection(brief)}
        ${deskSection(brief, "Markets", "市場焦點", layout.markets, "利率、能源、外匯、商品與宏觀風險。")}
        ${deskSection(brief, "Technology & AI", "科技與 AI", layout.technology, "AI 平台、半導體、科技企業與資本開支。")}
        ${archiveSearchAccess(brief)}
      </main>
      <aside class="home-sidebar">
        ${latestUpdatesSection(brief, layout.latest)}
        ${sourceTransparencyBlock(brief)}
      </aside>
    </div>
  </section>`;
}

function homeLeadSection(brief, lead) {
  if (!lead) return "";
  const updateTime = brief.generated_at ? `${formatTime(brief.generated_at)} HKT` : brief.date;
  return `<section class="today-lead" id="item-${escapeHtml(lead.id)}">
    <div class="lead-label">
      <p class="section-kicker">Today's Lead / 今日焦點</p>
      <span>${escapeHtml(updateTime)}</span>
    </div>
    <div class="today-lead-grid">
      <article class="lead-copy">
        ${storyMeta(lead, brief)}
        <h1>${headlineHtml(storyTitle(lead, "lead"))}</h1>
        ${summaryBlock(lead, { takeaway: true, showMissing: true })}
        <div class="lead-actions">
          <a class="action primary-action" href="${escapeHtml(lead.url)}" target="_blank" rel="noreferrer">${UI.readSource}</a>
          <a class="action" href="${linkFor(`/briefs/${brief.update_id || brief.date}`)}" data-link>${UI.readFullBrief}</a>
        </div>
      </article>
      <aside class="edition-stats" aria-label="今日資料透明度">
        <div><b>${asList(brief.hot_topics).length}</b><span>焦點主題</span></div>
        <div><b>${asList(brief.items).length}</b><span>新聞項目</span></div>
        <div><b>${asList(brief.sources).length}</b><span>來源</span></div>
      </aside>
    </div>
  </section>`;
}

function morningBriefSection(brief, layout) {
  return `<section class="morning-brief-section">
    <div>
      <p class="section-kicker">Morning Brief / 今日摘要</p>
      <h2>開市前需要知道的幾件事</h2>
    </div>
    <ul>${morningBullets(brief, layout).map((item) => `<li>${escapeHtml(shortenHeadline(item, "brief"))}</li>`).join("")}</ul>
  </section>`;
}

function topStoriesSection(brief, items) {
  return `<section class="home-section top-stories">
    <div class="home-section-head">
      <p class="section-kicker">Top Stories</p>
      <h2>今日重要新聞</h2>
    </div>
    <div class="top-story-grid">${items.map((item, index) => renderTopStoryCard(item, brief, index)).join("")}</div>
  </section>`;
}

function itemByIdMap(brief) {
  return new Map(asList(brief.items).map((item) => [item.id, item]));
}

function topNewsThemesSection(brief) {
  const topics = asList(brief.hot_topics).slice(0, 6);
  if (!topics.length) return "";
  const byId = itemByIdMap(brief);
  return `<section class="home-section topic-themes">
    <div class="home-section-head">
      <p class="section-kicker">Top News Themes</p>
      <h2>今日新聞熱點</h2>
      <p>先看市場集中討論的題材，再按相關原文深入核對。</p>
    </div>
    <div class="theme-list">${topics.map((topic) => renderThemeCard(topic, byId, brief)).join("")}</div>
  </section>`;
}

function renderThemeCard(topic, byId, brief) {
  const related = asList(topic.item_ids).map((id) => byId.get(id)).filter(Boolean);
  const primary = related[0];
  const summary = primary ? displaySummary(primary) : "";
  const sources = asList(topic.main_sources).slice(0, 4).join("、");
  return `<article class="theme-card">
    <div class="theme-rank">#${escapeHtml(topic.rank || "")}</div>
    <div class="theme-body">
      <div class="story-meta"><span>${escapeHtml(sources || "主要來源")}</span><span>${escapeHtml(topic.related_story_count || related.length || 1)} 條相關新聞</span><span>熱度 ${escapeHtml(topic.heat_score || 0)}</span></div>
      <h3>${headlineHtml(shortenHeadline(topic.topic || primary?.title_zh || "", "lead"))}</h3>
      ${summary ? `<p class="story-summary">${escapeHtml(summary)}</p>` : ""}
      <p class="story-takeaway"><span>Why it matters</span>${escapeHtml(topic.one_line_reason || editorialTakeaway(primary) || "")}</p>
      <div class="theme-related">
        ${related.slice(0, 4).map((item) => `<a href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer"><strong>${headlineHtml(storyTitle(item, "list"))}</strong><em>${escapeHtml(item.source || "")} · ${escapeHtml(storyTime(item, brief))}</em></a>`).join("")}
      </div>
    </div>
  </article>`;
}

function renderTopStoryCard(item, brief, index) {
  return `<article class="top-story-card" id="item-${escapeHtml(item.id)}">
    <span class="story-rank">${String(index + 1).padStart(2, "0")}</span>
    ${storyMeta(item, brief)}
    <h3>${headlineHtml(storyTitle(item, "card"))}</h3>
    ${summaryBlock(item, { takeaway: true, showMissing: true })}
    <a class="story-link-inline" href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer">${UI.readSource}</a>
  </article>`;
}

function latestUpdatesSection(brief, items) {
  return `<section class="latest-updates">
    <div class="rail-head"><span>Latest Updates</span><strong>${items.length} 條</strong></div>
    ${items.length ? items.map((item, index) => `<a class="latest-update" href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer">
      <span>${String(index + 1).padStart(2, "0")}</span>
      <strong>${headlineHtml(storyTitle(item, "list"))}</strong>
      <em>${escapeHtml(item.source || "")} · ${escapeHtml(storyTime(item, brief))}</em>
    </a>`).join("") : `<p class="rail-empty">其餘新聞已分配到主要版位。</p>`}
  </section>`;
}

const MARKET_PATTERNS = ["market", "markets", "能源", "外匯", "商品", "宏觀", "fed", "oil", "gold", "inflation", "rates", "債", "美元"];
const TECHNOLOGY_PATTERNS = ["technology", "科技", "ai", "半導體", "平台", "nvidia", "spacex", "deepseek", "chip", "semiconductor"];

function matchesDesk(item, patterns) {
  const haystack = [item.category, item.title_original, item.title_zh, ...asList(item.themes)].join(" ").toLowerCase();
  return patterns.some((pattern) => haystack.includes(pattern));
}

function marketItems(brief) {
  return sortedNewsItems(brief).filter((item) => matchesDesk(item, MARKET_PATTERNS)).slice(0, 4);
}

function technologyItems(brief) {
  return sortedNewsItems(brief).filter((item) => matchesDesk(item, TECHNOLOGY_PATTERNS)).slice(0, 4);
}

function deskSection(brief, label, title, items, note) {
  if (!items.length) return "";
  return `<section class="home-section desk-section">
    <div class="home-section-head">
      <p class="section-kicker">${escapeHtml(label)}</p>
      <h2>${escapeHtml(title)}</h2>
      <p>${escapeHtml(note)}</p>
    </div>
    <div class="desk-list">${items.map((item) => renderDeskStory(item, brief)).join("")}</div>
  </section>`;
}

function renderDeskStory(item, brief) {
  return `<article class="desk-story">
    ${storyMeta(item, brief)}
    <h3>${headlineHtml(storyTitle(item, "desk"))}</h3>
    ${summaryBlock(item, { showMissing: true })}
    <a class="story-link-inline" href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer">${UI.readSource}</a>
  </article>`;
}

function archiveSearchAccess(brief) {
  return `<section class="home-section utility-access">
    <a href="${linkFor("/archive")}" data-link>
      <span>Archive</span>
      <strong>翻查過往每日摘要</strong>
      <em>${escapeHtml(brief.date)} · ${escapeHtml(brief.update_id || "")}</em>
    </a>
    <a href="${linkFor("/search")}" data-link>
      <span>Search</span>
      <strong>搜尋公司、題材與來源</strong>
      <em>Nvidia · Fed · AI · 半導體</em>
    </a>
  </section>`;
}

function sourceTransparencyBlock(brief) {
  const sourceLinks = asList(brief.items).filter((item) => item.url && item.url !== "https://news.tinydreamlab.com/").length;
  const sourceNames = asList(brief.sources).map((source) => source.name).filter(Boolean).slice(0, 8);
  const report = brief.generation_report || {};
  const collection = report.collection || {};
  const quality = report.item_quality || {};
  const ai = report.ai || {};
  const contextConfidence = quality.context_confidence || {};
  const confidenceText = Object.entries(contextConfidence)
    .slice(0, 4)
    .map(([key, value]) => `${key} ${value}`)
    .join(" · ");
  const sourceStats = asList(report.source_stats);
  const blockedSources = sourceStats.filter((source) => source.access === "Blocked").length;
  const topSourceStats = sourceStats
    .filter((source) => Number(source.accepted_count || 0) > 0)
    .sort((a, b) => Number(b.accepted_count || 0) - Number(a.accepted_count || 0))
    .slice(0, 5);
  return `<section class="source-transparency">
    <p class="section-kicker">Source Transparency</p>
    <h2>來源透明度</h2>
    <dl>
      <div><dt>來源數</dt><dd>${asList(brief.sources).length}</dd></div>
      <div><dt>原文入口</dt><dd>${sourceLinks}/${asList(brief.items).length}</dd></div>
      <div><dt>核對方式</dt><dd>保留原文連結</dd></div>
    </dl>
    ${Object.keys(report).length ? `<div class="generation-report" aria-label="生成報告">
      <div><span>候選新聞</span><strong>${escapeHtml(collection.accepted_candidates || 0)}</strong><em>${escapeHtml(collection.raw_candidates || 0)} raw</em></div>
      <div><span>舊聞過濾</span><strong>${escapeHtml(collection.skipped_stale || 0)}</strong><em>96 小時外</em></div>
      <div><span>品質隔離</span><strong>${escapeHtml(asList(quality.skipped_items).length || 0)}</strong><em>不影響整次更新</em></div>
      <div><span>AI 摘要</span><strong>${escapeHtml(ai.summary_updates || 0)}/${escapeHtml(ai.summary_candidates || 0)}</strong><em>可核對文字</em></div>
      <div><span>摘要拒收</span><strong>${escapeHtml(asList(quality.summary_rejections).length || 0)}</strong><em>品質閘門</em></div>
      <div><span>來源狀態</span><strong>${escapeHtml((collection.sources_accessible || 0))}/${escapeHtml((collection.sources_total || asList(brief.sources).length))}</strong><em>${escapeHtml(blockedSources)} blocked</em></div>
    </div>` : ""}
    <p>每條新聞保留來源、時間、題材標籤和原文入口；摘要只使用可讀來源文字或可信 description，並通過摘要品質閘門。</p>
    ${confidenceText ? `<p class="confidence-note">來源可信度：${escapeHtml(confidenceText)}</p>` : ""}
    <div class="source-mini-list">${sourceNames.map((name) => `<span>${escapeHtml(name)}</span>`).join("")}</div>
    ${topSourceStats.length ? `<div class="source-stat-list">${topSourceStats.map((source) => `<span>${escapeHtml(source.name)} <b>${escapeHtml(source.accepted_count)}</b></span>`).join("")}</div>` : ""}
  </section>`;
}

function hero(brief, isHome) {
  const items = asList(brief.items).slice().sort((a, b) => (b.heat_score || 0) - (a.heat_score || 0));
  const lead = items[0];
  const briefId = brief.update_id || brief.date;
  const updateTime = brief.generated_at ? ` · ${formatTime(brief.generated_at)} HKT` : "";
  return `<section class="hero editorial-hero">
    <div class="hero-copy">
      <p class="eyebrow">${escapeHtml(brief.date)}${updateTime} · Daily Intelligence</p>
      <h1>${escapeHtml(isHome ? "全球財經與科技頭版" : brief.title || "每日國際財經與科技新聞摘要")}</h1>
      <p class="deck">${escapeHtml(brief.deck || "整理全球市場、科技產業與主要企業消息，協助快速掌握今日重點。")}</p>
      ${isHome ? `<p><a class="action primary-action" href="${linkFor(`/briefs/${briefId}`)}" data-link>${UI.readFullBrief}</a></p>` : ""}
    </div>
    <aside class="hero-meta newsroom-panel" aria-label="今日編輯資料">
      <div class="metric-grid">
        <div class="metric"><b>${asList(brief.hot_topics).length}</b><span>${UI.hotTopics}</span></div>
        <div class="metric"><b>${asList(brief.items).length}</b><span>${UI.newsItems}</span></div>
        <div class="metric"><b>${asList(brief.categories).length}</b><span>${UI.categories}</span></div>
        <div class="metric"><b>${asList(brief.sources).length}</b><span>${UI.sources}</span></div>
      </div>
      ${lead ? `<div class="morning-brief"><span>今日主線</span><strong>${headlineHtml(displayTitle(lead))}</strong></div>` : ""}
    </aside>
  </section>`;
}

function latestTicker(brief) {
  const items = asList(brief.items).slice().sort((a, b) => (b.heat_score || 0) - (a.heat_score || 0)).slice(0, 5);
  if (!items.length) return "";
  return `<section class="latest-ticker" aria-label="最新焦點">
    <strong>Latest</strong>
    <div>${items.map((item) => `<a href="#item-${escapeHtml(item.id)}" data-item-jump="${escapeHtml(item.id)}">${headlineHtml(displayTitle(item))}</a>`).join("")}</div>
  </section>`;
}

function summarySection(brief) {
  return `<section class="section overview-section">
    <div class="section-head">
      <h2>${UI.dailyOverview}</h2>
      <p class="section-note">先讀全日主線，再按焦點、分類或來源深入追蹤。</p>
    </div>
    <p class="summary-text">${escapeHtml(brief.daily_summary_zh || "")}</p>
  </section>`;
}

function frontPageSection(brief) {
  const itemById = new Map(asList(brief.items).map((item) => [item.id, item]));
  const topics = asList(brief.hot_topics).sort((a, b) => (a.rank || 99) - (b.rank || 99));
  const items = asList(brief.items).slice().sort((a, b) => (b.heat_score || 0) - (a.heat_score || 0));
  const leadTopic = topics[0];
  const leadItem = leadTopic ? asList(leadTopic.item_ids).map((id) => itemById.get(id)).find(Boolean) : items[0];
  const remaining = items.filter((item) => item.id !== leadItem?.id);
  const sideItems = remaining.slice(0, 4);
  const latestItems = remaining.slice(4, 10);

  return `<section class="section front-page editorial-front">
    <div class="section-head">
      <p class="section-kicker">${UI.focusRanking}</p>
      <h2>今日頭版</h2>
      <p class="section-note">以來源可核實度、題材熱度和市場影響排序，先讀最重要的一條，再掃描相關主線。</p>
    </div>
    <div class="front-grid">
      ${leadItem ? renderLeadStory(leadItem, leadTopic) : ""}
      <div class="brief-stack">${sideItems.map(renderCompactStory).join("")}</div>
      <aside class="latest-rail">
        <div class="rail-head"><span>Latest List</span><strong>${latestItems.length} 條</strong></div>
        ${latestItems.map(renderLatestRailItem).join("")}
      </aside>
    </div>
  </section>`;
}

function renderLeadStory(item, topic) {
  const label = heatLabel(item.heat_score);
  return `<article class="lead-story" id="item-${escapeHtml(item.id)}">
    <div class="item-top"><div class="item-meta"><span class="rank">#${escapeHtml(topic?.rank || 1)}</span>${sourceSignal(item)}<span>${escapeHtml(item.category)}</span></div><span class="badge ${heatClass(label)}">熱度 ${escapeHtml(item.heat_score || 0)}</span></div>
    <h3>${headlineHtml(displayTitle(item))}</h3>
    ${summaryBlock(item)}
    <div class="focus-list">${asList(item.themes).slice(0, 4).map((theme) => `<a class="pill" href="${linkFor(`/topics/${slugify(theme)}`)}" data-link>${escapeHtml(theme)}</a>`).join("")}</div>
    <div class="story-actions"><a class="action" href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer">${UI.readSource}</a></div>
  </article>`;
}

function renderCompactStory(item, index) {
  const label = heatLabel(item.heat_score);
  return `<article class="compact-story" id="item-${escapeHtml(item.id)}">
    <div class="item-meta"><span class="rank">${String(index + 2).padStart(2, "0")}</span>${sourceSignal(item)}<span>${escapeHtml(item.category)}</span></div>
    <h3>${headlineHtml(displayTitle(item))}</h3>
    ${summaryBlock(item)}
    <div class="compact-bottom"><span class="badge ${heatClass(label)}">熱度 ${escapeHtml(item.heat_score || 0)}</span><a href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer">${UI.readSource}</a></div>
  </article>`;
}

function renderLatestRailItem(item, index) {
  return `<a class="rail-item" href="#item-${escapeHtml(item.id)}" data-item-jump="${escapeHtml(item.id)}">
    <span>${String(index + 1).padStart(2, "0")}</span>
    <strong>${headlineHtml(displayTitle(item))}</strong>
    <em>${escapeHtml(item.source || "")}</em>
  </a>`;
}

function topicSections(brief) {
  const byId = new Map(asList(brief.items).map((item) => [item.id, item]));
  const sections = asList(brief.categories).slice(0, 5).map((category) => {
    const items = asList(category.item_ids).map((id) => byId.get(id)).filter(Boolean).slice(0, 3);
    if (!items.length) return "";
    return `<section class="topic-section">
      <div class="topic-section-head">
        <p class="section-kicker">Topic Desk</p>
        <h3>${escapeHtml(category.name)}</h3>
      </div>
      <div class="topic-section-grid">${items.map(renderTopicSectionItem).join("")}</div>
    </section>`;
  }).filter(Boolean).join("");
  if (!sections) return "";
  return `<section class="section topic-sections">
    <div class="section-head">
      <p class="section-kicker">Sections</p>
      <h2>按題材閱讀</h2>
      <p class="section-note">把同類新聞放在同一張編輯桌上，方便快速比較市場、科技與企業主線。</p>
    </div>
    <div class="topic-sections-grid">${sections}</div>
  </section>`;
}

function renderTopicSectionItem(item) {
  return `<article class="topic-section-item" id="item-${escapeHtml(item.id)}">
    <div class="item-meta">${sourceSignal(item)}<span>${escapeHtml(item.heat_score || 0)}</span></div>
    <h4>${headlineHtml(displayTitle(item))}</h4>
    ${summaryBlock(item)}
    <p class="story-link"><a href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer">${UI.readSource}</a></p>
  </article>`;
}

function categoriesSection(brief) {
  return `<section class="section">
    <div class="section-head"><h2>${UI.categoryNews}</h2><p class="section-note">按題材瀏覽，同時可在本日新聞內即時搜尋。</p></div>
    <div class="search-row"><input id="news-search" type="search" placeholder="在本日摘要搜尋公司、題材或來源" /><button class="filter-button" id="clear-search" type="button">${UI.clear}</button></div>
    <div class="category-tabs"><button class="filter-button active" data-category="all" type="button">${UI.all}</button>${asList(brief.categories).map((category) => `<button class="filter-button" data-category="${escapeHtml(category.slug)}" type="button">${escapeHtml(category.name)}</button>`).join("")}</div>
    <div id="category-panel" class="category-panel"></div>
  </section>`;
}

function bindCategoryControls(brief) {
  const panel = document.querySelector("#category-panel");
  const buttons = [...document.querySelectorAll("[data-category]")];
  const search = document.querySelector("#news-search");
  const clear = document.querySelector("#clear-search");
  const update = () => {
    buttons.forEach((button) => button.classList.toggle("active", button.dataset.category === state.categorySlug));
    panel.innerHTML = renderItems(brief, state.categorySlug, state.query);
    bindItemJumpControls();
  };
  buttons.forEach((button) => button.addEventListener("click", () => {
    state.categorySlug = button.dataset.category;
    update();
  }));
  search?.addEventListener("input", () => {
    state.query = search.value.trim().toLowerCase();
    update();
  });
  clear?.addEventListener("click", () => {
    state.query = "";
    search.value = "";
    update();
  });
  update();
}

function renderItems(brief, categorySlug, query) {
  const byId = new Map(asList(brief.items).map((item) => [item.id, item]));
  const category = asList(brief.categories).find((item) => item.slug === categorySlug);
  const baseItems = category ? asList(category.item_ids).map((id) => byId.get(id)).filter(Boolean) : asList(brief.items);
  const filtered = query
    ? baseItems.filter((item) => [displayTitle(item), item.title_original, item.source, item.category, displaySummary(item), ...asList(item.themes)].join(" ").toLowerCase().includes(query))
    : baseItems;
  if (!filtered.length) return `<p class="section-note">未找到符合條件的新聞。</p>`;
  return `<div class="item-list">${filtered.map(renderItem).join("")}</div>`;
}

function renderItem(item) {
  const label = heatLabel(item.heat_score);
  return `<article class="item-card" id="item-${escapeHtml(item.id)}">
    <div class="item-top"><div class="item-meta">${sourceSignal(item)}<span>${escapeHtml(item.category)}</span><span>${escapeHtml(item.time_horizon || "")}</span></div><span class="badge ${heatClass(label)}">熱度 ${escapeHtml(item.heat_score || 0)}</span></div>
    <h3>${headlineHtml(displayTitle(item))}</h3>
    ${summaryBlock(item)}
    <div class="focus-list">${asList(item.themes).slice(0, 4).map((theme) => `<a class="pill" href="${linkFor(`/topics/${slugify(theme)}`)}" data-link>${escapeHtml(theme)}</a>`).join("")}</div>
    ${asList(item.key_facts).length ? `<ul class="facts">${asList(item.key_facts).slice(0, 3).map((fact) => `<li>${escapeHtml(fact)}</li>`).join("")}</ul>` : ""}
    ${detailBoxes(item)}
    <p><a class="action" href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer">${UI.readSource}</a></p>
  </article>`;
}

function bindItemJumpControls() {
  document.querySelectorAll("[data-item-jump]").forEach((link) => {
    link.addEventListener("click", (event) => {
      const id = link.dataset.itemJump;
      const target = id ? document.querySelector(`#item-${CSS.escape(id)}`) : null;
      if (!target) return;
      event.preventDefault();
      target.scrollIntoView({ behavior: "smooth", block: "start" });
      document.querySelectorAll(".highlighted").forEach((node) => node.classList.remove("highlighted"));
      target.classList.add("highlighted");
      window.setTimeout(() => target.classList.remove("highlighted"), 2200);
    });
  });
}

function sourcesSection(brief) {
  return `<section class="section">
    <div class="section-head"><h2>${UI.originalSources}</h2><p class="section-note">所有新聞保留原文入口，方便核對和深入閱讀。</p></div>
    <div class="source-grid">${asList(brief.sources).map((source) => `<a class="source-card" href="${escapeHtml(source.url)}" target="_blank" rel="noreferrer"><strong>${escapeHtml(source.name)}</strong><p>${escapeHtml(source.access || "Unknown access")}</p></a>`).join("")}</div>
  </section>`;
}

function renderArchive() {
  const rows = asList(state.index.briefs).map((brief) => {
    const updates = asList(brief.updates).map((update) => {
      const time = update.generated_at ? formatTime(update.generated_at) : update.update_id;
      return `<a class="archive-link" href="${linkFor(`/briefs/${update.update_id}`)}" data-link><strong>${escapeHtml(time)}</strong><span>${escapeHtml(update.item_count || 0)} 條新聞</span></a>`;
    }).join("");
    return `<article class="archive-row"><p class="eyebrow">${escapeHtml(brief.date)}</p><h3><a href="${linkFor(`/briefs/${brief.update_id || brief.date}`)}" data-link>${escapeHtml(brief.title)}</a></h3><p>${escapeHtml(brief.summary || "")}</p><div class="focus-list">${asList(brief.top_themes).map((theme) => `<span class="pill">${escapeHtml(theme)}</span>`).join("")}</div>${updates ? `<div class="archive-links"><strong>同日更新版本</strong>${updates}</div>` : ""}</article>`;
  }).join("");
  app.innerHTML = `<section class="section"><div class="section-head"><h1>${UI.archive}</h1><p class="section-note">按日期和更新時間翻查過往摘要。</p></div><div class="archive-list">${rows}</div></section>`;
}

async function renderSearch(query) {
  await ensureArchiveBriefs();
  const input = document.querySelector("#global-search-input");
  if (input) input.value = query || state.globalQuery || "";
  const results = searchItems(query || state.globalQuery);
  app.innerHTML = `<section class="section search-page"><div class="section-head"><h1>${UI.search}</h1><p class="section-note">搜尋會覆蓋已歸檔的每日摘要。</p></div><div class="search-row"><input id="search-page-input" type="search" value="${escapeHtml(query || state.globalQuery || "")}" placeholder="例如 Nvidia、AI、Fed、半導體" /><button class="filter-button" id="search-page-button" type="button">${UI.search}</button></div>${results.length ? `<p class="result-count">找到 ${results.length} 條相關新聞</p><div class="item-list">${results.map(renderSearchResult).join("")}</div>` : `<p class="section-note">未找到相關結果。可試 Nvidia、AI、Fed、semiconductors。</p>`}</section>`;
  const pageInput = document.querySelector("#search-page-input");
  const run = () => navigateToSearch(pageInput.value.trim());
  document.querySelector("#search-page-button")?.addEventListener("click", run);
  pageInput?.addEventListener("keydown", (event) => {
    if (event.key === "Enter") run();
  });
}

function renderSearchResult(result) {
  const item = result.item;
  const briefId = result.update_id || result.date;
  return `<article class="item-card"><div class="item-top"><div class="item-meta"><span>${escapeHtml(result.date)}</span>${sourceSignal(item)}<span>${escapeHtml(item.category)}</span></div><span class="badge ${heatClass(heatLabel(item.heat_score))}">熱度 ${escapeHtml(item.heat_score || 0)}</span></div><h3>${headlineHtml(displayTitle(item))}</h3>${summaryBlock(item)}<div class="focus-list">${asList(item.themes).map((theme) => `<a class="pill" href="${linkFor(`/topics/${slugify(theme)}`)}" data-link>${escapeHtml(theme)}</a>`).join("")}</div><p><a class="action" href="${linkFor(`/briefs/${briefId}`)}" data-link>${UI.viewDailyBrief}</a> <a class="action" href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer">${UI.readSource}</a></p></article>`;
}

function renderTopics() {
  const themes = collectThemes();
  app.innerHTML = `<section class="section"><div class="section-head"><h1>${UI.topics}</h1><p class="section-note">按正式標籤追蹤近期反覆出現的題材。</p></div><div class="topic-list">${themes.map((theme) => `<a class="pill" href="${linkFor(`/topics/${slugify(theme)}`)}" data-link>${escapeHtml(theme)}</a>`).join("")}</div></section>`;
}

function renderTopic(slug) {
  const matches = asList(state.brief.items).filter((item) => asList(item.themes).some((theme) => slugify(theme) === slug));
  const title = asList(matches[0]?.themes).find((theme) => slugify(theme) === slug) || slug;
  app.innerHTML = `<section class="section"><div class="section-head"><h1>${escapeHtml(title)}</h1><p class="section-note">以下是本期與此標籤相關的新聞。</p></div>${matches.length ? `<div class="item-list">${matches.map(renderItem).join("")}</div>` : `<p>暫時未有相關新聞。</p>`}</section>`;
}

function getAllBriefs() {
  const values = [...state.briefs.values()];
  const seen = new Set();
  return values.filter((brief) => {
    const key = brief.update_id || brief.date;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function searchItems(query) {
  const normalized = String(query || "").trim().toLowerCase();
  if (!normalized) return [];
  return getAllBriefs()
    .flatMap((brief) => asList(brief.items).map((item) => ({
      date: brief.date,
      update_id: brief.update_id,
      item,
      haystack: [brief.title, brief.deck, brief.daily_summary_zh, displayTitle(item), item.title_original, item.source, item.category, displaySummary(item), item.market_impact, item.tracking_value, ...asList(item.themes), ...asList(item.key_facts), ...asList(item.sources_reporting_same_topic)].join(" ").toLowerCase(),
    })))
    .filter((entry) => entry.haystack.includes(normalized))
    .sort((a, b) => (b.item.heat_score || 0) - (a.item.heat_score || 0));
}

function tagsSidebar() {
  const tags = formalTags();
  const recent = asList(state.index.briefs).slice(0, 5);
  return `<aside class="sidebar newsroom-panel" aria-label="${UI.formalTags}">
    <div><p class="eyebrow">${UI.formalTags}</p><h2>${UI.hotTags}</h2></div>
    <div class="sidebar-list">${tags.slice(0, 12).map((tag) => `<a class="tag-link" href="${linkFor(`/topics/${slugify(tag.name)}`)}" data-link><strong>${escapeHtml(tag.name)}</strong><small>${tag.count}</small></a>`).join("")}</div>
    <div class="sidebar-block"><h3>近期更新</h3>${recent.map((brief) => `<a class="mini-link" href="${linkFor(`/briefs/${brief.update_id || brief.date}`)}" data-link><strong>${escapeHtml(brief.date)}</strong><span>${escapeHtml(brief.item_count || 0)} 條</span></a>`).join("")}</div>
  </aside>`;
}

function formalTags() {
  const counts = new Map();
  getAllBriefs().forEach((brief) => asList(brief.items).forEach((item) => asList(item.themes).forEach((theme) => counts.set(theme, (counts.get(theme) || 0) + 1))));
  return [...counts.entries()].map(([name, count]) => ({ name, count })).sort((a, b) => b.count - a.count || a.name.localeCompare(b.name));
}

function collectThemes() {
  return formalTags().map((tag) => tag.name);
}

function slugify(value = "") {
  return String(value).trim().toLowerCase().replaceAll("&", "and").replace(/[^a-z0-9\u3400-\u9fff]+/g, "-").replace(/^-+|-+$/g, "");
}

const WORKSPACE_DEFAULTS = {
  filter: "all",
  query: "",
  fullOnly: false,
  focusOnly: false,
  readIds: new Set(),
};

function workspaceState(brief) {
  if (!state.workspace || state.workspace.briefId !== (brief.update_id || brief.date)) {
    const briefId = brief.update_id || brief.date;
    let readIds = [];
    try {
      readIds = JSON.parse(localStorage.getItem(`tdn-read-${briefId}`) || "[]");
    } catch {
      readIds = [];
    }
    state.workspace = { ...WORKSPACE_DEFAULTS, briefId, readIds: new Set(readIds) };
  }
  return state.workspace;
}

function saveWorkspaceState() {
  if (!state.workspace?.briefId) return;
  localStorage.setItem(`tdn-read-${state.workspace.briefId}`, JSON.stringify([...state.workspace.readIds]));
}

function itemSummaryTier(item) {
  const summary = displaySummary(item);
  if (!summary) return { grade: "C", label: "只列原文", detail: "未取得足夠可核實來源文字", readable: false };
  const confidence = Number(item?.source_confidence || 0);
  if (summary.length >= 85 && confidence >= 0.74) return { grade: "A", label: "完整摘要", detail: "通過品質閘門", readable: true };
  return { grade: "B", label: "摘要", detail: item?.summary_basis ? "根據來源描述生成" : "根據可讀來源文字", readable: true };
}

function normalizeDesk(item) {
  const text = [item?.category, item?.title_original, item?.title_zh, ...asList(item?.themes)].join(" ").toLowerCase();
  if (/fed|inflation|rate|yield|treasury|macro|央行|利率|通脹|宏觀|債/.test(text)) return "macro";
  if (/\bai\b|artificial intelligence|technology|tech|chip|semiconductor|meta|nvidia|microsoft|openai|科技|平台|半導體|算力/.test(text)) return "tech-ai";
  if (/oil|gold|commodity|energy|gas|dollar|yen|能源|原油|商品|黃金|外匯/.test(text)) return "energy";
  if (/earnings|stock|shares|ipo|deal|merger|acquisition|company|企業|併購|財報|上市/.test(text)) return "companies";
  return "markets";
}

const WORKSPACE_FILTERS = [
  ["all", "全部"],
  ["lead", "今日焦點"],
  ["macro", "宏觀"],
  ["tech-ai", "科技與 AI"],
  ["energy", "能源與商品"],
  ["companies", "企業"],
];

function leadItem(brief) {
  const sorted = sortedNewsItems(brief);
  return sorted.find((item) => displaySummary(item)) || sorted[0];
}

function workspaceCollections(brief) {
  const lead = leadItem(brief);
  const all = sortedNewsItems(brief);
  const readable = all.filter((item) => itemSummaryTier(item).readable);
  const sourceOnly = all.filter((item) => !itemSummaryTier(item).readable);
  return { lead, all, readable, sourceOnly };
}

function matchesWorkspaceFilter(item, filter, lead) {
  if (filter === "all") return true;
  if (filter === "lead") return item?.id === lead?.id;
  return normalizeDesk(item) === filter;
}

function matchesWorkspaceQuery(item, query) {
  const normalized = String(query || "").trim().toLowerCase();
  if (!normalized) return true;
  const haystack = [displayTitle(item), item?.title_original, item?.source, item?.category, displaySummary(item), ...asList(item?.themes)].join(" ").toLowerCase();
  return haystack.includes(normalized);
}

function filteredReadableItems(brief) {
  const ws = workspaceState(brief);
  const { lead, readable } = workspaceCollections(brief);
  return readable.filter((item) => {
    const filter = ws.focusOnly ? "lead" : ws.filter;
    const fullAllowed = !ws.fullOnly || itemSummaryTier(item).grade === "A";
    return fullAllowed && matchesWorkspaceFilter(item, filter, lead) && matchesWorkspaceQuery(item, ws.query);
  });
}

function filteredSourceOnlyItems(brief) {
  const ws = workspaceState(brief);
  if (ws.fullOnly) return [];
  const { lead, sourceOnly } = workspaceCollections(brief);
  const filter = ws.focusOnly ? "lead" : ws.filter;
  return sourceOnly.filter((item) => matchesWorkspaceFilter(item, filter, lead) && matchesWorkspaceQuery(item, ws.query));
}

function workspaceCounts(brief) {
  const { lead, all } = workspaceCollections(brief);
  const counts = Object.fromEntries(WORKSPACE_FILTERS.map(([key]) => [key, 0]));
  counts.markets = 0;
  counts.full = 0;
  all.forEach((item) => {
    counts.all += 1;
    if (item.id === lead?.id) counts.lead += 1;
    const desk = normalizeDesk(item);
    counts[desk] = (counts[desk] || 0) + 1;
    if (itemSummaryTier(item).grade === "A") counts.full += 1;
  });
  return counts;
}

function estimateReadingMinutes(items) {
  const words = items.reduce((sum, item) => sum + Math.max(70, (displaySummary(item).length || displayTitle(item).length) * 1.3), 0);
  return Math.max(2, Math.ceil(words / 420));
}

function readProgress(brief) {
  const ws = workspaceState(brief);
  const readable = workspaceCollections(brief).readable;
  if (!readable.length) return 0;
  const readCount = readable.filter((item) => ws.readIds.has(item.id)).length;
  return Math.round((readCount / readable.length) * 100);
}

function homePage(brief) {
  workspaceState(brief);
  return `<section class="morning-workbench minimal-brief" data-workspace>
    ${workbenchHero(brief)}
    <main class="reading-main">
      ${workspaceToolbar(brief)}
      ${articleWorkspace(brief)}
      ${sourceOnlySection(brief)}
      ${trustMethodologyPanel(brief)}
    </main>
    <button class="back-top" type="button" data-back-top>回到頂部</button>
  </section>`;
}

function workbenchHero(brief) {
  const lead = leadItem(brief);
  const leadHeadline = editorialHeadlineParts(lead || {}, "lead");
  const updateTime = brief.generated_at ? `${formatTime(brief.generated_at)} HKT` : brief.date;
  return `<section class="brief-hero">
    <div class="brief-hero-top">
      <p class="section-kicker">Editorial Morning Brief</p>
      <span>${escapeHtml(formatBriefDate(brief.date))} · ${escapeHtml(updateTime)} · ${escapeHtml(asList(brief.items).length)} 篇</span>
    </div>
    <div class="brief-hero-grid">
      <article class="brief-lead-card summary-collapsed" id="item-${escapeHtml(lead?.id || "lead")}">
        <div class="workspace-meta">${lead ? storyMeta(lead, brief) : ""}<span>${escapeHtml(itemSummaryTier(lead || {}).label)}</span></div>
        <p class="lead-overline">Today’s Lead / 今日焦點</p>
        <h1>${headlineHtml(leadHeadline.headline)}</h1>
        ${leadHeadline.dek ? `<p class="lead-dek">${escapeHtml(leadHeadline.dek)}</p>` : ""}
        ${leadSummaryBlock(lead)}
        <div class="lead-actions">
          ${displaySummary(lead) ? `<button class="summary-toggle" type="button" data-toggle-summary>展開完整摘要</button>` : ""}
          ${lead?.url ? `<a class="action primary-action" href="${escapeHtml(lead.url)}" target="_blank" rel="noreferrer">${UI.readSource}</a>` : ""}
        </div>
      </article>
      <aside class="morning-five">
        <p class="section-kicker">Morning Brief / 開市前 5 件事</p>
        <ol>${morningFive(brief).map((point) => `<li>${headlineHtml(point)}</li>`).join("")}</ol>
      </aside>
    </div>
  </section>`;
}

function leadSummaryBlock(item) {
  const summary = displaySummary(item);
  if (!summary) return `<p class="lead-summary muted">今日焦點未有足夠可信摘要文字，請由原文入口核對。</p>`;
  return `<p class="lead-conclusion">${escapeHtml(oneLineConclusion(item))}</p>
    <div class="lead-summary article-summary summary-collapsed" data-summary-body>
      ${summaryParagraphs(summary, itemSummaryTier(item).grade).map((paragraph) => `<p>${escapeHtml(paragraph)}</p>`).join("")}
    </div>`;
}

function morningFive(brief) {
  const { lead, all } = workspaceCollections(brief);
  const slots = [
    ["lead", "今日焦點", lead],
    ["macro", "宏觀與利率", all.find((item) => item?.id !== lead?.id && normalizeDesk(item) === "macro")],
    ["tech-ai", "科技與 AI", all.find((item) => item?.id !== lead?.id && normalizeDesk(item) === "tech-ai")],
    ["energy", "能源與商品", all.find((item) => item?.id !== lead?.id && normalizeDesk(item) === "energy")],
    ["companies", "企業事件", all.find((item) => item?.id !== lead?.id && normalizeDesk(item) === "companies")],
  ];
  const usedTopics = new Set();
  const usedLines = new Set();
  const points = [];
  slots.forEach(([key, label, item]) => {
    if (!item) return;
    const topic = normalizeDesk(item);
    const lineKey = compactEditorialText(editorialHeadlineParts(item).headline, "morning").replace(/\s+/g, "");
    if (usedTopics.has(topic) || usedLines.has(lineKey)) return;
    usedTopics.add(topic);
    usedLines.add(lineKey);
    const text = `${label}：${editorialHeadlineParts(item).headline}`;
    points.push(compactEditorialText(text, "morning"));
  });
  if (points.length < 5) {
    all.forEach((item) => {
      const topic = storyTopicKey(item);
      const line = compactEditorialText(editorialHeadlineParts(item).headline, "morning");
      const lineKey = line.replace(/\s+/g, "");
      if (points.length >= 5 || usedTopics.has(topic) || usedLines.has(lineKey)) return;
      usedTopics.add(topic);
      usedLines.add(lineKey);
      points.push(line);
    });
  }
  return points.slice(0, 5);
}

function marketPulse(brief) {
  const counts = workspaceCounts(brief);
  const all = sortedNewsItems(brief);
  const cards = [
    ["macro", "央行與利率", counts.macro || 0],
    ["tech-ai", "科技與 AI", counts["tech-ai"] || 0],
    ["energy", "能源與商品", counts.energy || 0],
    ["companies", "企業事件", counts.companies || 0],
  ];
  return `<section class="market-pulse">
    <div class="pulse-head"><p class="section-kicker">Market Pulse / 今日市場主線</p><h2>市場正在看什麼</h2></div>
    <div class="pulse-grid">${cards.map(([key, label, count]) => {
      const item = all.find((entry) => normalizeDesk(entry) === key);
      return `<article class="pulse-card">
        <span>${escapeHtml(label)}</span>
        <p>${escapeHtml(pulseMeaning(key, item))}</p>
        <b>${escapeHtml(count)} 篇相關</b>
      </article>`;
    }).join("")}</div>
  </section>`;
}

function pulseMeaning(key, item) {
  if (item) return compactEditorialText(oneLineConclusion(item), "brief");
  const fallback = {
    macro: "利率與通脹訊號仍是風險資產定價核心。",
    "tech-ai": "AI 資本開支與估值壓力繼續主導科技股情緒。",
    energy: "油價、金價與美元走勢影響通脹與避險交易。",
    companies: "企業交易、財報與上市消息影響個股估值。",
  };
  return fallback[key] || "今日未有足夠明確主線。";
}

function readingSidebar(brief) {
  const counts = workspaceCounts(brief);
  const items = workspaceCollections(brief).readable;
  const ws = workspaceState(brief);
  return `<aside class="reading-sidebar">
    <div class="sidebar-date">${formatBriefDate(brief.date)}</div>
    <h2>今日早報 · 共 ${asList(brief.items).length} 篇</h2>
    <div class="progress-block">
      <div><span>閱讀進度</span><strong data-progress-text>${readProgress(brief)}%</strong></div>
      <div class="progress-track"><span data-progress-bar style="width:${readProgress(brief)}%"></span></div>
    </div>
    <p class="reading-time">預計閱讀時間 ${estimateReadingMinutes(items)} 分鐘</p>
    <nav class="sidebar-filters">${WORKSPACE_FILTERS.map(([key, label]) => filterButtonHtml(key, label, counts, ws)).join("")}</nav>
    <div class="reading-method">
      <strong>今日閱讀法</strong>
      <p>先讀「開市前 5 件事」，再看今日焦點；有時間再按分類閱讀完整摘要。</p>
    </div>
  </aside>`;
}

function mobileWorkspaceBar(brief) {
  return `<section class="mobile-workspace-bar">
    <div><strong>${formatBriefDate(brief.date)}</strong><span>閱讀進度 <b data-progress-text>${readProgress(brief)}%</b></span></div>
    <div class="progress-track"><span data-progress-bar style="width:${readProgress(brief)}%"></span></div>
  </section>`;
}

function workspaceToolbar(brief) {
  const ws = workspaceState(brief);
  const counts = workspaceCounts(brief);
  if (counts.full === 0 && ws.fullOnly) {
    ws.fullOnly = false;
    saveWorkspaceState();
  }
  const fullSummaryToggle = counts.full > 0
    ? `<button type="button" class="summary-filter-toggle ${ws.fullOnly ? "active" : ""}" data-full-toggle>只看完整摘要 <b>${escapeHtml(counts.full)}</b></button>`
    : "";
  return `<section class="workspace-toolbar">
    <div class="toolbar-head">
      <div><p class="section-kicker">Today’s Stories</p><h2>今日文章</h2><p class="section-note">每篇先顯示約 100 字摘要；需要更多背景時再展開詳情。</p></div>
      <label class="workspace-search"><span>Search</span><input data-workspace-search type="search" value="${escapeHtml(ws.query)}" placeholder="搜尋公司、題材、來源" /></label>
    </div>
    <div class="workspace-controls">
      <div class="filter-chips">${WORKSPACE_FILTERS.map(([key, label]) => filterButtonHtml(key, label, counts, ws)).join("")}</div>
      ${fullSummaryToggle}
    </div>
  </section>`;
}

function filterButtonHtml(key, label, counts, ws) {
  const count = counts[key] || 0;
  const disabled = key !== "all" && count === 0;
  const className = `${workspaceActiveClass(key, ws)}${disabled ? " disabled" : ""}`;
  return `<button type="button" class="${className}" data-filter="${escapeHtml(key)}" ${disabled ? "disabled aria-disabled=\"true\"" : ""}>${escapeHtml(label)} <b>${escapeHtml(count)}</b></button>`;
}

function workspaceActiveClass(key, ws) {
  const active = (ws.focusOnly && key === "lead") || (!ws.focusOnly && ws.filter === key);
  return active ? "chip active" : "chip";
}

function articleWorkspace(brief) {
  const items = filteredReadableItems(brief);
  return `<section class="article-workspace" aria-live="polite">
    ${items.length ? items.map((item, index) => renderWorkbenchArticle(item, brief, index)).join("") : `<div class="empty-workspace"><h3>今日可核實摘要不足</h3><p>這個篩選暫時沒有通過品質檢查的摘要；可改看其他分類，或在下方 More source links 直接閱讀原文。</p></div>`}
  </section>`;
}

function renderWorkbenchArticle(item, brief, index) {
  const tier = itemSummaryTier(item);
  const summary = displaySummary(item);
  const read = workspaceState(brief).readIds.has(item.id);
  const points = articleKeyPoints(item);
  const title = editorialHeadlineParts(item);
  const paragraphs = summaryParagraphs(summary, tier.grade);
  const preview = summaryPreview(summary || oneLineConclusion(item));
  return `<article class="workbench-article ${tier.grade === "A" ? "full" : "limited"} summary-collapsed ${read ? "is-read" : ""}" id="item-${escapeHtml(item.id)}" data-article-id="${escapeHtml(item.id)}" data-grade="${escapeHtml(tier.grade)}">
    <div class="article-main">
      <div class="article-meta-row">
        <span>${escapeHtml(storyTime(item, brief))}</span>
        <span>${escapeHtml(item.source || "Source")}</span>
        <span>${escapeHtml(primaryTopic(item))}</span>
        <span class="summary-grade grade-${escapeHtml(tier.grade.toLowerCase())}">${escapeHtml(tier.label)}</span>
        <span>${Math.max(1, Math.ceil((summary.length || 90) / 180))} 分鐘</span>
      </div>
      <h2>${headlineHtml(title.headline)}</h2>
      ${title.dek ? `<p class="article-dek">${escapeHtml(title.dek)}</p>` : ""}
      <p class="summary-preview">${escapeHtml(preview)}</p>
      <div class="article-summary" data-summary-body>
        ${paragraphs.map((paragraph) => `<p>${escapeHtml(paragraph)}</p>`).join("")}
        ${points.length ? `<div class="article-points-inline"><strong>Editor’s Notes</strong><ul>${points.slice(0, 4).map((point) => `<li>${escapeHtml(point)}</li>`).join("")}</ul></div>` : ""}
      </div>
      <div class="article-footer">
        <div class="tag-row">${asList(item.themes).slice(0, 4).map((tag) => `<span>${escapeHtml(tag)}</span>`).join("")}</div>
        <div class="article-actions">
          ${paragraphs.length ? `<button type="button" data-toggle-summary>展開摘要</button>` : ""}
          <button type="button" data-mark-read="${escapeHtml(item.id)}">${read ? "已讀" : "標記已讀"}</button>
          <a href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer">${UI.readSource}</a>
        </div>
      </div>
      ${tier.grade === "B" ? `<p class="source-note">根據來源描述生成，請以原文作最後核對。</p>` : ""}
    </div>
  </article>`;
}

function summaryPreview(value = "") {
  const text = String(value || "").replace(/\s+/g, "").trim();
  if (!text) return "這篇新聞暫未有足夠可信摘要文字，請由原文入口核對。";
  const chars = Array.from(text);
  if (chars.length <= 115) return text;
  return `${chars.slice(0, 108).join("")}…`;
}

function oneLineConclusion(item) {
  const summary = displaySummary(item);
  if (summary) {
    const sentence = summary.split(/[。；;]/).map((part) => part.trim()).find((part) => part.length >= 8) || summary;
    return compactEditorialText(sentence, "brief");
  }
  return editorialHeadlineParts(item).headline;
}

function summaryParagraphs(summary, grade) {
  const sentences = String(summary || "")
    .split(/(?<=[。！？；;])\s*/)
    .map((part) => part.trim())
    .filter((part) => part && !isVagueSummarySentence(part));
  if (!sentences.length) return [];
  if (grade === "B") return [sentences.slice(0, 2).join("")];
  const paragraphs = [];
  for (let index = 0; index < sentences.length; index += 2) {
    paragraphs.push(sentences.slice(index, index + 2).join(""));
  }
  return paragraphs.slice(0, 3);
}

function isVagueSummarySentence(value = "") {
  const text = String(value || "");
  const vague = ["市場可能重新定價", "投資者需關注", "值得關注", "後續仍需觀察"];
  return vague.some((phrase) => text === phrase || (text.includes(phrase) && text.length < phrase.length + 10));
}

function articleKeyPoints(item) {
  const facts = asList(item.key_facts).filter((fact) => !String(fact).includes("摘要依據")).slice(0, 3);
  const points = [...facts];
  const summary = displaySummary(item);
  summary.split(/[。；;]/).map((part) => part.trim()).filter((part) => part.length >= 12).slice(0, 3).forEach((part) => {
    if (!points.some((point) => point.includes(part.slice(0, 8)))) points.push(shortenHeadline(part, "brief"));
  });
  const impact = impactSurface(item);
  if (!points.some((point) => point.includes("影響層面"))) points.push(`影響層面：${impact}`);
  points.push(`來源：${item.source || "主要來源"}`);
  return points.slice(0, 5);
}

function impactSurface(item) {
  const desk = normalizeDesk(item);
  if (desk === "macro") return "利率 / 美債 / 風險情緒";
  if (desk === "tech-ai") return "科技股 / AI 資本開支 / 估值";
  if (desk === "energy") return "商品 / 通脹 / 避險資金";
  if (desk === "companies") return "企業估值 / 交易風險 / 個股情緒";
  return "市場廣度 / 風險情緒";
}

function contextMap(item) {
  const issue = primaryTopic(item);
  const event = storyTitle(item, "brief");
  const impact = impactSurface(item);
  const risk = itemSummaryTier(item).grade === "A" ? "需追蹤後續數據" : "摘要有限，需核對原文";
  return `<div class="context-map" aria-label="脈絡圖">
    <span><b>核心議題</b>${escapeHtml(issue)}</span>
    <span><b>事件</b>${escapeHtml(event)}</span>
    <span><b>市場影響</b>${escapeHtml(impact)}</span>
    <span><b>風險</b>${escapeHtml(risk)}</span>
  </div>`;
}

function sourceOnlySection(brief) {
  const items = filteredSourceOnlyItems(brief);
  if (!items.length) return "";
  return `<section class="source-only-section">
    <details>
      <summary>More source links / 只列原文 <span>${items.length}</span></summary>
      <div class="source-only-list">${items.map((item) => `<a href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer">
        <strong>${headlineHtml(storyTitle(item, "desk"))}</strong>
        <span>${escapeHtml(item.source || "")} · ${escapeHtml(storyTime(item, brief))} · ${escapeHtml(primaryTopic(item))}</span>
      </a>`).join("")}</div>
    </details>
  </section>`;
}

function trustMethodologyPanel(brief) {
  const report = brief.generation_report || {};
  const collection = report.collection || {};
  const quality = report.item_quality || {};
  const ai = report.ai || {};
  const { readable, sourceOnly } = workspaceCollections(brief);
  const sourceLinks = readable.filter((item) => item.url && item.url !== "https://news.tinydreamlab.com/").length;
  const candidates = collection.raw_candidates || collection.candidate_count || collection.accepted_candidates || asList(brief.items).length;
  const sourcesTotal = collection.sources_total || asList(brief.sources).length;
  const sourcesAccessible = collection.sources_accessible || sourcesTotal;
  return `<section class="trust-panel compact-trust">
    <details class="method-details">
      <summary>今日核查：${escapeHtml(candidates)} 條候選，${escapeHtml(readable.length)} 條可摘要，原文入口 ${sourceLinks}/${readable.length}</summary>
      <p class="trust-readable">${escapeHtml(candidates)} 條候選新聞中，${escapeHtml(readable.length)} 條通過摘要品質檢查；${escapeHtml(sourceOnly.length)} 條因來源文字不足而只列原文；來源狀態 ${escapeHtml(sourcesAccessible)}/${escapeHtml(sourcesTotal)}。</p>
      <pre>${escapeHtml(JSON.stringify({ collection, ai, context_confidence: quality.context_confidence, rejected: asList(quality.summary_rejections).slice(0, 8) }, null, 2))}</pre>
    </details>
  </section>`;
}

function formatBriefDate(value) {
  const date = new Date(`${value}T00:00:00+08:00`);
  if (Number.isNaN(date.getTime())) return value || "今日";
  return date.toLocaleDateString("zh-HK", { month: "long", day: "numeric" });
}

function bindWorkspaceControls(brief) {
  const root = document.querySelector("[data-workspace]");
  if (!root) return;
  const ws = workspaceState(brief);
  root.querySelectorAll("[data-filter]").forEach((button) => {
    button.addEventListener("click", () => {
      const key = button.dataset.filter || "all";
      ws.fullOnly = false;
      ws.focusOnly = key === "lead";
      if (!ws.fullOnly && !ws.focusOnly) ws.filter = key;
      refreshWorkspace(brief);
    });
  });
  root.querySelector("[data-full-toggle]")?.addEventListener("click", () => {
    ws.fullOnly = !ws.fullOnly;
    refreshWorkspace(brief);
  });
  root.querySelector("[data-workspace-search]")?.addEventListener("input", (event) => {
    ws.query = event.target.value.trim();
    refreshWorkspace(brief);
  });
  root.querySelectorAll("[data-mark-read]").forEach((button) => {
    button.addEventListener("click", () => {
      const id = button.dataset.markRead;
      if (!id) return;
      if (ws.readIds.has(id)) ws.readIds.delete(id);
      else ws.readIds.add(id);
      saveWorkspaceState();
      refreshWorkspace(brief);
    });
  });
  root.querySelectorAll("[data-toggle-summary]").forEach((button) => {
    button.addEventListener("click", () => {
      const article = button.closest(".workbench-article, .brief-lead-card");
      article?.classList.toggle("summary-collapsed");
      button.textContent = article?.classList.contains("summary-collapsed") ? "展開摘要" : "收起摘要";
    });
  });
  root.querySelector("[data-back-top]")?.addEventListener("click", () => window.scrollTo({ top: 0, behavior: "smooth" }));
  observeReadingProgress(root, brief);
}

function refreshWorkspace(brief) {
  const main = document.querySelector(".reading-main");
  if (!main) return;
  main.innerHTML = `${workspaceToolbar(brief)}${articleWorkspace(brief)}${sourceOnlySection(brief)}${trustMethodologyPanel(brief)}`;
  document.querySelector(".reading-sidebar")?.replaceWith(htmlToElement(readingSidebar(brief)));
  const mobile = document.querySelector(".mobile-workspace-bar");
  if (mobile) mobile.outerHTML = mobileWorkspaceBar(brief);
  bindWorkspaceControls(brief);
}

function htmlToElement(html) {
  const template = document.createElement("template");
  template.innerHTML = html.trim();
  return template.content.firstElementChild;
}

function observeReadingProgress(root, brief) {
  if (!("IntersectionObserver" in window)) return;
  const ws = workspaceState(brief);
  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting && entry.intersectionRatio > 0.72) {
        const id = entry.target.dataset.articleId;
        if (id && !ws.readIds.has(id)) {
          ws.readIds.add(id);
          saveWorkspaceState();
          updateProgressUI(brief);
          entry.target.classList.add("is-read");
        }
      }
    });
  }, { threshold: [0.72] });
  root.querySelectorAll("[data-article-id]").forEach((card) => observer.observe(card));
}

function updateProgressUI(brief) {
  const progress = readProgress(brief);
  document.querySelectorAll("[data-progress-text]").forEach((node) => { node.textContent = `${progress}%`; });
  document.querySelectorAll("[data-progress-bar]").forEach((node) => { node.style.width = `${progress}%`; });
}

boot();
