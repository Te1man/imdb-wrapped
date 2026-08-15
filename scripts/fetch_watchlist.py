#!/usr/bin/env python3
"""Build watchlist.json from the public IMDb watchlist, with CSV as fallback."""

from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

from user_config import load_config, parse_profile_url

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
CSV_PATH = ROOT / "data" / "watchlist.csv"
OUT = ROOT / "src" / "data" / "watchlist.json"
CACHE = ROOT / "data" / "cache"
_IDS = parse_profile_url(load_config()["imdbUrl"])
WATCHLIST_URL = f"{_IDS['url']}/watchlist/"
GQL_URL = "https://api.graphql.imdb.com/"
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

TYPE_TO_ID = {
    "Movie": "movie",
    "TV Mini Series": "tvMiniSeries",
    "TV Series": "tvSeries",
    "TV Movie": "tvMovie",
    "TV Special": "tvSpecial",
    "TV Episode": "tvEpisode",
    "Short": "short",
    "Video": "video",
    "Video Game": "videoGame",
}

TITLE_QUERY = """
query($ids: [ID!]!) {
  titles(ids: $ids) {
    id
    titleText { text }
    originalTitleText { text }
    titleType { id text }
    releaseYear { year }
    runtime { seconds }
    ratingsSummary { aggregateRating voteCount }
    genres { genres { text } }
    primaryImage { url }
    countriesOfOrigin { countries { id text } }
  }
}
"""

LOCAL_QUERY = """
query($ids: [ID!]!) {
  titles(ids: $ids) {
    id
    titleText { text }
    primaryImage { url }
  }
}
"""


def poster_thumb(url: str | None, width: int = 320) -> str | None:
    if not url:
        return None
    return re.sub(r"\._V1_.*$", f"._V1_UX{width}.jpg", url)


def gql(
    query: str,
    variables: dict | None = None,
    language: str = "en-US",
    country: str | None = None,
) -> dict:
    payload: dict = {"query": query}
    if variables:
        payload["variables"] = variables
    headers = {
        "User-Agent": UA,
        "content-type": "application/json",
        "origin": "https://www.imdb.com",
        "referer": "https://www.imdb.com/",
        "x-imdb-client-name": "imdb-web-next",
        "x-imdb-user-language": language,
    }
    if country:
        headers["x-imdb-user-country"] = country
    req = urllib.request.Request(
        GQL_URL,
        data=json.dumps(payload).encode(),
        headers=headers,
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def apply_ru_locale(items: list[dict]) -> None:
    ids = sorted({tid for it in items if (tid := it.get("id"))})
    if not ids:
        return
    print(f"GraphQL RU watchlist {len(ids)}...", flush=True)
    local: dict[str, dict] = {}
    for i in range(0, len(ids), 40):
        batch = ids[i : i + 40]
        try:
            data = gql(LOCAL_QUERY, {"ids": batch}, language="ru-RU", country="RU")
            for t in (data.get("data") or {}).get("titles") or []:
                if t and t.get("id"):
                    local[t["id"]] = t
        except Exception as exc:  # noqa: BLE001
            print(f"  gql ru fail: {exc}", flush=True)
        time.sleep(0.08)
    for it in items:
        t = local.get(it.get("id") or "")
        if not t:
            continue
        title_ru = ((t.get("titleText") or {}).get("text") or "").strip()
        poster_ru = poster_thumb((t.get("primaryImage") or {}).get("url"))
        if title_ru and title_ru != it.get("title"):
            it["titleRu"] = title_ru
        if poster_ru and poster_ru != it.get("poster"):
            it["posterRu"] = poster_ru

def parse_csv(path: Path) -> list[dict]:
    items = []
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            const = (row.get("Const") or "").strip()
            if not const:
                continue
            year = (row.get("Year") or "").strip()
            runtime = (row.get("Runtime (mins)") or "").strip()
            votes = (row.get("Num Votes") or "").replace(",", "")
            imdb = (row.get("IMDb Rating") or "").strip()
            ttype = (row.get("Title Type") or "Movie").strip()
            original = (row.get("Original Title") or "").strip()
            title = original or (row.get("Title") or "").strip()
            items.append(
                {
                    "id": const,
                    "title": title,
                    "originalTitle": original or None,
                    "year": int(year) if year.isdigit() else None,
                    "type": TYPE_TO_ID.get(ttype, ttype),
                    "runtimeMin": int(runtime) if runtime.isdigit() else None,
                    "imdbRating": float(imdb) if imdb and imdb.lower() not in {"null", "n/a", "none"} else None,
                    "votes": int(votes) if votes.isdigit() else None,
                    "addedOn": (row.get("Created") or "").strip() or None,
                    "genres": [g.strip() for g in (row.get("Genres") or "").split(",") if g.strip()],
                    "directors": [n.strip() for n in (row.get("Directors") or "").split(",") if n.strip()],
                    "url": (row.get("URL") or f"https://www.imdb.com/title/{const}/").strip(),
                    "poster": None,
                    "releaseDate": (row.get("Release Date") or "").strip() or None,
                }
            )
    return items


def jina_fetch(url: str, timeout: int = 70) -> str:
    cmd = [
        "curl", "-sS", "--max-time", str(timeout),
        "-A", UA,
        "-H", "x-timeout: 25",
        f"https://r.jina.ai/{url}",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr[-300:] or f"curl {proc.returncode}")
    return proc.stdout


def live_ids() -> list[str]:
    """Pull current watchlist title IDs from the public IMDb page."""
    RAW.mkdir(parents=True, exist_ok=True)
    found: list[str] = []
    seen: set[str] = set()
    for page in (1, 2):
        url = WATCHLIST_URL if page == 1 else f"{WATCHLIST_URL}?page={page}"
        try:
            text = jina_fetch(url)
        except Exception as exc:  # noqa: BLE001
            print(f"live page {page} failed: {exc}", flush=True)
            continue
        (RAW / f"watchlist-p{page}.md").write_text(text)
        ids = re.findall(r"/title/(tt\d+)", text)
        for tid in ids:
            if tid not in seen:
                seen.add(tid)
                found.append(tid)
        print(f"live page {page}: {len(ids)} ids ({len(found)} unique so far)", flush=True)
        time.sleep(2)
    return found


def enrich(items: list[dict]) -> list[dict]:
    CACHE.mkdir(parents=True, exist_ok=True)
    meta_path = CACHE / "title-meta.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    ids = [it["id"] for it in items if it.get("id") and it["id"] not in meta]
    print(f"GraphQL watchlist enrich {len(ids)} new / {len(items)} total", flush=True)
    for i in range(0, len(ids), 20):
        batch = ids[i : i + 20]
        try:
            data = gql(TITLE_QUERY, {"ids": batch})
            for t in (data.get("data") or {}).get("titles") or []:
                if t and t.get("id"):
                    meta[t["id"]] = t
        except Exception as exc:  # noqa: BLE001
            print(f"  gql fail: {exc}", flush=True)
        time.sleep(0.12)
    meta_path.write_text(json.dumps(meta))

    for it in items:
        t = meta.get(it["id"])
        if not t:
            continue
        it["title"] = ((t.get("titleText") or {}).get("text")) or it["title"]
        orig = (t.get("originalTitleText") or {}).get("text")
        if orig:
            it["originalTitle"] = orig
        it["poster"] = poster_thumb((t.get("primaryImage") or {}).get("url"))
        ry = (t.get("releaseYear") or {}).get("year")
        if ry:
            it["year"] = ry
        rt = (t.get("runtime") or {}).get("seconds")
        if rt:
            it["runtimeMin"] = int(rt / 60)
        rs = t.get("ratingsSummary") or {}
        if rs.get("aggregateRating") is not None:
            it["imdbRating"] = rs["aggregateRating"]
        if rs.get("voteCount") is not None:
            it["votes"] = rs["voteCount"]
        genres = [g["text"] for g in ((t.get("genres") or {}).get("genres") or []) if g.get("text")]
        if genres:
            it["genres"] = genres
        ttype = (t.get("titleType") or {}).get("id")
        if ttype:
            it["type"] = ttype
        countries = [
            {"id": c.get("id"), "name": c.get("text")}
            for c in ((t.get("countriesOfOrigin") or {}).get("countries") or [])
            if c.get("text")
        ]
        if countries:
            it["countries"] = countries
    apply_ru_locale(items)
    return items


def merge_live(csv_items: list[dict], live: list[str]) -> list[dict]:
    by_id = {it["id"]: it for it in csv_items}
    if len(live) < 100:
        print("live scrape too small, keeping CSV order", flush=True)
        return csv_items
    merged = []
    seen = set()
    for tid in live:
        seen.add(tid)
        if tid in by_id:
            merged.append(by_id[tid])
        else:
            merged.append(
                {
                    "id": tid,
                    "title": tid,
                    "originalTitle": None,
                    "year": None,
                    "type": "movie",
                    "runtimeMin": None,
                    "imdbRating": None,
                    "votes": None,
                    "addedOn": None,
                    "genres": [],
                    "directors": [],
                    "url": f"https://www.imdb.com/title/{tid}/",
                    "poster": None,
                    "releaseDate": None,
                    "liveNew": True,
                }
            )
    for it in csv_items:
        if it["id"] not in seen:
            merged.append(it)
    print(f"merged live {len(live)} + csv leftover {len(merged) - len(live)} = {len(merged)}", flush=True)
    return merged


def payload(items: list[dict], source: str) -> dict:
    years = sorted({int(it["addedOn"][:4]) for it in items if it.get("addedOn") and it["addedOn"][:4].isdigit()})
    return {
        "source": source,
        "url": WATCHLIST_URL,
        "updatedAt": datetime.now().isoformat(timespec="seconds"),
        "count": len(items),
        "addedYears": years,
        "items": items,
    }


def main() -> int:
    live = "--live" in sys.argv
    if not CSV_PATH.exists():
        print(f"Missing {CSV_PATH}", flush=True)
        return 1
    items = parse_csv(CSV_PATH)
    source = "csv"
    print(f"CSV watchlist: {len(items)} titles", flush=True)
    if live:
        try:
            ids = live_ids()
            if ids:
                items = merge_live(items, ids)
                source = "imdb+csv" if len(ids) >= 20 else "csv"
        except Exception as exc:  # noqa: BLE001
            print(f"live fetch skipped: {exc}", flush=True)
    items = enrich(items)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload(items, source), ensure_ascii=False))
    posters = sum(1 for it in items if it.get("poster"))
    print(f"Wrote {OUT} ({len(items)} titles, {posters} posters, source={source})", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
