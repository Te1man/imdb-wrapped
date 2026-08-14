import { useState } from "react";
import type { CatalogKind, NamedCount } from "./types";
import { useLocale } from "./LocaleContext";
import { fmt, tagName } from "./i18n";

type Mode = "watched" | "rated";

function barWidth(row: NamedCount, mode: Mode, max: number) {
  if (max <= 0) return 0;
  const v = mode === "rated" ? row.avgRating || 0 : row.count;
  return Math.max(6, (v / max) * 100);
}

function ThemeCol({
  heading,
  rows,
  mode,
  kind,
  capitalize,
}: {
  heading: string;
  rows: NamedCount[];
  mode: Mode;
  kind: CatalogKind;
  capitalize?: boolean;
}) {
  const { t, lang } = useLocale();
  if (!rows.length) return null;
  const max = Math.max(
    1,
    ...rows.map((r) => (mode === "rated" ? r.avgRating || 0 : r.count)),
  );
  return (
    <div className="theme-col">
      <h3>{heading}</h3>
      <ul className="theme-rows" key={mode}>
        {rows.map((row, i) => (
          <li key={row.id || row.name} style={{ ["--i" as string]: i } as React.CSSProperties}>
            <i className="theme-bar" style={{ width: `${barWidth(row, mode, max)}%` }} />
            <span className={`theme-name${capitalize && lang !== "ru" ? " is-kw" : ""}`}>
              {tagName(row.name, lang)}
            </span>
            <span className="theme-n">
              {mode === "rated" && row.avgRating != null ? (
                <b>{row.avgRating.toFixed(1)}</b>
              ) : (
                t.titlesByKind(fmt(row.count, lang), row.count, kind)
              )}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function ThemesKeywords({
  themes,
  themesRated,
  keywords,
  keywordsRated,
  kind,
}: {
  themes?: NamedCount[];
  themesRated?: NamedCount[];
  keywords?: NamedCount[];
  keywordsRated?: NamedCount[];
  kind: CatalogKind;
}) {
  const { t } = useLocale();
  const [mode, setMode] = useState<Mode>("watched");
  const themeRows = mode === "rated" ? themesRated || [] : themes || [];
  const keywordRows = mode === "rated" ? keywordsRated || [] : keywords || [];
  if (!themeRows.length && !keywordRows.length) return null;
  return (
    <section className="block themes-block">
      <div className="activity-toolbar">
        <h2>{t.themesKeywords}</h2>
        <div className="text-toggle" role="group">
          <button type="button" className={mode === "watched" ? "on" : undefined} onClick={() => setMode("watched")}>
            {t.mostWatched}
          </button>
          <button type="button" className={mode === "rated" ? "on" : undefined} onClick={() => setMode("rated")}>
            {t.byRating}
          </button>
        </div>
      </div>
      <div className="theme-cols">
        <ThemeCol heading={t.themes} rows={themeRows} mode={mode} kind={kind} />
        <ThemeCol heading={t.keywords} rows={keywordRows} mode={mode} kind={kind} capitalize />
      </div>
    </section>
  );
}
