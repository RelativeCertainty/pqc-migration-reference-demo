import { spawnSync } from "node:child_process";
import { mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const appRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const portableRoot = resolve(appRoot, "portable");
const operation = process.argv[2];

function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    cwd: options.cwd ?? portableRoot,
    env: options.env ?? process.env,
    encoding: options.encoding,
    stdio: options.stdio ?? "inherit",
  });
  if (result.error) throw result.error;
  if (result.status !== 0) {
    throw new Error(`${command} exited with status ${result.status}`);
  }
  return result.stdout?.trim() ?? "";
}

function safeValue(value, fallback, pattern) {
  return value && pattern.test(value) ? value : fallback;
}

function gitSHA() {
  const configured = process.env.PQC_DEMO_GIT_SHA;
  if (configured) return safeValue(configured, "unknown", /^[0-9a-f]{40}$/);
  try {
    return safeValue(
      run("git", ["rev-parse", "HEAD"], { cwd: appRoot, encoding: "utf8", stdio: "pipe" }),
      "unknown",
      /^[0-9a-f]{40}$/,
    );
  } catch {
    return "unknown";
  }
}

function sourceState() {
  try {
    const status = run(
      "git",
      ["status", "--porcelain=v1", "--untracked-files=normal", "--", "."],
      { cwd: appRoot, encoding: "utf8", stdio: "pipe" },
    );
    return status ? "dirty_worktree" : "clean_commit";
  } catch {
    return "unknown";
  }
}

function buildTimestamp() {
  const raw = process.env.SOURCE_DATE_EPOCH ?? "0";
  if (!/^(0|[1-9][0-9]*)$/.test(raw)) {
    throw new Error("SOURCE_DATE_EPOCH must be a non-negative integer");
  }
  const milliseconds = Number(raw) * 1000;
  if (!Number.isSafeInteger(milliseconds)) {
    throw new Error("SOURCE_DATE_EPOCH is outside the supported range");
  }
  return new Date(milliseconds).toISOString();
}

const goEnvironment = {
  ...process.env,
  GOTOOLCHAIN: process.env.GOTOOLCHAIN ?? "go1.26.6",
};

if (operation === "test") {
  run("go", ["test", "./..."], { env: goEnvironment });
} else if (operation === "vet") {
  run("go", ["vet", "./..."], { env: goEnvironment });
} else if (operation === "build") {
  const suffix = process.env.GOOS === "windows" ? ".exe" : "";
  const output = resolve(
    process.env.PQC_DEMO_BINARY_OUTPUT ?? resolve(portableRoot, "bin", `pqc-reference-demo${suffix}`),
  );
  mkdirSync(dirname(output), { recursive: true, mode: 0o755 });

  const version = safeValue(
    process.env.PQC_DEMO_VERSION ?? process.env.npm_package_version,
    "0.0.0-development",
    /^[0-9A-Za-z][0-9A-Za-z.+_-]{0,63}$/,
  );
  const timestamp = buildTimestamp();
  const linkerFlags = [
    "-buildid=",
    `-X main.Version=${version}`,
    `-X main.GitSHA=${gitSHA()}`,
    `-X main.SourceState=${sourceState()}`,
    `-X main.BuildTimestamp=${timestamp}`,
  ].join(" ");

  run(
    "go",
    ["build", "-tags", "portable_release", "-trimpath", "-ldflags", linkerFlags, "-o", output, "."],
    { env: { ...goEnvironment, CGO_ENABLED: "0" } },
  );
  process.stdout.write(`built portable executable: ${output}\n`);
} else {
  throw new Error("usage: node scripts/run-portable-go.mjs <test|vet|build>");
}
