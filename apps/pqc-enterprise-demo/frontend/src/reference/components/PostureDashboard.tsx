import { useMemo, useState } from "react";

import { CRYPTO_SYSTEMS, QUESTION_GROUPS, sectionById } from "../domain/data";
import { APPROVED_PQC_BASELINE, CURRENT_ELIGIBILITY_CAVEAT } from "../domain/claims";
import { SOURCE_ONLY_DEPLOYMENT_EVIDENCE } from "../domain/deploymentEvidence.v1";
import type { CryptoSystem, EvidenceState } from "../domain/model";
import { usePosture } from "../hooks/usePosture";
import { Callout, MetricCard, SectionHeader, StatusPill } from "./Primitives";

function PostureRow({
  label,
  state,
  value,
  detail,
}: {
  label: string;
  state: EvidenceState;
  value: string;
  detail: string;
}) {
  return (
    <article className="posture-row">
      <div><span>{label}</span><StatusPill state={state} /></div>
      <strong>{value}</strong>
      <p>{detail}</p>
    </article>
  );
}

export function PostureSection() {
  const posture = usePosture();
  const descriptor = SOURCE_ONLY_DEPLOYMENT_EVIDENCE;
  const payload = posture.payload;
  const tlsVersion = payload?.request_transport.tls_version.value;
  const tlsCipher = payload?.request_transport.tls_cipher.value;
  const httpProtocol = payload?.request_transport.http_protocol.value;

  return (
    <section className="page-section" aria-labelledby="posture-title">
      <SectionHeader
        section={sectionById("posture")}
        summary="The demo reports only what each evidence layer can support: source configuration, bounded request metadata, hostname capability, algorithm standards, and module validation remain separate."
        aside={<span className="development-label">SOURCE-ONLY · NOT DEPLOYED</span>}
      />

      <div className="posture-banner">
        <div>
          <p className="eyebrow">Portfolio publication boundary</p>
          <h2>Source-only package; deployment claims withheld</h2>
          <p className="approved-baseline">{APPROVED_PQC_BASELINE}</p>
          <p>{CURRENT_ELIGIBILITY_CAVEAT}</p>
        </div>
        <StatusPill state="Not validated" />
      </div>

      <p className="eyebrow">Source-only package path</p>
      <div className="deployment-chain" aria-label="Source-only package path">
        <div><span>01</span><strong>Synthetic fixtures</strong><small>Fictional records with explicit evidence limits</small></div>
        <i aria-hidden="true">→</i>
        <div><span>02</span><strong>React + TypeScript</strong><small>Interactive reference architecture and typed contracts</small></div>
        <i aria-hidden="true">→</i>
        <div><span>03</span><strong>Unified C# host</strong><small>Posture and assessment APIs share one authenticated application</small></div>
        <i aria-hidden="true">→</i>
        <div><span>04</span><strong>Automated checks</strong><small>Source, contract, package, and parity tests</small></div>
      </div>

      <Callout label="Source descriptor versus current runtime" tone="warning">
        <p>
          This descriptor records a source-only portfolio snapshot. Its reserved <strong>example.invalid</strong> hostname is a placeholder,
          not evidence of DNS, routing, identity, certificates, or a deployed provider resource.
        </p>
        <p>
          {payload === null
            ? "Current runtime context has not been observed in this view."
            : `Runtime metadata came from the current execution context (${payload.hostname}). It does not change the source-only status or prove deployment, hostname PQ capability, identity policy, or external validation.`}
        </p>
      </Callout>

      <Callout label="Runtime observation" tone={posture.state === "observed" ? "success" : "warning"}>
        <p>{posture.message}</p>
        {posture.state === "unavailable" ? (
          <button type="button" className="secondary-button posture-retry" onClick={posture.retry}>Retry bounded posture check</button>
        ) : null}
      </Callout>

      <section className="deployment-evidence" aria-labelledby="deployment-evidence-title">
        <div className="block-heading">
          <div>
            <p className="eyebrow">Fail-closed source descriptor · v{descriptor.descriptorVersion}</p>
            <h2 id="deployment-evidence-title">Evidence layers stay separate</h2>
          </div>
          <StatusPill state="Not validated" />
        </div>
        <Callout label="Bounded source evidence" tone="warning">
          <p><strong>{descriptor.deploymentState}</strong> · approved-label eligible: <strong>no</strong> · fail closed: <strong>yes</strong>.</p>
          <p>Record: {descriptor.evidenceRecord.kind} · locator: {descriptor.evidenceRecord.reference}. Runtime metadata cannot promote this source descriptor into deployment or external evidence. A future deployment requires separate provider, hostname, runtime, and human validation.</p>
        </Callout>
        <div className="evidence-layer-grid">
          {descriptor.layers.map((layer) => (
            <article key={layer.id}>
              <div><span>{layer.label}</span><StatusPill state={layer.state} /></div>
              <strong>{layer.claim}</strong>
              <p>{layer.boundary}</p>
              <small>Locator: {layer.locator}</small>
            </article>
          ))}
        </div>
      </section>

      <div className="posture-grid">
        <PostureRow
          label="Request TLS version"
          state={tlsVersion ? "Observed" : "Not validated"}
          value={tlsVersion ?? "Unavailable in this context"}
          detail="This loopback C# host does not terminate upstream TLS; proxy headers are not trusted as observations."
        />
        <PostureRow
          label="Request TLS cipher"
          state={tlsCipher ? "Observed" : "Not validated"}
          value={tlsCipher ?? "Unavailable in this context"}
          detail="The cipher is observable request metadata; it does not identify the exact session key exchange."
        />
        <PostureRow
          label="Request HTTP protocol"
          state={httpProtocol ? "Observed" : "Not validated"}
          value={httpProtocol ?? "Unavailable in this context"}
          detail="Transport metadata only. No source IP, cookie, identity, or request body is returned or stored."
        />
        <PostureRow
          label="Exact browser-session key exchange"
          state="Not observable"
          value="No claim"
          detail="TLS version and cipher do not prove whether this exact visitor session negotiated hybrid post-quantum key agreement."
        />
        <PostureRow
          label="Hostname hybrid PQ capability"
          state="Not validated"
          value="No deployed hostname"
          detail="Capability requires a separately deployed hostname and an external handshake observation; neither exists in this source-only snapshot."
        />
        <PostureRow
          label="Visitor-edge PQ signatures"
          state="Not deployed"
          value="Not deployed or claimed"
          detail="Post-quantum digital signatures are separate from hybrid key agreement. This visitor-edge connection does not deploy them."
        />
        <PostureRow
          label="Identity boundary"
          state="Not implemented"
          value="No identity policy or provider resource is asserted"
          detail="The app has synthetic sessions and assessment-scoped authorization. Enterprise identity and provider access still require qualification."
        />
        <PostureRow
          label="Application storage + origin dependency"
          state="Development evidence"
          value="Isolated SQLite and same-origin C# serving"
          detail="Synthetic assessment state is durable in SQLite. Session cookies and role checks are active. The application does not log request bodies or infer upstream TLS from headers."
        />
        <PostureRow
          label="Deployment target"
          state="Not deployed"
          value="pqc-demo.example.invalid (reserved placeholder)"
          detail="The reserved hostname documents a safe placeholder only. It does not resolve and represents no route, certificate, Worker binding, or production service."
        />
        <PostureRow
          label="DNS + provider resources"
          state="Not implemented"
          value="No DNS or provider resource asserted"
          detail="The repository contains application source and configuration examples only; it supplies no public DNS, provider evidence, or infrastructure ownership evidence."
        />
        <PostureRow
          label="Response controls"
          state="Development evidence"
          value="CSP · HSTS · no framing · no sniffing"
          detail="Source and package tests define restrictive static/API headers. They have not been observed on a deployed production response."
        />
        <PostureRow
          label="Application evidence posture"
          state="Development evidence"
          value="Synthetic · secret-free · source-reviewed"
          detail="Ten synthetic records, no application secret binding, and explicit source-level evidence boundaries."
        />
        <PostureRow
          label="External validation"
          state="Not validated"
          value="No customer or production outcome"
          detail="No customer deployment, assessor statement, measured user result, or operational acceptance is represented."
        />
      </div>

      <div className="evidence-separation">
        <div className="block-heading">
          <div><p className="eyebrow">Do not collapse evidence layers</p><h2>Standardized algorithm ≠ validated module ≠ observed protocol</h2></div>
        </div>
        <div className="algorithm-grid">
          <article><span>FIPS 203</span><h3>ML-KEM</h3><StatusPill state="Final standard" /><p>NIST key-encapsulation mechanism standard. Documentary algorithm evidence.</p></article>
          <article><span>FIPS 204</span><h3>ML-DSA</h3><StatusPill state="Final standard" /><p>NIST module-lattice digital-signature standard. Documentary algorithm evidence.</p></article>
          <article><span>FIPS 205</span><h3>SLH-DSA</h3><StatusPill state="Final standard" /><p>NIST stateless hash-based digital-signature standard. Documentary algorithm evidence.</p></article>
          <article className="module-card"><span>MODULE / RUNTIME</span><h3>Implementation evidence</h3><StatusPill state="Not validated" /><p>No FIPS 140 certificate, module build identity, protocol integration, or installed-runtime validation is asserted here.</p></article>
        </div>
        <p className="validation-boundary">Algorithm validation evidence such as CAVP/ACVP results is not CMVP evidence that a complete cryptographic module is FIPS 140 validated.</p>
      </div>
    </section>
  );
}

type DashboardFilterKey = "businessService" | "status" | "priority" | "owner" | "environment" | "technology";

function technologyFor(system: CryptoSystem): string {
  const signal = `${system.protocol} ${system.runtime} ${system.cryptographicUse}`.toLowerCase();
  if (signal.includes("x.509") || signal.includes("certificate") || signal.includes("sign")) return "PKI + signing";
  if (signal.includes("ssh") || signal.includes("sftp")) return "SSH + transfer";
  if (signal.includes("ike") || signal.includes("vpn")) return "Network access";
  if (signal.includes("kubernetes") || signal.includes("spiffe")) return "Cloud native";
  if (signal.includes("oidc") || signal.includes("identity")) return "Identity";
  if (signal.includes("envelope") || signal.includes("kms")) return "Data protection";
  return "TLS + application";
}

const DASHBOARD_FILTERS: ReadonlyArray<{ key: DashboardFilterKey; label: string }> = [
  { key: "businessService", label: "Business service" },
  { key: "technology", label: "Technology" },
  { key: "status", label: "Migration status" },
  { key: "priority", label: "Risk priority" },
  { key: "owner", label: "Owner" },
  { key: "environment", label: "Environment" },
] as const;

function dashboardValue(system: CryptoSystem, key: DashboardFilterKey): string {
  return key === "technology" ? technologyFor(system) : String(system[key]);
}

export function DashboardSection() {
  const [filterKey, setFilterKey] = useState<DashboardFilterKey>("businessService");
  const [filterValue, setFilterValue] = useState("all");

  const options = useMemo(
    () => [...new Set(CRYPTO_SYSTEMS.map((system) => dashboardValue(system, filterKey)))].sort(),
    [filterKey],
  );
  const systems = useMemo(
    () => CRYPTO_SYSTEMS.filter((system) => filterValue === "all" || dashboardValue(system, filterKey) === filterValue),
    [filterKey, filterValue],
  );

  const highPriority = systems.filter((system) => system.priority === "Urgent" || system.priority === "High").length;
  const inProgress = systems.filter((system) => ["Pilot", "Migrating"].includes(system.status)).length;
  const vendorBlockers = systems.filter((system) => system.vendorManaged && ["Blocked", "Unknown"].includes(system.readiness)).length;
  const activeExceptions = systems.filter((system) => system.status === "Exception").length;
  const unknown = systems.filter((system) => system.readiness === "Unknown").length;
  const agile = systems.filter((system) => system.cryptoAgility === "High").length;
  const dependencyCount = systems.reduce((sum, system) => sum + system.dependencyCount, 0);
  const ownershipCoverage = systems.length === 0 ? 0 : Math.round((systems.filter((system) => system.owner).length / systems.length) * 100);
  const statusCounts = [...new Set(CRYPTO_SYSTEMS.map((system) => system.status))].map((status) => ({
    status,
    count: systems.filter((system) => system.status === status).length,
  }));

  const changeFilterKey = (key: DashboardFilterKey) => {
    setFilterKey(key);
    setFilterValue("all");
  };

  return (
    <section className="page-section" aria-labelledby="dashboard-title">
      <SectionHeader
        section={sectionById("dashboard")}
        summary="Synthetic measures connect discovery coverage, migration flow, blockers, validation, and crypto agility without presenting development fixtures as operational results."
        aside={<span className="synthetic-badge">SYNTHETIC METRICS</span>}
      />

      <div className="dashboard-filters">
        <label><span>Filter dimension</span><select value={filterKey} onChange={(event) => changeFilterKey(event.target.value as DashboardFilterKey)}>{DASHBOARD_FILTERS.map((filter) => <option key={filter.key} value={filter.key}>{filter.label}</option>)}</select></label>
        <label><span>Filter value</span><select value={filterValue} onChange={(event) => setFilterValue(event.target.value)}><option value="all">All</option>{options.map((option) => <option key={option}>{option}</option>)}</select></label>
        <div><span>Current seed-fixture slice</span><strong>{systems.length} systems / {dependencyCount} modeled dependencies</strong></div>
      </div>

      <div className="metrics-grid">
        <MetricCard label="Seed systems in slice" value={systems.length} detail="Static synthetic fixture rows" />
        <MetricCard label="Fixture dependencies" value={dependencyCount} detail="Static modeled relationship total" />
        <MetricCard label="Ownership coverage" value={`${ownershipCoverage}%`} detail="Named accountable groups" />
        <MetricCard label="High-priority migrations" value={highPriority} detail="Urgent + high" accent="red" />
        <MetricCard label="Migrations in progress" value={inProgress} detail="Pilot + migrating" accent="violet" />
        <MetricCard label="Validated migrations" value={systems.filter((system) => system.status === "Validated").length} detail="Requires result evidence" />
        <MetricCard label="Vendor blockers" value={vendorBlockers} detail="Blocked or unknown readiness" accent="amber" />
        <MetricCard label="Active exceptions" value={activeExceptions} detail="Time-bound path" accent="amber" />
        <MetricCard label="Unknown readiness" value={unknown} detail="Unclassified product support" accent="red" />
        <MetricCard label="High crypto agility" value={agile} detail="Configurable or replaceable path" />
      </div>

      <div className="dashboard-panels">
        <article>
          <div className="block-heading"><div><p className="eyebrow">Flow distribution</p><h2>Migration status</h2></div></div>
          <div className="bar-list">
            {statusCounts.map((item) => (
              <div key={item.status}>
                <span>{item.status}</span>
                <progress
                  max={Math.max(1, systems.length)}
                  value={item.count}
                  aria-label={`${item.status}: ${item.count} of ${systems.length} seed systems`}
                >{item.count}</progress>
                <strong>{item.count}</strong>
              </div>
            ))}
          </div>
        </article>
        <article>
          <div className="block-heading"><div><p className="eyebrow">Operating readout</p><h2>What the slice says</h2></div></div>
          <ul className="insight-list">
            <li><span>01</span><p><strong>{highPriority} high-priority systems</strong> need sequencing against dependencies and accountable owners.</p></li>
            <li><span>02</span><p><strong>{vendorBlockers} vendor-controlled blockers</strong> need roadmap evidence, upgrade paths, and expiry-based exceptions.</p></li>
            <li><span>03</span><p><strong>{agile} high-agility systems</strong> are candidates for bounded pilots that produce reusable patterns.</p></li>
          </ul>
          <Callout label="Evidence boundary"><p>These numbers demonstrate dashboard behavior only. They are not measurements of any organization or deployed migration program.</p></Callout>
        </article>
      </div>
    </section>
  );
}

export function QuestionsSection() {
  return (
    <section className="page-section" aria-labelledby="questions-title">
      <SectionHeader
        section={sectionById("questions")}
        summary="Use discovery questions to replace assumptions with environment evidence and turn the reference architecture into a scoped migration program."
      />

      <div className="questions-intro">
        <p className="eyebrow">Interview close</p>
        <h2>The architecture is a hypothesis until the environment answers back.</h2>
        <p>Start with scope, sources of truth, dependency ownership, platform readiness, and the evidence required to call a migration complete.</p>
      </div>

      <div className="question-grid">
        {QUESTION_GROUPS.map((group, index) => (
          <article key={group.category}>
            <header><span>{String(index + 1).padStart(2, "0")}</span><h2>{group.category}</h2></header>
            <ul>{group.questions.map((question) => <li key={question}>{question}</li>)}</ul>
          </article>
        ))}
      </div>

      <div className="closing-frame">
        <div><span>DISCOVER</span><p>What cryptography and data matter?</p></div>
        <div><span>DECIDE</span><p>Which capability should we integrate, buy, or build?</p></div>
        <div><span>DELIVER</span><p>What evidence proves the installed outcome?</p></div>
      </div>
    </section>
  );
}
