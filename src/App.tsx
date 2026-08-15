import { useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from "react";
import type {
  ActivityPoster,
  CatalogKind,
  HighsAndLows,
  TitleCard,
  WatchlistData,
  WatchlistItem,
  WrappedData,
  YearStats,
} from "./types";
import { FALLBACK_STATS, useData } from "./DataContext";
import { WorldMapBlock } from "./WorldMap";
import { ThemesKeywords } from "./ThemesKeywords";
import { useLocale } from "./LocaleContext";
import {
  MONTHS,
  WEEKDAYS,
  WEEKDAYS_FULL,
  WEEKDAYS_WHEN,
  decadeName,
  languageName,
  fmt as fmtLocale,
  formatDate,
  formatDateLong,
  formatDateShort,
  formatUpdatedAt,
  latestUpdatedAt,
  genreName,
  mediaPoster,
  mediaTitle,
  tagName,
  typeLabel,
  type Copy,
  type Lang,
} from "./i18n";

const KINDS: CatalogKind[] = ["movies", "series", "all"];
const MOVIE_TYPES = new Set([
  "movie",
  "tvMovie",
  "short",
  "video",
  "tvSpecial",
  "tvShort",
  "musicVideo",
]);
const SERIES_TYPES = new Set([
  "tvSeries",
  "tvMiniSeries",
  "tvEpisode",
  "podcastSeries",
  "podcastEpisode",
]);

function fmt(n: number, lang: Lang) {
  return fmtLocale(n, lang);
}

function readKindParam(): CatalogKind {
  const q = new URLSearchParams(window.location.search).get("kind");
  if (q === "movies" || q === "series" || q === "all") return q;
  try {
    const stored = localStorage.getItem("imdbw-kind");
    if (stored === "movies" || stored === "series" || stored === "all") return stored;
  } catch {
    /* ignore */
  }
  return "all";
}

function setKindParam(kind: CatalogKind) {
  const url = new URL(window.location.href);
  if (kind === "all") url.searchParams.delete("kind");
  else url.searchParams.set("kind", kind);
  window.history.replaceState({}, "", url);
  try {
    localStorage.setItem("imdbw-kind", kind);
  } catch {
    /* ignore */
  }
}

function matchesKind(type: string | undefined, kind: CatalogKind) {
  if (kind === "all") return true;
  if (kind === "movies") return MOVIE_TYPES.has(type || "movie");
  return SERIES_TYPES.has(type || "");
}

function telegramLink(url?: string | null) {
  if (!url) return null;
  const handle = url.match(/t\.me\/([^/?#]+)/i)?.[1];
  return (
    <a href={url} target="_blank" rel="noreferrer">
      {handle ? `@${handle}` : url}
    </a>
  );
}

const REPO_URL = "https://github.com/Te1man/imdb-wrapped";

function yearByline(
  year: string,
  toDate: boolean,
  kind: CatalogKind,
  t: Copy,
  updatedAt: string,
) {
  if (year === "all") {
    if (kind === "movies") return t.yearAllTimeMovies;
    if (kind === "series") return t.yearAllTimeSeries;
    return t.yearAllTime;
  }
  if (toDate) {
    if (kind === "movies") return t.yearToDateMovies(updatedAt);
    if (kind === "series") return t.yearToDateSeries(updatedAt);
    return t.yearToDate(updatedAt);
  }
  if (kind === "movies") return t.yearInMovies;
  if (kind === "series") return t.yearInSeries;
  return t.yearInFilm;
}

function readYearParam(data: WrappedData = FALLBACK_STATS): string {
  const y = new URLSearchParams(window.location.search).get("year");
  if (y === "all") return "all";
  if (y && data.byYear[y]) return y;
  return String(data.defaultYear);
}

function setYearParam(year: string, data: WrappedData) {
  const url = new URL(window.location.href);
  if (year === String(data.defaultYear)) url.searchParams.delete("year");
  else url.searchParams.set("year", year);
  window.history.replaceState({}, "", url);
}

function weekdayCounts(daily: Record<string, number>) {
  const counts = [0, 0, 0, 0, 0, 0, 0];
  for (const [date, n] of Object.entries(daily)) {
    if (!n) continue;
    const d = new Date(`${date}T00:00:00`);
    if (Number.isNaN(d.getTime())) continue;
    const js = d.getDay();
    counts[js === 0 ? 6 : js - 1] += n;
  }
  return counts;
}

function chartBarHeight(n: number, max: number, cap = 160) {
  if (n <= 0) return 3;
  return Math.max(3, (n / Math.max(1, max)) * cap);
}

function dec(n: number, lang: Lang, digits = 1) {
  const s = n.toFixed(digits);
  return lang === "ru" ? s.replace(".", ",") : s;
}

function CountUp({
  value,
  digits = 0,
  prefix = "",
  suffix = "",
  duration = 820,
}: {
  value: number;
  digits?: number;
  prefix?: string;
  suffix?: string;
  duration?: number;
}) {
  const { lang } = useLocale();
  const ref = useRef<HTMLSpanElement>(null);
  const [current, setCurrent] = useState(0);
  const [live, setLive] = useState(false);

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setLive(true);
      setCurrent(value);
      return;
    }
    setLive(false);
    setCurrent(0);
    const play = () => setLive(true);
    const host = el.closest("main > *");
    if (!host) {
      play();
      return;
    }
    if (host.classList.contains("is-in")) {
      play();
      return;
    }
    const mo = new MutationObserver(() => {
      if (host.classList.contains("is-in")) {
        play();
        mo.disconnect();
      }
    });
    mo.observe(host, { attributes: true, attributeFilter: ["class"] });
    return () => mo.disconnect();
  }, [value]);

  useEffect(() => {
    if (!live) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setCurrent(value);
      return;
    }
    const start = performance.now();
    let raf = 0;
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - (1 - t) ** 3;
      setCurrent(value * eased);
      if (t < 1) raf = requestAnimationFrame(tick);
      else setCurrent(value);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [live, value, duration]);

  const text = digits > 0 ? dec(current, lang, digits) : fmt(Math.round(current), lang);
  return (
    <span ref={ref}>
      {prefix}
      {text}
      {suffix}
    </span>
  );
}

function WeekdayChart({ daily, kind }: { daily: Record<string, number>; kind: CatalogKind }) {
  const { lang, t } = useLocale();
  const counts = weekdayCounts(daily);
  const max = Math.max(1, ...counts);
  const labels = WEEKDAYS[lang];
  const full = WEEKDAYS_FULL[lang];
  const when = WEEKDAYS_WHEN[lang];
  const top = counts.indexOf(Math.max(...counts));
  const topN = counts[top] || 0;
  return (
    <article className="weekday">
      <div className="weekday-chart">
        {counts.map((n, i) => (
          <div key={full[i]} className="weekday-col">
            <div className="weekday-bar-wrap">
              <div
                className="weekday-bar"
                style={
                  {
                    height: `${Math.max(n > 0 ? 8 : 3, (n / max) * 100)}%`,
                    ["--i" as string]: i,
                  } as React.CSSProperties
                }
              >
                <div className="weekday-tip" role="tooltip">
                  <b>{t.weekdayTip(fmt(n, lang), n, kind)}</b>
                  <span>{full[i]}</span>
                </div>
              </div>
            </div>
            <em>{labels[i]}</em>
          </div>
        ))}
      </div>
      <span>{t.byWeekday}</span>
      <small>{t.byWeekdayHint(when[top], fmt(topN, lang), topN)}</small>
    </article>
  );
}

function titleHref(t: TitleCard, profileUrl?: string) {
  return t.url || (t.id ? `https://www.imdb.com/title/${t.id}/` : profileUrl || FALLBACK_STATS.profile.url);
}

function normalizeActivityPoster(p: ActivityPoster): {
  id?: string | null;
  title: string;
  titleRu?: string | null;
  poster?: string | null;
  posterRu?: string | null;
  url?: string | null;
} {
  if (typeof p === "string") return { title: "", poster: p };
  return {
    id: p.id,
    title: p.title || "",
    titleRu: p.titleRu,
    poster: p.poster,
    posterRu: p.posterRu,
    url: p.url,
  };
}

function activityPosterSrc(p: ActivityPoster): string | null {
  const n = normalizeActivityPoster(p);
  return n.poster || n.posterRu || null;
}

function ActivityStackPosters({ posters }: { posters: ActivityPoster[] }) {
  const { lang } = useLocale();
  return (
    <>
      {posters.slice(0, 6).map((raw, k) => {
        const p = normalizeActivityPoster(raw);
        const src = mediaPoster(p, lang) || p.poster || p.posterRu;
        if (!src) return null;
        const title = mediaTitle(p, lang);
        const href = p.url || (p.id ? `https://www.imdb.com/title/${p.id}/` : undefined);
        const img = <img src={src} alt={title || ""} loading="lazy" />;
        return href ? (
          <a
            key={`${p.id || src}-${k}`}
            className="activity-poster"
            href={href}
            target="_blank"
            rel="noreferrer"
            title={title || undefined}
          >
            {img}
          </a>
        ) : (
          <span key={`${src}-${k}`} className="activity-poster is-static">
            {img}
          </span>
        );
      })}
    </>
  );
}

function useRevealOnScroll(resetKey: string) {
  useLayoutEffect(() => {
    const main = document.querySelector("main");
    if (!main) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const nodes = Array.from(main.children) as HTMLElement[];
    const io = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          // threshold 0: any pixel visible. Tall mobile sections (watchlist etc.)
          // never reach 0.16 of their own height inside the viewport.
          if (!entry.isIntersecting) continue;
          entry.target.classList.add("is-in");
          io.unobserve(entry.target);
        }
      },
      { threshold: 0, rootMargin: "0px 0px -6% 0px" },
    );
    const vh = window.innerHeight;
    for (const node of nodes) {
      if (node.classList.contains("is-in")) continue;
      const rect = node.getBoundingClientRect();
      const onScreen = rect.top < vh * 0.92 && rect.bottom > vh * 0.08;
      if (reduced || onScreen) {
        node.classList.add("is-in");
      } else {
        io.observe(node);
      }
    }
    return () => io.disconnect();
  }, [resetKey]);
}

function Poster({
  src,
  title,
  year,
  rating,
  href,
  caption,
  watchlisted,
  rank,
}: {
  src?: string | null;
  title: string;
  year?: number | null;
  rating?: number | null;
  href?: string | null;
  caption?: ReactNode;
  watchlisted?: boolean;
  rank?: number;
}) {
  const { t } = useLocale();
  const label = year ? `${title} (${year})` : title;
  const body = (
    <>
      <div className="poster-tip" role="tooltip">
        <span className="poster-tip-title">{label}</span>
        {rating != null && (
          <span className="poster-tip-rate">
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M12 2.6l2.76 5.84 6.4.84-4.7 4.38 1.2 6.32L12 17.02 6.34 19.98l1.2-6.32-4.7-4.38 6.4-.84L12 2.6z" />
            </svg>
            {rating}
          </span>
        )}
      </div>
      <div className="poster-frame">
        {src ? <img src={src} alt={title} loading="lazy" /> : <div className="poster-fallback">{title}</div>}
        {rank != null && <span className="poster-rank">{rank}</span>}
        {watchlisted && (
          <span className={`poster-watch${rank != null ? " shifted" : ""}`} title={t.inWatchlist} aria-label={t.inWatchlist}>
            <svg viewBox="0 0 24 34" aria-hidden="true">
              <polygon fill="#F5C518" points="24 0 0 0 0 32 12.244 26.293 24 31.773" />
              <polyline
                fill="none"
                stroke="#000"
                strokeWidth="2.2"
                strokeLinecap="round"
                strokeLinejoin="round"
                points="9.5 16.4 11.8 18.8 16.4 13.4"
              />
            </svg>
          </span>
        )}
      </div>
      {caption != null && <span className="poster-cap">{caption}</span>}
    </>
  );
  return href ? (
    <a className="poster" href={href} target="_blank" rel="noreferrer">
      {body}
    </a>
  ) : (
    <div className="poster">{body}</div>
  );
}

function vsAvgCaption(card: TitleCard) {
  if (card.userRating == null || card.imdbRating == null) return undefined;
  return (
    <span className="vs-cap">
      <span className="vs-user">{card.userRating}</span>
      {` vs ${card.imdbRating.toFixed(1)}`}
    </span>
  );
}

function PosterRow({
  heading,
  items,
  caption,
  watchlistedIds,
  className,
}: {
  heading: string;
  items: TitleCard[];
  caption?: (t: TitleCard) => ReactNode;
  watchlistedIds?: Set<string>;
  className?: string;
}) {
  const { lang } = useLocale();
  if (!items.length) return null;
  return (
    <section className={className ? `block ${className}` : "block"}>
      <h2>{heading}</h2>
      <div className="poster-row">
        {items.map((t) => (
          <Poster
            key={`${t.id}-${t.title}-${t.ratedOn}`}
            src={mediaPoster(t, lang)}
            title={mediaTitle(t, lang)}
            year={t.year}
            rating={t.userRating}
            href={titleHref(t)}
            caption={caption?.(t)}
            watchlisted={watchlistedIds?.has(t.id)}
          />
        ))}
      </div>
    </section>
  );
}

function HeadingToggle({
  options,
  value,
  onChange,
}: {
  options: { value: string; label: string }[];
  value: string;
  onChange: (value: string) => void;
}) {
  const active = options.find((opt) => opt.value === value)?.label ?? options[0]?.label ?? "";
  return (
    <>
      <div className="text-toggle is-heading heading-toggle-buttons" role="group">
        {options.map((opt) => (
          <button
            key={opt.value}
            type="button"
            className={value === opt.value ? "on" : ""}
            aria-pressed={value === opt.value}
            onClick={() => onChange(opt.value)}
          >
            {opt.label}
          </button>
        ))}
      </div>
      <label className="heading-select">
        <span className="sr-only">{active}</span>
        <select value={value} onChange={(e) => onChange(e.target.value)} aria-label={active}>
          {options.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
        <span className="heading-select-caret" aria-hidden="true">
          <svg viewBox="0 0 24 24" width="18" height="18">
            <path fill="currentColor" d="M7 10l5 5 5-5z" />
          </svg>
        </span>
      </label>
    </>
  );
}

function ToggledPosterRow({
  a,
  b,
  watchlistedIds,
  className,
}: {
  a: { heading: string; items: TitleCard[]; caption?: (t: TitleCard) => ReactNode };
  b: { heading: string; items: TitleCard[]; caption?: (t: TitleCard) => ReactNode };
  watchlistedIds?: Set<string>;
  className?: string;
}) {
  const { lang } = useLocale();
  const hasA = a.items.length > 0;
  const hasB = b.items.length > 0;
  const [side, setSide] = useState<"a" | "b">(hasA ? "a" : "b");
  const current = (side === "b" && hasB) || !hasA ? b : a;
  const active = current === b ? "b" : "a";
  if (!hasA && !hasB) return null;
  return (
    <section className={className ? `block ${className}` : "block"}>
      {hasA && hasB ? (
        <HeadingToggle
          value={active}
          onChange={(v) => setSide(v === "b" ? "b" : "a")}
          options={[
            { value: "a", label: a.heading },
            { value: "b", label: b.heading },
          ]}
        />
      ) : (
        <h2>{current.heading}</h2>
      )}
      <div className="poster-row">
        {current.items.map((t) => (
          <Poster
            key={`${t.id}-${t.title}-${t.ratedOn}`}
            src={mediaPoster(t, lang)}
            title={mediaTitle(t, lang)}
            year={t.year}
            rating={t.userRating}
            href={titleHref(t)}
            caption={current.caption?.(t)}
            watchlisted={watchlistedIds?.has(t.id)}
          />
        ))}
      </div>
    </section>
  );
}

function HighsStar({ value }: { value: number }) {
  return (
    <>
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 2.6l2.76 5.84 6.4.84-4.7 4.38 1.2 6.32L12 17.02 6.34 19.98l1.2-6.32-4.7-4.38 6.4-.84L12 2.6z" />
      </svg>
      {value.toFixed(1)}
    </>
  );
}

function HighsAndLowsBlock({
  data,
  watchlistedIds,
}: {
  data?: HighsAndLows;
  watchlistedIds?: Set<string>;
}) {
  const { t, lang } = useLocale();
  if (!data) return null;
  const cells: {
    key: keyof HighsAndLows;
    label: string;
    value: ReactNode;
    star?: boolean;
  }[] = [
    {
      key: "highestAverage",
      label: t.highestAverage,
      star: true,
      value: data.highestAverage?.imdbRating != null ? <HighsStar value={data.highestAverage.imdbRating} /> : null,
    },
    {
      key: "lowestAverage",
      label: t.lowestAverage,
      star: true,
      value: data.lowestAverage?.imdbRating != null ? <HighsStar value={data.lowestAverage.imdbRating} /> : null,
    },
    {
      key: "mostPopular",
      label: t.mostPopularOne,
      star: true,
      value: data.mostPopular?.imdbRating != null ? <HighsStar value={data.mostPopular.imdbRating} /> : null,
    },
    {
      key: "mostObscure",
      label: t.mostObscure,
      star: true,
      value: data.mostObscure?.imdbRating != null ? <HighsStar value={data.mostObscure.imdbRating} /> : null,
    },
    {
      key: "newest",
      label: t.newest,
      value: data.newest?.releaseDate
        ? formatDateLong(data.newest.releaseDate, lang)
        : data.newest?.year
          ? String(data.newest.year)
          : null,
    },
    {
      key: "oldest",
      label: t.oldest,
      value: data.oldest?.releaseDate
        ? formatDateLong(data.oldest.releaseDate, lang)
        : data.oldest?.year
          ? String(data.oldest.year)
          : null,
    },
    {
      key: "longest",
      label: t.longest,
      value: data.longest?.runtimeMin != null ? t.minutesLong(data.longest.runtimeMin) : null,
    },
    {
      key: "shortest",
      label: t.shortest,
      value: data.shortest?.runtimeMin != null ? t.minutesLong(data.shortest.runtimeMin) : null,
    },
  ].filter((cell) => data[cell.key]);
  if (!cells.length) return null;
  return (
    <section className="block highs">
      <h2>{t.highsAndLows}</h2>
      <div className="highs-grid">
        {cells.map((cell) => {
          const card = data[cell.key]!;
          return (
            <div key={cell.key} className="highs-item">
              <span className="highs-label">{cell.label}</span>
              <Poster
                src={mediaPoster(card, lang)}
                title={mediaTitle(card, lang)}
                year={card.year}
                rating={card.userRating}
                href={titleHref(card)}
                watchlisted={card.id ? watchlistedIds?.has(card.id) : false}
              />
              {cell.value ? (
                <span className={`highs-value${cell.star ? " is-rating" : ""}`}>{cell.value}</span>
              ) : (
                <span className="highs-value is-empty" />
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}

function BestOfYear({
  year,
  best,
  worst,
  watchlistedIds,
  kind,
}: {
  year: string;
  best: TitleCard[];
  worst: TitleCard[];
  watchlistedIds?: Set<string>;
  kind: CatalogKind;
}) {
  const { lang, t } = useLocale();
  const { wrapped } = useData();
  const canBest = best.length >= 2;
  const canWorst = worst.length >= 2;
  const [mode, setMode] = useState<"best" | "worst">(canBest ? "best" : "worst");
  if (!canBest && !canWorst) return null;
  const items = mode === "worst" && canWorst ? worst : best;
  const isWorst = items === worst;
  const lead = items[0];
  const nine = items.slice(1, 10);
  const ten = items.slice(10, 20);
  const count = Math.min(20, items.length);
  return (
    <section className="block bestof">
      <div className="bestof-head">
        {canBest && canWorst ? (
          <HeadingToggle
            value={isWorst ? "worst" : "best"}
            onChange={(v) => setMode(v === "worst" ? "worst" : "best")}
            options={[
              { value: "best", label: t.bestOf(year) },
              { value: "worst", label: t.worstOf(year) },
            ]}
          />
        ) : (
          <h2>{isWorst ? t.worstOf(year) : t.bestOf(year)}</h2>
        )}
        <p>
          <img src={wrapped.profile.avatar} alt="" />
          <span>{t.bestOfItems(count, kind)}</span>
        </p>
      </div>
      <div className="bestof-lead">
        <Poster
          src={mediaPoster(lead, lang)}
          title={mediaTitle(lead, lang)}
          year={lead.year}
          rating={lead.userRating}
          href={titleHref(lead)}
          watchlisted={lead.id ? watchlistedIds?.has(lead.id) : false}
        />
      </div>
      <div className="bestof-nine">
        {nine.map((card) => (
          <Poster
            key={card.id || card.title}
            src={mediaPoster(card, lang)}
            title={mediaTitle(card, lang)}
            year={card.year}
            rating={card.userRating}
            href={titleHref(card)}
            watchlisted={card.id ? watchlistedIds?.has(card.id) : false}
          />
        ))}
      </div>
      {ten.length > 0 && (
        <div className="bestof-ten">
          {ten.map((card) => (
            <Poster
              key={card.id || card.title}
              src={mediaPoster(card, lang)}
              title={mediaTitle(card, lang)}
              year={card.year}
              rating={card.userRating}
              href={titleHref(card)}
              watchlisted={card.id ? watchlistedIds?.has(card.id) : false}
            />
          ))}
        </div>
      )}
    </section>
  );
}

function milestoneDate(iso: string | null | undefined, year: string, lang: Lang) {
  return year === "all" ? formatDate(iso, lang) : formatDateShort(iso, lang);
}

function MilestonesBlock({
  stats,
  year,
  kind,
}: {
  stats: YearStats;
  year: string;
  kind: CatalogKind;
}) {
  const { lang, t } = useLocale();
  if (!stats.first && !stats.last) return null;
  const marks = stats.milestones || [];
  return (
    <section className="block milestones">
      <h2>{t.milestones}</h2>
      <div className={`milestones-board${marks.length ? "" : " no-mid"}`}>
        {stats.first && (
          <article className="milestone-end">
            <h3>{t.firstRated(kind)}</h3>
            <Poster
              src={mediaPoster(stats.first, lang)}
              title={mediaTitle(stats.first, lang)}
              year={stats.first.year}
              rating={stats.first.userRating}
              href={titleHref(stats.first)}
            />
            <p>{milestoneDate(stats.first.ratedOn, year, lang)}</p>
          </article>
        )}
        {marks.length > 0 && (
          <div className="milestone-mid">
            <h3>{t.ratingMilestones}</h3>
            <div className="milestone-grid">
              {marks.map((card) => (
                <article key={`${card.n}-${card.id || card.title}`} className="milestone-card">
                  <div className="milestone-frame">
                    <div className="milestone-frame-inner">
                      <div className="milestone-plate">
                        <strong>{t.ordinal(card.n)}</strong>
                      </div>
                      <div className="milestone-art">
                        <Poster
                          src={mediaPoster(card, lang)}
                          title={mediaTitle(card, lang)}
                          year={card.year}
                          rating={card.userRating}
                          href={titleHref(card)}
                        />
                      </div>
                    </div>
                  </div>
                  <p className="milestone-date">{milestoneDate(card.ratedOn, year, lang)}</p>
                </article>
              ))}
            </div>
          </div>
        )}
        {stats.last && (
          <article className="milestone-end last">
            <h3>{t.mostRecent(kind)}</h3>
            <Poster
              src={mediaPoster(stats.last, lang)}
              title={mediaTitle(stats.last, lang)}
              year={stats.last.year}
              rating={stats.last.userRating}
              href={titleHref(stats.last)}
            />
            <p>{milestoneDate(stats.last.ratedOn, year, lang)}</p>
          </article>
        )}
      </div>
    </section>
  );
}

function Donut({
  slices,
  center,
  sub,
}: {
  slices: { label: string; value: number; color: string }[];
  center: ReactNode;
  sub: string;
}) {
  const { lang } = useLocale();
  const total = slices.reduce((s, x) => s + x.value, 0) || 1;
  let acc = 0;
  const r = 42;
  const c = 2 * Math.PI * r;
  return (
    <div className="donut">
      <svg viewBox="0 0 120 120" className="donut-svg">
        <circle cx="60" cy="60" r={r} fill="none" stroke="#222" strokeWidth="12" />
        {slices.map((sl) => {
          const len = (sl.value / total) * c;
          const dash = `${len} ${c - len}`;
          const rot = (acc / total) * 360 - 90;
          acc += sl.value;
          return (
            <circle
              key={sl.label}
              cx="60"
              cy="60"
              r={r}
              fill="none"
              stroke={sl.color}
              strokeWidth="12"
              strokeDasharray={dash}
              transform={`rotate(${rot} 60 60)`}
              strokeLinecap="butt"
            />
          );
        })}
      </svg>
      <div className="donut-center">
        <strong>{center}</strong>
        <span>{sub}</span>
      </div>
      <ul className="donut-legend">
        {slices.map((sl) => (
          <li key={sl.label}>
            <i style={{ background: sl.color }} />
            <b>{fmt(sl.value, lang)}</b> {sl.label}
          </li>
        ))}
      </ul>
    </div>
  );
}

type ActivityView = "bars" | "heat";

function readActivityView(): ActivityView {
  try {
    const v = localStorage.getItem("imdbw-activity");
    if (v === "heat" || v === "bars") return v;
  } catch {
    /* ignore */
  }
  return "bars";
}

function ymd(d: Date) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function heatRange(year: string): { start: Date; end: Date } {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  if (year === "all") {
    const end = today;
    const start = new Date(end);
    start.setDate(start.getDate() - 52 * 7 + 1);
    return { start, end };
  }
  const y = Number(year);
  return {
    start: new Date(y, 0, 1),
    end: new Date(y, 11, 31),
  };
}

function heatLevel(count: number, max: number) {
  if (count <= 0 || max <= 0) return 0;
  const t = Math.log(count + 1) / Math.log(max + 1);
  return Math.min(4, Math.max(1, Math.ceil(t * 4)));
}

function starDelay(date: string) {
  let h = 2166136261;
  for (let i = 0; i < date.length; i++) {
    h ^= date.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return `${(Math.abs(h) % 780) / 1000}s`;
}

function Heatmap({
  daily,
  year,
}: {
  daily: Record<string, number>;
  year: string;
}) {
  const { lang, t } = useLocale();
  const months = MONTHS[lang];
  const { start, end } = heatRange(year);
  const startKey = ymd(start);
  const endKey = ymd(end);
  const pad = new Date(start);
  pad.setDate(pad.getDate() - pad.getDay());
  const last = new Date(end);
  last.setDate(last.getDate() + (6 - last.getDay()));

  const weeks: { date: string; count: number; inRange: boolean }[][] = [];
  let week: { date: string; count: number; inRange: boolean }[] = [];
  const cur = new Date(pad);
  while (cur <= last) {
    const date = ymd(cur);
    const inRange = date >= startKey && date <= endKey;
    week.push({ date, count: inRange ? daily[date] || 0 : 0, inRange });
    if (week.length === 7) {
      weeks.push(week);
      week = [];
    }
    cur.setDate(cur.getDate() + 1);
  }

  const max = Math.max(1, ...weeks.flat().map((c) => c.count));
  const monthLabels: { i: number; label: string }[] = [];
  let prevMonth = -1;
  weeks.forEach((w, i) => {
    const first = w.find((c) => c.inRange);
    if (!first) return;
    const m = Number(first.date.slice(5, 7)) - 1;
    if (m !== prevMonth) {
      prevMonth = m;
      monthLabels.push({ i, label: months[m] });
    }
  });
  const cell = 14;

  return (
    <div className="heat">
      <div className="heat-inner">
        <div className="heat-months">
          {monthLabels.map((m) => (
            <span key={`${m.label}-${m.i}`} style={{ ["--x" as string]: `${m.i * cell}px` }}>
              {m.label}
            </span>
          ))}
        </div>
        <div className="heat-dows" aria-hidden="true">
          <span />
          <span>{t.mon}</span>
          <span />
          <span>{t.wed}</span>
          <span />
          <span>{t.fri}</span>
          <span />
        </div>
        <div className="heat-weeks">
          {weeks.map((w) => (
            <div key={w[0].date} className="heat-week">
              {w.map((c) => (
                <span
                  key={c.date}
                  className={`heat-cell${c.inRange ? ` l${heatLevel(c.count, max)}` : " out"}`}
                  style={
                    c.inRange && c.count > 0
                      ? ({ ["--star" as string]: starDelay(c.date) } as React.CSSProperties)
                      : undefined
                  }
                  title={c.inRange ? t.heatTitle(formatDate(c.date, lang), c.count) : undefined}
                />
              ))}
            </div>
          ))}
        </div>
      </div>
      <div className="heat-legend">
        <span>{t.less}</span>
        <i />
        <i className="l1" />
        <i className="l2" />
        <i className="l3" />
        <i className="l4" />
        <span>{t.more}</span>
      </div>
    </div>
  );
}

function ActivityBlock({
  stats,
  year,
}: {
  stats: YearStats;
  year: string;
}) {
  const { lang, t } = useLocale();
  const months = MONTHS[lang];
  const [view, setView] = useState(readActivityView);
  useEffect(() => {
    try {
      localStorage.setItem("imdbw-activity", view);
    } catch {
      /* ignore */
    }
  }, [view]);
  const maxMonth = Math.max(1, ...stats.monthly);

  return (
    <section className="block activity">
      <div className="activity-toolbar">
        <h2>{year === "all" ? t.last12Months : t.ratedThisYear}</h2>
        <div className="view-toggle" role="group" aria-label={t.activityView}>
          <button
            type="button"
            className={view === "bars" ? "on" : ""}
            aria-pressed={view === "bars"}
            title={t.monthlyBars}
            onClick={() => setView("bars")}
          >
            <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
              <rect x="1" y="9" width="3" height="6" fill="currentColor" rx="0.5" />
              <rect x="6.5" y="4" width="3" height="11" fill="currentColor" rx="0.5" />
              <rect x="12" y="7" width="3" height="8" fill="currentColor" rx="0.5" />
            </svg>
          </button>
          <button
            type="button"
            className={view === "heat" ? "on" : ""}
            aria-pressed={view === "heat"}
            title={t.heatCalendar}
            onClick={() => setView("heat")}
          >
            <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
              <rect x="1" y="1" width="3" height="3" rx="0.5" fill="currentColor" />
              <rect x="6.5" y="1" width="3" height="3" rx="0.5" fill="currentColor" />
              <rect x="12" y="1" width="3" height="3" rx="0.5" fill="currentColor" />
              <rect x="1" y="6.5" width="3" height="3" rx="0.5" fill="currentColor" />
              <rect x="6.5" y="6.5" width="3" height="3" rx="0.5" fill="currentColor" />
              <rect x="12" y="6.5" width="3" height="3" rx="0.5" fill="currentColor" />
              <rect x="1" y="12" width="3" height="3" rx="0.5" fill="currentColor" />
              <rect x="6.5" y="12" width="3" height="3" rx="0.5" fill="currentColor" />
              <rect x="12" y="12" width="3" height="3" rx="0.5" fill="currentColor" />
            </svg>
          </button>
        </div>
      </div>
      {view === "heat" ? (
        <Heatmap key={`${year}-${stats.count}`} daily={stats.daily || {}} year={year} />
      ) : (
        <>
          <div className="activity-head">
            <span>{months[0]}</span>
            <span>{months[11]}</span>
          </div>
          <div className="activity-chart" key={`${year}-${stats.monthly.join(",")}`}>
            {stats.monthly.map((n, i) => (
              <div key={months[i]} className="activity-col" title={`${months[i]}: ${n}`}>
                <div className="activity-stack">
                  <ActivityStackPosters posters={stats.monthlyPosters[i] || []} />
                  <div
                    className="activity-bar"
                    style={
                      {
                        height: `${Math.max(n > 0 ? 22 : 6, (n / maxMonth) * 160)}px`,
                        ["--i" as string]: i,
                      } as React.CSSProperties
                    }
                  >
                    {n > 0 ? (
                      <span className="activity-n">
                        <CountUp value={n} duration={700} />
                      </span>
                    ) : null}
                  </div>
                </div>
                <em>{months[i]}</em>
              </div>
            ))}
          </div>
        </>
      )}
    </section>
  );
}

function yearPosters(stats: YearStats | undefined): string[] {
  if (!stats) return [];
  const fromMonths = stats.monthlyPosters
    .flat()
    .map(activityPosterSrc)
    .filter((p): p is string => Boolean(p));
  if (fromMonths.length) return fromMonths.slice(0, 6);
  return (stats.heroPosters || []).slice(0, 6);
}

function YearlyActivityBlock({
  kind,
  onSelectYear,
}: {
  kind: CatalogKind;
  onSelectYear: (y: string) => void;
}) {
  const { t } = useLocale();
  const { wrapped } = useData();
  const years = useMemo(() => {
    const listed = [...wrapped.years].sort((a, b) => a - b);
    if (!listed.length) return listed;
    const start = listed[0];
    const end = listed[listed.length - 1];
    return Array.from({ length: end - start + 1 }, (_, i) => start + i);
  }, [wrapped.years]);
  const rows = years.map((y) => {
    const stats = wrapped.byYear[String(y)]?.[kind] ?? wrapped.byYear[String(y)]?.all;
    return { year: y, count: stats?.count ?? 0, posters: yearPosters(stats) };
  });
  if (!rows.length) return null;
  const max = Math.max(1, ...rows.map((r) => r.count));

  return (
    <section className="block activity">
      <div className="activity-toolbar">
        <h2>{t.ratedByYear}</h2>
      </div>
      <div className="activity-head">
        <span>{rows[0].year}</span>
        <span>{rows[rows.length - 1].year}</span>
      </div>
      <div
        className="activity-chart is-yearly"
        style={{ ["--cols" as string]: rows.length }}
        key={`years-${kind}-${rows.map((r) => r.count).join(",")}`}
      >
        {rows.map((r, i) => (
          <button
            key={r.year}
            type="button"
            className="activity-col"
            title={`${r.year}: ${r.count}`}
            onClick={() => onSelectYear(String(r.year))}
          >
            <div className="activity-stack">
              {r.posters.map((p, k) => (
                <span key={p + k} className="activity-poster is-static">
                  <img src={p} alt="" loading="lazy" />
                </span>
              ))}
              <div
                className="activity-bar"
                style={
                  {
                    height: `${Math.max(r.count > 0 ? 22 : 6, (r.count / max) * 160)}px`,
                    ["--i" as string]: i,
                  } as React.CSSProperties
                }
              >
                {r.count > 0 ? (
                  <span className="activity-n">
                    <CountUp value={r.count} duration={700} />
                  </span>
                ) : null}
              </div>
            </div>
            <em>{r.year}</em>
          </button>
        ))}
      </div>
    </section>
  );
}

function YearSelect({
  value,
  years,
  onChange,
}: {
  value: string;
  years: number[];
  onChange: (y: string) => void;
}) {
  const { t, lang } = useLocale();
  const { wrapped, watchlist } = useData();
  const currentYear = new Date().getFullYear();
  const asOf = formatUpdatedAt(latestUpdatedAt(wrapped.generatedAt, watchlist.updatedAt), lang);
  const label = value === "all" ? t.allTime : value;
  return (
    <label className={`year-select${value === "all" ? " is-all" : ""}`}>
      <span className="year-btn-label">{label}</span>
      <span className="year-caret" aria-hidden="true">
        <svg width="18" height="18" viewBox="0 0 20 20">
          <path d="M5 8l5 5 5-5" fill="none" stroke="currentColor" strokeWidth="2" />
        </svg>
      </span>
      <select
        className="year-native"
        value={value}
        aria-label={label}
        onChange={(e) => onChange(e.target.value)}
      >
        {years.map((y) => (
          <option key={y} value={String(y)}>
            {y === currentYear ? `${y} ${t.toDate(asOf)}` : String(y)}
          </option>
        ))}
        <option value="all">{t.allTime}</option>
      </select>
    </label>
  );
}

function ShareButton({ year }: { year: string }) {
  const { t, lang } = useLocale();
  const [copied, setCopied] = useState(false);

  async function onShare() {
    const url = new URL(window.location.href);
    url.searchParams.set("lang", lang);
    const href = url.toString();
    const payload = { title: document.title, text: t.shareText(t.displayName, year), url: href };
    if (typeof navigator.share === "function") {
      try {
        await navigator.share(payload);
        return;
      } catch (err) {
        if ((err as DOMException).name === "AbortError") return;
      }
    }
    try {
      await navigator.clipboard.writeText(href);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2200);
    } catch {
      window.prompt(t.share, href);
    }
  }

  return (
    <button
      type="button"
      className={`share-btn${copied ? " copied" : ""}`}
      onClick={onShare}
    >
      <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true">
        <path
          d="M12 3v11M7.5 7.5 12 3l4.5 4.5M5 14.5v4A1.5 1.5 0 0 0 6.5 20h11A1.5 1.5 0 0 0 19 18.5v-4"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      {copied ? t.shareCopied : t.share}
    </button>
  );
}

function KindSwitch({
  value,
  onChange,
}: {
  value: CatalogKind;
  onChange: (kind: CatalogKind) => void;
}) {
  const { t } = useLocale();
  const labels: Record<CatalogKind, string> = {
    movies: t.kindMovies,
    series: t.kindSeries,
    all: t.kindAll,
  };
  return (
    <nav className="kind-bar">
      <div className="kind-switch" role="radiogroup" aria-label={t.kindLabel}>
        {KINDS.map((kind) => (
          <button
            key={kind}
            type="button"
            role="radio"
            aria-checked={value === kind}
            className={value === kind ? "on" : ""}
            onClick={() => onChange(kind)}
          >
            {labels[kind]}
          </button>
        ))}
      </div>
    </nav>
  );
}

function PersonPlaceholder() {
  return (
    <svg className="person-placeholder" viewBox="0 0 48 48" aria-hidden="true">
      <circle cx="24" cy="18" r="8.5" fill="#6d6d6d" />
      <ellipse cx="24" cy="46" rx="16" ry="13" fill="#6d6d6d" />
    </svg>
  );
}

function PeopleRow({
  heading,
  people,
  showCount = true,
  nested,
}: {
  heading: string;
  people: { id?: string | null; name: string; count?: number; poster?: string | null }[];
  showCount?: boolean;
  nested?: boolean;
}) {
  const { t } = useLocale();
  if (!people.length) return null;
  const Tag = nested ? "div" : "section";
  const Heading = nested ? "h3" : "h2";
  return (
    <Tag className={nested ? undefined : "block"}>
      <Heading>{heading}</Heading>
      <div className="people-row">
        {people.map((p) => {
          const href = p.id ? `https://www.imdb.com/name/${p.id}/` : null;
          const body = (
            <>
              <div className="person-poster">
                {p.poster ? <img src={p.poster} alt="" /> : <PersonPlaceholder />}
              </div>
              <div>
                <strong>{p.name}</strong>
                {showCount && p.count != null ? <span>{t.peopleTitles(p.count)}</span> : null}
              </div>
            </>
          );
          return href ? (
            <a key={p.id || p.name} className="person" href={href} target="_blank" rel="noreferrer">
              {body}
            </a>
          ) : (
            <article key={p.name} className="person">
              {body}
            </article>
          );
        })}
      </div>
    </Tag>
  );
}

function WatchlistBlock({
  data,
  year,
  kind,
  onSelectYear,
}: {
  data: WatchlistData;
  year: string;
  kind: CatalogKind;
  onSelectYear: (y: string) => void;
}) {
  const { lang, t } = useLocale();
  const items = data.items.filter((item) => matchesKind(item.type, kind));
  if (!items.length) return null;

  const added =
    year === "all" ? [] : items.filter((tItem) => tItem.addedOn?.startsWith(year));
  const byYear = new Map<string, number>();
  for (const tItem of items) {
    const y = tItem.addedOn?.slice(0, 4);
    if (!y) continue;
    byYear.set(y, (byYear.get(y) || 0) + 1);
  }
  const yearRows = [...byYear.entries()].sort((a, b) => b[0].localeCompare(a[0]));

  if (year === "all") {
    return (
      <section className="block watchlist" id="watchlist">
        <h2>{t.watchlist}</h2>
        <p className="lede">
          {t.watchlistAll(fmt(items.length, lang), items.length)}
          <a href={data.url} target="_blank" rel="noreferrer">
            IMDb
          </a>
          .
        </p>
        <ul className="watch-years">
          {yearRows.map(([y, n]) => (
            <li key={y}>
              <button type="button" onClick={() => onSelectYear(y)}>
                <b>{y}</b>
                <span>{fmt(n, lang)} {t.added}</span>
              </button>
            </li>
          ))}
        </ul>
      </section>
    );
  }

  if (!added.length) {
    return (
      <section className="block watchlist" id="watchlist">
        <h2>{t.watchlist}</h2>
        <p className="lede">
          {t.watchlistEmpty(year)}
          <a href={data.url} target="_blank" rel="noreferrer">
            IMDb
          </a>
          .
        </p>
      </section>
    );
  }

  return (
    <section className="block watchlist" id="watchlist">
      <h2>{t.watchlist}</h2>
      <p className="lede">
        {t.watchlistYear(year)}{" "}
        <a href={data.url} target="_blank" rel="noreferrer">
          {t.watchlistFull}
        </a>
        .
      </p>
      <div className="watch-stats">
        <article>
          <strong>
            <CountUp value={added.length} />
          </strong>
          <span>{t.addedIn(year)}</span>
        </article>
      </div>
      <div className="poster-row">
        {added.map((item) => (
          <Poster
            key={item.id}
            src={mediaPoster(item, lang)}
            title={mediaTitle(item, lang)}
            year={item.year}
            href={item.url}
            watchlisted
          />
        ))}
      </div>
    </section>
  );
}

function isIndianTitle(item: WatchlistItem) {
  const primary = item.countries?.[0];
  return primary?.id === "IN" || primary?.name === "India";
}

function YetToSee({ items, kind }: { items: WatchlistItem[]; kind: CatalogKind }) {
  const { t, lang } = useLocale();
  const pool = useMemo(() => {
    const eligible = items.filter(
      (item) =>
        matchesKind(item.type, kind) &&
        item.poster &&
        item.imdbRating != null &&
        item.imdbRating >= 7.5 &&
        !isIndianTitle(item),
    );
    eligible.sort(
      (a, b) => (b.imdbRating || 0) - (a.imdbRating || 0) || (b.votes || 0) - (a.votes || 0),
    );
    const preferred = eligible.filter((item) => (item.votes || 0) >= 25_000);
    const rest = eligible.filter((item) => (item.votes || 0) < 25_000);
    return [...preferred, ...rest].slice(0, 8);
  }, [items, kind]);
  if (pool.length < 4) return null;
  return (
    <section className="block yet-to-see">
      <h2>{t.yetToSee(t.displayName, kind)}</h2>
      <div className="poster-row yet-row">
        {pool.map((item) => (
          <Poster
            key={item.id}
            src={mediaPoster(item, lang)}
            title={mediaTitle(item, lang)}
            year={item.year}
            rating={item.imdbRating}
            href={item.url}
          />
        ))}
      </div>
    </section>
  );
}

function InterestsBlock({
  items,
}: {
  items?: WrappedData["profile"]["interests"];
}) {
  const { t, lang } = useLocale();
  const { wrapped } = useData();
  if (!items?.length) return null;
  return (
    <section className="block interests">
      <h2>
        <a href={`${wrapped.profile.url}/interests`} target="_blank" rel="noreferrer">
          {t.interests}
        </a>
      </h2>
      <div className="interest-grid">
        {items.map((item) => (
          <a key={item.id} className="interest-card" href={item.url} target="_blank" rel="noreferrer">
            {item.image ? <img src={item.image} alt="" /> : <span className="interest-fallback" />}
            <span className="interest-copy">
              <span className="interest-name">{tagName(item.name, lang)}</span>
              <span className="interest-meta">
                {t.titlesByKind(fmt(item.count, lang), item.count, "all")}
                {item.avgRating != null ? ` · ${item.avgRating.toFixed(1)}` : ""}
              </span>
            </span>
          </a>
        ))}
      </div>
    </section>
  );
}

export default function App() {
  const { lang, setLang, t } = useLocale();
  const { wrapped, watchlist } = useData();
  const [year, setYear] = useState(() => readYearParam(FALLBACK_STATS));
  const [kind, setKind] = useState<CatalogKind>(readKindParam);
  const bundle = (year === "all" ? wrapped.allTime : wrapped.byYear[year]) ?? wrapped.allTime;
  const stats: YearStats = bundle[kind] ?? bundle.all;
  const watchlistedIds = useMemo(
    () => new Set(watchlist.items.map((item) => item.id)),
    [watchlist],
  );

  useEffect(() => {
    if (year !== "all" && !wrapped.byYear[year]) {
      setYear(String(wrapped.defaultYear));
    }
  }, [wrapped, year]);

  useRevealOnScroll(`${year}-${kind}-${stats.count}`);

  useEffect(() => {
    setYearParam(year, wrapped);
    setKindParam(kind);
    const yearLabel = year === "all" ? t.allTime : stats.label;
    const kindLabel = kind === "all" ? "" : ` · ${kind === "movies" ? t.kindMovies : t.kindSeries}`;
    document.title = `${t.displayName} · ${yearLabel}${kindLabel} · IMDb Wrapped`;
  }, [year, kind, stats.label, t.allTime, t.displayName, t.kindMovies, t.kindSeries, wrapped]);

  const maxSpread = Math.max(1, ...Object.values(stats.ratingsSpread));
  const maxGenre = Math.max(1, ...stats.genres.map((g) => g.count));
  const maxDecade = Math.max(1, ...stats.decades.map((d) => d.count));
  const maxLanguage = Math.max(1, ...(stats.languages || []).map((l) => l.count));
  const watchAdded =
    year === "all"
      ? watchlist.items.filter((item) => matchesKind(item.type, kind)).length
      : watchlist.items.filter(
          (item) => item.addedOn?.startsWith(year) && matchesKind(item.type, kind),
        ).length;
  const typeEntries = Object.entries(stats.types).sort((a, b) => b[1] - a[1]);
  const movieN = stats.types.movie || 0;
  const epN = stats.types.tvEpisode || 0;
  const showN = (stats.types.tvSeries || 0) + (stats.types.tvMiniSeries || 0);
  const otherN = stats.count - movieN - epN - showN;
  const hoursHint1 =
    kind === "movies" ? t.hoursHint1Movies : kind === "series" ? t.hoursHint1Series : t.hoursHint1;
  const avgRuntimeMin = stats.count > 0 ? Math.round((stats.hours * 60) / stats.count) : 0;
  const avgRuntimeH = Math.floor(avgRuntimeMin / 60);
  const avgRuntimeM = avgRuntimeMin % 60;

  return (
    <div className="page">
      <section className="hero">
        <div className="hero-mosaic" aria-hidden="true">
          <div className="hero-mosaic-grid">
            {stats.heroPosters.map((src, i) => (
              <img key={src + i} src={src} alt="" />
            ))}
          </div>
        </div>
        <div className="hero-shade" />
        <KindSwitch value={kind} onChange={setKind} />
        <div className="hero-copy">
          <div className="hero-identity">
            <YearSelect value={year} years={wrapped.years} onChange={setYear} />
            <div className="hero-byline-row">
              <a className="hero-byline" href={wrapped.profile.url} target="_blank" rel="noreferrer">
                <img src={wrapped.profile.avatar} alt="" />
                <span>
                  {yearByline(
                    year,
                    stats.toDate,
                    kind,
                    t,
                    formatUpdatedAt(latestUpdatedAt(wrapped.generatedAt, watchlist.updatedAt), lang),
                  )}
                </span>
              </a>
              <ShareButton year={year} />
            </div>
          </div>
        </div>
      </section>

      <main>
        {year === "all" ? (
          <YearlyActivityBlock kind={kind} onSelectYear={setYear} />
        ) : (
          <ActivityBlock stats={stats} year={year} />
        )}

        <section className="big-stats">
          <article>
            <strong>
              <CountUp value={stats.count} />
            </strong>
            <span>{t.titlesRated(stats.count)}</span>
            <small>
              {t.avgPerMonth(fmt(stats.avgPerMonth, lang))}
              <br />
              {t.avgPerWeek(fmt(stats.avgPerWeek, lang))}
            </small>
          </article>
          <article>
            <strong>
              <CountUp
                value={stats.hours >= 100 ? Math.round(stats.hours) : stats.hours}
                digits={stats.hours >= 100 || Number.isInteger(stats.hours) ? 0 : 1}
              />
            </strong>
            <span>{t.hours(stats.hours >= 100 ? Math.round(stats.hours) : stats.hours)}</span>
            <small>
              {avgRuntimeMin > 0 ? (
                <>
                  {t.avgRuntime(avgRuntimeH, avgRuntimeM)}
                  <br />
                </>
              ) : null}
              {hoursHint1}
            </small>
          </article>
          <article>
            <strong>
              {stats.avgRating != null ? <CountUp value={stats.avgRating} digits={1} /> : "—"}
            </strong>
            <span>{t.averageRating}</span>
            <small>
              {t.avgHint1}
              <br />
              {t.avgHint2(
                fmt(stats.count, lang),
                stats.count,
                year === "all" ? undefined : year,
              )}
            </small>
          </article>
          <WeekdayChart daily={stats.daily || {}} kind={kind} />
        </section>

        <section className="block donuts">
          <Donut
            center={
              <CountUp
                value={Math.round((stats.premieres / Math.max(1, stats.count)) * 100)}
                suffix="%"
              />
            }
            sub={t.newThisYear}
            slices={[
              { label: t.premieres(stats.premieres, stats.year), value: stats.premieres, color: "#F5C518" },
              { label: t.olderTitles(stats.older), value: stats.older, color: "#3a3a3a" },
            ]}
          />
          <Donut
            center={
              <CountUp
                value={kind === "all" ? stats.count : kind === "series" ? showN : movieN}
              />
            }
            sub={
              kind === "all"
                ? t.pictures(stats.count)
                : kind === "series"
                  ? t.series(showN)
                  : t.movies(movieN)
            }
            slices={[
              { label: t.moviesSlice(movieN), value: movieN, color: "#F5C518" },
              { label: t.tvEpisodes(epN), value: epN, color: "#7a6a2a" },
              { label: t.series(showN), value: showN, color: "#c4a227" },
              { label: t.other(Math.max(0, otherN)), value: Math.max(0, otherN), color: "#3a3a3a" },
            ].filter((s) => s.value > 0)}
          />
          <Donut
            center={
              <CountUp
                value={stats.vsImdb.delta}
                digits={1}
                prefix={stats.vsImdb.delta > 0 ? "+" : ""}
              />
            }
            sub={t.vsImdb}
            slices={[
              { label: t.kinder, value: stats.vsImdb.kinder, color: "#F5C518" },
              { label: t.harsher, value: stats.vsImdb.harsher, color: "#6b5a16" },
              { label: t.same, value: stats.vsImdb.same, color: "#3a3a3a" },
            ].filter((s) => s.value > 0)}
          />
        </section>

        {year !== "all" && !stats.toDate && (
          <BestOfYear
            key={`${year}-${kind}-bestof`}
            year={year}
            best={stats.highest}
            worst={stats.lowest}
            watchlistedIds={watchlistedIds}
            kind={kind}
          />
        )}
        {!(year !== "all" && !stats.toDate) && (
          <ToggledPosterRow
            key={`${year}-${kind}-highlow`}
            a={{ heading: t.highest, items: stats.highest }}
            b={{ heading: t.lowest, items: stats.lowest }}
            watchlistedIds={watchlistedIds}
          />
        )}

        <MilestonesBlock stats={stats} year={year} kind={kind} />

        <section className="block">
          <h2>{t.ratingsSpread}</h2>
          <div className="spread" key={`${year}-${kind}`}>
            {Array.from({ length: 10 }, (_, i) => {
              const score = String(i + 1);
              const n = stats.ratingsSpread[score] || 0;
              const h = chartBarHeight(n, maxSpread);
              const inside = n > 0 && h >= 22;
              return (
                <div key={score} className="spread-col">
                  {!inside && n > 0 ? (
                    <span className="activity-n is-over">
                      <CountUp value={n} duration={700} />
                    </span>
                  ) : null}
                  <div
                    className="activity-bar"
                    style={
                      {
                        height: `${h}px`,
                        ["--i" as string]: i,
                      } as React.CSSProperties
                    }
                  >
                    {inside ? (
                      <span className="activity-n">
                        <CountUp value={n} duration={700} />
                      </span>
                    ) : null}
                  </div>
                  <b>{score}</b>
                </div>
              );
            })}
          </div>
        </section>

        {kind !== "movies" && stats.series.length > 0 && (
          <section className="block">
            <h2>{t.mostRatedSeries}</h2>
            <div className="poster-row">
              {stats.series.map((s) => (
                <Poster
                  key={s.id || s.name}
                  src={mediaPoster(s, lang)}
                  title={mediaTitle(s, lang)}
                  year={s.year}
                  href={s.id ? `https://www.imdb.com/title/${s.id}/` : undefined}
                  caption={t.episodesRated(s.count)}
                  watchlisted={s.id ? watchlistedIds.has(s.id) : false}
                />
              ))}
            </div>
          </section>
        )}

        <HighsAndLowsBlock data={stats.highsAndLows} watchlistedIds={watchlistedIds} />
        <ToggledPosterRow
          key={`${year}-${kind}-vsavg`}
          className="vs-avg"
          a={{ heading: t.ratedHigher, items: stats.kinderThanAvg, caption: vsAvgCaption }}
          b={{ heading: t.ratedLower, items: stats.harsherThanAvg, caption: vsAvgCaption }}
          watchlistedIds={watchlistedIds}
        />
        <ToggledPosterRow
          key={`${year}-${kind}-popular`}
          a={{ heading: t.mostPopular, items: stats.popular }}
          b={{ heading: t.mostObscure, items: stats.obscure }}
          watchlistedIds={watchlistedIds}
        />
        <ToggledPosterRow
          key={`${year}-${kind}-age`}
          a={{ heading: t.newest, items: stats.newest }}
          b={{ heading: t.oldest, items: stats.oldest }}
          watchlistedIds={watchlistedIds}
        />
        <ToggledPosterRow
          key={`${year}-${kind}-runtime`}
          a={{ heading: t.longest, items: stats.longest, caption: (card) => t.minutes(card.runtimeMin || 0) }}
          b={{ heading: t.shortest, items: stats.shortest, caption: (card) => t.minutes(card.runtimeMin || 0) }}
          watchlistedIds={watchlistedIds}
        />

        {stats.decades.length > 0 && (
          <section className="block">
            <h2>{t.decades}</h2>
            <div className="decades" key={`${year}-${kind}`}>
              {stats.decades.map((d, i) => {
                const h = chartBarHeight(d.count, maxDecade);
                const inside = d.count > 0 && h >= 22;
                return (
                  <div key={d.name} className="decade">
                    {!inside && d.count > 0 ? (
                      <span className="activity-n is-over">
                        <CountUp value={d.count} duration={700} />
                      </span>
                    ) : null}
                    <div
                      className="activity-bar"
                      style={
                        {
                          height: `${h}px`,
                          ["--i" as string]: i,
                        } as React.CSSProperties
                      }
                    >
                      {inside ? (
                        <span className="activity-n">
                          <CountUp value={d.count} duration={700} />
                        </span>
                      ) : null}
                    </div>
                    <span className="decade-label">{decadeName(d.name, lang)}</span>
                  </div>
                );
              })}
            </div>
          </section>
        )}

        {stats.genres.length > 0 && (
          <section className="block">
            <h2>{t.genres}</h2>
            <ul className="bars">
              {stats.genres.map((g, i) => (
                <li key={g.name} style={{ ["--i" as string]: i } as React.CSSProperties}>
                  <span>{genreName(g.name, lang)}</span>
                  <div className="bar-track">
                    <i style={{ width: `${(g.count / maxGenre) * 100}%` }} />
                  </div>
                  <b>
                    <CountUp value={g.count} duration={700} />
                  </b>
                </li>
              ))}
            </ul>
          </section>
        )}

        <ThemesKeywords
          kind={kind}
          themes={stats.themes}
          themesRated={stats.themesRated}
          keywords={stats.keywords}
          keywordsRated={stats.keywordsRated}
        />

        {stats.countries.length > 0 && (
          <WorldMapBlock countries={stats.countries} />
        )}

        {(stats.languages || []).length > 0 && (
          <section className="block">
            <h2>{t.languages}</h2>
            <ul className="bars">
              {stats.languages.map((l, i) => (
                <li key={l.name} style={{ ["--i" as string]: i } as React.CSSProperties}>
                  <span>{languageName(l.name, lang)}</span>
                  <div className="bar-track">
                    <i style={{ width: `${(l.count / maxLanguage) * 100}%` }} />
                  </div>
                  <b>
                    <CountUp value={l.count} duration={700} />
                  </b>
                </li>
              ))}
            </ul>
          </section>
        )}

        {typeEntries.length > 0 && (
          <section className="block">
            <h2>{t.titleTypes}</h2>
            <ul className="type-pills">
              {typeEntries.map(([k, v]) => (
                <li key={k}>
                  <b>{fmt(v, lang)}</b> {typeLabel(k, lang, v)}
                </li>
              ))}
            </ul>
          </section>
        )}

        <PeopleRow heading={t.directors} people={stats.directors} />
        <PeopleRow heading={t.stars} people={stats.stars} />

        <WatchlistBlock data={watchlist} year={year} kind={kind} onSelectYear={setYear} />

        <section className="block extras">
          <h2>{t.onProfile}</h2>
          <div className="extra-grid">
            <a href={`${wrapped.profile.url}/ratings`} target="_blank" rel="noreferrer">
              <strong>
                <CountUp value={stats.count} />
              </strong>
              <span>{t.allTimeRatings(kind)}</span>
            </a>
            <a href="#watchlist">
              <strong>
                <CountUp value={watchAdded} />
              </strong>
              <span>{t.stillToWatch}</span>
            </a>
            <a href={`${wrapped.profile.url}/badges/`} target="_blank" rel="noreferrer">
              <strong>
                <CountUp value={wrapped.profile.badges} />
              </strong>
              <span>{t.badges(wrapped.profile.badges)}</span>
            </a>
            <a href={`${wrapped.profile.url}/lists/`} target="_blank" rel="noreferrer">
              <strong>
                <CountUp value={wrapped.profile.lists.length} />
              </strong>
              <span>{t.collections(wrapped.profile.lists.length)}</span>
            </a>
          </div>
          {year === "all" && wrapped.profile.favorites.length > 0 && (
            <>
              <h3>{t.favoriteTitles}</h3>
              <div className="poster-row">
                {wrapped.profile.favorites.map((card) => (
                  <Poster
                    key={card.id}
                    src={mediaPoster(card, lang)}
                    title={mediaTitle(card, lang)}
                    year={card.year}
                    rating={card.userRating}
                    href={titleHref(card)}
                    watchlisted={watchlistedIds.has(card.id)}
                  />
                ))}
              </div>
            </>
          )}
          {year === "all" && (wrapped.profile.favoritePeople || []).length > 0 && (
            <PeopleRow
              heading={t.favoritePeople}
              people={wrapped.profile.favoritePeople}
              showCount={false}
              nested
            />
          )}
        </section>

        {year === "all" && <InterestsBlock items={wrapped.profile.interests} />}
        <YetToSee items={watchlist.items} kind={kind} />
      </main>

      <footer>
        <div className="footer-row">
          <a
            className="footer-brand"
            href={REPO_URL}
            target="_blank"
            rel="noreferrer"
            title="GitHub"
          >
            <span className="imdb-mark">IMDb</span>
            <span className="brand-rest">{t.wrapped}</span>
          </a>
          <div className="lang-switch" role="group" aria-label={t.language}>
            <button
              type="button"
              className={lang === "en" ? "on" : ""}
              aria-pressed={lang === "en"}
              onClick={() => setLang("en")}
            >
              EN
            </button>
            <button
              type="button"
              className={lang === "ru" ? "on" : ""}
              aria-pressed={lang === "ru"}
              onClick={() => setLang("ru")}
            >
              RU
            </button>
          </div>
        </div>
        <p className="footer-copy">
          <span>© 2005–2026</span>
          <span>
            {t.footerCredit}
            <a href={wrapped.profile.url} target="_blank" rel="noreferrer">
              {wrapped.profile.username || t.displayName}
            </a>
            .
          </span>
          <span>
            {t.footerOpenBefore}
            <a href={REPO_URL} target="_blank" rel="noreferrer">
              {t.footerOpenLink}
            </a>
            {t.footerOpenAfter}.
          </span>
          {wrapped.profile.telegram ? (
            <span>
              {t.footerContact} {telegramLink(wrapped.profile.telegram)}
            </span>
          ) : null}
        </p>
      </footer>
    </div>
  );
}
