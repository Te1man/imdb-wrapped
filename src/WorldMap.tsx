import { useMemo, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import type { NamedCount } from "./types";
import world from "./data/world-paths.json";
import { useLocale } from "./LocaleContext";
import { countryName, fmt as fmtLocale } from "./i18n";

type WorldData = {
  viewBox: string;
  countries: { id: string; name: string; d: string }[];
};

const paths = world as WorldData;
const MAX_ZOOM = 6;
const ZOOM_STEP = 1.65;

function lerp(a: number, b: number, t: number) {
  return Math.round(a + (b - a) * t);
}

function fillFor(count: number, max: number, hover: boolean) {
  if (count <= 0) return hover ? "#2a2a2a" : "#1c1c1c";
  const t = Math.max(0, Math.min(1, Math.log(count) / Math.log(Math.max(2, max))));
  const u = hover ? Math.min(1, t * 0.72 + 0.28) : t;
  return `rgb(${lerp(74, 245, u)}, ${lerp(58, 197, u)}, ${lerp(8, 24, u)})`;
}

function mapDelay(d: string) {
  const m = /^M\s*([\d.]+)/.exec(d);
  const x = m ? Number(m[1]) : 0;
  return `${(x / 1000) * 0.7}s`;
}

export function WorldMapBlock({ countries }: { countries: NamedCount[] }) {
  const { t, lang } = useLocale();
  const frameRef = useRef<HTMLDivElement>(null);
  const drag = useRef<{ x: number; y: number; panX: number; panY: number } | null>(null);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [hover, setHover] = useState<{
    id: string;
    name: string;
    count: number;
    x: number;
    y: number;
  } | null>(null);

  const byId = useMemo(() => {
    const map = new Map<string, NamedCount>();
    for (const c of countries) {
      if (c.id) map.set(c.id, c);
    }
    return map;
  }, [countries]);

  const max = useMemo(
    () => Math.max(1, ...countries.map((c) => c.count)),
    [countries],
  );

  const vb = paths.viewBox.split(" ").map(Number);
  const vbW = vb[2] || 1000;
  const vbH = vb[3] || 460;
  const cx = vbW / 2;
  const cy = vbH / 2;

  function clampPan(next: { x: number; y: number }, scale: number) {
    const maxX = ((scale - 1) * vbW) / 2;
    const maxY = ((scale - 1) * vbH) / 2;
    return {
      x: Math.max(-maxX, Math.min(maxX, next.x)),
      y: Math.max(-maxY, Math.min(maxY, next.y)),
    };
  }

  function applyZoom(dir: 1 | -1) {
    setZoom((z) => {
      const next = dir > 0 ? Math.min(MAX_ZOOM, z * ZOOM_STEP) : Math.max(1, z / ZOOM_STEP);
      if (next <= 1.01) {
        setPan({ x: 0, y: 0 });
        return 1;
      }
      setPan((p) => clampPan(p, next));
      return next;
    });
  }

  function clientToVb(e: { clientX: number; clientY: number }) {
    const rect = frameRef.current?.getBoundingClientRect();
    if (!rect) return { x: 0, y: 0 };
    return {
      x: ((e.clientX - rect.left) / rect.width) * vbW,
      y: ((e.clientY - rect.top) / rect.height) * vbH,
    };
  }

  function onPointerDown(e: ReactPointerEvent<SVGSVGElement>) {
    if (zoom <= 1 || e.button !== 0) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    drag.current = { x: e.clientX, y: e.clientY, panX: pan.x, panY: pan.y };
  }

  function onPointerMove(e: ReactPointerEvent<SVGSVGElement>) {
    const rect = frameRef.current?.getBoundingClientRect();
    if (rect) {
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      setHover((h) => (h ? { ...h, x, y } : h));
    }
    if (!drag.current) return;
    const sx = rect ? vbW / rect.width : 1;
    const sy = rect ? vbH / rect.height : 1;
    setPan(
      clampPan(
        {
          x: drag.current.panX + (e.clientX - drag.current.x) * sx,
          y: drag.current.panY + (e.clientY - drag.current.y) * sy,
        },
        zoom,
      ),
    );
  }

  function onPointerUp(e: ReactPointerEvent<SVGSVGElement>) {
    drag.current = null;
    if (e.currentTarget.hasPointerCapture(e.pointerId)) {
      e.currentTarget.releasePointerCapture(e.pointerId);
    }
  }

  function enterCountry(id: string, fallback: string, e: ReactPointerEvent<SVGPathElement>) {
    const row = byId.get(id);
    const name = countryName(row?.name || fallback, lang);
    const pt = clientToVb(e);
    const rect = frameRef.current?.getBoundingClientRect();
    setHover({
      id,
      name,
      count: row?.count || 0,
      x: rect ? e.clientX - rect.left : pt.x,
      y: rect ? e.clientY - rect.top : pt.y,
    });
  }

  if (!countries.length) return null;

  return (
    <section className="block world-map-block">
      <h2 className="world-map-title">{t.worldMap}</h2>
      <div className={`world-shell${zoom > 1 ? " is-zoomed" : ""}`} ref={frameRef}>
        <div className="world-frame">
          <svg
            viewBox={paths.viewBox}
            role="img"
            aria-label={t.worldMap}
            onPointerDown={onPointerDown}
            onPointerMove={onPointerMove}
            onPointerUp={onPointerUp}
            onPointerLeave={() => {
              drag.current = null;
              setHover(null);
            }}
          >
            <g transform={`translate(${pan.x} ${pan.y}) translate(${cx} ${cy}) scale(${zoom}) translate(${-cx} ${-cy})`}>
              {paths.countries.map((c) => {
                const count = byId.get(c.id)?.count || 0;
                const active = hover?.id === c.id;
                return (
                  <path
                    key={c.id}
                    d={c.d}
                    className={count > 0 ? "has-data" : undefined}
                    fill={fillFor(count, max, active)}
                    fillRule="evenodd"
                    style={
                      count > 0
                        ? ({ ["--star" as string]: mapDelay(c.d) } as React.CSSProperties)
                        : undefined
                    }
                    onPointerEnter={(e) => enterCountry(c.id, c.name, e)}
                    onPointerLeave={() => setHover((h) => (h?.id === c.id ? null : h))}
                  />
                );
              })}
            </g>
          </svg>
          <div className="world-zoom">
            <button type="button" onClick={() => applyZoom(1)} aria-label="+">
              +
            </button>
            <button type="button" onClick={() => applyZoom(-1)} disabled={zoom <= 1} aria-label="−">
              −
            </button>
          </div>
          <p className="world-attr">{t.mapAttribution}</p>
        </div>
        {hover && (
          <div
            className="world-tip"
            role="tooltip"
            style={{ left: hover.x, top: hover.y }}
          >
            <b>{hover.name}</b>
            {hover.count > 0 ? <span>{fmtLocale(hover.count, lang)}</span> : null}
          </div>
        )}
      </div>
      <h2 className="world-list-head">{t.countriesN(countries.length)}</h2>
      <ul className="countries">
        {countries.map((c) => (
          <li key={c.id || c.name}>
            <b>{countryName(c.name, lang)}</b>
            <span>{fmtLocale(c.count, lang)}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
