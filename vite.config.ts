import { execFile } from "node:child_process";
import { readFile, stat } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import type { Plugin, PreviewServer, ViteDevServer } from "vite";
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

export default defineConfig({
  plugins: [react(), watchlistPlugin()],
});
