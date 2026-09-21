import { useState } from "react";

import {
  CSF_2_CONCURRENT_OVERLAY,
  EXECUTIVE_LOOP,
  NIST_ALIGNED_LIFECYCLE,
  sectionById,
} from "../domain/data";
import {
  EVIDENCE_FUSION_FEEDS,
  EVIDENCE_FUSION_VIEW,
  INITIAL_INVENTORY_SOURCE,
  ISSUE_TYPE_LABELS,
} from "../domain/evidenceFusion";
import { Callout, FlowTrack, SectionHeader, StatusPill } from "./Primitives";

const SOURCE_DOMAINS = [
  {
    id: "crypto",
    label: "Crypto + PKI",
    items: ["Enterprise CA / PKI", "Certificate lifecycle", "Certificate discovery", "HSM + KMS", "Secrets management", "Code signing"],
    signal: "Algorithms, keys, certificates, issuers, profiles, lifetime, and trust dependencies",
  },
  {
    id: "infrastructure",
    label: "Infrastructure",
    items: ["Endpoints + servers", "Network + WAF", "Load balancers", "API gateways + VPN", "Kubernetes", "Service mesh + SSH"],
    signal: "Runtime, protocol, termination point, external exposure, and platform readiness",
  },
  {
    id: "cloud",
    label: "Cloud platforms",
    items: ["AWS", "Azure", "GCP", "Cloud resource inventory", "Managed certificates + keys"],
    signal: "Account, subscription, project, resource, termination, key-reference, exposure, and ownership metadata",
  },
  {
    id: "application",
    label: "Application estate",
    items: ["Application inventory", "Source repositories", "CI/CD", "Languages + runtimes", "Third-party products"],
    signal: "Crypto libraries, embedded dependencies, maintainers, release paths, and upgrade constraints",
  },
  {
    id: "security",
    label: "Security sources",
    items: ["TVM platforms", "Exposure management", "EDR inventory", "Asset inventory", "CMDB"],
    signal: "Asset context, vulnerability posture, ownership hints, reachability, and criticality enrichment",
  },
  {
    id: "business",
    label: "Business context",
    items: ["Service inventory", "Ownership", "Data classification", "Vendor management", "Criticality"],
    signal: "Impact, accountable owner, data lifetime, contractual constraints, and migration sequencing",
  },
] as const;

const CONTROL_PLANE_CAPABILITIES = [
  "Ingestion",
  "Normalization",
  "Crypto inventory",
  "Asset correlation",
  "Dependency mapping",
  "Ownership correlation",
  "Risk scoring",
  "Pattern selection",
  "Exception management",
  "Workflow orchestration",
  "Validation",
  "Metrics",
] as const;

const EXECUTION_GROUPS = [
  "ITSM / work management",
  "Application engineering",
  "Infrastructure + network",
  "PKI + IAM",
  "Cloud + DevSecOps",
  "Vendor management",
  "Governance + audit",
  "Executive reporting",
] as const;

export function OverviewSection() {
  return (
    <section className="page-section" aria-labelledby="overview-title">
      <SectionHeader
        section={sectionById("overview")}
        summary="A control-loop view of enterprise migration: find the cryptography, add context, sequence change, prove the result, and repeat."
        aside={<StatusPill state="Not validated" />}
      />

      <div className="hero-grid">
        <article className="hero-panel">
          <div className="hero-kicker">
            <span>ENTERPRISE SECURITY ARCHITECTURE</span>
            <span>DEVELOPMENT EVIDENCE</span>
          </div>
          <h2>Enterprise PQC Migration Reference Architecture</h2>
          <p className="hero-subtitle">Discovery, prioritization, orchestration, migration, validation.</p>
          <Callout label="Scope" tone="info">
            <p>Illustrative reference architecture. Technologies and integrations are environment-dependent. Synthetic data only.</p>
          </Callout>
          <div className="target-label">
            <span>Publication boundary</span>
            <strong>Source-only reference; not deployed</strong>
            <small>No public hostname, provider resource, identity policy, or PQ negotiation is asserted.</small>
          </div>
        </article>

        <aside className="brief-panel" aria-label="Walkthrough framing">
          <p className="eyebrow">The 60-second frame</p>
          <h3>Different cryptography. Familiar operating discipline.</h3>
          <ul className="check-list">
            <li>Inventory before prescribing algorithms</li>
            <li>Prioritize business exposure, not scanner volume</li>
            <li>Integrate commodity capability; build targeted gaps</li>
            <li>Validate installed behavior, not planned intent</li>
          </ul>
          <div className="time-box">
            <strong>05–08</strong>
            <span>minute guided walkthrough</span>
          </div>
        </aside>
      </div>

      <div className="content-block">
        <div className="block-heading">
          <div>
            <p className="eyebrow">Executive operating loop</p>
            <h2>Evidence moves forward. Discovery loops back.</h2>
          </div>
          <span className="loop-label">continuous discovery ↻</span>
        </div>
        <FlowTrack items={EXECUTIVE_LOOP} />
      </div>

      <div className="content-block">
        <div className="block-heading">
          <div>
            <p className="eyebrow">NIST-aligned lifecycle</p>
            <h2>Six stages for program governance</h2>
          </div>
          <span className="evidence-chip">SYNTHESIZED MODEL</span>
        </div>
        <Callout label="Evidence boundary">
          <p>Labels mirror the living NCCoE FAQ; ordering, artifacts, and gates are this demo’s synthesis—not a NIST-mandated taxonomy.</p>
        </Callout>
        <ol className="lifecycle-grid">
          {NIST_ALIGNED_LIFECYCLE.map((item, index) => (
            <li key={item.stage}>
              <span>{String(index + 1).padStart(2, "0")}</span>
              <h3>{item.stage}</h3>
              <p>{item.outcome}</p>
            </li>
          ))}
        </ol>

        <section className="csf-overlay" aria-labelledby="csf-overlay-title">
          <div className="csf-overlay-heading">
            <div>
              <p className="eyebrow">CSF 2.0 concurrent governance overlay</p>
              <h3 id="csf-overlay-title">Govern across the lifecycle. Apply every Function concurrently.</h3>
            </div>
            <span className="evidence-chip">DEMO MAPPING</span>
          </div>
          <Callout label="Mapping boundary" tone="warning">
            <p>CSF 2.0 Functions are concurrent. The stage emphases below are this demo’s operating overlay—not an official NIST crosswalk, required sequence, or maturity assessment.</p>
          </Callout>
          <article className="csf-govern">
            <div><span>{CSF_2_CONCURRENT_OVERLAY[0].function}</span><strong>{CSF_2_CONCURRENT_OVERLAY[0].stageEmphasis}</strong></div>
            <p>{CSF_2_CONCURRENT_OVERLAY[0].contribution}</p>
          </article>
          <div className="csf-function-grid">
            {CSF_2_CONCURRENT_OVERLAY.slice(1).map((item) => (
              <article key={item.function}>
                <span>{item.function}</span>
                <strong>{item.stageEmphasis}</strong>
                <p>{item.contribution}</p>
              </article>
            ))}
          </div>
        </section>
      </div>
    </section>
  );
}

export function ArchitectureSection() {
  const [selectedSourceId, setSelectedSourceId] = useState<(typeof SOURCE_DOMAINS)[number]["id"]>("crypto");
  const selected = SOURCE_DOMAINS.find((source) => source.id === selectedSourceId) ?? SOURCE_DOMAINS[0];

  return (
    <section className="page-section" aria-labelledby="architecture-title">
      <SectionHeader
        section={sectionById("architecture")}
        summary="A logical control plane connects existing discovery and business systems to governed execution—without assuming one giant custom platform."
      />

      <div className="architecture-map" aria-label="Enterprise PQC reference architecture">
        <section className="architecture-column source-column">
          <div className="column-heading">
            <span>01</span>
            <div><p>INPUT</p><h2>Source systems</h2></div>
          </div>
          <div className="source-tabs" aria-label="Source system categories">
            {SOURCE_DOMAINS.map((source) => (
              <button
                className={selected.id === source.id ? "source-tab is-active" : "source-tab"}
                key={source.id}
                onClick={() => setSelectedSourceId(source.id)}
                aria-pressed={selected.id === source.id}
              >
                {source.label}
              </button>
            ))}
          </div>
          <div className="source-detail" aria-live="polite">
            <h3>{selected.label}</h3>
            <ul>{selected.items.map((item) => <li key={item}>{item}</li>)}</ul>
            <p><span>Signals</span>{selected.signal}</p>
          </div>
        </section>

        <div className="map-connector" aria-hidden="true"><span>normalize</span></div>

        <section className="architecture-column control-column">
          <div className="column-heading">
            <span>02</span>
            <div><p>LOGICAL LAYER</p><h2>Migration control plane</h2></div>
          </div>
          <p className="column-note">Composable capabilities. Systems of record remain authoritative.</p>
          <div className="capability-cloud">
            {CONTROL_PLANE_CAPABILITIES.map((item, index) => (
              <span key={item} data-emphasis={index === 2 || index === 6 || index === 9 || index === 10 ? "high" : "normal"}>{item}</span>
            ))}
          </div>
          <div className="control-loop-mini">
            <span>evidence in</span>
            <strong>context → decision → work → proof</strong>
            <span>metrics out</span>
          </div>
        </section>

        <div className="map-connector" aria-hidden="true"><span>orchestrate</span></div>

        <section className="architecture-column execution-column">
          <div className="column-heading">
            <span>03</span>
            <div><p>OUTCOME</p><h2>Execution + assurance</h2></div>
          </div>
          <ul className="execution-list">
            {EXECUTION_GROUPS.map((item) => <li key={item}><span aria-hidden="true">→</span>{item}</li>)}
          </ul>
          <Callout label="Boundary" tone="warning">
            <p>Workflow automation coordinates work. Engineering owners authorize and execute production change.</p>
          </Callout>
        </section>
      </div>

      <section className="fusion-workbench" aria-labelledby="fusion-workbench-title">
        <div className="block-heading">
          <div>
            <p className="eyebrow">Automated evidence fusion · reference design</p>
            <h2 id="fusion-workbench-title">Adapters isolate feeds. A neutral contract protects the core.</h2>
          </div>
          <span className="development-label">SYNTHETIC · MODELED · NOT CONNECTED</span>
        </div>

        <Callout label="Bootstrap boundary" tone="warning">
          <p><strong>{INITIAL_INVENTORY_SOURCE.label}:</strong> {INITIAL_INVENTORY_SOURCE.contribution} {INITIAL_INVENTORY_SOURCE.authorityBoundary}</p>
        </Callout>

        <div className="adapter-flow" aria-label="Ports and adapters evidence-fusion path">
          <div><span>INBOUND ADAPTERS</span><strong>Six named adapters</strong><small>Feed-native shapes stop here</small></div>
          <i aria-hidden="true">→</i>
          <div><span>INBOUND PORT</span><strong>EvidenceObservation v1</strong><small>Versioned, safe, provenance-bearing</small></div>
          <i aria-hidden="true">→</i>
          <div><span>DOMAIN CORE</span><strong>Normalize · correlate · dedupe</strong><small>Conflict + unmatched review, no hidden merging</small></div>
          <i aria-hidden="true">→</i>
          <div><span>OUTBOUND PORT</span><strong>CanonicalCryptoRecord v1</strong><small>View model preserves evidence references</small></div>
        </div>

        <div className="feed-grid">
          {EVIDENCE_FUSION_FEEDS.map((feed) => (
            <article key={feed.id}>
              <header><span>{feed.family}</span><small>{feed.status}</small></header>
              <h3>{feed.label}</h3>
              <ul>{feed.signals.map((signal) => <li key={signal}>{signal}</li>)}</ul>
              <div className="issue-tag-row">
                {feed.issueTypes.map((type) => <span key={type}>{ISSUE_TYPE_LABELS[type]}</span>)}
              </div>
              <p>{feed.contribution}</p>
              <small>{feed.authorityBoundary}</small>
            </article>
          ))}
        </div>

        <div className="fusion-metrics" aria-label="Synthetic evidence fusion example results">
          <div><span>Seed assets</span><strong>{EVIDENCE_FUSION_VIEW.seedAssetCount}</strong><small>synthetic stand-ins</small></div>
          <div><span>Expanded seed observations</span><strong>{EVIDENCE_FUSION_VIEW.seedObservationCount}</strong><small>one per seed issue type</small></div>
          <div><span>Enrichment submissions</span><strong>{EVIDENCE_FUSION_VIEW.rawEnrichmentObservationCount}</strong><small>normalized inputs before exact dedupe</small></div>
          <div><span>Retained enrichment</span><strong>{EVIDENCE_FUSION_VIEW.uniqueEnrichmentEvidenceCount}</strong><small>synthetic refs preserved after dedupe</small></div>
          <div><span>Exact replay submissions</span><strong>{EVIDENCE_FUSION_VIEW.exactDuplicateCount}</strong><small>identical same-source content</small></div>
          <div><span>Seed + enrichment matched</span><strong>{EVIDENCE_FUSION_VIEW.correlatedCount}</strong><small>identity fields agree; completeness unproven</small></div>
          <div><span>Identity / classification conflicts</span><strong>{EVIDENCE_FUSION_VIEW.conflictCount}</strong><small>same candidate, governed fields disagree</small></div>
          <div><span>One-sided candidates</span><strong>{EVIDENCE_FUSION_VIEW.unmatchedCount}</strong><small>seed-only or enrichment-only</small></div>
        </div>

        <Callout label="Axes stay separate">
          <p><strong>Feed</strong> identifies provenance. <strong>Issue type</strong> identifies the cryptographic concern. <strong>Estate class</strong> determines ownership and change-control routing. None substitutes for another, and no percentage coverage is claimed without a real denominator.</p>
        </Callout>
      </section>
    </section>
  );
}

const TVM_FLOW = ["Asset discovery", "Vulnerability finding", "Asset + business context", "Risk prioritization", "Ticket / remediation", "Rescan", "Validation"] as const;
const PQC_FLOW = ["Crypto discovery", "Cryptographic dependency", "Asset + business context", "Migration prioritization", "Ticket / migration", "Rediscovery / test", "Validation"] as const;

export function TvmMappingSection() {
  return (
    <section className="page-section" aria-labelledby="tvm-mapping-title">
      <SectionHeader
        section={sectionById("tvm-mapping")}
        summary="Threat and Vulnerability Management provides a proven enterprise operating analogy and valuable enrichment—but it is not the cryptographic source of truth."
      />

      <div className="parallel-flows">
        <article>
          <div className="track-heading"><span>FAMILIAR DOMAIN</span><h2>TVM</h2></div>
          <FlowTrack items={TVM_FLOW} compact />
        </article>
        <div className="mapping-spine" aria-hidden="true">
          {TVM_FLOW.map((item, index) => <span key={item}>{index === 2 || index === 6 ? "=" : "↔"}</span>)}
        </div>
        <article>
          <div className="track-heading"><span>TARGET DOMAIN</span><h2>PQC migration</h2></div>
          <FlowTrack items={PQC_FLOW} compact />
        </article>
      </div>

      <blockquote className="thesis-quote">
        <p>Different security domain. Similar enterprise operating model.</p>
        <footer>Transfer the control-loop discipline—not the data-source assumptions.</footer>
      </blockquote>

      <div className="enrichment-grid">
        <article className="enrichment-primary">
          <p className="eyebrow">TVM contributes</p>
          <h2>High-value context</h2>
          <div className="tag-grid">
            {["Endpoint inventory", "Operating system", "Installed software", "Internet exposure", "Ownership", "Criticality", "Vulnerability posture", "Network context"].map((item) => <span key={item}>{item}</span>)}
          </div>
        </article>
        <article className="authority-card">
          <p className="eyebrow">Authority boundary</p>
          <div className="authority-row"><StatusPill state="Supported" /><span>Enrichment source</span></div>
          <div className="authority-row"><StatusPill state="Not implemented" /><span>Authoritative crypto inventory</span></div>
          <p>Cryptographic inventory needs direct evidence about algorithms, protocols, keys, certificates, libraries, and usage—not a proxy vulnerability record.</p>
        </article>
      </div>
    </section>
  );
}
