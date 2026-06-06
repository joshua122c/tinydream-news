# Tiny Dream News

Static website for `news.tinydreamlab.com`.

## V1.5 architecture

- GitHub stores the website code and daily JSON data.
- Cloudflare Pages connects to this repository.
- Every push to `main` triggers an automatic deploy.
- The news supply workflow updates JSON under `data/`.

## Data paths

```text
data/index.json
data/briefs/YYYY-MM-DD.json
```

## Cloudflare Pages settings

```text
Project name: tinydream-news
Production branch: main
Framework preset: None
Build command: leave blank
Build output directory: /
Root directory: /
Custom domain: news.tinydreamlab.com
```

## Daily update flow

```text
News supply workflow
-> Generate data/briefs/YYYY-MM-DD.json
-> Update data/index.json
-> Commit and push to GitHub
-> Cloudflare Pages auto deploy
-> news.tinydreamlab.com updates
```
