# IMDb Wrapped

[![IMDb Wrapped](docs/preview.jpg)](https://telman.ru/imdb)

A personal year-in-review from your public IMDb ratings — Letterboxd Wrapped energy, IMDb palette.

Fork it, paste your profile URL, drop in your export CSVs, and you get the same page with your films, series, map, directors, watchlist, and the rest.

Live demo: [telman.ru/imdb](https://telman.ru/imdb) — data from [telman3D](https://www.imdb.com/user/p.myngzks6b5tydnbl7kkgmnpmqy).

## Make it yours

1. **Fork** this repo (or clone it).
2. Copy the example config and put your IMDb profile URL in it:

```bash
cp config.example.json config.json
```

Open `config.json` and set:

```json
{
  "imdbUrl": "https://www.imdb.com/user/p.xxxxxxxx",
  "displayName": {
    "en": "Alex",
    "ru": "Алекс",
    "ruGenitive": "Алекса"
  },
  "telegram": ""
}
```

Use the URL from the browser after you open **your profile** — it should look like `/user/p.…`, not the old `ur…` id. Ratings and the watchlist must be **public**.

`ruGenitive` is the Russian genitive (“год Алекса”). Leave `telegram` empty, or put `https://t.me/yourname`.

3. Export two CSVs from IMDb and replace the files in `data/`:

| Export | Where in IMDb | Save as |
| --- | --- | --- |
| Ratings | Profile → Ratings → Export | `data/ratings.csv` |
| Watchlist | Profile → Watchlist → Export | `data/watchlist.csv` |

4. Build the page:

```bash
npm install
npm run data:full
npm run dev
```

`data:full` talks to IMDb’s public GraphQL API (posters, people, badges, lists). First run can take a few minutes if you have thousands of ratings.

## Commands

```bash
npm run dev          # local site
npm run data         # rebuild stats from CSV, skip most live fetches
npm run data:full    # stats + live watchlist / profile extras
npm run watchlist    # refresh watchlist.json
npm run build        # production bundle
```

## What you need

- Node 20+
- Python 3.10+
- Public IMDb ratings (and watchlist, if you want that block)

MIT. IMDb is a trademark of IMDb.com, Inc. This is an unofficial fan project and is not affiliated with IMDb.
