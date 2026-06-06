const app = document.querySelector("#app");
const state = { index: null, brief: null, categorySlug: "all", query: "", globalQuery: "" };

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

function heatLabel(score = 0, explicit) {
  if (explicit) return explicit;
  if (score >= 75) return "High";
  if (score >= 50) return "Medium";
  return "Low";
}

function heatClass(label = "") {
  const normalized = label.toLowerCase();
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
    state.brief = await readJson(dataPath(`data/briefs/${latestDate}.json`));
    bindNavigation();
    render();
  } catch (error) {
    app.innerHTML = `<section class="error"><p class="eyebrow">Data loading failed</p><h1>Sample JSON could not be loaded.</h1><p>${escapeHtml(error.message)}</p></section>`;
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

function render() {
  const current = route();
  state.categorySlug = "all";
  state.query = "";
  if (current.name === "archive") return renderArchive();
  if (current.name === "search") return renderSearch(current.query);
  if (current.name === "topics") return renderTopics();
  if (current.name === "topic") return renderTopic(current.slug);
  return renderBrief(current.name === "brief" ? current.date : state.brief.date, current.name === "home");
}

function renderBrief(date, isHome = false) {
  const brief = state.brief;
  if (date !== brief.date) {
    app.innerHTML = `<section class="error"><p class="eyebrow">Brief not available</p><h1>${escapeHtml(date)}</h1><p>V1 currently includes sample data for ${escapeHtml(brief.date)} only.</p></section>`;
    return;
  }

  app.innerHTML = `${hero(brief, isHome)}<div class="content-layout"><div class="brief-main">${summarySection(brief)}${hotTopicsSection(brief)}${categoriesSection(brief)}${sourcesSection(brief)}</div>${tagsSidebar()}</div>`;
  bindCategoryControls(brief);
}

function hero(brief, isHome) {
  const indexEntry = state.index.briefs?.find((item) => item.date === brief.date) || {};
  return `<section class="hero"><div><p class="eyebrow">${escapeHtml(brief.date)} · Latest daily brief</p><h1>${escapeHtml(brief.title || "Daily finance and technology brief")}</h1><p class="deck">${escapeHtml(brief.deck || indexEntry.summary || "")}</p>${isHome ? `<p><a class="action" href="${linkFor(`/briefs/${brief.date}`)}" data-link>Read full brief</a></p>` : ""}</div><aside class="hero-meta" aria-label="Brief metrics"><div class="metric-grid"><div class="metric"><b>${asList(brief.hot_topics).length}</b><span>Hot topics</span></div><div class="metric"><b>${asList(brief.items).length}</b><span>News items</span></div><div class="metric"><b>${asList(brief.categories).length}</b><span>Categories</span></div><div class="metric"><b>${asList(brief.sources).length}</b><span>Sources</span></div></div><div class="focus-list">${asList(brief.market_focus).map((item) => `<span class="pill">${escapeHtml(item)}</span>`).join("")}</div></aside></section>`;
}

function summarySection(brief) {
  return `<section class="section"><div class="section-head"><h2>Daily overview</h2><p class="section-note">Quick reading entry generated from <code>daily_summary_zh</code>.</p></div><p class="summary-text">${escapeHtml(brief.daily_summary_zh || "")}</p></section>`;
}

function hotTopicsSection(brief) {
  const itemById = new Map(asList(brief.items).map((item) => [item.id, item]));
  const cards = asList(brief.hot_topics)
    .sort((a, b) => (a.rank || 99) - (b.rank || 99))
    .map((topic) => {
      const label = heatLabel(topic.heat_score, topic.heat_label);
      const related = asList(topic.item_ids).map((id) => itemById.get(id)).filter(Boolean);
      return `<article class="topic-card"><div class="item-top"><span class="rank">#${escapeHtml(topic.rank || "")}</span><span class="badge ${heatClass(label)}">${escapeHtml(label)} · ${escapeHtml(topic.heat_score || 0)}</span></div><h3>${escapeHtml(topic.topic)}</h3><p>${escapeHtml(topic.one_line_reason || "")}</p><div class="focus-list">${asList(topic.main_sources).map((source) => `<span class="pill">${escapeHtml(source)}</span>`).join("")}</div>${related.length ? `<div class="related-items"><strong>Related news</strong>${related.map((item) => `<a class="related-link" href="#item-${escapeHtml(item.id)}" data-item-jump="${escapeHtml(item.id)}"><strong>${escapeHtml(item.title_zh || item.title_original)}</strong><span>${escapeHtml(item.source)}</span></a>`).join("")}</div>` : ""}</article>`;
    })
    .join("");
  return `<section class="section"><div class="section-head"><h2>Today's focus ranking</h2><p class="section-note">Built from <code>hot_topics</code>, sorted by rank and heat score.</p></div><div class="topic-grid">${cards}</div></section>`;
}

function categoriesSection(brief) {
  return `<section class="section"><div class="section-head"><h2>Category news</h2><p class="section-note">Categories connect to detailed articles through <code>categories[].item_ids</code>.</p></div><div class="search-row"><input id="news-search" type="search" placeholder="Search title, summary, source or tag" /><button class="filter-button" id="clear-search" type="button">Clear</button></div><div class="category-tabs"><button class="filter-button active" data-category="all" type="button">All</button>${asList(brief.categories).map((category) => `<button class="filter-button" data-category="${escapeHtml(category.slug)}" type="button">${escapeHtml(category.name)}</button>`).join("")}</div><div id="category-panel" class="category-panel"></div></section>`;
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
  buttons.forEach((button) => button.addEventListener("click", () => { state.categorySlug = button.dataset.category; update(); }));
  search?.addEventListener("input", () => { state.query = search.value.trim().toLowerCase(); update(); });
  clear?.addEventListener("click", () => { state.query = ""; search.value = ""; update(); });
  update();
}

function renderItems(brief, categorySlug, query) {
  const byId = new Map(asList(brief.items).map((item) => [item.id, item]));
  const category = asList(brief.categories).find((item) => item.slug === categorySlug);
  const baseItems = category ? asList(category.item_ids).map((id) => byId.get(id)).filter(Boolean) : asList(brief.items);
  const filtered = query ? baseItems.filter((item) => [item.title_zh, item.title_original, item.source, item.category, item.summary_zh, ...asList(item.themes)].join(" ").toLowerCase().includes(query)) : baseItems;
  if (!filtered.length) return `<p class="section-note">No matching news items.</p>`;
  return `<div class="item-list">${filtered.map(renderItem).join("")}</div>`;
}

function renderItem(item) {
  const label = heatLabel(item.heat_score);
  return `<article class="item-card" id="item-${escapeHtml(item.id)}"><div class="item-top"><div class="item-meta"><span>${escapeHtml(item.source)}</span><span>${escapeHtml(item.category)}</span><span>${escapeHtml(item.time_horizon || "")}</span></div><span class="badge ${heatClass(label)}">${label} · ${escapeHtml(item.heat_score || 0)}</span></div><h3>${escapeHtml(item.title_zh || item.title_original)}</h3><p>${escapeHtml(item.summary_zh || "")}</p><div class="focus-list">${asList(item.themes).map((theme) => `<a class="pill" href="${linkFor(`/topics/${slugify(theme)}`)}" data-link>${escapeHtml(theme)}</a>`).join("")}</div>${asList(item.key_facts).length ? `<ul class="facts">${asList(item.key_facts).map((fact) => `<li>${escapeHtml(fact)}</li>`).join("")}</ul>` : ""}<div class="two-col"><div class="detail-box"><strong>Market impact</strong>${escapeHtml(item.market_impact || "")}</div><div class="detail-box"><strong>Tracking value</strong>${escapeHtml(item.tracking_value || "")}</div></div><p><a class="action" href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer">Read source</a></p></article>`;
}

function bindItemJumpControls() {
  document.querySelectorAll("[data-item-jump]").forEach((link) => {
    link.addEventListener("click", (event) => {
      const id = link.dataset.itemJump;
      const target = document.querySelector(`#item-${CSS.escape(id)}`);
      if (!target) return;
      event.preventDefault();
      target.scrollIntoView({ behavior: "smooth", block: "start" });
      document.querySelectorAll(".item-card.highlighted").forEach((node) => node.classList.remove("highlighted"));
      target.classList.add("highlighted");
      window.setTimeout(() => target.classList.remove("highlighted"), 2200);
    });
  });
}

function sourcesSection(brief) {
  return `<section class="section"><div class="section-head"><h2>Original sources</h2><p class="section-note">Source links and access status from <code>sources</code>.</p></div><div class="source-grid">${asList(brief.sources).map((source) => `<a class="source-card" href="${escapeHtml(source.url)}" target="_blank" rel="noreferrer"><strong>${escapeHtml(source.name)}</strong><p>${escapeHtml(source.access || "Unknown access")}</p></a>`).join("")}</div></section>`;
}

function renderArchive() {
  const rows = asList(state.index.briefs).map((brief) => {
    const fullBrief = getBriefByDate(brief.date);
    const itemLinks = asList(fullBrief?.items).slice().sort((a, b) => (b.heat_score || 0) - (a.heat_score || 0)).slice(0, 5).map((item) => `<a class="archive-link" href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer"><strong>${escapeHtml(item.title_zh || item.title_original)}</strong><span>${escapeHtml(item.source)}</span></a>`).join("");
    return `<article class="archive-row"><p class="eyebrow">${escapeHtml(brief.date)}</p><h3><a href="${linkFor(`/briefs/${brief.date}`)}" data-link>${escapeHtml(brief.title)}</a></h3><p>${escapeHtml(brief.summary || "")}</p><div class="focus-list">${asList(brief.top_themes).map((theme) => `<span class="pill">${escapeHtml(theme)}</span>`).join("")}</div>${itemLinks ? `<div class="archive-links">${itemLinks}</div>` : ""}</article>`;
  }).join("");
  app.innerHTML = `<section class="section"><div class="section-head"><h1>Archive</h1><p class="section-note">Daily briefs listed from <code>data/index.json</code>.</p></div><div class="archive-list">${rows}</div></section>`;
}

function renderSearch(query) {
  const input = document.querySelector("#global-search-input");
  if (input) input.value = query || state.globalQuery || "";
  const results = searchItems(query || state.globalQuery);
  app.innerHTML = `<section class="section"><div class="section-head"><h1>Search</h1><p class="section-note">Search all loaded articles by title, summary, source, category and formal tags.</p></div><div class="search-row"><input id="search-page-input" type="search" value="${escapeHtml(query || state.globalQuery || "")}" placeholder="Try Nvidia, AI cloud, Fed policy" /><button class="filter-button" id="search-page-button" type="button">Search</button></div>${results.length ? `<div class="item-list">${results.map((result) => renderSearchResult(result)).join("")}</div>` : `<p class="section-note">No matching articles. Try Nvidia, AI cloud, Fed policy or semiconductors.</p>`}</section>`;
  const pageInput = document.querySelector("#search-page-input");
  const run = () => navigateToSearch(pageInput.value.trim());
  document.querySelector("#search-page-button")?.addEventListener("click", run);
  pageInput?.addEventListener("keydown", (event) => { if (event.key === "Enter") run(); });
}

function renderSearchResult(result) {
  const item = result.item;
  return `<article class="item-card"><div class="item-top"><div class="item-meta"><span>${escapeHtml(result.date)}</span><span>${escapeHtml(item.source)}</span><span>${escapeHtml(item.category)}</span></div><span class="badge ${heatClass(heatLabel(item.heat_score))}">${heatLabel(item.heat_score)} · ${escapeHtml(item.heat_score || 0)}</span></div><h3>${escapeHtml(item.title_zh || item.title_original)}</h3><p>${escapeHtml(item.summary_zh || "")}</p><div class="focus-list">${asList(item.themes).map((theme) => `<a class="pill" href="${linkFor(`/topics/${slugify(theme)}`)}" data-link>${escapeHtml(theme)}</a>`).join("")}</div><p><a class="action" href="${linkFor(`/briefs/${result.date}`)}" data-link>View daily brief</a> <a class="action" href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer">Read source</a></p></article>`;
}

function renderTopics() {
  const themes = collectThemes();
  app.innerHTML = `<section class="section"><div class="section-head"><h1>Topics</h1><p class="section-note">Formal tags generated from <code>items[].themes</code>.</p></div><div class="topic-list">${themes.map((theme) => `<a class="pill" href="${linkFor(`/topics/${slugify(theme)}`)}" data-link>${escapeHtml(theme)}</a>`).join("")}</div></section>`;
}

function renderTopic(slug) {
  const matches = asList(state.brief.items).filter((item) => asList(item.themes).some((theme) => slugify(theme) === slug));
  const title = asList(matches[0]?.themes).find((theme) => slugify(theme) === slug) || slug;
  app.innerHTML = `<section class="section"><div class="section-head"><h1>${escapeHtml(title)}</h1><p class="section-note">Topic-filtered articles from loaded brief data.</p></div>${matches.length ? `<div class="item-list">${matches.map(renderItem).join("")}</div>` : `<p>No related news items.</p>`}</section>`;
}

function getAllBriefs() {
  return state.brief ? [state.brief] : [];
}

function getBriefByDate(date) {
  return getAllBriefs().find((brief) => brief.date === date);
}

function searchItems(query) {
  const normalized = String(query || "").trim().toLowerCase();
  if (!normalized) return [];
  return getAllBriefs().flatMap((brief) => asList(brief.items).map((item) => ({ date: brief.date, item, haystack: [brief.title, brief.deck, brief.daily_summary_zh, item.title_zh, item.title_original, item.source, item.category, item.summary_zh, item.market_impact, item.tracking_value, ...asList(item.themes), ...asList(item.key_facts), ...asList(item.sources_reporting_same_topic)].join(" ").toLowerCase() }))).filter((entry) => entry.haystack.includes(normalized)).sort((a, b) => (b.item.heat_score || 0) - (a.item.heat_score || 0));
}

function tagsSidebar() {
  const tags = formalTags();
  return `<aside class="sidebar" aria-label="Formal tags"><div><p class="eyebrow">Formal tags</p><h2>Hot tags</h2></div><div class="sidebar-list">${tags.slice(0, 14).map((tag) => `<a class="tag-link" href="${linkFor(`/topics/${slugify(tag.name)}`)}" data-link><strong>${escapeHtml(tag.name)}</strong><small>${tag.count}</small></a>`).join("")}</div></aside>`;
}

function formalTags() {
  const counts = new Map();
  getAllBriefs().forEach((brief) => asList(brief.items).forEach((item) => asList(item.themes).forEach((theme) => counts.set(theme, (counts.get(theme) || 0) + 1))));
  return [...counts.entries()].map(([name, count]) => ({ name, count })).sort((a, b) => b.count - a.count || a.name.localeCompare(b.name));
}

function collectThemes() { return formalTags().map((tag) => tag.name); }
function slugify(value = "") { return String(value).trim().toLowerCase().replaceAll("&", "and").replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, ""); }

boot();
