import { readdir, readFile } from "node:fs/promises";
import { join } from "node:path";
import process from "node:process";
import { fileURLToPath, URL } from "node:url";

const root = new URL("../", import.meta.url);
const wrangler = JSON.parse(await readFile(new URL("wrangler.jsonc", root), "utf8"));
const vite = await readFile(new URL("vite.config.ts", root), "utf8");

if (wrangler.upload_source_maps !== false) {
  throw new Error("wrangler.jsonc must set upload_source_maps to false explicitly.");
}

if (wrangler.observability?.enabled !== false) {
  throw new Error("wrangler.jsonc must disable Workers Logs observability explicitly.");
}

if (!/sourcemap:\s*false/.test(vite)) {
  throw new Error("vite.config.ts must keep build.sourcemap disabled.");
}

async function listFiles(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) {
      files.push(...(await listFiles(path)));
    } else {
      files.push(path);
    }
  }
  return files;
}

const dist = fileURLToPath(new URL("dist/", root));
const distFiles = await listFiles(dist);
const sourceMaps = distFiles.filter((path) => path.endsWith(".map"));

if (sourceMaps.length > 0) {
  throw new Error(`Client build contains source maps: ${sourceMaps.join(", ")}`);
}

for (const path of distFiles.filter((entry) => entry.endsWith(".js") || entry.endsWith(".css"))) {
  const source = await readFile(path, "utf8");
  if (source.includes("sourceMappingURL=")) {
    throw new Error(`Client build references a source map: ${path}`);
  }
}

process.stdout.write(
  `source-map-policy: PASS client_maps=${sourceMaps.length} upload_source_maps=${wrangler.upload_source_maps} observability_enabled=${wrangler.observability.enabled}\n`,
);
