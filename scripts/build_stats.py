#!/usr/bin/env python3
"""Parse IMDb ratings markdown dumps, enrich via GraphQL, emit per-year stats."""

from __future__ import annotations

import csv
import json
import re
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from user_config import display_names, load_config, parse_profile_url, telegram_url

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
HISTORY = ROOT / "data" / "history"
OUT = ROOT / "src" / "data"
CACHE = ROOT / "data" / "cache"
YEAR = datetime.now().year
CFG = load_config()
_IDS = parse_profile_url(CFG["imdbUrl"])
IMDB_USER_CONST = _IDS["userConst"]
IMDB_PROFILE_ID = _IDS["profileId"]
FAVORITES_LIST_ID = None
_IDENTITY: dict | None = None

GQL_URL = "https://api.graphql.imdb.com/"
SUGGEST = "https://v2.sg.media-imdb.com/suggestion/{}/{}.json"
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

TYPES = [
    "TV Episode",
    "TV Mini Series",
    "TV Series",
    "TV Movie",
    "TV Special",
    "TV Short",
    "Video Game",
    "Music Video",
    "Podcast Series",
    "Podcast Episode",
    "Video",
    "Short",
    "Movie",
]
TYPE_TO_ID = {
    "TV Episode": "tvEpisode",
    "TV Mini Series": "tvMiniSeries",
    "TV Series": "tvSeries",
    "TV Movie": "tvMovie",
    "TV Special": "tvSpecial",
    "TV Short": "tvShort",
    "Video Game": "videoGame",
    "Music Video": "musicVideo",
    "Podcast Series": "podcastSeries",
    "Podcast Episode": "podcastEpisode",
    "Video": "video",
    "Short": "short",
    "Movie": "movie",
}

MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1
)}

VOTE_RE = re.compile(r"\(([\d.]+)([KMB])?\)")
EP_RE = re.compile(r"^S(\d+)\.E(\d+)$")
YEAR_RE = re.compile(r"^(19|20)\d{2}")
RUNTIME_RE = re.compile(r"(?:(\d+)h)?\s*(\d+)m")
MASHED_RE = re.compile(
    r"^(?P<year>(?:19|20)\d{2})(?:[–-](?P<end>(?:19|20)\d{2})?)?(?P<rest>.*)$"
)


def parse_votes(token: str) -> int | None:
    m = VOTE_RE.search(token.replace("\xa0", " "))
    if not m:
        return None
    n = float(m.group(1))
    suf = m.group(2)
    mult = {None: 1, "K": 1_000, "M": 1_000_000, "B": 1_000_000_000}[suf]
    return int(n * mult)


def parse_runtime(text: str) -> int | None:
    m = RUNTIME_RE.search(text.replace("\xa0", " "))
    if not m:
        hm = re.search(r"(\d+)h(?!\s*\d)", text)
        if hm:
            return int(hm.group(1)) * 60
        return None
    hours = int(m.group(1) or 0)
    mins = int(m.group(2) or 0)
    return hours * 60 + mins


def parse_mashed(line: str) -> dict:
    """Handle lines like '20261h 50mR' or '2026– TV-MATV Series'."""
    info: dict = {}
    m = MASHED_RE.match(line.strip())
    if not m:
        return info
    info["releaseYear"] = int(m.group("year"))
    rest = m.group("rest") or ""
    rt = parse_runtime(rest)
    if rt:
        info["runtimeMin"] = rt
    for t in TYPES:
        if t in rest:
            info["type"] = t
            rest = rest.replace(t, "")
            break
    cert = re.sub(r"\s+", "", rest)
    cert = re.sub(r"(?:\d+h)?\d+m", "", cert)
    cert = cert.replace("–", "").replace("-", "")
    if cert and len(cert) <= 8:
        info["certificate"] = cert
    return info


def parse_credits_line(line: str) -> dict:
    credits: dict[str, str] = {}
    for key in ("Director", "Directors", "Creator", "Creators", "Writers", "Writer", "Stars"):
        if key in line:
            credits["raw"] = line
            break
    return credits


def parse_block(block: str) -> dict | None:
    lines = [ln.strip() for ln in block.strip().splitlines() if ln.strip()]
    if not lines or not lines[0].startswith("Rated on "):
        return None
    try:
        rated = datetime.strptime(lines[0].replace("Rated on ", ""), "%b %d, %Y")
    except ValueError:
        return None
    title_line = next((ln for ln in lines[1:] if re.match(r"^\d+\. ", ln)), None)
    if not title_line:
        return None
    m = re.match(r"^(\d+)\. (.+)$", title_line)
    if not m:
        return None
    item = {
        "index": int(m.group(1)),
        "title": m.group(2).strip(),
        "ratedOn": rated.strftime("%Y-%m-%d"),
        "ratedYear": rated.year,
        "ratedMonth": rated.month,
        "ratedDay": rated.day,
    }
    body = lines[lines.index(title_line) + 1 :]
    # Trim trailing chrome
    cut = []
    for ln in body:
        if ln.startswith("Rated on ") or ln in {"Menu", "Sign in", "Next"}:
            break
        cut.append(ln)
        if ln == "Rate":
            break
    body = cut

    i = 0
    if i < len(body) and EP_RE.match(body[i]):
        sm = EP_RE.match(body[i])
        item["season"] = int(sm.group(1))
        item["episode"] = int(sm.group(2))
        i += 1
        if i < len(body) and not YEAR_RE.match(body[i]) and body[i] not in TYPES:
            item["series"] = body[i]
            i += 1

    while i < len(body):
        ln = body[i]
        if ln in TYPES:
            item["type"] = ln
            i += 1
            continue
        if YEAR_RE.match(ln) or (ln[:4].isdigit() and int(ln[:4]) >= 1870):
            mashed = parse_mashed(ln)
            item.update({k: v for k, v in mashed.items() if k not in item})
            i += 1
            continue
        if parse_runtime(ln) and "h" in ln or re.fullmatch(r"\d+m", ln):
            item["runtimeMin"] = parse_runtime(ln)
            i += 1
            continue
        if ln in {"TV-MA", "TV-14", "TV-PG", "TV-Y7", "TV-G", "TV-Y", "R", "PG-13", "PG", "G", "NC-17", "Approved", "Not Rated", "Unrated"}:
            item["certificate"] = ln
            i += 1
            continue
        votes = parse_votes(ln)
        if votes is not None:
            item["votes"] = votes
            i += 1
            continue
        if re.fullmatch(r"\d+(?:\.\d+)?", ln):
            val = float(ln)
            # IMDb rating is first x.x, user rating is last integer before Rate
            if "imdbRating" not in item and "." in ln:
                item["imdbRating"] = val
            elif "imdbRating" not in item and val <= 10:
                item["imdbRating"] = val
            else:
                item["userRating"] = int(val) if val == int(val) and 1 <= val <= 10 else val
            i += 1
            continue
        if ln in {"Rate", "Mark as watched"}:
            break
        i += 1

    # User rating is the last 1-10 integer before Rate
    for ln in reversed(body):
        if ln.isdigit() and 1 <= int(ln) <= 10:
            item["userRating"] = int(ln)
            break
        if ln == "Rate":
            continue

    if "type" not in item:
        if item.get("season") is not None:
            item["type"] = "TV Episode"
        else:
            item["type"] = "Movie"

    # credits after Rate / plot
    rest = block.split("Rate", 1)[-1]
    cred = re.search(r"(Director|Directors|Creator|Creators|Writers|Writer|Stars).+", rest)
    if cred:
        item["creditsRaw"] = cred.group(0).split("\n")[0][:400]

    return item


def parse_file(path: Path) -> list[dict]:
    text = path.read_text(errors="replace")
    chunks = re.split(r"\n(?=Rated on )", text)
    items = []
    for chunk in chunks:
        if not chunk.startswith("Rated on "):
            # first file header + first block
            idx = chunk.find("Rated on ")
            if idx == -1:
                continue
            chunk = chunk[idx:]
        rec = parse_block(chunk)
        if rec:
            items.append(rec)
    return items


CSV_TYPE = {v: k for k, v in TYPE_TO_ID.items()} | {
    "tvEpisode": "TV Episode",
    "tvSeries": "TV Series",
    "tvMiniSeries": "TV Mini Series",
    "tvMovie": "TV Movie",
    "tvSpecial": "TV Special",
    "tvShort": "TV Short",
    "videoGame": "Video Game",
    "musicVideo": "Music Video",
    "podcastSeries": "Podcast Series",
    "podcastEpisode": "Podcast Episode",
    "video": "Video",
    "short": "Short",
    "movie": "Movie",
}


def _blank(val: str | None) -> bool:
    s = (val or "").strip()
    return not s or s.lower() in {"null", "n/a", "none", "nan"}


def parse_int(val: str | None) -> int | None:
    if _blank(val):
        return None
    s = (val or "").strip().replace(",", "")
    if s.isdigit() or (s.startswith("-") and s[1:].isdigit()):
        return int(s)
    try:
        return int(float(s))
    except ValueError:
        return None


def parse_float(val: str | None) -> float | None:
    if _blank(val):
        return None
    try:
        return float((val or "").strip().replace(",", ""))
    except ValueError:
        return None


def parse_csv(path: Path) -> list[dict]:
    items = []
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            rated = (row.get("Date Rated") or "").strip()
            if not rated:
                continue
            try:
                dt = datetime.strptime(rated, "%Y-%m-%d")
            except ValueError:
                continue
            ttype = (row.get("Title Type") or "Movie").strip()
            type_id = TYPE_TO_ID.get(ttype, ttype[:1].lower() + ttype[1:].replace(" ", ""))
            const = (row.get("Const") or "").strip()
            original = (row.get("Original Title") or "").strip()
            title = original or (row.get("Title") or "").strip()
            series = None
            if type_id == "tvEpisode" and ": " in original:
                series, ep = original.split(": ", 1)
                # "Batman: Caped Crusader: Savage Night" → series keeps colons
                if original.count(": ") >= 2:
                    series, ep = original.rsplit(": ", 1)
                title = ep
            rated_on = dt.strftime("%Y-%m-%d")
            item = {
                "id": const or None,
                "title": title,
                "ratedOn": rated_on,
                "lastRatedOn": rated_on,
                "ratedYear": dt.year,
                "ratedMonth": dt.month,
                "ratedDay": dt.day,
                "type": ttype if ttype in TYPE_TO_ID else CSV_TYPE.get(ttype, ttype),
                "typeId": type_id,
                "releaseYear": parse_int(row.get("Year")),
                "releaseDate": (row.get("Release Date") or "").strip() or None,
                "runtimeMin": parse_int(row.get("Runtime (mins)") or row.get("Runtime (Mins)")),
                "userRating": parse_int(row.get("Your Rating")),
                "imdbRating": parse_float(row.get("IMDb Rating")),
                "votes": parse_int(row.get("Num Votes")),
                "genres": [g.strip() for g in (row.get("Genres") or "").split(",") if g.strip()],
                "directors": [
                    {"name": n.strip()}
                    for n in (row.get("Directors") or "").split(",")
                    if n.strip()
                ],
                "url": (row.get("URL") or "").strip() or None,
            }
            if series:
                item["series"] = series
            items.append(item)
    return items


def load_all() -> list[dict]:
    csv_path = ROOT / "data" / "ratings.csv"
    if csv_path.exists():
        items = parse_csv(csv_path)
        items.sort(key=lambda r: (r["ratedOn"], r.get("title") or ""), reverse=True)
        print(f"Loaded {len(items)} ratings from {csv_path.name}", flush=True)
        return items
    files = sorted(RAW.glob("ratings-p*.md"))
    seen = set()
    items = []
    for f in files:
        for rec in parse_file(f):
            key = (rec["ratedOn"], rec["title"], rec.get("series"), rec.get("season"), rec.get("episode"), rec.get("index"))
            if key in seen:
                continue
            seen.add(key)
            items.append(rec)
    items.sort(key=lambda r: (r["ratedOn"], r.get("index") or 0), reverse=True)
    return items


def http_json(
    url: str,
    data: dict | None = None,
    retries: int = 3,
    language: str = "en-US",
    country: str | None = None,
) -> dict:
    body = None
    headers = {"User-Agent": UA, "Accept": "application/json"}
    if data is not None:
        body = json.dumps(data).encode()
        headers.update({
            "content-type": "application/json",
            "origin": "https://www.imdb.com",
            "referer": "https://www.imdb.com/",
            "x-imdb-client-name": "imdb-web-next",
            "x-imdb-user-language": language,
        })
        if country:
            headers["x-imdb-user-country"] = country
    req = urllib.request.Request(url, data=body, headers=headers)
    last = None
    for i in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(0.6 * (i + 1))
    raise RuntimeError(last)


def gql(
    query: str,
    variables: dict | None = None,
    language: str = "en-US",
    country: str | None = None,
) -> dict:
    payload: dict = {"query": query}
    if variables:
        payload["variables"] = variables
    return http_json(GQL_URL, payload, language=language, country=country)


PROFILE_QUERY = """
query($id: ID!) {
  userProfile(input: {profileId: $id}) {
    profileId
    userId
    username { text }
    primaryImage { image { url } }
  }
}
"""

LISTS_QUERY = """
query($userId: ID) {
  lists(listOwnerUserId: $userId, first: 20, filter: {classTypes: [LIST]}) {
    edges {
      node {
        id
        name { originalText }
        items(first: 1) { total }
      }
    }
  }
}
"""

BADGES_QUERY = """
query($userId: ID!) {
  userBadges(first: 1, input: {userId: $userId}) { total }
}
"""

FAVORITE_TITLES_QUERY = """
query($id: ID!) {
  list(id: $id) {
    items(first: 12) {
      edges {
        node {
          item {
            ... on Title {
              id
              titleText { text }
              releaseYear { year }
              primaryImage { url }
            }
          }
        }
      }
    }
  }
}
"""


def hydrate_identity() -> dict:
    """Fill userConst / profileId / username / avatar from the public profile URL."""
    global IMDB_USER_CONST, IMDB_PROFILE_ID, FAVORITES_LIST_ID, _IDENTITY
    if _IDENTITY is not None:
        return _IDENTITY
    info = {
        "username": None,
        "avatar": None,
        "userId": IMDB_USER_CONST,
        "profileId": IMDB_PROFILE_ID,
        "url": _IDS["url"],
        "badges": 0,
        "lists": [],
        "favorites": [],
    }
    if IMDB_PROFILE_ID:
        try:
            data = gql(PROFILE_QUERY, {"id": IMDB_PROFILE_ID})
            node = ((data.get("data") or {}).get("userProfile") or {})
            if node.get("userId"):
                IMDB_USER_CONST = node["userId"]
                info["userId"] = IMDB_USER_CONST
            if node.get("profileId"):
                IMDB_PROFILE_ID = node["profileId"]
                info["profileId"] = IMDB_PROFILE_ID
            info["username"] = ((node.get("username") or {}).get("text") or "").strip() or None
            info["avatar"] = ux_image(
                (((node.get("primaryImage") or {}).get("image") or {}).get("url")),
                256,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"Profile identity fail: {exc}", flush=True)
    if IMDB_USER_CONST:
        try:
            data = gql(LISTS_QUERY, {"userId": IMDB_USER_CONST})
            edges = (((data.get("data") or {}).get("lists") or {}).get("edges") or [])
            lists = []
            for edge in edges:
                node = edge.get("node") or {}
                lid = node.get("id")
                name = ((node.get("name") or {}).get("originalText") or "").strip()
                count = int(((node.get("items") or {}).get("total") or 0))
                if lid and name:
                    lists.append({"name": name, "count": count, "id": lid})
            info["lists"] = lists
            fav = next((item for item in lists if "favorite" in item["name"].lower()), None)
            if fav or lists:
                FAVORITES_LIST_ID = (fav or lists[0])["id"]
        except Exception as exc:  # noqa: BLE001
            print(f"Lists fail: {exc}", flush=True)
        try:
            data = gql(BADGES_QUERY, {"userId": IMDB_USER_CONST})
            info["badges"] = int((((data.get("data") or {}).get("userBadges") or {}).get("total") or 0))
        except Exception as exc:  # noqa: BLE001
            print(f"Badges fail: {exc}", flush=True)
    if FAVORITES_LIST_ID:
        try:
            data = gql(FAVORITE_TITLES_QUERY, {"id": FAVORITES_LIST_ID})
            edges = ((((data.get("data") or {}).get("list") or {}).get("items") or {}).get("edges") or [])
            favs = []
            for edge in edges:
                title = ((edge.get("node") or {}).get("item") or {})
                tid = title.get("id")
                name = ((title.get("titleText") or {}).get("text") or "").strip()
                if not tid or not name:
                    continue
                year = (title.get("releaseYear") or {}).get("year")
                favs.append({
                    "id": tid,
                    "title": name,
                    "year": year,
                    "poster": ux_image(((title.get("primaryImage") or {}).get("url")), 200),
                })
            info["favorites"] = favs
        except Exception as exc:  # noqa: BLE001
            print(f"Favorite titles fail: {exc}", flush=True)
    cache_path = CACHE / "identity.json"
    if cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text())
            if isinstance(cached, dict):
                for key, value in cached.items():
                    if info.get(key) in (None, 0, [], ""):
                        info[key] = value
                IMDB_USER_CONST = info.get("userId") or IMDB_USER_CONST
                IMDB_PROFILE_ID = info.get("profileId") or IMDB_PROFILE_ID
                FAVORITES_LIST_ID = FAVORITES_LIST_ID or (info.get("favoritesListId"))
        except Exception as exc:  # noqa: BLE001
            print(f"Identity cache fail: {exc}", flush=True)
    info["favoritesListId"] = FAVORITES_LIST_ID
    CACHE.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(info, ensure_ascii=False))
    print(
        f"Identity {info.get('username') or '?'}  {IMDB_USER_CONST}  {IMDB_PROFILE_ID}",
        flush=True,
    )
    _IDENTITY = info
    return info


PROFILE_INTERESTS_QUERY = """
query($id: ID!, $first: Int!) {
  userProfile(input: {profileId: $id}) {
    ratingsAggregation(inputs: [{type: INTERESTS, first: $first, sort: {by: COUNT, order: DESC}}]) {
      buckets {
        count
        averageRating
        text { id text }
      }
    }
  }
}
"""

INTEREST_META_QUERY = """
query($ids: [ID!]!) {
  interests(ids: $ids) {
    id
    type
    primaryImage { url }
  }
}
"""

FAVORITE_PEOPLE_QUERY = """
query($userId: ID, $classType: ListClassId!) {
  predefinedList(classType: $classType, userId: $userId) {
    items(first: 50) {
      edges {
        node {
          item {
            ... on Name {
              id
              nameText { text }
              primaryImage { url }
            }
          }
        }
      }
    }
  }
}
"""


def ux_image(url: str | None, width: int = 480) -> str | None:
    if not url:
        return None
    url = url.split("?")[0]
    return re.sub(r"\._V1_.*$", f"._V1_UX{width}.jpg", url)


def fetch_profile_interests(limit: int = 24) -> list[dict]:
    """Public IMDb /interests buckets: subgenres by how often they were rated."""
    cache_path = CACHE / "profile-interests.json"
    if not IMDB_PROFILE_ID:
        if cache_path.exists():
            cached = json.loads(cache_path.read_text())
            if isinstance(cached, list) and cached:
                return cached
        return []
    try:
        data = gql(PROFILE_INTERESTS_QUERY, {"id": IMDB_PROFILE_ID, "first": 80})
        buckets = (
            (((data.get("data") or {}).get("userProfile") or {}).get("ratingsAggregation") or [{}])[0]
            .get("buckets")
            or []
        )
        ids = [((b.get("text") or {}).get("id")) for b in buckets if (b.get("text") or {}).get("id")]
        meta = {}
        if ids:
            raw = gql(INTEREST_META_QUERY, {"ids": ids})
            for node in (raw.get("data") or {}).get("interests") or []:
                if node.get("id"):
                    meta[node["id"]] = node
        out = []
        for bucket in buckets:
            text = bucket.get("text") or {}
            iid = text.get("id")
            name = text.get("text")
            info = meta.get(iid) or {}
            if info.get("type") != "SUBGENRE" or not iid or not name:
                continue
            avg = bucket.get("averageRating")
            out.append({
                "id": iid,
                "name": name,
                "count": int(bucket.get("count") or 0),
                "avgRating": round(float(avg), 1) if avg is not None else None,
                "image": ux_image(((info.get("primaryImage") or {}).get("url"))),
                "url": f"https://www.imdb.com/interest/{iid}/",
            })
            if len(out) >= limit:
                break
        if out:
            CACHE.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(out, ensure_ascii=False))
            print(f"Profile interests: {len(out)} subgenres", flush=True)
            return out
    except Exception as exc:  # noqa: BLE001
        print(f"Profile interests fail: {exc}", flush=True)
    if cache_path.exists():
        cached = json.loads(cache_path.read_text())
        if isinstance(cached, list) and cached:
            print(f"Profile interests cache: {len(cached)}", flush=True)
            return cached
    return []


def fetch_favorite_people() -> list[dict]:
    """Public IMDb favorite people list (predefined FAVORITE_ACTORS)."""
    cache_path = CACHE / "favorite-people.json"
    if not IMDB_USER_CONST:
        if cache_path.exists():
            cached = json.loads(cache_path.read_text())
            if isinstance(cached, list) and cached:
                return cached
        return []
    try:
        data = gql(
            FAVORITE_PEOPLE_QUERY,
            {"userId": IMDB_USER_CONST, "classType": "FAVORITE_ACTORS"},
        )
        edges = (
            (((data.get("data") or {}).get("predefinedList") or {}).get("items") or {}).get("edges")
            or []
        )
        out = []
        for edge in edges:
            person = ((edge.get("node") or {}).get("item") or {})
            nid = person.get("id")
            name = ((person.get("nameText") or {}).get("text") or "").strip()
            if not nid or not name:
                continue
            out.append({
                "id": nid,
                "name": name,
                "poster": ux_image(((person.get("primaryImage") or {}).get("url")), 256),
            })
        if out:
            CACHE.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(out, ensure_ascii=False))
            print(f"Favorite people: {len(out)}", flush=True)
            return out
    except Exception as exc:  # noqa: BLE001
        print(f"Favorite people fail: {exc}", flush=True)
    if cache_path.exists():
        cached = json.loads(cache_path.read_text())
        if isinstance(cached, list) and cached:
            print(f"Favorite people cache: {len(cached)}", flush=True)
            return cached
    return []


LIST_DATES_QUERY = """
query($id: ID!, $after: ID) {
  list(id: $id) {
    items(first: 100, after: $after) {
      pageInfo { endCursor hasNextPage }
      edges {
        node {
          createdDate
          item { ... on Title { id } }
        }
      }
    }
  }
}
"""

USER_RATINGS_QUERY = """
query($id: ID!, $after: String) {
  userRatings(userId: $id, first: 100, after: $after, sort: {by: MOST_RECENT, order: DESC}) {
    total
    pageInfo { endCursor hasNextPage }
    edges {
      node {
        title { id }
        userRating { date value }
      }
    }
  }
}
"""


def load_historical_first_dates() -> dict[str, str]:
    """Earliest Date Rated from older IMDb exports. CSV Date Rated is overwritten on a re-rate."""
    out: dict[str, str] = {}
    paths = []
    if HISTORY.exists():
        paths.extend(sorted(HISTORY.glob("*.csv")))
    for path in paths:
        with path.open(newline="", encoding="utf-8") as fh:
            n = 0
            for row in csv.DictReader(fh):
                tid = (row.get("Const") or "").strip()
                dated = (row.get("Date Rated") or "").strip()[:10]
                if not tid or len(dated) < 10:
                    continue
                if tid not in out or dated < out[tid]:
                    out[tid] = dated
                    n += 1
            print(f"History {path.name}: {n} first-seen dates", flush=True)
    return out


def fetch_list_first_dates(list_id: str | None) -> dict[str, str]:
    """Earliest date a title appeared on a public IMDb list (e.g. favorites)."""
    out: dict[str, str] = {}
    if not list_id:
        return out
    after = None
    try:
        while True:
            variables: dict = {"id": list_id}
            if after:
                variables["after"] = after
            data = gql(LIST_DATES_QUERY, variables)
            conn = ((((data.get("data") or {}).get("list") or {}).get("items") or {}))
            for edge in conn.get("edges") or []:
                node = edge.get("node") or {}
                tid = ((node.get("item") or {}).get("id"))
                created = (node.get("createdDate") or "")[:10]
                if tid and created and (tid not in out or created < out[tid]):
                    out[tid] = created
            page = conn.get("pageInfo") or {}
            if not page.get("hasNextPage"):
                break
            after = page.get("endCursor")
            if not after:
                break
            time.sleep(0.08)
    except Exception as exc:  # noqa: BLE001
        print(f"  list {list_id} dates fail: {exc}", flush=True)
    return out


def fetch_all_user_ratings() -> dict[str, dict]:
    """Latest score + last-modified date for every public rating."""
    cache_path = CACHE / "user-ratings.json"
    if cache_path.exists():
        cached = json.loads(cache_path.read_text())
        rows = cached.get("ratings") if isinstance(cached, dict) else None
        if isinstance(rows, dict) and rows:
            print(f"User ratings cache: {len(rows)} titles", flush=True)
            return rows
    if not IMDB_USER_CONST:
        return {}
    out: dict[str, dict] = {}
    after = None
    total = None
    pages = 0
    try:
        while True:
            variables: dict = {"id": IMDB_USER_CONST}
            if after:
                variables["after"] = after
            data = gql(USER_RATINGS_QUERY, variables)
            conn = ((data.get("data") or {}).get("userRatings") or {})
            if total is None:
                total = conn.get("total")
                print(f"GraphQL userRatings total {total}", flush=True)
            for edge in conn.get("edges") or []:
                node = edge.get("node") or {}
                tid = ((node.get("title") or {}).get("id"))
                rating = node.get("userRating") or {}
                dated = (rating.get("date") or "")[:10]
                value = rating.get("value")
                if tid and dated and value is not None:
                    out[tid] = {"date": dated, "value": int(value)}
            pages += 1
            if pages % 10 == 0:
                print(f"  ratings {len(out)}/{total or '?'}", flush=True)
            page = conn.get("pageInfo") or {}
            if not page.get("hasNextPage"):
                break
            after = page.get("endCursor")
            if not after:
                break
            time.sleep(0.08)
    except Exception as exc:  # noqa: BLE001
        print(f"  userRatings fail: {exc}", flush=True)
        if cache_path.exists():
            return (json.loads(cache_path.read_text()).get("ratings") or {})
    CACHE.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps({"count": len(out), "ratings": out}, ensure_ascii=False))
    print(f"Wrote {cache_path} ({len(out)} titles, {pages} pages)", flush=True)
    return out


def apply_first_rated(items: list[dict]) -> list[dict]:
    """Keep each title in the year it was first rated; always use the latest score.

    IMDb's CSV Date Rated is overwritten on a re-rate. We take the earliest date
    we have ever seen (previous builds + public list add dates) for the year
    bucket, and leave userRating as the current value from the CSV / GraphQL.
    """
    CACHE.mkdir(parents=True, exist_ok=True)
    cache_path = CACHE / "first-rated.json"
    cache: dict[str, str] = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    list_dates = fetch_list_first_dates(FAVORITES_LIST_ID)
    hist_dates = load_historical_first_dates()
    gql_ratings = fetch_all_user_ratings()
    if list_dates:
        print(f"List first-dates: {len(list_dates)} titles from favorites", flush=True)

    moved = 0
    score_updated = 0
    for it in items:
        tid = it.get("id")
        g = gql_ratings.get(tid) if tid else None
        if g:
            if it.get("userRating") != g["value"]:
                it["userRating"] = g["value"]
                score_updated += 1
            it["lastRatedOn"] = g["date"]
        last = it.get("lastRatedOn") or it.get("ratedOn")
        it["lastRatedOn"] = last
        candidates = [
            d
            for d in (
                last,
                cache.get(tid) if tid else None,
                list_dates.get(tid) if tid else None,
                hist_dates.get(tid) if tid else None,
            )
            if d
        ]
        first = min(candidates)
        if tid:
            prev = cache.get(tid)
            cache[tid] = first if not prev else min(prev, first)
            first = cache[tid]
        if last and first < last:
            moved += 1
        dt = datetime.strptime(first, "%Y-%m-%d")
        it["firstRatedOn"] = first
        it["ratedOn"] = first
        it["ratedYear"] = dt.year
        it["ratedMonth"] = dt.month
        it["ratedDay"] = dt.day

    cache_path.write_text(json.dumps(cache, sort_keys=True))
    items.sort(key=lambda r: (r["ratedOn"], r.get("title") or ""), reverse=True)
    print(f"Latest scores from GraphQL: {score_updated}", flush=True)
    print(f"Re-rates kept in original year: {moved}", flush=True)
    return items


def slug(title: str) -> str:
    s = title.lower()
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s[:80] or "x"


def suggestion(title: str) -> list[dict]:
    s = slug(title)
    letter = s[0] if s and s[0].isalpha() else "x"
    url = SUGGEST.format(letter, s.replace("_", "_"))
    # IMDb suggestion uses underscores
    url = f"https://v2.sg.media-imdb.com/suggestion/{letter}/{s}.json"
    try:
        data = http_json(url)
    except Exception:
        return []
    return data.get("d") or []


def main_search(term: str, first: int = 12) -> list[dict]:
    query = """
    query($term: String!, $first: Int!) {
      mainSearch(first: $first, options: { searchTerm: $term, type: TITLE }) {
        edges {
          node {
            entity {
              ... on Title {
                id
                titleText { text }
                titleType { id }
                releaseYear { year }
                series { series { id titleText { text } } }
              }
            }
          }
        }
      }
    }
    """
    try:
        data = gql(query, {"term": term, "first": first})
    except Exception:
        return []
    edges = (((data.get("data") or {}).get("mainSearch") or {}).get("edges")) or []
    out = []
    for e in edges:
        ent = ((e.get("node") or {}).get("entity")) or {}
        if ent.get("id"):
            out.append(ent)
    return out


TITLE_QUERY = """
query($ids: [ID!]!) {
  titles(ids: $ids) {
    id
    titleText { text }
    titleType { id text }
    releaseYear { year }
    runtime { seconds }
    ratingsSummary { aggregateRating voteCount }
    genres { genres { text } }
    primaryImage { url }
    series { series { id titleText { text } primaryImage { url } releaseYear { year } } episodeNumber { seasonNumber episodeNumber } }
    countriesOfOrigin { countries { id text } }
    spokenLanguages { spokenLanguages { id text } }
    interests(first: 12) { edges { node { id primaryText { text } } } }
    keywords(first: 8) { edges { node { text } } }
    principalCredits {
      category { text }
      credits { name { id nameText { text } } }
    }
  }
}
"""

LANG_QUERY = """
query($ids: [ID!]!) {
  titles(ids: $ids) {
    id
    spokenLanguages { spokenLanguages { id text } }
  }
}
"""

THEME_QUERY = """
query($ids: [ID!]!) {
  titles(ids: $ids) {
    id
    interests(first: 12) { edges { node { id primaryText { text } } } }
    keywords(first: 8) { edges { node { text } } }
  }
}
"""

NAMES_QUERY = """
query($ids: [ID!]!) {
  names(ids: $ids) {
    id
    nameText { text }
    primaryImage { url }
    images(first: 1) { edges { node { url } } }
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


def fetch_ru_titles(ids: list[str]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for i in range(0, len(ids), 40):
        batch = ids[i : i + 40]
        try:
            data = gql(LOCAL_QUERY, {"ids": batch}, language="ru-RU", country="RU")
            for t in (data.get("data") or {}).get("titles") or []:
                if t and t.get("id"):
                    out[t["id"]] = t
        except Exception as exc:  # noqa: BLE001
            print(f"  gql ru batch fail: {exc}", flush=True)
        time.sleep(0.08)
    return out


def apply_ru_locale(items: list[dict]) -> None:
    ids = sorted({tid for it in items if (tid := it.get("id"))})
    if not ids:
        return
    print(f"GraphQL RU titles {len(ids)}...", flush=True)
    local = fetch_ru_titles(ids)
    for it in items:
        tid = it.get("id")
        t = local.get(tid or "")
        if not t:
            continue
        title_ru = ((t.get("titleText") or {}).get("text") or "").strip()
        poster_ru = poster_thumb((t.get("primaryImage") or {}).get("url"))
        if title_ru and title_ru != it.get("title"):
            it["titleRu"] = title_ru
        if poster_ru and poster_ru != it.get("poster"):
            it["posterRu"] = poster_ru


def spoken_langs(title: dict) -> list[dict]:
    return [
        {"id": lang.get("id"), "name": lang.get("text")}
        for lang in ((title.get("spokenLanguages") or {}).get("spokenLanguages") or [])
        if lang.get("text")
    ]


def interests_of(title: dict) -> list[dict]:
    out = []
    for edge in ((title.get("interests") or {}).get("edges") or []):
        node = edge.get("node") or {}
        name = ((node.get("primaryText") or {}).get("text") or "").strip()
        if name:
            out.append({"id": node.get("id"), "name": name})
    return out


def keywords_of(title: dict) -> list[str]:
    out = []
    for edge in ((title.get("keywords") or {}).get("edges") or []):
        node = edge.get("node") or {}
        text = node.get("text")
        if isinstance(text, dict):
            text = text.get("text")
        if text:
            out.append(str(text).strip())
    return out


def credits_of(title: dict, category: str) -> list[dict]:
    out = []
    for block in title.get("principalCredits") or []:
        cat = ((block.get("category") or {}).get("text") or "").lower()
        if category.lower() in cat:
            for c in block.get("credits") or []:
                name = ((c.get("name") or {}).get("nameText") or {}).get("text")
                nid = (c.get("name") or {}).get("id")
                if name:
                    out.append({"id": nid, "name": name})
    return out


def resolve_id(item: dict, cache: dict) -> str | None:
    key = json.dumps(
        {
            "t": item["title"],
            "s": item.get("series"),
            "y": item.get("releaseYear"),
            "ty": item.get("type"),
            "se": item.get("season"),
            "ep": item.get("episode"),
        },
        sort_keys=True,
    )
    if key in cache:
        return cache[key]
    ttype = TYPE_TO_ID.get(item.get("type") or "", "")
    found = None
    if ttype == "tvEpisode" and item.get("series"):
        term = f"{item['title']} {item['series']}"
        for ent in main_search(term, 16):
            if (ent.get("titleType") or {}).get("id") != "tvEpisode":
                continue
            series_name = (((ent.get("series") or {}).get("series") or {}).get("titleText") or {}).get("text")
            if series_name and series_name.lower() == item["series"].lower():
                if (ent.get("titleText") or {}).get("text", "").lower() == item["title"].lower():
                    found = ent["id"]
                    break
                if not found:
                    found = ent["id"]
        if not found:
            for ent in main_search(item["series"], 8):
                if (ent.get("titleType") or {}).get("id") in {"tvSeries", "tvMiniSeries"}:
                    if (ent.get("titleText") or {}).get("text", "").lower() == item["series"].lower():
                        found = ent["id"]  # series poster fallback
                        break
    else:
        for hit in suggestion(item["title"]):
            hid = hit.get("id") or ""
            if not hid.startswith("tt"):
                continue
            qid = hit.get("qid") or ""
            if ttype and qid and qid != ttype and not (
                ttype == "tvMiniSeries" and qid in {"tvSeries", "tvMiniSeries"}
            ):
                continue
            if item.get("releaseYear") and hit.get("y") and hit["y"] != item["releaseYear"]:
                continue
            if (hit.get("l") or "").lower() == item["title"].lower():
                found = hid
                break
            if not found:
                found = hid
        if not found:
            for ent in main_search(item["title"], 8):
                if ttype and (ent.get("titleType") or {}).get("id") not in {ttype, ttype.replace("Mini", "")}:
                    continue
                if (ent.get("titleText") or {}).get("text", "").lower() == item["title"].lower():
                    found = ent["id"]
                    break
                if not found:
                    found = ent.get("id")
    cache[key] = found
    return found


def apply_suggestion_hit(item: dict, hit: dict) -> None:
    hid = hit.get("id")
    # Never replace a CSV / already-resolved IMDb id (e.g. Batman Begins vs 1966 Batman).
    if hid and str(hid).startswith("tt") and not item.get("id"):
        item["id"] = hid
    img = (hit.get("i") or {}).get("imageUrl")
    if img:
        item["poster"] = poster_thumb(img)
    if hit.get("y") and not item.get("releaseYear"):
        item["releaseYear"] = hit["y"]
    stars = hit.get("s") or ""
    if stars and not item.get("stars"):
        item["stars"] = [{"name": n.strip()} for n in stars.split(",") if n.strip()]


def fast_enrich(items: list[dict]) -> list[dict]:
    """Poster + id via IMDb suggestion. One lookup per unique movie/series name."""
    CACHE.mkdir(parents=True, exist_ok=True)
    sug_path = CACHE / "suggest.json"
    sug = json.loads(sug_path.read_text()) if sug_path.exists() else {}

    def lookup(title: str) -> dict | None:
        if title in sug:
            return sug[title]
        hits = suggestion(title)
        best = next((h for h in hits if str(h.get("id", "")).startswith("tt")), None)
        sug[title] = best
        return best

    already = sum(1 for it in items if it.get("id"))
    if already == len(items) and items:
        print(f"All {len(items)} titles already have IMDb IDs, skipping suggestion", flush=True)
        return items
    seen_series: dict[str, dict | None] = {}
    for i, it in enumerate(items, 1):
        ttype = TYPE_TO_ID.get(it.get("type") or "", "")
        if ttype == "tvEpisode" and it.get("series"):
            series = it["series"]
            if series not in seen_series:
                seen_series[series] = lookup(series)
            hit = seen_series[series]
            if hit:
                img = (hit.get("i") or {}).get("imageUrl")
                if img:
                    it["seriesPoster"] = poster_thumb(img)
                    if not it.get("poster"):
                        it["poster"] = it["seriesPoster"]
                it["seriesId"] = hit.get("id")
                if hit.get("y") and not it.get("seriesYear"):
                    it["seriesYear"] = hit["y"]
                stars = hit.get("s") or ""
                if stars and not it.get("stars"):
                    it["stars"] = [{"name": n.strip()} for n in stars.split(",") if n.strip()]
        else:
            if it.get("id"):
                continue
            hit = lookup(it["title"])
            if hit:
                apply_suggestion_hit(it, hit)
        if i % 80 == 0:
            sug_path.write_text(json.dumps(sug))
            print(f"  suggestion {i}/{len(items)}", flush=True)
    sug_path.write_text(json.dumps(sug))
    print(
        f"  posters {sum(1 for it in items if it.get('poster'))}/{len(items)}",
        flush=True,
    )
    return items


def enrich(items: list[dict], graphql: bool = True) -> list[dict]:
    items = fast_enrich(items)
    if not graphql:
        apply_ru_locale(items)
        return items
    CACHE.mkdir(parents=True, exist_ok=True)
    id_cache_path = CACHE / "id-map.json"
    meta_path = CACHE / "title-meta.json"
    id_cache = json.loads(id_cache_path.read_text()) if id_cache_path.exists() else {}
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}

    print("Skipping per-title ID search; using suggestion IDs.", flush=True)

    ids = sorted({
        tid for it in items
        for tid in (it.get("id"), it.get("seriesId"))
        if tid and tid not in meta
    })
    print(f"GraphQL enrich {len(ids)} new titles...", flush=True)
    for i in range(0, len(ids), 40):
        batch = ids[i : i + 40]
        try:
            data = gql(TITLE_QUERY, {"ids": batch})
            for t in (data.get("data") or {}).get("titles") or []:
                if t and t.get("id"):
                    meta[t["id"]] = t
        except Exception as exc:  # noqa: BLE001
            print(f"  gql batch fail: {exc}", flush=True)
        if i % 200 == 0:
            meta_path.write_text(json.dumps(meta))
            print(f"  enriched {min(i+40, len(ids))}/{len(ids)}", flush=True)
        time.sleep(0.08)
    meta_path.write_text(json.dumps(meta))

    lang_ids = sorted({
        tid for it in items
        for tid in (it.get("id"), it.get("seriesId"))
        if tid and tid in meta and "spokenLanguages" not in (meta.get(tid) or {})
    })
    if lang_ids:
        print(f"GraphQL languages {len(lang_ids)} titles...", flush=True)
        for i in range(0, len(lang_ids), 40):
            batch = lang_ids[i : i + 40]
            try:
                data = gql(LANG_QUERY, {"ids": batch})
                for t in (data.get("data") or {}).get("titles") or []:
                    if t and t.get("id") and t["id"] in meta:
                        meta[t["id"]]["spokenLanguages"] = t.get("spokenLanguages")
            except Exception as exc:  # noqa: BLE001
                print(f"  gql lang batch fail: {exc}", flush=True)
            if i % 200 == 0:
                meta_path.write_text(json.dumps(meta))
                print(f"  languages {min(i + 40, len(lang_ids))}/{len(lang_ids)}", flush=True)
            time.sleep(0.08)
        meta_path.write_text(json.dumps(meta))

    theme_ids = sorted({
        tid for it in items
        for tid in (it.get("id"), it.get("seriesId"))
        if tid and tid in meta and "interests" not in (meta.get(tid) or {})
    })
    if theme_ids:
        print(f"GraphQL interests {len(theme_ids)} titles...", flush=True)
        for i in range(0, len(theme_ids), 40):
            batch = theme_ids[i : i + 40]
            try:
                data = gql(THEME_QUERY, {"ids": batch})
                for t in (data.get("data") or {}).get("titles") or []:
                    if t and t.get("id") and t["id"] in meta:
                        meta[t["id"]]["interests"] = t.get("interests")
                        meta[t["id"]]["keywords"] = t.get("keywords")
            except Exception as exc:  # noqa: BLE001
                print(f"  gql theme batch fail: {exc}", flush=True)
            if i % 200 == 0:
                meta_path.write_text(json.dumps(meta))
                print(f"  interests {min(i + 40, len(theme_ids))}/{len(theme_ids)}", flush=True)
            time.sleep(0.08)
        meta_path.write_text(json.dumps(meta))

    for it in items:
        t = meta.get(it.get("id") or "")
        if not t:
            continue
        it["id"] = t["id"]
        it["title"] = ((t.get("titleText") or {}).get("text")) or it["title"]
        it["typeId"] = ((t.get("titleType") or {}).get("id")) or TYPE_TO_ID.get(it.get("type") or "", "movie")
        it["type"] = ((t.get("titleType") or {}).get("text")) or it.get("type")
        ry = (t.get("releaseYear") or {}).get("year")
        if ry:
            it["releaseYear"] = ry
        rt = (t.get("runtime") or {}).get("seconds")
        if rt:
            it["runtimeMin"] = int(rt / 60)
        rs = t.get("ratingsSummary") or {}
        if rs.get("aggregateRating") is not None:
            it["imdbRating"] = rs["aggregateRating"]
        if rs.get("voteCount") is not None:
            it["votes"] = rs["voteCount"]
        # Keep the user's 1–10 rating from the CSV; GraphQL only has the IMDb average.
        poster = poster_thumb((t.get("primaryImage") or {}).get("url"))
        if poster:
            it["poster"] = poster
        it["genres"] = [g["text"] for g in ((t.get("genres") or {}).get("genres") or []) if g.get("text")]
        it["countries"] = [
            {"id": c.get("id"), "name": c.get("text")}
            for c in ((t.get("countriesOfOrigin") or {}).get("countries") or [])
            if c.get("text")
        ]
        it["languages"] = spoken_langs(t)
        it["interests"] = interests_of(t)
        it["keywords"] = keywords_of(t)
        it["directors"] = credits_of(t, "director")
        it["stars"] = credits_of(t, "star")
        series = ((t.get("series") or {}).get("series") or {})
        if series.get("titleText"):
            it["series"] = series["titleText"]["text"]
            it["seriesId"] = series.get("id")
        epn = ((t.get("series") or {}).get("episodeNumber") or {})
        if epn.get("seasonNumber") is not None:
            it["season"] = epn["seasonNumber"]
            it["episode"] = epn.get("episodeNumber")

    for it in items:
        t = meta.get(it.get("seriesId") or "")
        if not t:
            continue
        if not it.get("genres"):
            it["genres"] = [g["text"] for g in ((t.get("genres") or {}).get("genres") or []) if g.get("text")]
        if not it.get("countries"):
            it["countries"] = [
                {"id": c.get("id"), "name": c.get("text")}
                for c in ((t.get("countriesOfOrigin") or {}).get("countries") or [])
                if c.get("text")
            ]
        if not it.get("languages"):
            it["languages"] = spoken_langs(t)
        if not it.get("interests"):
            it["interests"] = interests_of(t)
        if not it.get("keywords"):
            it["keywords"] = keywords_of(t)
        if not it.get("directors"):
            it["directors"] = credits_of(t, "director")
        if not it.get("stars"):
            it["stars"] = credits_of(t, "star")

    missing_series = sorted({
        sid for it in items
        if (sid := it.get("seriesId")) and sid not in meta
    })
    if missing_series:
        print(f"GraphQL enrich {len(missing_series)} parent series...", flush=True)
        for i in range(0, len(missing_series), 40):
            batch = missing_series[i : i + 40]
            try:
                data = gql(TITLE_QUERY, {"ids": batch})
                for t in (data.get("data") or {}).get("titles") or []:
                    if t and t.get("id"):
                        meta[t["id"]] = t
            except Exception as exc:  # noqa: BLE001
                print(f"  gql series batch fail: {exc}", flush=True)
            time.sleep(0.08)
        meta_path.write_text(json.dumps(meta))

    for it in items:
        sid = it.get("seriesId")
        if not sid:
            continue
        st = meta.get(sid)
        if not st:
            continue
        poster = poster_thumb((st.get("primaryImage") or {}).get("url"))
        if poster:
            it["seriesPoster"] = poster
        ry = (st.get("releaseYear") or {}).get("year")
        if ry:
            it["seriesYear"] = ry
        if not it.get("languages"):
            it["languages"] = spoken_langs(st)
        if not it.get("interests"):
            it["interests"] = interests_of(st)
        if not it.get("keywords"):
            it["keywords"] = keywords_of(st)
    apply_ru_locale(items)
    return items
    "Action",
    "Adventure",
    "Animation",
    "Biography",
    "Comedy",
    "Crime",
    "Documentary",
    "Drama",
    "Family",
    "Fantasy",
    "Film-Noir",
    "Game-Show",
    "History",
    "Horror",
    "Music",
    "Musical",
    "Mystery",
    "News",
    "Reality-TV",
    "Romance",
    "Sci-Fi",
    "Short",
    "Sport",
    "Talk-Show",
    "Thriller",
    "War",
    "Western",
}
KEYWORD_SKIP = (
    "nudity",
    "naked",
    "sex scene",
    "topless",
    "bare chest",
    "bare breasts",
)


def theme_tags(item: dict) -> list[dict]:
    return [tag for tag in (item.get("interests") or []) if tag.get("name") not in IMDB_GENRES]


def keyword_tags(item: dict) -> list[dict]:
    out = []
    for word in item.get("keywords") or []:
        low = word.lower()
        if any(part in low for part in KEYWORD_SKIP):
            continue
        out.append({"name": word})
    return out


MOVIE_TYPES = {
    "movie",
    "tvMovie",
    "short",
    "video",
    "tvSpecial",
    "tvShort",
    "musicVideo",
}
SERIES_TYPES = {
    "tvSeries",
    "tvMiniSeries",
    "tvEpisode",
    "podcastSeries",
    "podcastEpisode",
}
SERIES_SHOW_TYPES = {"tvSeries", "tvMiniSeries", "podcastSeries"}


def type_id_of(item: dict) -> str:
    return item.get("typeId") or TYPE_TO_ID.get(item.get("type") or "", "")


def is_feature(item: dict) -> bool:
    return type_id_of(item) not in {"tvEpisode", "podcastEpisode"}


def is_watch_hours(item: dict) -> bool:
    return type_id_of(item) not in {"tvSeries", "tvMiniSeries", "podcastSeries"}


def is_movie_item(item: dict) -> bool:
    return type_id_of(item) in MOVIE_TYPES


def is_series_item(item: dict) -> bool:
    return type_id_of(item) in SERIES_TYPES


def is_series_show(item: dict) -> bool:
    return type_id_of(item) in SERIES_SHOW_TYPES


TV_SHOW_GENRES = {"Talk-Show", "Game-Show", "Reality-TV", "News"}
CLIP_TYPES = {"musicVideo", "video", "tvSpecial", "tvShort", "short"}


def is_tv_show(item: dict) -> bool:
    return bool(set(item.get("genres") or []) & TV_SHOW_GENRES)


def is_music_clip(item: dict) -> bool:
    tid = type_id_of(item)
    if tid == "musicVideo":
        return True
    genres = set(item.get("genres") or [])
    runtime = item.get("runtimeMin") or 0
    if tid in CLIP_TYPES and "Music" in genres:
        return True
    # Long-form clips IMDb sometimes files as Movie (e.g. Smooth Criminal).
    if (
        tid == "movie"
        and "Music" in genres
        and "Drama" not in genres
        and "Biography" not in genres
        and runtime
        and runtime < 60
    ):
        return True
    return False


def is_best_movie(item: dict) -> bool:
    return type_id_of(item) in {"movie", "tvMovie"} and not is_music_clip(item)


def is_best_series(item: dict) -> bool:
    return is_series_show(item) and not is_tv_show(item)


def is_best_title(item: dict) -> bool:
    tid = type_id_of(item)
    if tid in CLIP_TYPES or is_music_clip(item) or is_tv_show(item):
        return False
    return is_feature(item)


def compact_title(item: dict) -> dict:
    out = {
        "id": item.get("id"),
        "title": item["title"],
        "year": item.get("releaseYear"),
        "type": item.get("typeId") or TYPE_TO_ID.get(item.get("type") or "", "movie"),
        "poster": item.get("poster"),
        "userRating": item.get("userRating"),
        "imdbRating": item.get("imdbRating"),
        "votes": item.get("votes"),
        "runtimeMin": item.get("runtimeMin"),
        "releaseDate": item.get("releaseDate"),
        "ratedOn": item.get("ratedOn"),
        "series": item.get("series"),
        "season": item.get("season"),
        "episode": item.get("episode"),
        "url": f"https://www.imdb.com/title/{item['id']}/" if item.get("id") else None,
    }
    if item.get("titleRu"):
        out["titleRu"] = item["titleRu"]
    if item.get("posterRu"):
        out["posterRu"] = item["posterRu"]
    return out


def top_n(items: list[dict], key, reverse=True, n=10, require=None) -> list[dict]:
    getter = key if callable(key) else lambda it, k=key: it.get(k)
    pool = [it for it in items if getter(it) is not None]
    if require:
        pool = [it for it in pool if require(it)]
    pool.sort(
        key=lambda it: (getter(it), it.get("userRating") or 0, it.get("imdbRating") or 0),
        reverse=reverse,
    )
    # unique by id/title
    out, seen = [], set()
    for it in pool:
        k = it.get("id") or f"{it['title']}|{it.get('series')}"
        if k in seen:
            continue
        seen.add(k)
        out.append(compact_title(it))
        if len(out) >= n:
            break
    return out


def vs_average(items: list[dict], *, kinder=True, n=8, require=None, min_delta=1.5, min_votes=1000) -> list[dict]:
    def delta(it: dict) -> float:
        return it["userRating"] - it["imdbRating"]

    pool = [
        it
        for it in items
        if it.get("userRating") is not None
        and it.get("imdbRating") is not None
        and (it.get("votes") or 0) >= min_votes
    ]
    if require:
        pool = [it for it in pool if require(it)]
    if kinder:
        pool = [it for it in pool if delta(it) >= min_delta]
        pool.sort(key=lambda it: (delta(it), it["userRating"]), reverse=True)
    else:
        pool = [it for it in pool if delta(it) <= -min_delta]
        pool.sort(key=lambda it: (delta(it), it["userRating"]))
    out, seen = [], set()
    for it in pool:
        k = it.get("id") or f"{it['title']}|{it.get('series')}"
        if k in seen:
            continue
        seen.add(k)
        out.append(compact_title(it))
        if len(out) >= n:
            break
    return out


def count_people(items: list[dict], field: str, n=8) -> list[dict]:
    c: Counter = Counter()
    ids: dict[str, str] = {}
    for it in items:
        for p in it.get(field) or []:
            name = p.get("name")
            if not name:
                continue
            c[name] += 1
            if p.get("id"):
                ids.setdefault(name, p["id"])
    return [
        {"name": name, "id": ids.get(name), "count": count, "poster": None}
        for name, count in c.most_common(n)
    ]


def named_tag_stats(items: list[dict], getter, n: int = 12, min_rated: int = 3) -> tuple[list[dict], list[dict]]:
    counts: Counter = Counter()
    ids: dict[str, str] = {}
    rating_sum: dict[str, float] = defaultdict(float)
    rating_n: Counter = Counter()
    for it in items:
        seen: set[str] = set()
        for tag in getter(it) or []:
            name = tag["name"] if isinstance(tag, dict) else tag
            if not name or name in seen:
                continue
            seen.add(name)
            counts[name] += 1
            tid = tag.get("id") if isinstance(tag, dict) else None
            if tid:
                ids[name] = tid
            r = it.get("userRating")
            if r:
                rating_sum[name] += r
                rating_n[name] += 1

    def row(name: str) -> dict:
        rn = rating_n[name]
        return {
            "name": name,
            "id": ids.get(name),
            "count": counts[name],
            "avgRating": round(rating_sum[name] / rn, 2) if rn else None,
        }

    watched = [row(name) for name, _ in counts.most_common(n)]
    rated = [row(name) for name in counts if rating_n[name] >= min_rated]
    rated.sort(key=lambda x: (x["avgRating"] or 0, x["count"]), reverse=True)
    return watched, rated[:n]


def name_photo_url(entry: dict | None) -> str | None:
    n = entry or {}
    url = (n.get("primaryImage") or {}).get("url")
    if not url:
        edges = ((n.get("images") or {}).get("edges")) or []
        if edges:
            url = ((edges[0].get("node") or {}).get("url"))
    return poster_thumb(url, 256)


def fetch_name_images(ids: list[str]) -> dict[str, str]:
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / "name-meta.json"
    meta = json.loads(path.read_text()) if path.exists() else {}
    missing = [
        nid
        for nid in ids
        if nid
        and (
            nid not in meta
            or (not (meta[nid] or {}).get("primaryImage") and "images" not in (meta[nid] or {}))
        )
    ]
    if missing:
        print(f"GraphQL enrich {len(missing)} people...", flush=True)
        for i in range(0, len(missing), 40):
            batch = missing[i : i + 40]
            try:
                data = gql(NAMES_QUERY, {"ids": batch})
                found = set()
                for n in (data.get("data") or {}).get("names") or []:
                    if n and n.get("id"):
                        meta[n["id"]] = n
                        found.add(n["id"])
                for nid in batch:
                    if nid not in found:
                        meta.setdefault(nid, {"id": nid, "images": {"edges": []}})
            except Exception as exc:  # noqa: BLE001
                print(f"  gql names batch fail: {exc}", flush=True)
            time.sleep(0.08)
        path.write_text(json.dumps(meta))
    out: dict[str, str] = {}
    for nid in ids:
        img = name_photo_url(meta.get(nid))
        if img:
            out[nid] = img
    return out


def attach_people_photos(payload: dict) -> None:
    people: list[dict] = []
    bundles = [payload.get("allTime") or {}]
    bundles.extend((payload.get("byYear") or {}).values())
    for bundle in bundles:
        for kind in bundle.values():
            if not isinstance(kind, dict):
                continue
            people.extend(kind.get("directors") or [])
            people.extend(kind.get("stars") or [])
    ids = sorted({p.get("id") for p in people if p.get("id")})
    photos = fetch_name_images(ids)
    for p in people:
        nid = p.get("id")
        if nid and nid in photos:
            p["poster"] = photos[nid]


def stats_for(
    items: list[dict],
    year: int | None,
    *,
    list_require=is_feature,
    runtime_require=None,
    best_require=None,
) -> dict:
    label = "All time" if year is None else str(year)
    n = len(items)
    hours_items = [it for it in items if is_watch_hours(it) and it.get("runtimeMin")]
    minutes = sum(it["runtimeMin"] for it in hours_items)
    months_span = 12
    if year == YEAR:
        months_span = max(1, datetime.now().month)
    elif year is None and items:
        years = sorted({it["ratedYear"] for it in items})
        months_span = max(1, (years[-1] - years[0] + 1) * 12)
    monthly = [0] * 12
    monthly_posters: list[list[str]] = [[] for _ in range(12)]
    for it in items:
        m = it["ratedMonth"] - 1
        monthly[m] += 1
        if it.get("poster") and len(monthly_posters[m]) < 8:
            monthly_posters[m].append(it["poster"])
    type_counts = Counter(it.get("typeId") or TYPE_TO_ID.get(it.get("type") or "", "other") for it in items)
    premieres = sum(1 for it in items if it.get("releaseYear") == (year or it.get("ratedYear")))
    if year is None:
        premieres = sum(1 for it in items if it.get("releaseYear") and it.get("releaseYear") == it.get("ratedYear"))
    older = n - premieres
    spread = {str(i): 0 for i in range(1, 11)}
    for it in items:
        r = it.get("userRating")
        if r and 1 <= int(r) <= 10:
            spread[str(int(r))] += 1
    genres = Counter()
    for it in items:
        for g in it.get("genres") or []:
            genres[g] += 1
    decades = Counter()
    for it in items:
        y = it.get("releaseYear")
        if y:
            decades[f"{(y // 10) * 10}s"] += 1
    countries = Counter()
    country_ids = {}
    for it in items:
        for c in it.get("countries") or []:
            countries[c["name"]] += 1
            country_ids[c["name"]] = c.get("id")
    languages = Counter()
    language_ids = {}
    for it in items:
        for lang in it.get("languages") or []:
            languages[lang["name"]] += 1
            language_ids[lang["name"]] = lang.get("id")
    min_rated = 5 if year is None else 3
    themes, themes_rated = named_tag_stats(items, theme_tags, n=12, min_rated=min_rated)
    keywords, keywords_rated = named_tag_stats(items, keyword_tags, n=12, min_rated=min_rated)
    series_c = Counter()
    series_poster = {}
    series_year = {}
    series_id = {}
    for it in items:
        if it.get("series"):
            name = it["series"]
            series_c[name] += 1
            series_id.setdefault(name, it.get("seriesId"))
            if it.get("seriesPoster"):
                series_poster.setdefault(name, it["seriesPoster"])
            if it.get("seriesYear"):
                series_year.setdefault(name, it["seriesYear"])
        elif type_id_of(it) in SERIES_SHOW_TYPES and it.get("title"):
            name = it["title"]
            series_id.setdefault(name, it.get("id"))
            if it.get("poster"):
                series_poster[name] = it["poster"]
            if it.get("releaseYear"):
                series_year.setdefault(name, it["releaseYear"])
    day_counts = Counter(it["ratedOn"] for it in items)
    most_day, most_day_n = (day_counts.most_common(1)[0] if day_counts else (None, 0))
    user_rs = [it["userRating"] for it in items if it.get("userRating")]
    imdb_rs = [it["imdbRating"] for it in items if it.get("imdbRating") and it.get("userRating")]
    paired = [
        (it["userRating"], it["imdbRating"])
        for it in items
        if it.get("userRating") and it.get("imdbRating")
    ]
    delta = sum(u - i for u, i in paired) / len(paired) if paired else 0
    ordered = sorted(
        items,
        key=lambda it: (it.get("ratedOn") or "9999-99-99", it.get("id") or "", it.get("title") or ""),
    )
    first = ordered[0] if ordered else None
    last = ordered[-1] if ordered else None
    step = 50 if year is not None else 500
    marks = []
    k = step
    while k <= n:
        card = compact_title(ordered[k - 1])
        card["n"] = k
        marks.append(card)
        k += step
    if runtime_require is None:
        runtime_require = lambda it: is_watch_hours(it) and list_require(it)
    hero = []
    seen = set()
    for it in items:
        p = it.get("poster")
        k = it.get("id") or p
        if not p or k in seen:
            continue
        seen.add(k)
        hero.append(p)
        if len(hero) >= 40:
            break

    def release_key(it: dict):
        return it.get("releaseDate") or (
            f"{it['releaseYear']:04d}-01-01" if it.get("releaseYear") else None
        )

    def avg_ok(it: dict) -> bool:
        return list_require(it) and (it.get("votes") or 0) >= 1000 and it.get("imdbRating") is not None

    highest = top_n(items, "userRating", True, 20, require=best_require or list_require)
    lowest = top_n(items, "userRating", False, 20, require=list_require)
    popular = top_n(items, "votes", True, 10, require=list_require)
    obscure = top_n(
        items, "votes", False, 10, require=lambda it: list_require(it) and (it.get("votes") or 0) >= 5
    )
    newest = top_n(items, release_key, True, 10, require=list_require)
    oldest = top_n(items, release_key, False, 10, require=list_require)
    longest = top_n(items, "runtimeMin", True, 10, require=runtime_require)
    shortest = top_n(
        items,
        "runtimeMin",
        False,
        10,
        require=lambda it: runtime_require(it) and (it.get("runtimeMin") or 0) >= 1,
    )
    hi_avg = top_n(items, "imdbRating", True, 1, require=avg_ok)
    lo_avg = top_n(items, "imdbRating", False, 1, require=avg_ok)
    kinder_avg = vs_average(items, kinder=True, n=8, require=list_require)
    harsher_avg = vs_average(items, kinder=False, n=8, require=list_require)

    return {
        "year": year,
        "label": label,
        "toDate": year == YEAR,
        "count": n,
        "hours": round(minutes / 60, 1),
        "minutes": minutes,
        "avgPerMonth": round(n / months_span, 1),
        "avgPerWeek": round(n / max(1, months_span * 4.345), 1),
        "avgRating": round(sum(user_rs) / len(user_rs), 2) if user_rs else None,
        "monthly": monthly,
        "monthlyPosters": monthly_posters,
        "daily": dict(day_counts),
        "types": dict(type_counts),
        "premieres": premieres,
        "older": older,
        "ratingsSpread": spread,
        "highsAndLows": {
            "highestAverage": hi_avg[0] if hi_avg else None,
            "lowestAverage": lo_avg[0] if lo_avg else None,
            "mostPopular": popular[0] if popular else None,
            "mostObscure": obscure[0] if obscure else None,
            "newest": newest[0] if newest else None,
            "oldest": oldest[0] if oldest else None,
            "longest": longest[0] if longest else None,
            "shortest": shortest[0] if shortest else None,
        },
        "highest": highest,
        "lowest": lowest,
        "kinderThanAvg": kinder_avg,
        "harsherThanAvg": harsher_avg,
        "popular": popular,
        "obscure": obscure,
        "newest": newest,
        "oldest": oldest,
        "longest": longest,
        "shortest": shortest,
        "genres": [{"name": k, "count": v} for k, v in genres.most_common(12)],
        "decades": [{"name": k, "count": v} for k, v in sorted(decades.items(), key=lambda kv: kv[0])],
        "countries": [
            {"name": k, "id": country_ids.get(k), "count": v}
            for k, v in countries.most_common()
        ],
        "languages": [
            {"name": k, "id": language_ids.get(k), "count": v}
            for k, v in languages.most_common(12)
        ],
        "themes": themes,
        "themesRated": themes_rated,
        "keywords": keywords,
        "keywordsRated": keywords_rated,
        "directors": count_people(items, "directors", 8),
        "stars": count_people(items, "stars", 8),
        "series": [
            {
                "name": k,
                "id": series_id.get(k),
                "count": v,
                "poster": series_poster.get(k),
                "year": series_year.get(k),
            }
            for k, v in series_c.most_common(10)
            if v >= 2
        ],
        "first": compact_title(first) if first else None,
        "last": compact_title(last) if last else None,
        "milestones": marks,
        "mostActiveDay": {"date": most_day, "count": most_day_n} if most_day else None,
        "vsImdb": {
            "avgUser": round(sum(user_rs) / len(user_rs), 2) if user_rs else None,
            "avgImdb": round(sum(imdb_rs) / len(imdb_rs), 2) if imdb_rs else None,
            "delta": round(delta, 2),
            "kinder": sum(1 for u, i in paired if u > i),
            "harsher": sum(1 for u, i in paired if u < i),
            "same": sum(1 for u, i in paired if u == i),
        },
        "heroPosters": hero,
    }


def watchlist_count() -> int:
    path = OUT / "watchlist.json"
    if path.exists():
        try:
            return int(json.loads(path.read_text()).get("count") or 0)
        except Exception:  # noqa: BLE001
            pass
    csv_path = ROOT / "data" / "watchlist.csv"
    if csv_path.exists():
        with csv_path.open(encoding="utf-8") as fh:
            return max(sum(1 for _ in fh) - 1, 0)
    return 0


def stats_bundle(items: list[dict], year: int | None) -> dict:
    movies = [it for it in items if is_movie_item(it)]
    series = [it for it in items if is_series_item(it)]
    return {
        "all": stats_for(items, year, best_require=is_best_title),
        "movies": stats_for(movies, year, best_require=is_best_movie),
        "series": stats_for(
            series,
            year,
            list_require=is_series_show,
            runtime_require=is_watch_hours,
            best_require=is_best_series,
        ),
    }


def build(items: list[dict]) -> dict:
    identity = hydrate_identity()
    names = display_names(CFG, identity.get("username") or "User")
    years = sorted({it["ratedYear"] for it in items}, reverse=True)
    by_year = {str(y): stats_bundle([it for it in items if it["ratedYear"] == y], y) for y in years}
    payload = {
        "profile": {
            "username": identity.get("username") or names["en"],
            "userId": identity.get("profileId") or identity.get("userId") or _IDS["slug"],
            "url": identity.get("url") or _IDS["url"],
            "avatar": identity.get("avatar") or "",
            "totalRatings": len(items),
            "watchlist": watchlist_count(),
            "badges": int(identity.get("badges") or 0),
            "lists": [
                {"name": item["name"], "count": item["count"], "id": item["id"]}
                for item in (identity.get("lists") or [])
                if item.get("name") and item.get("id")
            ],
            "interests": fetch_profile_interests(),
            "favoritePeople": fetch_favorite_people(),
            "favorites": identity.get("favorites") or [],
            "displayName": names,
            "telegram": telegram_url(CFG),
        },
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "years": years,
        "defaultYear": years[0] if years else YEAR,
        "allTime": stats_bundle(items, None),
        "byYear": by_year,
        "coverage": {
            "parsed": len(items),
            "withPoster": sum(1 for it in items if it.get("poster")),
            "withId": sum(1 for it in items if it.get("id")),
        },
    }
    attach_people_photos(payload)
    return payload


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--fast", action="store_true", help="Skip GraphQL, suggestion posters only")
    args = parser.parse_args()
    hydrate_identity()
    items = apply_first_rated(load_all())
    print(f"Parsed {len(items)} ratings across years {sorted({i['ratedYear'] for i in items})}")
    types = Counter(i.get("type") for i in items)
    print("types", dict(types))
    CACHE.mkdir(parents=True, exist_ok=True)
    (CACHE / "parsed.json").write_text(json.dumps(items, ensure_ascii=False))
    items = enrich(items, graphql=not args.fast)
    (CACHE / "enriched.json").write_text(json.dumps(items, ensure_ascii=False))
    payload = build(items)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "stats.json").write_text(json.dumps(payload, ensure_ascii=False))
    print("Wrote", OUT / "stats.json", "years", payload["years"], "coverage", payload["coverage"])


if __name__ == "__main__":
    main()
