# Cloudflare Pages GitHub Auto Deploy Setup

Target domain:

```text
news.tinydreamlab.com
```

## Setup Steps

1. In Cloudflare dashboard, open Workers & Pages.
2. Create a new Pages project.
3. Connect to Git.
4. Select this repository:

```text
joshua122c/tinydream-news
```

5. Use these build settings:

```text
Framework preset: None
Build command: leave blank
Build output directory: /
Root directory: /
Production branch: main
```

6. Deploy the project.
7. Add custom domain:

```text
news.tinydreamlab.com
```

8. Confirm Cloudflare creates or updates the DNS record for the custom domain.

## Daily Update Contract

The news supply workflow should update:

```text
data/index.json
data/briefs/YYYY-MM-DD.json
```

Then commit and push to GitHub.

Cloudflare Pages will automatically deploy the updated site after each push.

## No D1 Yet

V1.5 intentionally avoids D1, Worker ingestion API, R2, and KV. GitHub is the JSON data store for now.
