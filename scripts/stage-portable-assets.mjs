import { createHash } from "node:crypto";
import { copyFile, lstat, mkdir, readdir, readFile, rm, writeFile } from "node:fs/promises";
import { dirname, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const appRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const sourceRoot = resolve(appRoot, "dist");
const targetRoot = resolve(appRoot, "portable", "generated-ui");

function portablePath(path) {
  return path.split(sep).join("/");
}

function assertSafeRelativePath(path) {
  if (
    !path ||
    path.startsWith("/") ||
    path.includes("\\") ||
    path.split("/").some((segment) => !segment || segment === "." || segment === ".." || segment.startsWith("."))
  ) {
    throw new Error(`refusing unsafe or hidden asset path: ${path}`);
  }
  if (path.endsWith(".map")) {
    throw new Error(`source maps are forbidden in the portable asset stage: ${path}`);
  }
}

async function collectFiles(root, current = root) {
  const entries = await readdir(current, { withFileTypes: true });
  const files = [];

  for (const entry of entries.sort((left, right) => left.name.localeCompare(right.name, "en"))) {
    const absolute = resolve(current, entry.name);
    const path = portablePath(relative(root, absolute));
    assertSafeRelativePath(path);

    const metadata = await lstat(absolute);
    if (metadata.isSymbolicLink()) {
      throw new Error(`symbolic links are forbidden in the portable asset stage: ${path}`);
    }
    if (metadata.isDirectory()) {
      files.push(...(await collectFiles(root, absolute)));
      continue;
    }
    if (!metadata.isFile()) {
      throw new Error(`unsupported portable asset type: ${path}`);
    }
    files.push({ absolute, path });
  }

  return files;
}

const indexMetadata = await lstat(resolve(sourceRoot, "index.html")).catch(() => null);
if (!indexMetadata?.isFile()) {
  throw new Error("dist/index.html is missing; run `npm run build` before staging portable assets");
}

const files = await collectFiles(sourceRoot);
if (files.length === 0) {
  throw new Error("the Vite dist tree is empty");
}

await rm(targetRoot, { force: true, recursive: true });
await mkdir(targetRoot, { recursive: true, mode: 0o755 });

const manifestLines = [];
for (const file of files.sort((left, right) => left.path.localeCompare(right.path, "en"))) {
  const bytes = await readFile(file.absolute);
  const digest = createHash("sha256").update(bytes).digest("hex");
  const destination = resolve(targetRoot, file.path);
  await mkdir(dirname(destination), { recursive: true, mode: 0o755 });
  await copyFile(file.absolute, destination);
  manifestLines.push(`${digest}  ${file.path}`);
}

await writeFile(resolve(targetRoot, "asset-manifest.sha256"), `${manifestLines.join("\n")}\n`, {
  encoding: "utf8",
  mode: 0o644,
});

const manifestDigest = createHash("sha256")
  .update(`${manifestLines.join("\n")}\n`)
  .digest("hex");
process.stdout.write(`staged ${files.length} portable UI assets; manifest sha256=${manifestDigest}\n`);
