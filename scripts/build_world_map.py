#!/usr/bin/env python3
"""Project Natural Earth 110m countries to compact SVG paths."""

from __future__ import annotations

import json
import math
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "src" / "data" / "world-paths.json"
SRC = (
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/"
    "master/geojson/ne_110m_admin_0_countries.geojson"
)
WIDTH = 1000
PAD = 8


def iso_of(props: dict) -> str | None:
    eh = props.get("ISO_A2_EH") or ""
    a2 = props.get("ISO_A2") or ""
    if len(eh) == 2 and eh != "-99":
        return eh
    if len(a2) == 2 and a2 != "-99":
        return a2
    return None


def project(lon: float, lat: float) -> tuple[float, float]:
    lam = math.radians(lon)
    phi = math.radians(lat)
    x = (3 * lam / (2 * math.pi)) * math.sqrt(max(0.0, math.pi**2 / 3 - phi * phi))
    return x, phi


def split_ring(coords: list[list[float]]) -> list[list[list[float]]]:
    if not coords:
        return []
    parts: list[list[list[float]]] = []
    cur = [coords[0]]
    for prev, pt in zip(coords, coords[1:]):
        if abs(pt[0] - prev[0]) > 180:
            if len(cur) >= 2:
                parts.append(cur)
            cur = [pt]
        else:
            cur.append(pt)
    if len(cur) >= 2:
        parts.append(cur)
    return parts


def rings_of(geom: dict) -> list:
    kind = geom.get("type")
    if kind == "Polygon":
        return [geom["coordinates"]]
    if kind == "MultiPolygon":
        return geom["coordinates"]
    return []


def path_from_xy(points: list[tuple[float, float]]) -> str:
    if len(points) < 3:
        return ""
    parts = [f"M{points[0][0]} {points[0][1]}"]
    for x, y in points[1:]:
        parts.append(f"L{x} {y}")
    parts.append("Z")
    return "".join(parts)


def main() -> None:
    print(f"Downloading {SRC} ...", flush=True)
    with urllib.request.urlopen(SRC, timeout=60) as resp:
        geo = json.loads(resp.read().decode())

    raw: list[tuple[str, str, list[list[list[tuple[float, float]]]]]] = []
    pts: list[tuple[float, float]] = []
    for feat in geo["features"]:
        props = feat.get("properties") or {}
        iso = iso_of(props)
        if not iso or iso == "AQ":
            continue
        name = props.get("NAME") or props.get("ADMIN") or iso
        polys: list[list[list[tuple[float, float]]]] = []
        for poly in rings_of(feat["geometry"]):
            projected_rings: list[list[tuple[float, float]]] = []
            for ring in poly:
                xy_ring = [[c[0], c[1]] for c in ring]
                for part in split_ring(xy_ring):
                    xy = [project(c[0], c[1]) for c in part]
                    if len(xy) >= 3:
                        projected_rings.append(xy)
                        pts.extend(xy)
            if projected_rings:
                polys.append(projected_rings)
        if polys:
            raw.append((iso, name, polys))

    minx = min(p[0] for p in pts)
    maxx = max(p[0] for p in pts)
    miny = min(p[1] for p in pts)
    maxy = max(p[1] for p in pts)
    scale = (WIDTH - 2 * PAD) / (maxx - minx)
    height = (maxy - miny) * scale + 2 * PAD

    def to_svg(x: float, y: float) -> tuple[float, float]:
        return (
            round(PAD + (x - minx) * scale, 1),
            round(PAD + (maxy - y) * scale, 1),
        )

    merged: dict[str, dict] = {}
    for iso, name, polys in raw:
        chunks: list[str] = []
        for poly in polys:
            for ring in poly:
                d = path_from_xy([to_svg(x, y) for x, y in ring])
                if d:
                    chunks.append(d)
        if chunks:
            entry = merged.setdefault(iso, {"id": iso, "name": name, "d": []})
            entry["d"].extend(chunks)

    countries = [
        {"id": row["id"], "name": row["name"], "d": "".join(row["d"])}
        for row in (merged[k] for k in sorted(merged))
    ]
    payload = {
        "viewBox": f"0 0 {WIDTH} {round(height, 1)}",
        "countries": countries,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, separators=(",", ":")))
    print(f"Wrote {OUT} ({OUT.stat().st_size} bytes, {len(countries)} countries)", flush=True)


if __name__ == "__main__":
    main()
