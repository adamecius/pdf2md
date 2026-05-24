import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";
import fs from "node:fs";

// The repo root sits two directories up from webui/validator/.
const REPO_ROOT = path.resolve(__dirname, "..", "..");

/**
 * Tiny dev-time middleware that serves files from the repo root under
 * the /api/ prefix. Lets the SPA `fetch("/api/groundtruth/...json")`
 * without a separate backend process.
 *
 * Only allow-listed prefixes are served so the SPA cannot reach into
 * arbitrary parts of the host filesystem.
 */
const ALLOWED_PREFIXES = [
  "groundtruth/",
  ".tmp/",
  "src/pdf2md/data/factory_priors/",
  "examples/",
];

const repoDataServer: Plugin = {
  name: "pdf2md-repo-data-server",
  configureServer(server) {
    server.middlewares.use("/api", (req, res, next) => {
      try {
        const url = req.url ?? "/";
        if (url === "/" || url === "") {
          res.statusCode = 404;
          res.end("api path required");
          return;
        }
        const rel = url.replace(/^\/+/, "").split("?")[0];
        if (!ALLOWED_PREFIXES.some((p) => rel.startsWith(p))) {
          res.statusCode = 403;
          res.end(`forbidden prefix: ${rel}`);
          return;
        }
        const filePath = path.join(REPO_ROOT, rel);
        // Guard against ".." escaping the allow-listed root.
        if (!filePath.startsWith(REPO_ROOT + path.sep)) {
          res.statusCode = 403;
          res.end("forbidden");
          return;
        }
        if (!fs.existsSync(filePath)) {
          res.statusCode = 404;
          res.end(`not found: ${rel}`);
          return;
        }
        const stat = fs.statSync(filePath);
        if (stat.isDirectory()) {
          // Cheap directory listing — used by /api/groundtruth/corpus/latex/
          res.setHeader("Content-Type", "application/json");
          const entries = fs.readdirSync(filePath).map((name) => ({
            name,
            is_dir: fs.statSync(path.join(filePath, name)).isDirectory(),
          }));
          res.end(JSON.stringify(entries));
          return;
        }
        if (filePath.endsWith(".pdf")) {
          res.setHeader("Content-Type", "application/pdf");
          res.end(fs.readFileSync(filePath));
          return;
        }
        if (filePath.endsWith(".json")) {
          res.setHeader("Content-Type", "application/json");
          res.end(fs.readFileSync(filePath, "utf-8"));
          return;
        }
        if (filePath.endsWith(".md")) {
          res.setHeader("Content-Type", "text/markdown");
          res.end(fs.readFileSync(filePath, "utf-8"));
          return;
        }
        res.end(fs.readFileSync(filePath));
      } catch (e) {
        res.statusCode = 500;
        res.end(String(e));
      }
      void next; // typeguard
    });
  },
};

// Production base path. Set via `VITE_BASE=/pdf2md/ npm run build:pages`
// for GitHub Pages deploys (where the SPA is served from
// https://<owner>.github.io/<repo>/). Defaults to "/" so local builds and
// previews work without configuration.
const PROD_BASE = process.env.VITE_BASE ?? "/";

export default defineConfig({
  base: PROD_BASE,
  plugins: [react(), repoDataServer],
  resolve: {
    alias: {
      "@pdf2md/shared": path.resolve(__dirname, "..", "shared", "src", "index.ts"),
    },
  },
  server: {
    port: 5173,
    fs: {
      // Allow Vite to read files from the parent dirs (the shared package
      // sits a level up, and we explicitly let the dev middleware reach
      // the repo root for the /api/ endpoint above).
      allow: [".", "..", "../.."],
    },
  },
});
