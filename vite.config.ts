import { execFile } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { readFile, stat } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import type { IndexHtmlTransformContext, Plugin, PreviewServer, ViteDevServer } from "vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const root = path.dirname(fileURLToPath(import.meta.url));
const jsonPath = path.join(root, "src/data/watchlist.json");
const TTL_MS = 2 * 60 * 1000;
let refresh: Promise<void> | null = null;

function runFetch(live: boolean) {
  const args = ["scripts/fetch_watchlist.py"];
  if (live) args.push("--live");
  return new Promise<void>((resolve, reject) => {
    execFile("python3", args, { cwd: root }, (err, stdout, stderr) => {
      if (stdout) process.stdout.write(stdout);
      if (stderr) process.stderr.write(stderr);
      if (err) reject(err);
      else resolve();
    });
  });
}

async function ageMs() {
  try {
    const s = await stat(jsonPath);
    return Date.now() - s.mtimeMs;
  } catch {
    return Number.POSITIVE_INFINITY;
  }
}

async function ensureWatchlist(live: boolean) {
  const age = await ageMs();
  if (age < TTL_MS) return;
  if (!refresh) {
    refresh = runFetch(live).finally(() => {
      refresh = null;
    });
  }
  if (!Number.isFinite(age)) {
    try {
      await refresh;
    } catch (err) {
      console.warn("[watchlist] refresh failed", err);
    }
    return;
  }
  refresh.catch((err) => console.warn("[watchlist] background refresh failed", err));
}

function attachWatchlistApi(server: ViteDevServer | PreviewServer) {
  server.middlewares.use("/api/watchlist", async (req, res, next) => {
    if (req.method !== "GET") return next();
    await ensureWatchlist(true);
    try {
      const body = await readFile(jsonPath, "utf8");
      res.setHeader("Content-Type", "application/json; charset=utf-8");
      res.setHeader("Cache-Control", "no-store");
      res.end(body);
    } catch {
      res.statusCode = 503;
      res.setHeader("Content-Type", "application/json");
      res.end(JSON.stringify({ count: 0, items: [], source: "missing" }));
    }
  });
}

function watchlistPlugin(): Plugin {
  return {
    name: "imdb-watchlist",
    configureServer(server) {
      attachWatchlistApi(server);
      void ensureWatchlist(true);
    },
    configurePreviewServer(server) {
      attachWatchlistApi(server);
    },
  };
}

function attr(value: string) {
  return value.replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");
}

function readJson(file: string) {
  try {
    return JSON.parse(readFileSync(file, "utf8")) as Record<string, unknown>;
  } catch {
    return null;
  }
}

type OgPage = {
  title: string;
  description: string;
  image: string;
  imageFile: string;
  imageAlt: string;
  locale: string;
  canonical: string;
  lang: string;
  year: string;
  kind: string;
};

type OgMeta = {
  siteUrl?: string;
  defaultYear?: string;
  defaultKind?: string;
  defaultLang?: string;
  width?: number;
  height?: number;
  profileUrl?: string;
  name?: string;
  nameEn?: string;
  years?: string[];
  pages?: Record<string, OgPage>;
};

const SNIPPET_START = "<!--og-snippet-->";
const SNIPPET_END = "<!--/og-snippet-->";

function loadOg(): OgMeta {
  return (readJson(path.join(root, "og-meta.json")) as OgMeta) || {};
}

function pickPage(meta: OgMeta, search: string): OgPage | null {
  const q = new URLSearchParams(search.startsWith("?") ? search.slice(1) : search);
  const years = new Set(meta.years || []);
  const lang = q.get("lang") === "en" || q.get("lang") === "ru" ? q.get("lang")! : meta.defaultLang || "ru";
  const kindRaw = q.get("kind");
  const kind = kindRaw === "movies" || kindRaw === "series" || kindRaw === "all" ? kindRaw : meta.defaultKind || "all";
  let year = q.get("year") || "";
  if (year !== "all" && !years.has(year)) year = meta.defaultYear || "";
  const key = `${lang}|${year}|${kind}`;
  return meta.pages?.[key] || meta.pages?.[`${meta.defaultLang || "ru"}|${meta.defaultYear}|${meta.defaultKind || "all"}`] || null;
}

function searchFrom(ctx: IndexHtmlTransformContext) {
  const raw = ctx.originalUrl || ctx.path || "";
  const q = raw.includes("?") ? raw.slice(raw.indexOf("?")) : "";
  return q;
}

function snippetTags(page: OgPage, extra: { telegram?: string; profileUrl?: string; name?: string; width: number; height: number; devBase?: string }) {
  const image = extra.devBase ? `${extra.devBase}${page.imageFile}`.replace(/([^:]\/)\/+/g, "$1") : page.image;
  const canonical = page.canonical;
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "ProfilePage",
    name: page.title,
    url: canonical || undefined,
    description: page.description,
    inLanguage: page.lang,
    image: { "@type": "ImageObject", url: image, width: extra.width, height: extra.height },
    mainEntity: { "@type": "Person", name: extra.name, url: extra.profileUrl || undefined },
  };
  return [
    `<title>${attr(page.title)}</title>`,
    `<meta name="description" content="${attr(page.description)}" />`,
    canonical ? `<link rel="canonical" href="${attr(canonical)}" />` : "",
    extra.telegram ? `<link rel="me" href="${attr(extra.telegram)}" />` : "",
    `<meta property="og:type" content="website" />`,
    `<meta property="og:site_name" content="IMDb Wrapped" />`,
    `<meta property="og:locale" content="${attr(page.locale)}" />`,
    `<meta property="og:locale:alternate" content="${page.lang === "ru" ? "en_US" : "ru_RU"}" />`,
    canonical ? `<meta property="og:url" content="${attr(canonical)}" />` : "",
    `<meta property="og:title" content="${attr(page.title)}" />`,
    `<meta property="og:description" content="${attr(page.description)}" />`,
    `<meta property="og:image" content="${attr(image)}" />`,
    `<meta property="og:image:secure_url" content="${attr(image)}" />`,
    `<meta property="og:image:type" content="image/jpeg" />`,
    `<meta property="og:image:width" content="${extra.width}" />`,
    `<meta property="og:image:height" content="${extra.height}" />`,
    `<meta property="og:image:alt" content="${attr(page.imageAlt)}" />`,
    `<link rel="image_src" href="${attr(image)}" />`,
    `<meta name="twitter:card" content="summary_large_image" />`,
    `<meta name="twitter:title" content="${attr(page.title)}" />`,
    `<meta name="twitter:description" content="${attr(page.description)}" />`,
    `<meta name="twitter:image" content="${attr(image)}" />`,
    `<meta name="twitter:image:alt" content="${attr(page.imageAlt)}" />`,
    `<script type="application/ld+json">${JSON.stringify(jsonLd)}</script>`,
  ]
    .filter(Boolean)
    .map((line) => `    ${line}`)
    .join("\n");
}

function wrapSnippet(tags: string) {
  return `${SNIPPET_START}\n${tags}\n    ${SNIPPET_END}`;
}

function applySnippet(html: string, tags: string, lang: string) {
  const wrapped = wrapSnippet(tags);
  const next = html.includes(SNIPPET_START)
    ? html.replace(new RegExp(`${SNIPPET_START}[\\s\\S]*?${SNIPPET_END}`), wrapped)
    : html.replace("    <title>IMDb Wrapped</title>", wrapped);
  return next.replace(/<html lang="[^"]*">/, `<html lang="${lang}">`);
}

function snippetPlugin(): Plugin {
  return {
    name: "html-snippet",
    transformIndexHtml: {
      order: "pre",
      handler(html, ctx) {
        const cfg = readJson(path.join(root, "config.json")) || {};
        const og = loadOg();
        const page = pickPage(og, searchFrom(ctx));
        if (!page) return html;
        const telegram = String(cfg.telegram || "");
        const tags = snippetTags(page, {
          telegram,
          profileUrl: String(og.profileUrl || cfg.imdbUrl || ""),
          name: page.lang === "en" ? String(og.nameEn || "") : String(og.name || ""),
          width: Number(og.width || 1200),
          height: Number(og.height || 630),
          devBase: ctx.server ? ctx.server.config.base || "/" : undefined,
        });
        return applySnippet(html, tags, page.lang);
      },
    },
    configurePreviewServer(server) {
      server.middlewares.use((req, _res, next) => {
        const raw = req.url || "/";
        const qAt = raw.indexOf("?");
        if (qAt < 0) return next();
        const pathname = raw.slice(0, qAt);
        const base = (server.config.base || "/").replace(/\/$/, "") || "";
        const rel = (base && pathname.startsWith(base) ? pathname.slice(base.length) : pathname) || "/";
        if (rel !== "/" && rel !== "/index.html" && rel !== "") return next();
        const page = pickPage(loadOg(), raw.slice(qAt));
        if (!page) return next();
        req.url = `${base}/p/${page.lang}/${page.year}/${page.kind}/index.html`;
        next();
      });
    },
    closeBundle() {
      const og = loadOg();
      const pages = og.pages || {};
      const outDir = path.join(root, "dist");
      const indexPath = path.join(outDir, "index.html");
      let index: string;
      try {
        index = readFileSync(indexPath, "utf8");
      } catch {
        return;
      }
      const cfg = readJson(path.join(root, "config.json")) || {};
      for (const page of Object.values(pages)) {
        const tags = snippetTags(page, {
          telegram: String(cfg.telegram || ""),
          profileUrl: String(og.profileUrl || ""),
          name: page.lang === "en" ? String(og.nameEn || "") : String(og.name || ""),
          width: Number(og.width || 1200),
          height: Number(og.height || 630),
        });
        const dest = path.join(outDir, "p", page.lang, page.year, page.kind, "index.html");
        mkdirSync(path.dirname(dest), { recursive: true });
        writeFileSync(dest, applySnippet(index, tags, page.lang));
      }
    },
  };
}

export default defineConfig({
  base: process.env.VITE_BASE || "/",
  plugins: [react(), watchlistPlugin(), snippetPlugin()],
});
