#!/usr/bin/env python3
"""Compose Open Graph cards for every year × kind × language."""

from __future__ import annotations

import hashlib
import json
import math
import ssl
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont
from user_config import display_names, load_config, parse_profile_url

ROOT = Path(__file__).resolve().parents[1]
STATS = ROOT / "src" / "data" / "stats.json"
PUBLIC = ROOT / "public"
OG_DIR = PUBLIC / "og"
CACHE = ROOT / "data" / "cache" / "og"
FONTS = CACHE / "fonts"
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
CTX = ssl.create_default_context()

W, H = 1200, 630
SCALE = 2
CW, CH = W * SCALE, H * SCALE

YELLOW = (245, 197, 24, 255)
INK = (245, 245, 245, 255)
MUTED = (154, 154, 154, 255)
BG = (12, 12, 12, 255)
MARK_INK = (12, 12, 12, 255)

KINDS = ("movies", "series", "all")
LANGS = ("ru", "en")
KIND_LABELS = {
    "ru": {"movies": "Фильмы", "series": "Сериалы", "all": "Всё вместе"},
    "en": {"movies": "Movies", "series": "Series", "all": "All"},
}

FONT_URLS = {
    "BebasNeue-Regular.ttf": "https://github.com/google/fonts/raw/main/ofl/bebasneue/BebasNeue-Regular.ttf",
    "InterVariable.ttf": "https://github.com/rsms/inter/raw/master/docs/font-files/InterVariable.ttf",
}


def plural_ru(n: int, one: str, few: str, many: str) -> str:
    n = abs(int(n)) % 100
    if 11 <= n <= 14:
        return many
    r = n % 10
    if r == 1:
        return one
    if 2 <= r <= 4:
        return few
    return many


def en_plural(n: int, one: str, many: str) -> str:
    return one if abs(int(n)) == 1 else many


def fmt_hours(hours: float) -> tuple[str, float]:
    if hours >= 100 or float(hours).is_integer():
        value = int(math.floor(hours + 0.5))
        return str(value), float(value)
    return f"{hours:.1f}", float(hours)


def fmt_num(n: int | str, lang: str) -> str:
    raw = str(n)
    if raw.replace(".", "", 1).isdigit() and "." not in raw:
        value = int(raw)
        return f"{value:,}".replace(",", " ") if lang == "ru" else f"{value:,}"
    return raw


def fetch(url: str, dest: Path | None = None, timeout: int = 25) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, context=CTX, timeout=timeout) as res:
        data = res.read()
    if dest:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    return data


def ensure_fonts() -> dict[str, Path]:
    FONTS.mkdir(parents=True, exist_ok=True)
    out: dict[str, Path] = {}
    for name, url in FONT_URLS.items():
        path = FONTS / name
        if not path.exists() or path.stat().st_size < 10_000:
            print(f"[og] font {name}")
            fetch(url, path)
        out[name] = path
    return out


def font(path: Path, size: int, weight: int | None = None) -> ImageFont.FreeTypeFont:
    face = ImageFont.truetype(str(path), size)
    if weight is not None and hasattr(face, "get_variation_axes"):
        try:
            values = []
            for axis in face.get_variation_axes():
                raw = axis.get("tag") or axis.get("name") or ""
                tag = raw.decode("ascii", "ignore") if isinstance(raw, (bytes, bytearray)) else str(raw)
                tag = tag.lower()
                if "wght" in tag or tag == "weight":
                    values.append(float(weight))
                else:
                    values.append(float(axis.get("default", 400)))
            if values:
                face.set_variation_by_axes(values)
        except OSError:
            pass
    return face


def cache_key(url: str) -> str:
    return hashlib.sha1(url.encode()).hexdigest()[:20]


def load_image(url: str, posters: Path) -> Image.Image | None:
    if not url:
        return None
    path = posters / f"{cache_key(url)}.jpg"
    try:
        raw = path.read_bytes() if path.exists() else fetch(url, path)
        return Image.open(BytesIO(raw)).convert("RGB")
    except Exception as err:
        print(f"[og] skip {url[:64]} ({err})")
        if path.exists():
            path.unlink(missing_ok=True)
        return None


def circle(im: Image.Image, size: int) -> Image.Image:
    im = im.convert("RGBA").resize((size, size), Image.Resampling.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(im, (0, 0), mask)
    return out


def round_poster(im: Image.Image, size: tuple[int, int], radius: int) -> Image.Image:
    im = im.convert("RGB").resize(size, Image.Resampling.LANCZOS)
    rgba = im.convert("RGBA")
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius=radius, fill=255)
    out = Image.new("RGBA", size, (0, 0, 0, 0))
    out.paste(rgba, (0, 0), mask)
    return out


def mosaic(posters: list[Image.Image]) -> Image.Image:
    cols = 10
    cell_w = math.ceil(CW / cols)
    cell_h = math.ceil(cell_w * 1.5)
    rows = math.ceil(CH / cell_h) + 1
    need = cols * rows
    tiles = posters[:] or [Image.new("RGB", (cell_w, cell_h), (28, 28, 28))]
    while len(tiles) < need:
        tiles.extend(posters or tiles)
    layer = Image.new("RGBA", (cols * cell_w, rows * cell_h), BG)
    radius = max(4, round(8 * SCALE / 2))
    for i in range(need):
        x = (i % cols) * cell_w
        y = (i // cols) * cell_h
        tile = round_poster(tiles[i], (cell_w - 6, cell_h - 6), radius)
        layer.paste(tile, (x + 3, y + 3), tile)
    zoomed = layer.resize(
        (math.ceil(layer.width * 1.08), math.ceil(layer.height * 1.08)),
        Image.Resampling.LANCZOS,
    )
    left = (zoomed.width - CW) // 2
    top = (zoomed.height - CH) // 4
    crop = zoomed.crop((left, top, left + CW, top + CH))
    return ImageEnhance.Color(crop).enhance(0.85)


def shade(size: tuple[int, int]) -> Image.Image:
    w, h = size
    grad = Image.new("L", (1, h))
    pix = grad.load()
    for y in range(h):
        t = y / max(1, h - 1)
        if t < 0.42:
            a = 0.22 + (0.38 - 0.22) * (t / 0.42)
        elif t < 0.72:
            a = 0.38 + (0.78 - 0.38) * ((t - 0.42) / 0.30)
        else:
            a = 0.78 + (0.96 - 0.78) * ((t - 0.72) / 0.28)
        pix[0, y] = int(255 * a)
    overlay = Image.new("RGBA", size, (12, 12, 12, 255))
    overlay.putalpha(grad.resize((w, h), Image.Resampling.BILINEAR))
    return overlay


def text_size(draw: ImageDraw.ImageDraw, text: str, face: ImageFont.FreeTypeFont) -> tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=face)
    return box[2] - box[0], box[3] - box[1]


def italic_label(text: str, face: ImageFont.FreeTypeFont, fill: tuple[int, int, int, int], shear: float = 0.22) -> Image.Image:
    probe = ImageDraw.Draw(Image.new("RGBA", (8, 8), (0, 0, 0, 0)))
    tw, th = text_size(probe, text, face)
    pad = 8
    src = Image.new("RGBA", (tw + pad * 2, th + pad * 2), (0, 0, 0, 0))
    ImageDraw.Draw(src).text((pad, pad), text, font=face, fill=fill)
    extra = int(src.height * shear)
    return src.transform(
        (src.width + extra, src.height),
        Image.Transform.AFFINE,
        (1, -shear, extra, 0, 1, 0),
        resample=Image.Resampling.BICUBIC,
    )


def draw_imdb_mark(base: Image.Image, x: int, y: int, face: ImageFont.FreeTypeFont) -> int:
    label = italic_label("IMDb", face, MARK_INK)
    pad_x, pad_y = 14 * SCALE, 6 * SCALE
    box = (x, y, x + label.width + pad_x * 2, y + label.height + pad_y * 2 - 4 * SCALE)
    ImageDraw.Draw(base).rounded_rectangle(box, radius=8 * SCALE, fill=YELLOW)
    base.alpha_composite(label, (x + pad_x, y + pad_y - 2 * SCALE))
    return box[2] - box[0]


def draw_kind_switch(base: Image.Image, lang: str, kind: str, face: ImageFont.FreeTypeFont) -> None:
    labels = [KIND_LABELS[lang][k] for k in KINDS]
    keys = list(KINDS)
    probe = ImageDraw.Draw(base)
    pad_x, pad_y, gap = 28 * SCALE, 12 * SCALE, 4 * SCALE
    widths = [text_size(probe, label, face)[0] + 36 * SCALE for label in labels]
    bar_h = 44 * SCALE
    bar_w = sum(widths) + gap * (len(labels) - 1) + pad_x * 2
    x0 = CW - 64 * SCALE - bar_w
    y0 = 40 * SCALE
    ImageDraw.Draw(base).rounded_rectangle(
        (x0, y0, x0 + bar_w, y0 + bar_h),
        radius=bar_h // 2,
        fill=(12, 12, 12, 148),
        outline=(255, 255, 255, 36),
        width=2,
    )
    cursor = x0 + pad_x
    for key, label, tw in zip(keys, labels, widths):
        on = key == kind
        pill = (cursor, y0 + gap + 2, cursor + tw, y0 + bar_h - gap - 2)
        if on:
            ImageDraw.Draw(base).rounded_rectangle(pill, radius=bar_h // 2, fill=YELLOW)
        lw, lh = text_size(probe, label, face)
        tx = cursor + (tw - lw) // 2
        ty = y0 + (bar_h - lh) // 2 - 2 * SCALE
        ImageDraw.Draw(base).text( (tx, ty), label, font=face, fill=MARK_INK if on else (245, 245, 245, 200))
        cursor += tw + gap


def byline_for(year_key: str, kind: str, to_date: bool, lang: str, names: dict) -> str:
    if lang == "en":
        poss = f"{names['en']}’s" if not names["en"].endswith("s") else f"{names['en']}’"
        if year_key == "all":
            if kind == "movies":
                return f"{poss} films, all time"
            if kind == "series":
                return f"{poss} series, all time"
            return f"{poss} all time"
        if to_date:
            if kind == "movies":
                return f"{poss} year in movies to date"
            if kind == "series":
                return f"{poss} year in series to date"
            return f"{poss} year to date"
        if kind == "movies":
            return f"{poss} year in movies"
        if kind == "series":
            return f"{poss} year in series"
        return f"{poss} year in film"
    ru, gen = names["ru"], names["ruGenitive"]
    if year_key == "all":
        if kind == "movies":
            return f"фильмы {gen} за всё время"
        if kind == "series":
            return f"сериалы {gen} за всё время"
        return f"{ru} за всё время"
    if to_date:
        if kind == "movies":
            return f"год {gen} в фильмах на сегодня"
        if kind == "series":
            return f"год {gen} в сериалах на сегодня"
        return f"год {gen} на сегодня"
    if kind == "movies":
        return f"год {gen} в фильмах"
    if kind == "series":
        return f"год {gen} в сериалах"
    return f"год {gen} в кино"


def copy_for(stats: dict, names: dict, year_key: str, kind: str, lang: str) -> dict:
    hours_s, hours_n = fmt_hours(float(stats.get("hours") or 0))
    count = int(stats.get("count") or 0)
    avg = stats.get("avgRating")
    to_date = bool(stats.get("toDate")) and year_key != "all"
    if lang == "ru":
        rated = f"{fmt_num(count, 'ru')} {plural_ru(count, 'оценка', 'оценки', 'оценок')}"
        hours = f"{fmt_num(hours_s, 'ru')} {plural_ru(round(hours_n), 'час', 'часа', 'часов')}"
        headline = "За всё время" if year_key == "all" else year_key
        name = names["ru"]
        period = "за всё время" if year_key == "all" else f"в {year_key}"
        if year_key == "all":
            kind_bit = {"movies": " Фильмы.", "series": " Сериалы.", "all": ""}[kind]
        else:
            kind_bit = {"movies": " Фильмы.", "series": " Сериалы.", "all": " Личный год в кино и сериалах."}[kind]
        avg_bit = f" Средняя {avg:.1f}." if isinstance(avg, (int, float)) else ""
        description = f"{rated} · {hours} {period}.{avg_bit}{kind_bit}"
        locale = "ru_RU"
    else:
        rated = f"{fmt_num(count, 'en')} {en_plural(count, 'title rated', 'titles rated')}"
        hours = f"{fmt_num(hours_s, 'en')} {en_plural(round(hours_n), 'hour', 'hours')}"
        headline = "All time" if year_key == "all" else year_key
        name = names["en"]
        period = "all time" if year_key == "all" else f"in {year_key}"
        if year_key == "all":
            kind_bit = {"movies": " Movies.", "series": " Series.", "all": ""}[kind]
        else:
            kind_bit = {"movies": " Movies.", "series": " Series.", "all": " A personal year in film and series."}[kind]
        avg_bit = f" Average {avg:.1f}." if isinstance(avg, (int, float)) else ""
        description = f"{rated} · {hours} {period}.{avg_bit}{kind_bit}"
        locale = "en_US"
    year_label = headline if year_key == "all" else year_key
    title = f"{name} · {year_label} · IMDb Wrapped"
    return {
        "year": year_key,
        "headline": headline,
        "byline": byline_for(year_key, kind, to_date, lang, names),
        "kicker": f"{rated} · {hours}",
        "title": title,
        "description": description,
        "imageAlt": f"IMDb Wrapped: {name}, {headline}, {rated}, {hours}",
        "locale": locale,
        "allTime": year_key == "all",
        "lang": lang,
        "kind": kind,
    }


def canonical(site: str, lang: str, year_key: str, kind: str, default_year: str) -> str:
    if not site:
        return ""
    q = []
    if lang != "ru":
        q.append(f"lang={lang}")
    if year_key != default_year:
        q.append(f"year={year_key}")
    if kind != "all":
        q.append(f"kind={kind}")
    return f"{site}/" + (f"?{'&'.join(q)}" if q else "")


def compose(base: Image.Image, avatar: Image.Image | None, faces: dict, text: dict) -> Image.Image:
    canvas = base.copy()
    draw = ImageDraw.Draw(canvas)
    pad = 64 * SCALE
    mark_w = draw_imdb_mark(canvas, pad, 42 * SCALE, faces["mark"])
    draw.text(
        (pad + mark_w + 14 * SCALE, 52 * SCALE),
        "Wrapped",
        font=faces["wrapped"],
        fill=MUTED,
    )
    draw_kind_switch(canvas, text["lang"], text["kind"], faces["pill"])

    headline = text["headline"]
    if text["allTime"]:
        face = faces["all_ru"] if text["lang"] == "ru" else faces["all_en"]
    else:
        face = faces["bebas"]
    hw, hh = text_size(draw, headline, face)
    max_w = CW - pad * 2
    if hw > max_w and not text["allTime"]:
        # shrink numeric year if needed; shouldn't happen
        face = faces["bebas_sm"]
        hw, hh = text_size(draw, headline, face)
    year_y = CH - pad - 118 * SCALE - hh
    draw.text((pad - (6 * SCALE if not text["allTime"] else 0), year_y), headline, font=face, fill=INK)

    row_y = year_y + hh - (4 * SCALE if text["allTime"] else 8 * SCALE)
    text_x = pad
    av_size = 44 * SCALE
    if avatar is not None:
        av = circle(avatar, av_size)
        ring = Image.new("RGBA", (av_size + 4, av_size + 4), (0, 0, 0, 0))
        ImageDraw.Draw(ring).ellipse((0, 0, av_size + 3, av_size + 3), outline=(255, 255, 255, 36), width=2)
        canvas.alpha_composite(ring, (pad - 2, row_y + 2))
        canvas.alpha_composite(av, (pad, row_y + 4))
        text_x = pad + av_size + 16 * SCALE
    draw.text((text_x, row_y + 6 * SCALE), text["byline"], font=faces["inter"], fill=MUTED)
    draw.text((text_x, row_y + 38 * SCALE), text["kicker"], font=faces["inter_bold"], fill=INK)
    return canvas


def apple_touch(mark_font: ImageFont.FreeTypeFont) -> Image.Image:
    size = 180
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=40, fill=YELLOW)
    tw, th = text_size(draw, "W", mark_font)
    draw.text(((size - tw) / 2, (size - th) / 2 - 8), "W", font=mark_font, fill=MARK_INK)
    return im.convert("RGB")


def write_favicon(path: Path) -> None:
    path.write_text(
        """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
  <rect width="32" height="32" rx="7" fill="#F5C518"/>
  <text x="16" y="23" text-anchor="middle" font-family="Inter, Arial, sans-serif"
        font-size="18" font-weight="800" font-style="italic" fill="#0c0c0c">W</text>
</svg>
""",
        encoding="utf-8",
    )


def save_card(im: Image.Image, dest: Path) -> None:
    rgb = im.convert("RGB").resize((W, H), Image.Resampling.LANCZOS)
    rgb = rgb.filter(ImageFilter.UnsharpMask(radius=0.6, percent=80, threshold=2))
    dest.parent.mkdir(parents=True, exist_ok=True)
    rgb.save(dest, "JPEG", quality=88, optimize=True, progressive=True)


def stats_for(data: dict, year_key: str, kind: str) -> dict:
    bundle = data.get("allTime") if year_key == "all" else (data.get("byYear") or {}).get(year_key)
    if not bundle:
        bundle = data.get("allTime") or {}
    return bundle.get(kind) or bundle.get("all") or {}


def main() -> None:
    if not STATS.exists():
        raise SystemExit(f"Missing {STATS}. Run npm run data first.")
    cfg = load_config()
    data = json.loads(STATS.read_text())
    names = display_names(cfg, fallback=(data.get("profile") or {}).get("username") or "User")
    default_year = str(data.get("defaultYear") or "")
    years = [str(y) for y in (data.get("years") or [])]
    year_keys = years + ["all"]
    avatar_url = (data.get("profile") or {}).get("avatar") or ""
    site = (cfg.get("siteUrl") or "").rstrip("/")

    PUBLIC.mkdir(parents=True, exist_ok=True)
    OG_DIR.mkdir(parents=True, exist_ok=True)
    posters_dir = CACHE / "posters"
    posters_dir.mkdir(parents=True, exist_ok=True)
    fonts = ensure_fonts()

    urls: list[str] = []
    for year_key in year_keys:
        for kind in KINDS:
            urls.extend(u for u in (stats_for(data, year_key, kind).get("heroPosters") or [])[:40] if u)
    if avatar_url:
        urls.append(avatar_url)
    unique = list(dict.fromkeys(urls))
    loaded: dict[str, Image.Image | None] = {}
    with ThreadPoolExecutor(max_workers=12) as pool:
        jobs = {pool.submit(load_image, url, posters_dir): url for url in unique}
        for fut in as_completed(jobs):
            loaded[jobs[fut]] = fut.result()

    faces = {
        "bebas": font(fonts["BebasNeue-Regular.ttf"], 188 * SCALE),
        "bebas_sm": font(fonts["BebasNeue-Regular.ttf"], 110 * SCALE),
        "all_en": font(fonts["BebasNeue-Regular.ttf"], 96 * SCALE),
        "all_ru": font(fonts["InterVariable.ttf"], 72 * SCALE, 800),
        "inter": font(fonts["InterVariable.ttf"], 22 * SCALE, 500),
        "inter_bold": font(fonts["InterVariable.ttf"], 22 * SCALE, 650),
        "wrapped": font(fonts["InterVariable.ttf"], 28 * SCALE, 600),
        "mark": font(fonts["InterVariable.ttf"], 26 * SCALE, 800),
        "pill": font(fonts["InterVariable.ttf"], 15 * SCALE, 650),
        "touch": font(fonts["InterVariable.ttf"], 110, 800),
    }

    pages: dict[str, dict] = {}
    mosaic_cache: dict[tuple[str, str], Image.Image] = {}
    n = 0
    for year_key in year_keys:
        for kind in KINDS:
            st = stats_for(data, year_key, kind)
            poster_imgs = [loaded[u] for u in (st.get("heroPosters") or [])[:40] if loaded.get(u) is not None]
            cache_id = (year_key, kind)
            if cache_id not in mosaic_cache:
                layer = mosaic(poster_imgs)
                layer.alpha_composite(shade(layer.size))
                mosaic_cache[cache_id] = layer
            avatar = loaded.get(avatar_url) if avatar_url else None
            for lang in LANGS:
                text = copy_for(st, names, year_key, kind, lang)
                card = compose(mosaic_cache[cache_id], avatar, faces, text)
                rel = f"og/{lang}-{year_key}-{kind}.jpg"
                save_card(card, PUBLIC / rel)
                image = f"{site}/{rel}" if site else rel
                key = f"{lang}|{year_key}|{kind}"
                pages[key] = {
                    "title": text["title"],
                    "description": text["description"],
                    "image": image,
                    "imageFile": rel,
                    "imageAlt": text["imageAlt"],
                    "locale": text["locale"],
                    "canonical": canonical(site, lang, year_key, kind, default_year),
                    "lang": lang,
                    "year": year_key,
                    "kind": kind,
                }
                n += 1
                print(f"[og] {rel}")

    default_rel = f"og/ru-{default_year}-all.jpg"
    default_src = PUBLIC / default_rel
    if default_src.exists():
        (PUBLIC / "og.jpg").write_bytes(default_src.read_bytes())
    apple_touch(faces["touch"]).save(PUBLIC / "apple-touch-icon.png", "PNG")
    write_favicon(PUBLIC / "favicon.svg")

    meta = {
        "siteUrl": site,
        "defaultYear": default_year,
        "defaultKind": "all",
        "defaultLang": "ru",
        "width": W,
        "height": H,
        "profileUrl": parse_profile_url(cfg["imdbUrl"])["url"],
        "name": names["ru"],
        "nameEn": names["en"],
        "years": years,
        "pages": pages,
    }
    (ROOT / "og-meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    years_map = "\n".join(f"\t{y} {y}" for y in years)
    caddy = f"""# Generated — rewrite /imdb query strings to prerendered OG HTML.
map {{query.lang}} {{og_lang}} {{
	en en
	ru ru
	default ru
}}
map {{query.kind}} {{og_kind}} {{
	movies movies
	series series
	all all
	default all
}}
map {{query.year}} {{og_year}} {{
	all all
{years_map}
	default {default_year}
}}
@imdb_page {{
	path /imdb /imdb/ /imdb/index.html
}}
rewrite @imdb_page /imdb/p/{{og_lang}}/{{og_year}}/{{og_kind}}/index.html
"""
    (ROOT / "og-caddy.conf").write_text(caddy, encoding="utf-8")
    print(f"[og] {n} cards")


if __name__ == "__main__":
    main()
