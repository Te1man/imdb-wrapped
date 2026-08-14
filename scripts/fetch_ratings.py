#!/usr/bin/env python3
"""Optional: scrape public IMDb ratings pages when you don't have a CSV export."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

from user_config import load_config, parse_profile_url

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
_IDS = parse_profile_url(load_config()["imdbUrl"])
USER = _IDS["slug"]
PAGE_SIZE = 250
MIN_BLOCKS = 80


def csv_rating_count() -> int:
    path = ROOT / "data" / "ratings.csv"
    if not path.exists():
        return 0
    with path.open(encoding="utf-8") as fh:
        return max(sum(1 for _ in fh) - 1, 0)


TOTAL = csv_rating_count()
PAGES = max((TOTAL + PAGE_SIZE - 1) // PAGE_SIZE, 1) if TOTAL else 1


def page_url(page: int) -> str:
    base = f"https://www.imdb.com/user/{USER}/ratings"
    if page <= 1:
        return base
    return f"{base}/?page={page}"


def jina_fetch(url: str, timeout: int = 70) -> str:
    cmd = [
        "curl",
        "-sS",
        "--max-time",
        str(timeout),
        "-A",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "-H",
        "x-timeout: 25",
        "-H",
        "x-retain-images: none",
        f"https://r.jina.ai/{url}",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr[-400:] or f"curl exit {proc.returncode}")
    return proc.stdout


def is_good(text: str) -> bool:
    return text.count("Rated on ") >= MIN_BLOCKS


def fetch_page(page: int, attempts: int = 6) -> Path:
    RAW.mkdir(parents=True, exist_ok=True)
    dest = RAW / f"ratings-p{page:02d}.md"
    if dest.exists() and is_good(dest.read_text(errors="replace")):
        return dest
    last_err = ""
    for i in range(1, attempts + 1):
        try:
            text = jina_fetch(page_url(page))
            rated = text.count("Rated on ")
            print(f"  page {page} try {i}: {len(text)} bytes, Rated on={rated}", flush=True)
            if is_good(text):
                dest.write_text(text)
                return dest
            last_err = f"incomplete ({rated} dates, {len(text)} bytes)"
        except Exception as exc:  # noqa: BLE001
            last_err = str(exc)
            print(f"  page {page} try {i} error: {last_err[:200]}", flush=True)
        time.sleep(2.5 * i)
    raise RuntimeError(f"page {page} failed: {last_err}")


def main() -> int:
    if not TOTAL:
        print("No data/ratings.csv — export your ratings from IMDb and save them there.", flush=True)
        return 1
    pages = list(range(1, PAGES + 1))
    print(f"Fetching {PAGES} pages ({TOTAL} ratings) for {USER}", flush=True)
    failed: list[int] = []
    # Sequential + pause — Jina throttles bursts into empty shells.
    for page in pages:
        try:
            path = fetch_page(page)
            print(f"OK page {page} -> {path.name}", flush=True)
            time.sleep(8)
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL page {page}: {exc}", flush=True)
            failed.append(page)
            time.sleep(20)
    if failed:
        print(f"Failed pages: {sorted(failed)}", flush=True)
        return 1
    print("All pages saved.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
