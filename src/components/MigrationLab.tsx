import { useMemo, useState } from "react";

import snykSyntheticSarif from "../fixtures/snyk-code.synthetic.sarif.json";
import venafiSyntheticSearch from "../fixtures/venafi-certificate-search.synthetic.json";
import { runMigrationSlice } from "../application/runMigrationSlice";
import { CRYPTO_SYSTEMS } from "../domain/data";
import type { MigrationEvidencePackageV1 } from "../domain/migrationPlanning";
import type { EvidenceAdapterId, EvidenceImportRequest } from "../ports/evidenceIngestion";
import { ISSUE_TYPE_LABELS } from "../domain/evidenceFusion";

const MAX_IMPORT_BYTES = 2 * 1024 * 1024;

interface LabSourceState {
  readonly adapterId: EvidenceAdapterId;
  readonly payload: unknown;
  readonly assetKey: string;
  readonly sourceName: string;
  readonly synthetic: boolean;
}

const DEFAULT_SOURCES: readonly LabSourceState[] = [
  {
    adapterId: "snyk-code-sarif",
    payload: snykSyntheticSarif,
    assetKey: "syn-sign-06",
    sourceName: "snyk-code.synthetic.sarif.json",
    synthetic: true,
  },
  {
    adapterId: "venafi-certificate-search",
    payload: venafiSyntheticSearch,
    assetKey: "syn-api-edge-01",
    sourceName: "venafi-certificate-search.synthetic.json",
    synthetic: true,
  },
] as const;

function sourceRequest(source: LabSourceState): EvidenceImportRequest {
  const system = CRYPTO_SYSTEMS.find((candidate) => candidate.id === source.assetKey);
  if (!system) throw new Error(`Unknown synthetic correlation target: ${source.assetKey}`);
  return {
    adapterId: source.adapterId,
    payload: source.payload,
    context: {
      assetKey: system.id,
      assetName: system.asset,
      estateClass: system.estateClass,
      collectedAt: null,
      sourceName: source.sourceName,
      synthetic: source.synthetic,
    },
  };
}

function execute(sources: readonly LabSourceState[]): MigrationEvidencePackageV1 {
  return runMigrationSlice.execute(sources.map(sourceRequest));
}

function adapterLabel(adapterId: EvidenceAdapterId): string {
  return adapterId === "snyk-code-sarif" ? "Snyk Code SARIF" : "Venafi certificate search";
}

function localSourceLabel(adapterId: EvidenceAdapterId): string {
  return adapterId === "snyk-code-sarif" ? "Local Snyk Code SARIF import" : "Local certificate-search JSON import";
}

export function MigrationLabSection() {
  const [sources, setSources] = useState<readonly LabSourceState[]>(DEFAULT_SOURCES);
  const [inputError, setInputError] = useState<string | null>(null);
  const execution = useMemo((): { result: MigrationEvidencePackageV1 | null; error: string | null } => {
    try {
      return { result: execute(sources), error: null };
    } catch (caught) {
      return {
        result: null,
        error: caught instanceof Error ? caught.message : "The evidence import could not be processed.",
      };
    }
  }, [sources]);
  const result = execution.result;
  const error = inputError ?? execution.error;

  const sourceByAdapter = useMemo(
    () => new Map(sources.map((source) => [source.adapterId, source])),
    [sources],
  );

  const replaceSource = (adapterId: EvidenceAdapterId, update: Partial<LabSourceState>) => {
    setInputError(null);
    setSources((current) => current.map((source) => source.adapterId === adapterId ? { ...source, ...update } : source));
  };

  const importFile = async (adapterId: EvidenceAdapterId, file: File | undefined) => {
    if (!file) return;
    if (file.size > MAX_IMPORT_BYTES) {
      setInputError("Import rejected: local evidence files are limited to 2 MiB in this reference slice.");
      return;
    }
    try {
      const payload: unknown = JSON.parse(await file.text());
      replaceSource(adapterId, { payload, sourceName: localSourceLabel(adapterId), synthetic: false });
    } catch {
      setInputError("Import rejected: the selected file is not valid UTF-8 JSON.");
    }
  };

  const downloadPackage = () => {
    if (!result) return;
    const body = JSON.stringify(result, null, 2);
    const url = URL.createObjectURL(new Blob([body], { type: "application/json" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = "pqc-migration-evidence-package.v1.json";
    link.click();
    URL.revokeObjectURL(url);
  };

  const reset = () => {
    setInputError(null);
    setSources(DEFAULT_SOURCES.map((source) => ({ ...source })));
  };

  return (
    <section className="page-section migration-lab" aria-labelledby="lab-title">
      <header className="section-header">
        <div>
          <p className="eyebrow">05 / Execute locally</p>
          <h1 id="lab-title" tabIndex={-1}>Runnable migration lab</h1>
          <p className="section-summary">
            Import vendor-shaped evidence, normalize it through categorical ports, fuse it with inventory,
            create reviewable migration work, and export a bounded evidence package without the application
            uploading selected files.
          </p>
        </div>
        <div className="section-aside">
          <span className="status-pill" data-state="supported"><i className="status-dot" />2 LOCAL ADAPTERS</span>
        </div>
      </header>

      <ol className="lab-flow" aria-label="Runnable evidence-to-migration flow">
        {[
          ["01", "Import", "Vendor JSON stays in browser memory"],
          ["02", "Normalize", "SAST and PKI categorical ports"],
          ["03", "Fuse", "Canonical records preserve provenance"],
          ["04", "Govern", "Human review and authority gates"],
          ["05", "Export", "Bounded evidence package"],
        ].map(([ordinal, label, detail]) => (
          <li key={ordinal}><span>{ordinal}</span><strong>{label}</strong><small>{detail}</small></li>
        ))}
      </ol>

      <div className="lab-adapter-grid">
        {(["snyk-code-sarif", "venafi-certificate-search"] as const).map((adapterId) => {
          const source = sourceByAdapter.get(adapterId);
          const run = result?.importRuns.find((candidate) => candidate.adapterId === adapterId);
          const eligibleSystems = adapterId === "snyk-code-sarif"
            ? CRYPTO_SYSTEMS.filter((system) => system.estateClass === "source-code")
            : CRYPTO_SYSTEMS;
          return (
            <article className="lab-adapter" key={adapterId}>
              <header>
                <div>
                  <p className="eyebrow">{adapterId === "snyk-code-sarif" ? "SAST PORT" : "PKI-INVENTORY PORT"}</p>
                  <h2>{adapterLabel(adapterId)}</h2>
                </div>
                <span className="development-label">LOCAL IMPORT</span>
              </header>
              <p>
                {adapterId === "snyk-code-sarif"
                  ? "Consumes Snyk Code SARIF 2.1.0, retains only crypto-relevant normalized observations, and discards the native payload after this browser session."
                  : "Consumes a bounded Venafi-shaped certificate-search result and emits categorical trust, public-key algorithm, and dependency evidence while withholding native certificate fields."}
              </p>
              <code>{adapterId === "snyk-code-sarif" ? "snyk code test --sarif-file-output=snyk-code.sarif.json" : "Certificate search API → JSON response"}</code>

              <div className="lab-form-row">
                <label>
                  Correlate to synthetic asset
                  <select
                    value={source?.assetKey}
                    onChange={(event) => replaceSource(adapterId, { assetKey: event.target.value })}
                  >
                    {eligibleSystems.map((system) => <option value={system.id} key={system.id}>{system.asset}</option>)}
                  </select>
                </label>
                <label className="file-control">
                  Select {adapterId === "snyk-code-sarif" ? "SARIF" : "search JSON"}
                  <input
                    type="file"
                    accept="application/json,.json,.sarif"
                    onChange={(event) => void importFile(adapterId, event.target.files?.[0])}
                  />
                </label>
              </div>

              <dl className="adapter-run-stats">
                <div><dt>Source</dt><dd>{source?.sourceName}</dd></div>
                <div><dt>Accepted observations</dt><dd>{run?.acceptedCount ?? 0}</dd></div>
                <div><dt>Skipped native records</dt><dd>{run?.skippedCount ?? 0}</dd></div>
                <div><dt>Evidence class</dt><dd>{source?.synthetic ? "Synthetic fixture" : "Local file import"}</dd></div>
              </dl>
            </article>
          );
        })}
      </div>

      {error ? <div className="callout lab-error" data-tone="warning" role="alert"><span>Import stopped</span><p>{error}</p></div> : null}

      <section className="lab-outcome" aria-labelledby="lab-outcome-title">
        <header className="block-heading">
          <div>
            <p className="eyebrow">GOVERNED OUTPUT</p>
            <h2 id="lab-outcome-title">A working slice, not a dashboard simulation</h2>
          </div>
          <div className="lab-actions">
            <button className="secondary-button" type="button" onClick={reset}>Restore fixtures</button>
            <button className="primary-button" type="button" onClick={downloadPackage} disabled={error !== null || result === null}>Export evidence package</button>
          </div>
        </header>

        <dl className="lab-summary">
          <div><dt>Adapter runs</dt><dd>{result?.summary.adapterRuns ?? 0}</dd></div>
          <div><dt>Normalized evidence</dt><dd>{result?.summary.acceptedObservations ?? 0}</dd></div>
          <div><dt>Canonical candidates</dt><dd>{result?.summary.canonicalCandidates ?? 0}</dd></div>
          <div><dt>Proposed work</dt><dd>{result?.summary.proposedWorkItems ?? 0}</dd></div>
          <div><dt>Review queue</dt><dd>{result?.summary.reviewRequired ?? 0}</dd></div>
        </dl>

        <div className="lab-work-items">
          {(result?.workItems ?? []).map((item) => (
            <article key={item.workItemId}>
              <header>
                <div>
                  <span>{item.assetKey}</span>
                  <h3>{item.displayName ?? "Unresolved asset"}</h3>
                </div>
                <span className="priority-pill" data-priority={item.priority.toLowerCase()}>{item.priority}</span>
              </header>
              <div className="lab-chip-row">
                {item.issueTypes.map((issueType) => <span className="evidence-chip" key={issueType}>{ISSUE_TYPE_LABELS[issueType]}</span>)}
              </div>
              <p>{item.recommendedPattern}</p>
              <dl>
                <div><dt>Decision</dt><dd>{item.decision.replaceAll("-", " ")}</dd></div>
                <div><dt>Evidence references</dt><dd>{item.evidenceRefs.length}</dd></div>
                <div><dt>Automatic change</dt><dd>Not authorized</dd></div>
              </dl>
              <details>
                <summary>Review gates and validation</summary>
                <h4>Authority gates</h4>
                <ul>{item.authorityGates.map((gate) => <li key={gate}>{gate}</li>)}</ul>
                <h4>Completion evidence</h4>
                <ul>{item.validationRequirements.map((requirement) => <li key={requirement}>{requirement}</li>)}</ul>
              </details>
            </article>
          ))}
        </div>

        <div className="callout" data-tone="success">
          <span>Boundary held</span>
          <p>{result?.assurance.limitation ?? "No package is available until the import passes validation."} Native messages, paths, file names, certificate identifiers, subjects, issuers, and raw payloads are withheld from the exported package.</p>
        </div>
      </section>
    </section>
  );
}
