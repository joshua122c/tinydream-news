# Website Data Contract

This folder is the V1.5 JSON data store.

## Files

```text
data/index.json
data/briefs/YYYY-MM-DD.json
```

## `data/index.json`

Used by homepage, archive, and latest daily brief lookup.

Required fields:

- `latest_date`
- `briefs[]`

Each `briefs[]` item should include:

- `date`
- `title`
- `summary`
- `top_themes`
- `hot_topic_count`
- `item_count`
- `generated_at`

## `data/briefs/YYYY-MM-DD.json`

Used by daily brief page, hot topic leaderboard, category news sections, source links, formal tags sidebar, and search.

Required top-level fields:

- `date`
- `title`
- `deck`
- `daily_summary_zh`
- `market_focus`
- `hot_topics`
- `categories`
- `items`
- `sources`
- `generated_at`

## Hot Topic Linking

Every `hot_topics[]` item should include `item_ids`. Every ID must match an `items[].id` value in the same daily brief JSON file.
