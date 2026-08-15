import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { WatchlistData, WrappedData } from "./types";
import fallbackStats from "./data/stats.json";
import fallbackWatchlist from "./data/watchlist.json";

type DataCtx = {
  wrapped: WrappedData;
  watchlist: WatchlistData;
  ready: boolean;
};

const Ctx = createContext<DataCtx | null>(null);

const FALLBACK_STATS = fallbackStats as WrappedData;
const FALLBACK_WATCHLIST = fallbackWatchlist as WatchlistData;

function dataUrl(name: string) {
  const base = import.meta.env.BASE_URL || "/";
  const root = base.endsWith("/") ? base : `${base}/`;
  return `${root}data/${name}?t=${Date.now()}`;
}

async function loadJson<T>(url: string): Promise<T | null> {
  try {
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

export function DataProvider({ children }: { children: ReactNode }) {
  const [wrapped, setWrapped] = useState<WrappedData>(FALLBACK_STATS);
  const [watchlist, setWatchlist] = useState<WatchlistData>(FALLBACK_WATCHLIST);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let alive = true;
    (async () => {
      const [stats, wl] = await Promise.all([
        loadJson<WrappedData>(dataUrl("stats.json")),
        loadJson<WatchlistData>(dataUrl("watchlist.json")),
      ]);
      if (!alive) return;
      if (stats?.allTime && stats?.profile) setWrapped(stats);
      if (wl?.items) setWatchlist(wl);
      setReady(true);
    })();
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    if (!import.meta.env.DEV) return;
    let alive = true;
    const pull = () => {
      fetch("/api/watchlist")
        .then((r) => (r.ok ? r.json() : null))
        .then((d: WatchlistData | null) => {
          if (alive && d?.items?.length) setWatchlist(d);
        })
        .catch(() => undefined);
    };
    pull();
    const id = window.setInterval(pull, 120_000);
    return () => {
      alive = false;
      window.clearInterval(id);
    };
  }, []);

  const value = useMemo<DataCtx>(
    () => ({ wrapped, watchlist, ready }),
    [wrapped, watchlist, ready],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useData() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useData must be used within DataProvider");
  return ctx;
}

export { FALLBACK_STATS, FALLBACK_WATCHLIST };
