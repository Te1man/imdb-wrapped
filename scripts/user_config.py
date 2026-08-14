"""Load IMDb Wrapped config.json: profile URL, display names, optional Telegram."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config.json"

PROFILE_RE = re.compile(r"/user/([^/?#]+)", re.I)


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        example = ROOT / "config.example.json"
        raise SystemExit(
            f"Missing {CONFIG_PATH.name}. Copy {example.name}, paste your IMDb profile URL, "
            "and save it as config.json."
        )
    cfg = json.loads(CONFIG_PATH.read_text())
    url = (cfg.get("imdbUrl") or "").strip()
    if not url or "YOUR_PROFILE_ID" in url:
        raise SystemExit("Set imdbUrl in config.json to your public IMDb profile URL.")
    return cfg


def parse_profile_url(url: str) -> dict:
    m = PROFILE_RE.search(url or "")
    if not m:
        raise SystemExit(f"Could not parse IMDb user from URL: {url}")
    slug = m.group(1).strip().strip("/")
    url = f"https://www.imdb.com/user/{slug}"
    out = {
        "url": url,
        "slug": slug,
        "profileId": slug if slug.startswith("p.") else None,
        "userConst": slug if slug.startswith("ur") else None,
    }
    return out


def display_names(cfg: dict, fallback: str = "") -> dict:
    names = cfg.get("displayName") or {}
    en = (names.get("en") or fallback or "User").strip()
    ru = (names.get("ru") or en).strip()
    gen = (names.get("ruGenitive") or ru).strip()
    return {"en": en, "ru": ru, "ruGenitive": gen}


def telegram_url(cfg: dict) -> str | None:
    raw = (cfg.get("telegram") or "").strip()
    if not raw:
        return None
    if raw.startswith("http"):
        return raw
    handle = raw.lstrip("@")
    return f"https://t.me/{handle}"
