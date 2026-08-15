#!/usr/bin/env python3
"""Force-refresh ratings, watchlist, and OG assets from public IMDb data."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.check_call(cmd, cwd=ROOT)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    run([sys.executable, "scripts/build_stats.py", "--live"])
    run([sys.executable, "scripts/fetch_watchlist.py", "--live"])
    run([sys.executable, "scripts/build_og.py"])
    for name in ("stats.json", "watchlist.json"):
        src = ROOT / "src" / "data" / name
        dst = ROOT / "public" / "data" / name
        if src.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(src.read_bytes())
            print(f"Synced {dst.relative_to(ROOT)}", flush=True)
    print("sync_live done", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
