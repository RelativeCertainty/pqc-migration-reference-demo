import { useMemo, useState } from "react";

import { CRYPTO_SYSTEMS, sectionById } from "../domain/data";
import {
  ESTATE_ROUTING,
  EVIDENCE_FUSION_VIEW,
  ISSUE_TYPE_LABELS,
} from "../domain/evidenceFusion";
import type { CanonicalCryptoRecordV1 } from "../domain/evidenceFusion";
import type { CryptoSystem, RiskInputs } from "../domain/model";
import {
  calculateRisk,
  DEFAULT_RISK_INPUTS,
  RISK_INPUT_LABELS,
} from "../domain/risk";
import { Callout, EmptyState, PriorityPill, SectionHeader } from "./Primitives";

function hasSeedObservation(record: CanonicalCryptoRecordV1): boolean {
  return record.evidenceRefs.some((reference) => reference.feedId === "initial-inventory");
}

function evidenceMatchLabel(record: CanonicalCryptoRecordV1): string {
  if (record.correlation.status === "correlated") return "Seed + enrichment matched";
  if (record.correlation.status === "conflict") return "Identity / classification conflict";
  return hasSeedObservation(record)
    ? "Seed only — no enrichment match"
    : "Enrichment only — no seed match";
}

function syntheticObservationRefsLabel(count: number): string {
  return `${count} synthetic observation ${count === 1 ? "reference" : "references"} retained`;
}

const INVENTORY_READING_GUIDE = [
  {
    term: "Seed inventory",
    definition: "The ten fictional starting systems. These are inputs to matching, not a verified environment inventory.",
  },
  {
    term: "Enrichment feed",
    definition: "A modeled source—such as traffic, vulnerability, PKI, SAST, or CMDB—that contributes a bounded observation.",
  },
  {
    term: "Candidate",
    definition: "A proposed asset grouping created from a normalized identifier. It is something to review, not a confirmed system.",
  },
  {
    term: "Canonical record",
    definition: "A reviewable combined record produced by fixed rules. It is not automatically authoritative or complete.",
  },
  {
    term: "Correlated",
    definition: "The initial inventory and at least one enrichment feed point to the same candidate, with no disagreement in the governed identity fields.",
  },
  {
    term: "Unmatched",
    definition: "One side of the join is missing: a seed asset has no enrichment, or enrichment points to a candidate absent from the seed inventory.",
  },
  {
    term: "Conflict",
    definition: "Sources grouped to the same candidate disagree on a governed field, currently its display name or change-control class. The system does not choose a winner.",
  },
  {
    term: "Evidence reference",
    definition: "A retained pointer to one source observation. It supports traceability without copying a raw source payload into the canonical record.",
  },
  {
    term: "Review queue",
    definition: "Records requiring a person to resolve a mismatch, missing counterpart, unknown freshness, or low-confidence assumption before promotion.",
  },
] as const;

const INVENTORY_COLUMN_GUIDE = [
  ["Seed system / application", "The fictional asset name, application name, and stable demo identifier."],
  ["Change route / concern", "Who controls the change, followed by the cryptographic issue that makes action relevant."],
  ["Seed-to-enrichment match", "Whether modeled feed evidence agrees with, is missing from, or disagrees with the initial inventory."],
  ["Declared crypto use", "The fixture-authored algorithm, protocol, and purpose. It was not observed from a live system."],
  ["Illustrative business context", "The fictional service, owner, environment, and exposure used to make prioritization discussable."],
  ["Illustrative planning readiness", "Fixture-authored readiness, agility, dependency, and management labels; no readiness rubric calculated them."],
  ["Illustrative priority", "A fixture-authored urgency label, separate from the interactive scoring model on Page 05."],
  ["Migration stage / pattern", "A proposed lifecycle stage and migration approach, not evidence that work was executed."],
  ["Seed + fusion details", "Opens the seed assertions, derived matching result, evidence envelope, and remaining proof gaps."],
] as const;

function uniqueValues<K extends keyof CryptoSystem>(key: K): string[] {
  return [...new Set(CRYPTO_SYSTEMS.map((system) => String(system[key])))].sort();
}

function FilterSelect({
  label,
  value,
  options,
  onChange,
  formatOption = (option) => option,
}: {
  label: string;
  value: string;
  options: readonly string[];
  onChange: (value: string) => void;
  formatOption?: (option: string) => string;
}) {
  return (
    <label className="filter-control">
      <span>{label}</span>
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="all">All</option>
        {options.map((option) => <option key={option} value={option}>{formatOption(option)}</option>)}
      </select>
    </label>
  );
}

function InventoryRecordDetails({
  system,
  canonicalRecord,
  onClose,
}: {
  system: CryptoSystem;
  canonicalRecord: CanonicalCryptoRecordV1 | undefined;
  onClose: () => void;
}) {
  return (
    <div className="inventory-detail-panel" id={`inventory-detail-${system.id}`}>
      <header className="inventory-detail-header">
        <div>
          <p className="eyebrow">Record explanation</p>
          <h3>{system.asset}</h3>
          <p>Seed assertions, derived matching output, retained evidence references, and proof gaps remain visibly separated.</p>
        </div>
        <button className="text-button inventory-detail-close" type="button" onClick={onClose}>Close details</button>
      </header>
      <div className="inventory-details-groups">
        <section>
          <h4>Synthetic seed assertions</h4>
          <dl>
            <div><dt>Credential or key role — no key material</dt><dd>{system.credential}</dd></div>
            <div><dt>Declared issuer or manager</dt><dd>{system.issuer}</dd></div>
            <div><dt>Declared library or runtime</dt><dd>{system.runtime}</dd></div>
            <div><dt>Illustrative data sensitivity</dt><dd>{system.sensitivity}</dd></div>
            <div><dt>Protected-data retention horizon</dt><dd>{system.retention}</dd></div>
            <div><dt>Change-control class</dt><dd>{ESTATE_ROUTING[system.estateClass].label}</dd></div>
            <div><dt>Issue categories</dt><dd>{system.issueTypes.map((type) => ISSUE_TYPE_LABELS[type]).join(" · ")}</dd></div>
          </dl>
        </section>
        <section>
          <h4>Derived fusion result</h4>
          <dl>
            <div><dt>Seed-to-enrichment match</dt><dd>{canonicalRecord ? evidenceMatchLabel(canonicalRecord) : "Unresolved"}</dd></div>
            <div><dt>Retained synthetic observation refs</dt><dd>{canonicalRecord?.evidenceRefs.length ?? 0} refs · {canonicalRecord?.correlation.duplicateCount ?? 0} exact replay submissions ignored</dd></div>
            <div><dt>Fields that disagree</dt><dd>{canonicalRecord?.correlation.conflictFields.join(" · ") || "None"}</dd></div>
            <div><dt>Why human review is required</dt><dd><ul>{canonicalRecord?.review.reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul></dd></div>
          </dl>
        </section>
        <section>
          <h4>Seed evidence envelope</h4>
          <dl>
            <div><dt>Seed evidence record ID</dt><dd>{system.evidence.evidenceId}</dd></div>
            <div><dt>Seed evidence lifecycle stage</dt><dd>{system.evidence.stageRef} · Discovery &amp; Inventory</dd></div>
            <div><dt>Seed adapter</dt><dd>initial-inventory adapter · synthetic fixture stand-in</dd></div>
            <div><dt>Seed-record provenance</dt><dd>{system.evidence.provenance.kind.replaceAll("_", " ")} · {system.evidence.provenance.sourceLocator}</dd></div>
            <div><dt>Seed-record confidence</dt><dd>{system.evidence.confidence.level} · {system.evidence.confidence.rationale}</dd></div>
            <div><dt>Seed-record observation type</dt><dd>{system.evidence.observation.kind.replaceAll("_", " ")} · runtime observed: no</dd></div>
            <div><dt>Seed-record observation time</dt><dd>{system.evidence.observation.observedAt ?? `Not observed; fixture declared ${system.evidence.observation.declaredOn}`}</dd></div>
            <div><dt>Seed-record evidence assessment</dt><dd>{system.evidence.evidence.state}</dd></div>
            <div><dt>Evidence-review owner</dt><dd>{system.evidence.evidence.owner}</dd></div>
            <div><dt>Evidence-review date</dt><dd>{system.evidence.evidence.reviewDate}</dd></div>
            <div><dt>Artifact test status</dt><dd>{system.evidence.test.result.replaceAll("_", " ")} · run evidence is separate</dd></div>
            <div><dt>Test source locator</dt><dd>{system.evidence.test.locator}</dd></div>
          </dl>
        </section>
        <section>
          <h4>Known proof gaps</h4>
          <ul>{system.evidence.residualGaps.map((gap) => <li key={gap}>{gap}</li>)}</ul>
        </section>
      </div>
    </div>
  );
}

export function InventorySection() {
  const [query, setQuery] = useState("");
  const [environment, setEnvironment] = useState("all");
  const [status, setStatus] = useState("all");
  const [priority, setPriority] = useState("all");
  const [owner, setOwner] = useState("all");
  const [estateClass, setEstateClass] = useState("all");
  const [expandedSystemId, setExpandedSystemId] = useState<string | null>(null);

  const visibleSystems = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return CRYPTO_SYSTEMS.filter((system) => {
      const searchable = [system.asset, system.application, system.businessService, system.protocol, system.algorithm, system.runtime, ...system.issueTypes.map((type) => ISSUE_TYPE_LABELS[type])].join(" ").toLowerCase();
      return (
        (!normalizedQuery || searchable.includes(normalizedQuery)) &&
        (environment === "all" || system.environment === environment) &&
        (status === "all" || system.status === status) &&
        (priority === "all" || system.priority === priority) &&
        (owner === "all" || system.owner === owner) &&
        (estateClass === "all" || system.estateClass === estateClass)
      );
    });
  }, [environment, estateClass, owner, priority, query, status]);

  const resetFilters = () => {
    setQuery("");
    setEnvironment("all");
    setStatus("all");
    setPriority("all");
    setOwner("all");
    setEstateClass("all");
  };

  const seedOnlyCount = EVIDENCE_FUSION_VIEW.records.filter(
    (record) => record.correlation.status === "unmatched" && hasSeedObservation(record),
  ).length;
  const enrichmentOnlyCount = EVIDENCE_FUSION_VIEW.unmatchedCount - seedOnlyCount;

  return (
    <section className="page-section" aria-labelledby="inventory-title">
      <SectionHeader
        section={sectionById("inventory")}
        summary="A deliberately small synthetic seed inventory demonstrates prioritization and ownership while canonical fusion annotations preserve source-scoped evidence and review state."
        aside={<span className="synthetic-badge">10 / 10 synthetic</span>}
      />

      <section className="bootstrap-summary" aria-labelledby="bootstrap-summary-title">
        <div>
          <p className="eyebrow">Initial inventory bootstrap</p>
          <h2 id="bootstrap-summary-title">Seed, enrich, reconcile—preserve every source reference.</h2>
          <p>The 10 table rows below are synthetic stand-ins for an initial inventory. Their issue classifications expand to 36 seed observations; they are not 36 native inventory rows. Fusion produces {EVIDENCE_FUSION_VIEW.candidateCount} candidates because one modeled enrichment observation has no seed counterpart. That enrichment-only candidate appears in the review cards, not the 10-row seed table. No client inventory was imported.</p>
        </div>
        <dl>
          <div><dt>Seed systems</dt><dd>{EVIDENCE_FUSION_VIEW.seedAssetCount}</dd><small>Distinct fictional systems in the initial inventory</small></div>
          <div><dt>Seed issue observations</dt><dd>{EVIDENCE_FUSION_VIEW.seedObservationCount}</dd><small>One synthetic observation per assigned concern</small></div>
          <div><dt>Enrichment submissions</dt><dd>{EVIDENCE_FUSION_VIEW.rawEnrichmentObservationCount}</dd><small>Normalized synthetic submissions before duplicate handling</small></div>
          <div><dt>Retained enrichment</dt><dd>{EVIDENCE_FUSION_VIEW.uniqueEnrichmentEvidenceCount}</dd><small>Synthetic observations retained after exact deduplication</small></div>
          <div><dt>Exact replay submissions</dt><dd>{EVIDENCE_FUSION_VIEW.exactDuplicateCount}</dd><small>Identical same-source submissions counted once</small></div>
          <div><dt>Candidates for review</dt><dd>{EVIDENCE_FUSION_VIEW.reviewQueueCount}</dd><small>Review is required; it has not already occurred</small></div>
        </dl>
      </section>

      <section className="inventory-reading-guide" aria-labelledby="inventory-reading-guide-title">
        <div className="block-heading">
          <div>
            <p className="eyebrow">Plain-language key</p>
            <h2 id="inventory-reading-guide-title">How to read the evidence-matching terms</h2>
          </div>
          <span>Definitions used on this page</span>
        </div>
        <div>
          {INVENTORY_READING_GUIDE.map((entry) => (
            <article key={entry.term}>
              <h3>{entry.term}</h3>
              <p>{entry.definition}</p>
            </article>
          ))}
        </div>
        <p className="inventory-guide-boundary"><strong>Current fixture:</strong> {EVIDENCE_FUSION_VIEW.correlatedCount} seed-to-enrichment matches, {EVIDENCE_FUSION_VIEW.conflictCount} identity/classification conflict, and {EVIDENCE_FUSION_VIEW.unmatchedCount} one-sided candidates ({seedOnlyCount} seed-only and {enrichmentOnlyCount} enrichment-only). All {EVIDENCE_FUSION_VIEW.reviewQueueCount} require review because the observations are synthetic assumptions without runtime collection timestamps. Correlated does not mean correct or complete; unmatched does not mean nonexistent; conflict does not mean every source is wrong.</p>
      </section>

      <details className="inventory-column-guide" open>
        <summary>Nine-column dictionary</summary>
        <dl>
          {INVENTORY_COLUMN_GUIDE.map(([label, definition]) => (
            <div key={label}>
              <dt>{label}</dt>
              <dd>{definition}</dd>
            </div>
          ))}
        </dl>
      </details>

      <div className="estate-route-grid" aria-label="Software estate change-control routes">
        {Object.entries(ESTATE_ROUTING).map(([key, route]) => (
          <article key={key}>
            <span>{route.label}</span>
            <dl>
              <div><dt>Owner</dt><dd>{route.ownerPath}</dd></div>
              <div><dt>Change</dt><dd>{route.changePath}</dd></div>
              <div><dt>Validate</dt><dd>{route.validationPath}</dd></div>
            </dl>
          </article>
        ))}
      </div>

      <section className="fusion-review" aria-labelledby="fusion-review-title">
        <div className="block-heading">
          <div>
            <p className="eyebrow">Evidence-matching result</p>
            <h2 id="fusion-review-title">Records that need human review</h2>
          </div>
          <span>{EVIDENCE_FUSION_VIEW.reviewQueueCount} of {EVIDENCE_FUSION_VIEW.candidateCount} candidates require review</span>
        </div>
        <div className="fusion-review-grid">
          {EVIDENCE_FUSION_VIEW.records
            .filter((record) => record.review.required)
            .map((record) => (
              <article key={record.recordId}>
                <header>
                  <span data-status={record.correlation.status}>{evidenceMatchLabel(record)}</span>
                  <small>{syntheticObservationRefsLabel(record.evidenceRefs.length)}</small>
                </header>
                <strong>{record.displayName ?? "Unresolved display name"}</strong>
                <p>{record.canonicalAssetKey}</p>
                <small>{record.review.reasons[0]}</small>
              </article>
            ))}
        </div>
        <p className="fusion-review-boundary">Queue counts include unknown synthetic freshness. Conflict and unmatched records are candidates for accountable review, never automatic source-of-truth promotion. {EVIDENCE_FUSION_VIEW.sourceReconciliationCount} disputed source identities are excluded from canonical evidence and held in the separate source-reconciliation queue.</p>
      </section>

      <div className="inventory-toolbar" aria-label="Inventory filters">
        <label className="filter-control filter-control--search">
          <span>Search inventory</span>
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Asset, service, protocol…"
          />
        </label>
        <FilterSelect label="Illustrative environment" value={environment} options={uniqueValues("environment")} onChange={setEnvironment} />
        <FilterSelect label="Illustrative migration stage" value={status} options={uniqueValues("status")} onChange={setStatus} />
        <FilterSelect label="Illustrative priority" value={priority} options={uniqueValues("priority")} onChange={setPriority} />
        <FilterSelect label="System owner" value={owner} options={uniqueValues("owner")} onChange={setOwner} />
        <FilterSelect label="Change-control class" value={estateClass} options={uniqueValues("estateClass")} onChange={setEstateClass} formatOption={(option) => ESTATE_ROUTING[option as CryptoSystem["estateClass"]].label} />
      </div>

      <div className="results-line" aria-live="polite">
        <span><strong>{visibleSystems.length}</strong> of {CRYPTO_SYSTEMS.length} seed systems</span>
        <button className="text-button" type="button" onClick={resetFilters}>Reset filters</button>
      </div>

      {visibleSystems.length === 0 ? (
        <EmptyState>No synthetic systems match the current filters.</EmptyState>
      ) : (
        <div className="inventory-table-wrap">
          <table className="inventory-table">
            <caption className="sr-only">Synthetic seed inventory with canonical fusion annotations</caption>
            <thead>
              <tr>
                <th scope="col"><span>Seed system / application</span><small>Fictional seed identity</small></th>
                <th scope="col"><span>Change route / concern</span><small>Who changes it / why it matters</small></th>
                <th scope="col"><span>Seed-to-enrichment match</span><small>How synthetic feeds relate to the seed</small></th>
                <th scope="col"><span>Declared crypto use</span><small>Fixture algorithm / protocol / purpose</small></th>
                <th scope="col"><span>Illustrative business context</span><small>Fixture service / owner / exposure</small></th>
                <th scope="col"><span>Illustrative planning readiness</span><small>No implemented readiness rubric</small></th>
                <th scope="col"><span>Illustrative priority</span><small>Fixture-authored urgency</small></th>
                <th scope="col"><span>Migration stage / pattern</span><small>Proposed, not executed</small></th>
                <th scope="col"><span>Seed + fusion details</span><small>Authority / gaps / review</small></th>
              </tr>
            </thead>
            {visibleSystems.map((system) => {
                const canonicalRecord = EVIDENCE_FUSION_VIEW.records.find((record) => record.canonicalAssetKey === system.id);
                const isExpanded = expandedSystemId === system.id;
                return (
                  <tbody className="inventory-record-group" key={system.id}>
                    <tr className="inventory-record-row">
                      <td data-label="Seed system / application">
                        <strong>{system.asset}</strong>
                        <span>{system.application}</span>
                        <small>{system.id}</small>
                      </td>
                      <td data-label="Change route / concern">
                        <strong>{ESTATE_ROUTING[system.estateClass].label}</strong>
                        {system.issueTypes.map((type) => <span className="issue-label" key={type}>{ISSUE_TYPE_LABELS[type]}</span>)}
                        <small>Change control determines route; concern type says why</small>
                      </td>
                      <td data-label="Seed-to-enrichment match">
                        <strong className="correlation-state" data-status={canonicalRecord?.correlation.status}>{canonicalRecord ? evidenceMatchLabel(canonicalRecord) : "Unresolved"}</strong>
                        <span>{syntheticObservationRefsLabel(canonicalRecord?.evidenceRefs.length ?? 0)}</span>
                        <small>{canonicalRecord?.correlation.duplicateCount ?? 0} exact duplicate submissions ignored</small>
                      </td>
                      <td data-label="Declared crypto use">
                        <strong>{system.algorithm}</strong>
                        <span>{system.protocol}</span>
                        <small>{system.cryptographicUse}</small>
                      </td>
                      <td data-label="Illustrative business context">
                        <strong>{system.businessService}</strong>
                        <span>{system.owner}</span>
                        <small>{system.environment} · {system.exposure}</small>
                      </td>
                      <td data-label="Illustrative planning readiness">
                        <strong>{system.readiness}</strong>
                        <span>{system.cryptoAgility} agility</span>
                        <small>{system.dependencyCount} dependencies · {system.vendorManaged ? "vendor-managed" : "internally managed"}</small>
                      </td>
                      <td data-label="Illustrative priority"><PriorityPill priority={system.priority} /></td>
                      <td data-label="Migration stage / pattern">
                        <strong>{system.status}</strong>
                        <span>{system.migrationPattern}</span>
                      </td>
                      <td data-label="Seed + fusion details">
                        <button
                          aria-controls={`inventory-detail-${system.id}`}
                          aria-expanded={isExpanded}
                          className="inventory-explain-button"
                          type="button"
                          onClick={() => setExpandedSystemId(isExpanded ? null : system.id)}
                        >
                          {isExpanded ? "Hide record explanation" : "Explain record"}
                        </button>
                      </td>
                    </tr>
                    {isExpanded && (
                      <tr className="inventory-detail-row">
                        <td colSpan={9}>
                          <InventoryRecordDetails
                            canonicalRecord={canonicalRecord}
                            system={system}
                            onClose={() => setExpandedSystemId(null)}
                          />
                        </td>
                      </tr>
                    )}
                  </tbody>
                );
              })}
          </table>
        </div>
      )}

      <Callout label="Data boundary">
        <p>Every row is fictional and marked synthetic in source. This demo has no customer records, user profiles, persistence layer, or write path.</p>
      </Callout>
    </section>
  );
}

const DRIVER_KEYS: readonly (keyof RiskInputs)[] = [
  "algorithmRisk",
  "dataSensitivity",
  "retentionLifetime",
  "harvestNowRelevance",
  "publicExposure",
  "businessCriticality",
  "dependencyDepth",
  "migrationComplexity",
  "vendorDependency",
] as const;

const REDUCTION_KEYS: readonly (keyof RiskInputs)[] = [
  "platformReadiness",
  "cryptoAgility",
  "compensatingControls",
] as const;

function RatingControl({
  field,
  value,
  onChange,
}: {
  field: keyof RiskInputs;
  value: number;
  onChange: (value: number) => void;
}) {
  return (
    <label className="rating-control">
      <span>{RISK_INPUT_LABELS[field]}</span>
      <output>{value} / 5</output>
      <input
        type="range"
        min="1"
        max="5"
        step="1"
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
      />
      <small><span>Lower</span><span>Higher</span></small>
    </label>
  );
}

export function PrioritizationSection() {
  const [inputs, setInputs] = useState<RiskInputs>({ ...DEFAULT_RISK_INPUTS });
  const result = calculateRisk(inputs);
  const updateInput = (field: keyof RiskInputs, value: number) => setInputs((current) => ({ ...current, [field]: value }));

  return (
    <section className="page-section" aria-labelledby="prioritization-title">
      <SectionHeader
        section={sectionById("prioritization")}
        summary="Change the evidence inputs and inspect an explainable migration-priority signal. This is an illustrative model—not a standardized PQC risk formula."
      />

      <Callout label="Model boundary" tone="warning">
        <p>The score supports triage and discussion. It does not replace threat modeling, architecture review, regulatory obligations, or accountable risk acceptance.</p>
      </Callout>

      <div className="risk-layout">
        <div className="risk-controls">
          <section>
            <div className="control-group-heading"><span>Risk + urgency drivers</span><small>Add up to 100 points</small></div>
            <div className="rating-grid">
              {DRIVER_KEYS.map((field) => (
                <RatingControl key={field} field={field} value={inputs[field]} onChange={(value) => updateInput(field, value)} />
              ))}
            </div>
          </section>
          <section>
            <div className="control-group-heading"><span>Risk reductions</span><small>Subtract up to 20 points</small></div>
            <div className="rating-grid rating-grid--reductions">
              {REDUCTION_KEYS.map((field) => (
                <RatingControl key={field} field={field} value={inputs[field]} onChange={(value) => updateInput(field, value)} />
              ))}
            </div>
          </section>
        </div>

        <aside className="score-panel" aria-live="polite">
          <p className="eyebrow">Illustrative priority</p>
          <div className="score-value" data-priority={result.priority.toLowerCase()}>
            <strong>{result.score}</strong>
            <span>/ 100</span>
          </div>
          <PriorityPill priority={result.priority} />
          <meter
            min="0"
            max="100"
            low={35}
            high={75}
            optimum={20}
            value={result.score}
            aria-label={`Illustrative priority score: ${result.score} out of 100`}
          >{result.score}</meter>
          <div className="driver-list">
            <p>Primary drivers</p>
            {result.primaryDrivers.map((driver) => (
              <div key={driver.key}>
                <span>{driver.label}</span>
                <strong>+{driver.points.toFixed(1)}</strong>
              </div>
            ))}
          </div>
          <div className="score-actions">
            <button type="button" className="secondary-button" onClick={() => setInputs({ ...DEFAULT_RISK_INPUTS })}>Reset model</button>
          </div>
        </aside>
      </div>

      <details className="formula-disclosure">
        <summary>Inspect scoring logic</summary>
        <div>
          <p>Each 1–5 driver is normalized to 0–1 and multiplied by its published weight. Platform readiness, crypto agility, and compensating controls reduce the total. The result is clamped to 0–100.</p>
          <div className="formula-grid">
            {result.contributions.map((item) => (
              <span key={item.key} data-kind={item.kind}>{item.label}<strong>{item.points >= 0 ? "+" : ""}{item.points.toFixed(1)}</strong></span>
            ))}
          </div>
        </div>
      </details>
    </section>
  );
}
