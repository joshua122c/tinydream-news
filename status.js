async function renderDataStatus() {
  try {
    const response = await fetch(`/data/index.json?status=${Date.now()}`, { cache: "no-store" });
    if (!response.ok) return;
    const index = await response.json();
    const latest = Array.isArray(index.briefs) ? index.briefs[0] : null;
    if (!latest) return;

    const generated = latest.generated_at ? new Date(latest.generated_at) : null;
    const generatedText = generated && !Number.isNaN(generated.getTime())
      ? generated.toLocaleString("zh-HK", { timeZone: "Asia/Hong_Kong", hour12: false })
      : latest.generated_at || "Unknown";

    const bar = document.createElement("div");
    bar.className = "data-status-bar";
    bar.style.cssText = "border-bottom:1px solid #dedbd2;background:#fbfaf6;color:#485363;font-size:13px;padding:8px 20px;text-align:center;";
    bar.textContent = `\u6700\u5f8c\u751f\u6210\uff1a${generatedText} HKT \u00b7 \u6700\u65b0\u65e5\u671f\uff1a${index.latest_date || latest.date}`;

    const header = document.querySelector(".site-header");
    if (header && !document.querySelector(".data-status-bar")) {
      header.insertAdjacentElement("afterend", bar);
    }
  } catch (error) {
    console.warn("Unable to render data status", error);
  }
}

renderDataStatus();
