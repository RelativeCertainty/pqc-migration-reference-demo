// SPDX-License-Identifier: MIT

import { createHash } from "node:crypto";
import { lstat, open, readdir, realpath } from "node:fs/promises";
import path from "node:path";

import {
  InputBoundaryError,
  type RepositoryReaderPort,
  type RepositorySnapshot,
  type ScanDiagnostic,
} from "./types.ts";

const MAX_FILE_BYTES = 1024 * 1024;
const MAX_VISITED_FILES = 10_000;
const deniedDirectories = new Set([
  ".git",
  ".hg",
  ".next",
  ".scanner-dist",
  ".svn",
  "build",
  "coverage",
  "dist",
  "node_modules",
  "output",
  "scan-output",
  "target",
  "vendor",
]);
const deniedExtensions = new Set([
  ".7z", ".a", ".avi", ".bin", ".cer", ".crt", ".der", ".dll", ".dylib", ".exe",
  ".gif", ".gz", ".ico", ".jar", ".jpeg", ".jpg", ".jks", ".key", ".mov", ".mp3",
  ".mp4", ".o", ".p12", ".pdf", ".pem", ".pfx", ".png", ".pyc", ".so", ".tar",
  ".tgz", ".ttf", ".war", ".webp", ".woff", ".woff2", ".zip",
]);
const allowedExtensions = new Set([
  ".c", ".cc", ".cfg", ".conf", ".cpp", ".cs", ".css", ".go", ".h", ".hpp",
  ".html", ".ini", ".java", ".js", ".json", ".jsonc", ".jsx", ".kt", ".kts",
  ".lock", ".md", ".mjs", ".properties", ".py", ".rb", ".rs", ".sh", ".swift",
  ".toml", ".ts", ".tsx", ".txt", ".xml", ".yaml", ".yml",
]);
const allowedBasenames = new Set([
  "cargo.lock", "cargo.toml", "dockerfile", "gemfile", "gemfile.lock", "go.mod",
  "go.sum", "makefile", "package-lock.json", "package.json", "pnpm-lock.yaml",
  "poetry.lock", "pyproject.toml", "requirements.txt", "yarn.lock",
]);

function normalizeRelative(value: string): string {
  return value.split(path.sep).join("/");
}

function safeExclude(pattern: string): string {
  const normalized = normalizeRelative(pattern.trim()).replace(/^\.\//u, "");
  if (
    normalized.length === 0 ||
    normalized.startsWith("/") ||
    normalized.includes("\0") ||
    normalized.split("/").includes("..")
  ) {
    throw new InputBoundaryError("exclude patterns must be relative");
  }
  return normalized;
}

function globExpression(pattern: string): RegExp {
  const escaped = pattern.replace(/[.+^$()|[\]\\]/gu, "\\$&");
  const expanded = escaped.replace(/\*\*/gu, ".*").replace(/\*/gu, "[^/]*");
  return new RegExp(`^(?:${expanded})(?:/.*)?$`, "u");
}

function shouldInspect(relativePath: string): boolean {
  const basename = relativePath.split("/").at(-1)?.toLowerCase() ?? "";
  const extension = path.posix.extname(relativePath).toLowerCase();
  return allowedBasenames.has(basename) || allowedExtensions.has(extension);
}

function sha256(value: Uint8Array | string): string {
  return createHash("sha256").update(value).digest("hex");
}

export class ReadOnlyFilesystemAdapter implements RepositoryReaderPort {
  async read(rootInput: string, excludes: string[]): Promise<RepositorySnapshot> {
    const root = path.resolve(rootInput);
    let metadata;
    try {
      metadata = await lstat(root);
    } catch {
      throw new InputBoundaryError("selected root is unavailable");
    }
    if (metadata.isSymbolicLink() || !metadata.isDirectory()) {
      throw new InputBoundaryError("selected root must be a regular directory");
    }

    const canonicalRoot = await realpath(root);
    const excludeExpressions = excludes.map((item) => globExpression(safeExclude(item)));
    const files: RepositorySnapshot["files"] = [];
    const diagnostics: ScanDiagnostic[] = [];
    let visitedFiles = 0;
    let skippedFiles = 0;

    const walk = async (directory: string): Promise<void> => {
      let entries;
      try {
        entries = await readdir(directory, { withFileTypes: true });
      } catch {
        throw new InputBoundaryError("a selected directory cannot be read");
      }
      entries.sort((left, right) => left.name.localeCompare(right.name, "en"));

      for (const entry of entries) {
        const absolutePath = path.join(directory, entry.name);
        const relativePath = normalizeRelative(path.relative(canonicalRoot, absolutePath));
        if (
          relativePath.startsWith("../") ||
          path.isAbsolute(relativePath) ||
          relativePath.length > 512
        ) {
          throw new InputBoundaryError("repository traversal boundary rejected");
        }

        const excluded = excludeExpressions.some((expression) => expression.test(relativePath));
        if (entry.isDirectory()) {
          if (deniedDirectories.has(entry.name.toLowerCase()) || excluded) continue;
          await walk(absolutePath);
          continue;
        }

        visitedFiles += 1;
        if (visitedFiles > MAX_VISITED_FILES) {
          throw new InputBoundaryError("repository file-count limit exceeded");
        }

        if (entry.isSymbolicLink()) {
          skippedFiles += 1;
          diagnostics.push({
            code: "symlink-skipped",
            severity: "warning",
            relativePath,
            message: "Symbolic links are never followed or inspected.",
          });
          continue;
        }
        if (!entry.isFile()) {
          skippedFiles += 1;
          diagnostics.push({
            code: "unsupported-path-type",
            severity: "warning",
            relativePath,
            message: "The path is not a regular file and was skipped.",
          });
          continue;
        }
        if (excluded) {
          skippedFiles += 1;
          diagnostics.push({
            code: "operator-excluded",
            severity: "information",
            relativePath,
            message: "The file matched an operator-provided relative exclusion.",
          });
          continue;
        }

        const extension = path.posix.extname(relativePath).toLowerCase();
        if (deniedExtensions.has(extension)) {
          skippedFiles += 1;
          diagnostics.push({
            code: "denied-file-type",
            severity: "information",
            relativePath,
            message: "A binary, archive, certificate, key, or key-container file type was skipped.",
          });
          continue;
        }
        if (!shouldInspect(relativePath)) {
          skippedFiles += 1;
          diagnostics.push({
            code: "unsupported-text-type",
            severity: "information",
            relativePath,
            message: "The file type is outside the conservative text allowlist.",
          });
          continue;
        }

        let handle;
        try {
          handle = await open(absolutePath, "r");
          const stat = await handle.stat();
          if (stat.size > MAX_FILE_BYTES) {
            skippedFiles += 1;
            diagnostics.push({
              code: "oversized-file",
              severity: "information",
              relativePath,
              message: "The file exceeds the one-megabyte inspection limit.",
            });
            continue;
          }
          const bytes = await handle.readFile();
          let content;
          try {
            content = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
          } catch {
            skippedFiles += 1;
            diagnostics.push({
              code: "non-utf8-file",
              severity: "information",
              relativePath,
              message: "The file is not valid UTF-8 text and was skipped.",
            });
            continue;
          }
          files.push({ relativePath, content, digest: sha256(bytes) });
        } catch {
          skippedFiles += 1;
          diagnostics.push({
            code: "unreadable-file",
            severity: "warning",
            relativePath,
            message: "The file could not be read and was skipped.",
          });
        } finally {
          await handle?.close();
        }
      }
    };

    await walk(canonicalRoot);
    files.sort((left, right) => left.relativePath.localeCompare(right.relativePath, "en"));
    diagnostics.sort((left, right) =>
      (left.relativePath ?? "").localeCompare(right.relativePath ?? "", "en") ||
      left.code.localeCompare(right.code, "en")
    );

    return {
      files,
      diagnostics,
      visitedFiles,
      skippedFiles,
      digestMaterial: files.map((file) => `${file.relativePath}\0${file.digest}\n`).join(""),
    };
  }
}
