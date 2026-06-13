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

const asList = (value) => (Array.isArray(value) ? value : []);
const linkFor = (path) => path;
const dataPath = (path) => `/${path}`;

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

function summaryBlock(item) {
  const summary = displaySummary(item);
  return summary ? `<p>${escapeHtml(summary)}</p>` : "";
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
  const response = await fetch(path);
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
  app.innerHTML = `${hero(brief, isHome)}<div class="edition-layout"><main>${summarySection(brief)}${frontPageSection(brief)}${categoriesSection(brief)}${sourcesSection(brief)}</main>${tagsSidebar(brief)}</div>`;
  bindCategoryControls(brief);
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

function hero(brief, isHome) {
  const items = asList(brief.items).slice().sort((a, b) => (b.heat_score || 0) - (a.heat_score || 0));
  const lead = items[0];
  const briefId = brief.update_id || brief.date;
  const updateTime = brief.generated_at ? ` · ${formatTime(brief.generated_at)} HKT` : "";
  return `<section class="hero v2-hero">
    <div class="hero-copy">
      <p class="eyebrow">${escapeHtml(brief.date)}${updateTime} · ${UI.latestBrief}</p>
      <h1>${escapeHtml(brief.title || "每日國際財經與科技新聞摘要")}</h1>
      <p class="deck">${escapeHtml(brief.deck || "整理全球市場、科技產業與主要企業消息，協助快速掌握今日重點。")}</p>
      ${isHome ? `<p><a class="action primary-action" href="${linkFor(`/briefs/${briefId}`)}" data-link>${UI.readFullBrief}</a></p>` : ""}
    </div>
    <aside class="hero-meta newsroom-panel">
      <div class="metric-grid">
        <div class="metric"><b>${asList(brief.hot_topics).length}</b><span>${UI.hotTopics}</span></div>
        <div class="metric"><b>${asList(brief.items).length}</b><span>${UI.newsItems}</span></div>
        <div class="metric"><b>${asList(brief.categories).length}</b><span>${UI.categories}</span></div>
        <div class="metric"><b>${asList(brief.sources).length}</b><span>${UI.sources}</span></div>
      </div>
      ${lead ? `<div class="morning-brief"><span>今日主線</span><strong>${escapeHtml(displayTitle(lead))}</strong></div>` : ""}
    </aside>
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
  const sideItems = items.filter((item) => item.id !== leadItem?.id).slice(0, 4);

  return `<section class="section front-page">
    <div class="section-head">
      <h2>${UI.focusRanking}</h2>
      <p class="section-note">以市場影響、來源可信度和題材熱度排序。</p>
    </div>
    <div class="front-grid">
      ${leadItem ? renderLeadStory(leadItem, leadTopic) : ""}
      <div class="brief-stack">${sideItems.map(renderCompactStory).join("")}</div>
    </div>
    <div class="topic-strip">${topics.slice(0, 5).map(renderTopicChip).join("")}</div>
  </section>`;
}

function renderLeadStory(item, topic) {
  const label = heatLabel(item.heat_score);
  return `<article class="lead-story" id="item-${escapeHtml(item.id)}">
    <div class="item-top"><div class="item-meta"><span class="rank">#${escapeHtml(topic?.rank || 1)}</span>${sourceSignal(item)}<span>${escapeHtml(item.category)}</span></div><span class="badge ${heatClass(label)}">${label} · ${escapeHtml(item.heat_score || 0)}</span></div>
    <h3>${escapeHtml(displayTitle(item))}</h3>
    ${summaryBlock(item)}
    <div class="focus-list">${asList(item.themes).slice(0, 4).map((theme) => `<a class="pill" href="${linkFor(`/topics/${slugify(theme)}`)}" data-link>${escapeHtml(theme)}</a>`).join("")}</div>
    <div class="story-actions"><a class="action" href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer">${UI.readSource}</a></div>
  </article>`;
}

function renderCompactStory(item, index) {
  const label = heatLabel(item.heat_score);
  return `<article class="compact-story" id="item-${escapeHtml(item.id)}">
    <div class="item-meta">${sourceSignal(item)}<span>${escapeHtml(item.category)}</span></div>
    <h3>${escapeHtml(displayTitle(item))}</h3>
    ${summaryBlock(item)}
    <div class="compact-bottom"><span class="badge ${heatClass(label)}">${label} · ${escapeHtml(item.heat_score || 0)}</span><a href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer">${UI.readSource}</a></div>
  </article>`;
}

function renderTopicChip(topic) {
  const label = heatLabel(topic.heat_score, topic.heat_label);
  return `<a class="topic-chip" href="#item-${escapeHtml(asList(topic.item_ids)[0] || "")}" data-item-jump="${escapeHtml(asList(topic.item_ids)[0] || "")}">
    <span>#${escapeHtml(topic.rank || "")} · ${escapeHtml(topic.source_count || 1)} 來源</span>
    <strong>${escapeHtml(topic.topic || "")}</strong>
    <em class="${heatClass(label)}">${escapeHtml(topic.heat_score || 0)}</em>
  </a>`;
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
    <div class="item-top"><div class="item-meta">${sourceSignal(item)}<span>${escapeHtml(item.category)}</span><span>${escapeHtml(item.time_horizon || "")}</span></div><span class="badge ${heatClass(label)}">${label} · ${escapeHtml(item.heat_score || 0)}</span></div>
    <h3>${escapeHtml(displayTitle(item))}</h3>
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
  return `<article class="item-card"><div class="item-top"><div class="item-meta"><span>${escapeHtml(result.date)}</span>${sourceSignal(item)}<span>${escapeHtml(item.category)}</span></div><span class="badge ${heatClass(heatLabel(item.heat_score))}">${heatLabel(item.heat_score)} · ${escapeHtml(item.heat_score || 0)}</span></div><h3>${escapeHtml(displayTitle(item))}</h3>${summaryBlock(item)}<div class="focus-list">${asList(item.themes).map((theme) => `<a class="pill" href="${linkFor(`/topics/${slugify(theme)}`)}" data-link>${escapeHtml(theme)}</a>`).join("")}</div><p><a class="action" href="${linkFor(`/briefs/${briefId}`)}" data-link>${UI.viewDailyBrief}</a> <a class="action" href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer">${UI.readSource}</a></p></article>`;
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

boot();
