/**
 * Thin fetch helpers that target /api/ paths.
 *
 * Two runtime modes:
 *
 *   - Dev (`npm run dev`): the vite.config.ts middleware synthesises
 *     directory listings on demand and reads files from the repo root.
 *   - Production / GitHub Pages: artefacts are pre-staged into
 *     validator/public/api/ by webui/scripts/stage-data.mjs, and every
 *     directory the SPA tries to list has a sibling `_index.json` written
 *     at staging time.
 *
 * The helpers below normalise both paths:
 *
 *   1. Every `/api/...` URL is rewritten to include Vite's `BASE_URL`
 *      (so GitHub Pages deploys at /pdf2md/api/... work).
 *   2. `listDir()` requests the directory in dev (where the middleware
 *      returns JSON for it) and falls back to fetching
 *      `<path>/_index.json` in prod where the static host cannot list.
 */

const BASE = (import.meta.env.BASE_URL ?? "/").replace(/\/+$/, "");
// True when Vite ran us via `vite build` (not `vite` dev).
const IS_PROD = import.meta.env.PROD;

/** Rewrite a `/api/...` URL to include the deploy's base path. */
export function apiUrl(p: string): string {
  // Tolerate callers that already pass an absolute https:// URL.
  if (p.startsWith("http://") || p.startsWith("https://")) return p;
  const rel = p.startsWith("/") ? p : `/${p}`;
  return `${BASE}${rel}`;
}

export async function fetchJson<T>(url: string): Promise<T> {
  const target = apiUrl(url);
  const res = await fetch(target);
  if (!res.ok) {
    throw new Error(`GET ${target} -> ${res.status} ${res.statusText}`);
  }
  return (await res.json()) as T;
}

export async function tryFetchJson<T>(url: string): Promise<T | null> {
  try {
    return await fetchJson<T>(url);
  } catch {
    return null;
  }
}

export async function fetchText(url: string): Promise<string> {
  const res = await fetch(apiUrl(url));
  if (!res.ok) {
    throw new Error(`GET ${url} -> ${res.status} ${res.statusText}`);
  }
  return await res.text();
}

/** Asset URL for non-JSON resources (PDFs, etc.) routed through /api/. */
export function assetUrl(p: string): string {
  return apiUrl(p);
}

/**
 * List a directory under /api/.
 *
 * Returns `null` when the directory does not exist or cannot be listed.
 * In dev, hits the middleware (which returns JSON for any directory).
 * In prod, fetches `<dir>/_index.json` written at staging time.
 */
export async function listDir(
  dirUrl: string,
): Promise<{ name: string; is_dir: boolean }[] | null> {
  const normalised = dirUrl.replace(/\/+$/, "");
  if (IS_PROD) {
    return await tryFetchJson<{ name: string; is_dir: boolean }[]>(
      `${normalised}/_index.json`,
    );
  }
  return await tryFetchJson<{ name: string; is_dir: boolean }[]>(normalised);
}
