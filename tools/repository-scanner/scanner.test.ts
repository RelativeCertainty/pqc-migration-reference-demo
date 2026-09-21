// SPDX-License-Identifier: MIT

import { mkdtemp, mkdir, readFile, symlink, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";

import evidenceSchema from "../../contracts/evidence-observation.v1.schema.json" with { type: "json" };
import resultSchema from "../../contracts/repository-scan-result.v1.schema.json" with { type: "json" };
import { assertRepositoryScanResultV1 } from "./contracts.ts";
import { CreateOnlyReportAdapter } from "./reports.ts";
import { createScanRepository } from "./scan.ts";
import { OutputBoundaryError } from "./types.ts";

const fixedTimestamp = "2026-08-20T00:00:00Z";

async function fixture(): Promise<string> {
  const root = await mkdtemp(path.join(os.tmpdir(), "pqc-scan-fixture-"));
  await writeFile(
    path.join(root, "package.json"),
    JSON.stringify({ dependencies: { "node-forge": "1.4.0" } }),
  );
  await mkdir(path.join(root, "src"));
  await writeFile(path.join(root, "src", "crypto.ts"), "const algorithm = 'RSA';\n");
  return root;
}

describe("repository scanner contracts", () => {
  it("produces deterministic contract-valid output without source excerpts or absolute paths", async () => {
    const root = await fixture();
    const request = {
      root,
      label: "contract-fixture",
      excludes: [],
      synthetic: true,
      collectedAt: fixedTimestamp,
    };
    const first = await createScanRepository().execute(request);
    const second = await createScanRepository().execute(request);

    expect(resultSchema.properties.schemaVersion.const).toBe(first.schemaVersion);
    expect(evidenceSchema.properties.schemaVersion.const).toBe(first.observations[0]?.schemaVersion);
    expect(() => assertRepositoryScanResultV1(first)).not.toThrow();
    expect(JSON.stringify(first)).toBe(JSON.stringify(second));
    expect(JSON.stringify(first)).not.toContain(root);
    expect(JSON.stringify(first)).not.toContain("const algorithm");
  });

  it("skips symbolic links and denied key containers", async () => {
    const root = await fixture();
    await writeFile(path.join(root, "private.key"), "not-a-real-key");
    await symlink(path.join(root, "src", "crypto.ts"), path.join(root, "linked.ts"));

    const result = await createScanRepository().execute({
      root,
      label: "boundary-fixture",
      excludes: [],
      synthetic: true,
      collectedAt: fixedTimestamp,
    });

    expect(result.diagnostics.map((item) => item.code).sort()).toEqual([
      "denied-file-type",
      "symlink-skipped",
    ]);
    expect(result.summary.skippedFiles).toBe(2);
  });

  it("refuses preexisting output directories", async () => {
    const root = await fixture();
    const result = await createScanRepository().execute({
      root,
      label: "output-fixture",
      excludes: [],
      synthetic: true,
      collectedAt: fixedTimestamp,
    });
    const output = await mkdtemp(path.join(os.tmpdir(), "pqc-existing-output-"));
    await expect(new CreateOnlyReportAdapter().write(output, result)).rejects.toBeInstanceOf(
      OutputBoundaryError,
    );
  });

  it("writes byte-stable JSON and Markdown for a fixed timestamp", async () => {
    const root = await fixture();
    const result = await createScanRepository().execute({
      root,
      label: "report-fixture",
      excludes: [],
      synthetic: true,
      collectedAt: fixedTimestamp,
    });
    const parent = await mkdtemp(path.join(os.tmpdir(), "pqc-report-parent-"));
    const first = path.join(parent, "first");
    const second = path.join(parent, "second");
    const writer = new CreateOnlyReportAdapter();
    await writer.write(first, result);
    await writer.write(second, result);
    expect(await readFile(path.join(first, "scan-result.json"), "utf8")).toBe(
      await readFile(path.join(second, "scan-result.json"), "utf8"),
    );
    expect(await readFile(path.join(first, "assessment.md"), "utf8")).toBe(
      await readFile(path.join(second, "assessment.md"), "utf8"),
    );
  });
});
