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

PROFILE_QUERY = """
query($id: ID!) {
  userProfile(input: {profileId: $id}) {
    userId
  }
}
"""

WATCHLIST_QUERY = """
query($userId: ID, $after: ID) {
  predefinedList(classType: WATCH_LIST, userId: $userId) {
    items(first: 100, after: $after, sort: {by: CREATED_DATE, order: DESC}) {
      total
      pageInfo { endCursor hasNextPage }
      edges {
        node {
          createdDate
          item {
            ... on Title {
              id
              titleText { text }
              titleType { id }
              releaseYear { year }
              runtime { seconds }
              ratingsSummary { aggregateRating voteCount }
              genres { genres { text } }
              primaryImage { url }
              countriesOfOrigin { countries { id text } }
            }
          }
        }
      }
    }
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


def resolve_user_id() -> str | None:
    if _IDS.get("userConst"):
        return _IDS["userConst"]
    cache_path = CACHE / "identity.json"
    if cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text())
            if isinstance(cached, dict) and cached.get("userId"):
                return str(cached["userId"])
        except Exception:  # noqa: BLE001
            pass
    profile_id = _IDS.get("profileId")
    if not profile_id:
        return None
    try:
        data = gql(PROFILE_QUERY, {"id": profile_id})
        uid = ((data.get("data") or {}).get("userProfile") or {}).get("userId")
        return str(uid) if uid else None
    except Exception as exc:  # noqa: BLE001
        print(f"watchlist userId fail: {exc}", flush=True)
        return None


def live_watchlist() -> list[dict]:
    """Pull the public watchlist via GraphQL (HTML scrape is blocked by WAF)."""
    user_id = resolve_user_id()
    if not user_id:
        raise RuntimeError("Could not resolve IMDb userId for watchlist")
    out: list[dict] = []
    after = None
    total = None
    page = 0
    while True:
        data = gql(WATCHLIST_QUERY, {"userId": user_id, "after": after})
        conn = (((data.get("data") or {}).get("predefinedList") or {}).get("items") or {})
        if total is None:
            total = int(conn.get("total") or 0)
            print(f"GraphQL watchlist total {total}", flush=True)
        for edge in conn.get("edges") or []:
            node = edge.get("node") or {}
            title = node.get("item") or {}
            tid = title.get("id")
            if not tid:
                continue
            created = (node.get("createdDate") or "")[:10] or None
            runtime = (title.get("runtime") or {}).get("seconds")
            rs = title.get("ratingsSummary") or {}
            genres = [
                g["text"]
                for g in ((title.get("genres") or {}).get("genres") or [])
                if g.get("text")
            ]
            countries = [
                {"id": c.get("id"), "name": c.get("text")}
                for c in ((title.get("countriesOfOrigin") or {}).get("countries") or [])
                if c.get("text")
            ]
            out.append(
                {
                    "id": tid,
                    "title": ((title.get("titleText") or {}).get("text") or tid).strip(),
                    "year": (title.get("releaseYear") or {}).get("year"),
                    "type": (title.get("titleType") or {}).get("id") or "movie",
                    "runtimeMin": int(runtime / 60) if runtime else None,
                    "imdbRating": rs.get("aggregateRating"),
                    "votes": rs.get("voteCount"),
                    "addedOn": created,
                    "genres": genres,
                    "directors": [],
                    "url": f"https://www.imdb.com/title/{tid}/",
                    "poster": poster_thumb((title.get("primaryImage") or {}).get("url")),
                    "countries": countries,
                    "liveNew": True,
                }
            )
        page += 1
        print(f"  watchlist page {page}: {len(out)}/{total or '?'}", flush=True)
        page_info = conn.get("pageInfo") or {}
        if not page_info.get("hasNextPage"):
            break
        after = page_info.get("endCursor")
        if not after:
            break
        time.sleep(0.08)
    return out


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


def live_ids_html() -> list[str]:
    """Legacy HTML scrape via jina — kept as a last-resort fallback."""
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


def merge_live(csv_items: list[dict], live_items: list[dict]) -> list[dict]:
    by_id = {it["id"]: it for it in csv_items}
    if len(live_items) < 20:
        print("live watchlist too small, keeping CSV order", flush=True)
        return csv_items
    merged = []
    seen: set[str] = set()
    for live in live_items:
        tid = live.get("id")
        if not tid or tid in seen:
            continue
        seen.add(tid)
        if tid in by_id:
            item = dict(by_id[tid])
            if live.get("addedOn"):
                item["addedOn"] = live["addedOn"]
            # Prefer live poster/meta when CSV row is sparse.
            for key in ("poster", "year", "type", "imdbRating", "votes", "runtimeMin", "genres", "countries"):
                if live.get(key) not in (None, [], "") and not item.get(key):
                    item[key] = live[key]
            merged.append(item)
        else:
            merged.append(live)
    leftover = [it for it in csv_items if it["id"] not in seen]
    if leftover:
        merged.extend(leftover)
    print(
        f"merged live {len(live_items)} + csv leftover {len(leftover)} = {len(merged)}",
        flush=True,
    )
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
            live_items = live_watchlist()
            if live_items:
                items = merge_live(items, live_items)
                source = "imdb+csv"
            else:
                # Last resort: blocked HTML scrape (usually returns 0 now).
                ids = live_ids_html()
                if ids:
                    items = merge_live(
                        items,
                        [{"id": tid, "title": tid, "url": f"https://www.imdb.com/title/{tid}/"} for tid in ids],
                    )
                    source = "imdb+csv" if len(ids) >= 20 else "csv"
        except Exception as exc:  # noqa: BLE001
            print(f"live fetch skipped: {exc}", flush=True)
    items = enrich(items)
    body = json.dumps(payload(items, source), ensure_ascii=False)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(body)
    public_data = ROOT / "public" / "data"
    public_data.mkdir(parents=True, exist_ok=True)
    (public_data / "watchlist.json").write_text(body)
    # Keep the hero "as of" stamp in sync when only the watchlist refreshed.
    for stats_path in (ROOT / "src" / "data" / "stats.json", public_data / "stats.json"):
        if not stats_path.exists():
            continue
        try:
            stats = json.loads(stats_path.read_text())
            stats["generatedAt"] = datetime.now().astimezone().isoformat(timespec="seconds")
            if isinstance(stats.get("profile"), dict):
                stats["profile"]["watchlist"] = len(items)
            stats_path.write_text(json.dumps(stats, ensure_ascii=False))
        except Exception as exc:  # noqa: BLE001
            print(f"stats stamp bump skipped: {exc}", flush=True)
    posters = sum(1 for it in items if it.get("poster"))
    print(f"Wrote {OUT} ({len(items)} titles, {posters} posters, source={source})", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
