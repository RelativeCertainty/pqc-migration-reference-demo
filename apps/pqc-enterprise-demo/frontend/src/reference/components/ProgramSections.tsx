import { useState } from "react";

import {
  CAPABILITY_QUESTIONS,
  MATURITY_SCENARIOS,
  MIGRATION_PATTERNS,
  NIST_ALIGNED_LIFECYCLE,
  sectionById,
} from "../domain/data";
import { Callout, SectionHeader } from "./Primitives";

const WORKFLOW_LANES = [
  {
    lane: "Discovery systems",
    tone: "aqua",
    steps: ["Observe crypto", "Emit evidence", "Rediscover result"],
  },
  {
    lane: "PQC program",
    tone: "violet",
    steps: ["Normalize + correlate", "Resolve owner", "Score + select pattern", "Verify evidence", "Measure"],
  },
  {
    lane: "ITSM / work system",
    tone: "amber",
    steps: ["Create work item", "Track target + dependencies", "Route exception or closure"],
  },
  {
    lane: "Engineering",
    tone: "green",
    steps: ["Assess compatibility", "Implement pilot", "Roll out + rollback ready"],
  },
  {
    lane: "Governance",
    tone: "neutral",
    steps: ["Approve pattern boundary", "Review exception", "Accept validation evidence"],
  },
] as const;

export function WorkflowSection() {
  const [ticketOpen, setTicketOpen] = useState(false);

  return (
    <section className="page-section" aria-labelledby="workflow-title">
      <SectionHeader
        section={sectionById("workflow")}
        summary="A governed workflow turns cryptographic evidence into accountable engineering work, then requires rediscovery or test evidence before closure."
        aside={<span className="evidence-chip">NO EXTERNAL ACTIONS</span>}
      />

      <div className="lifecycle-ribbon" aria-label="Six-stage NIST-aligned lifecycle">
        {NIST_ALIGNED_LIFECYCLE.map((stage, index) => (
          <span key={stage.stage}><b>{index + 1}</b>{stage.stage}</span>
        ))}
      </div>

      <div className="swimlane" aria-label="PQC migration workflow swimlane">
        {WORKFLOW_LANES.map((lane) => (
          <section key={lane.lane} className="swimlane-row" data-tone={lane.tone}>
            <h2>{lane.lane}</h2>
            <ol>
              {lane.steps.map((step, index) => (
                <li key={step}>
                  <span>{String(index + 1).padStart(2, "0")}</span>
                  {step}
                </li>
              ))}
            </ol>
          </section>
        ))}
      </div>

      <div className="workflow-decision">
        <article>
          <p className="eyebrow">Closure gate</p>
          <h2>Did installed behavior match the target?</h2>
          <div className="branch-grid">
            <div><span>YES</span><strong>Attach validation evidence</strong><p>Rediscovery, compatibility tests, installed configuration, and accountable review support closure.</p></div>
            <div><span>NO</span><strong>Rework or time-bound exception</strong><p>Record the blocker, owner, compensating controls, expiry, and required next evidence.</p></div>
          </div>
        </article>
        <article className="ticket-launcher">
          <p className="eyebrow">Illustrative integration</p>
          <h2>Synthetic ITSM work item</h2>
          <p>Preview the handoff contract. No ticket is created and no external system is connected.</p>
          <button className="primary-button" type="button" onClick={() => setTicketOpen((open) => !open)} aria-expanded={ticketOpen}>
            {ticketOpen ? "Close work item" : "Open work item"}
          </button>
        </article>
      </div>

      {ticketOpen ? (
        <article className="ticket-preview" aria-label="Synthetic ITSM work item preview">
          <header>
            <div><span>SYN-PQC-0042</span><h2>Migrate signing dependency for Ledger Relay</h2></div>
            <span className="ticket-state">PLANNING</span>
          </header>
          <dl>
            <div><dt>Application</dt><dd>Ledger Relay</dd></div>
            <div><dt>Asset / CI</dt><dd>Internal Java Payment Service</dd></div>
            <div><dt>Owner</dt><dd>Application Engineering</dd></div>
            <div><dt>Dependency</dt><dd>Payload signatures and service TLS</dd></div>
            <div><dt>Current algorithm</dt><dd>RSA-2048 + SHA-256</dd></div>
            <div><dt>Affected protocol</dt><dd>TLS 1.2 and JWS</dd></div>
            <div><dt>Exposure</dt><dd>Internal · critical data · 10-year retention</dd></div>
            <div><dt>Business criticality</dt><dd>Critical · settlement processing</dd></div>
            <div><dt>Priority</dt><dd>Urgent · illustrative model</dd></div>
            <div><dt>Target date</dt><dd>Synthetic planning date · 2027 Q2</dd></div>
            <div><dt>Recommended pattern</dt><dd>Runtime uplift + dual-sign validation</dd></div>
            <div><dt>Target state</dt><dd>Approved interoperable signature pattern</dd></div>
            <div><dt>Validation</dt><dd>Verifier matrix + rediscovery + rollback evidence</dd></div>
            <div><dt>Exception path</dt><dd>Named owner, controls, expiry, replacement trigger</dd></div>
          </dl>
        </article>
      ) : null}
    </section>
  );
}

export function ScenariosSection() {
  const [selectedId, setSelectedId] = useState(MATURITY_SCENARIOS[1].id);
  const selected = MATURITY_SCENARIOS.find((scenario) => scenario.id === selectedId) ?? MATURITY_SCENARIOS[1];

  return (
    <section className="page-section" aria-labelledby="scenarios-title">
      <SectionHeader
        section={sectionById("scenarios")}
        summary="The target operating model remains stable while implementation effort changes with source quality, ownership coverage, and integration maturity."
      />

      <div className="scenario-selector" aria-label="Maturity scenarios">
        {MATURITY_SCENARIOS.map((scenario) => (
          <button
            key={scenario.id}
            aria-pressed={selected.id === scenario.id}
            className={selected.id === scenario.id ? "scenario-tab is-active" : "scenario-tab"}
            onClick={() => setSelectedId(scenario.id)}
          >
            <span>{scenario.label}</span>
            <strong>{scenario.headline}</strong>
          </button>
        ))}
      </div>

      <div className="scenario-detail" aria-live="polite">
        <article className="scenario-profile">
          <div className="scenario-title"><span>{selected.label}</span><h2>{selected.headline}</h2></div>
          <p className="eyebrow">Available now</p>
          <ul className="check-list">{selected.available.map((item) => <li key={item}>{item}</li>)}</ul>
          <div className="strategy-box"><span>Strategy</span><strong>{selected.strategy}</strong></div>
        </article>
        <article className="scenario-radar">
          <h2>Delivery implications</h2>
          <dl>
            <div><dt>Custom engineering</dt><dd>{selected.customEngineering}</dd></div>
            <div><dt>Manual effort</dt><dd>{selected.manualEffort}</dd></div>
            <div><dt>Integration need</dt><dd>{selected.integrationNeed}</dd></div>
            <div><dt>Time to value</dt><dd>{selected.timeToValue}</dd></div>
          </dl>
          <Callout label="Build-vs-buy implication">
            <p>{selected.decision}</p>
          </Callout>
        </article>
      </div>

      <p className="relative-note">All estimates are intentionally relative. Exact duration requires environment evidence, scope, constraints, and accountable delivery planning.</p>
    </section>
  );
}

type DecisionAnswer = "yes" | "no";
type BuildChoice = "integrate" | "buy" | "build";

const BUILD_CHOICES: ReadonlyArray<{
  id: BuildChoice;
  title: string;
  useWhen: string;
  guardrail: string;
}> = [
  { id: "integrate", title: "Integrate existing platform", useWhen: "A capable system exists, has reliable ownership, and can produce supportable evidence.", guardrail: "Do not create a parallel system of record." },
  { id: "buy", title: "Buy / adopt enterprise capability", useWhen: "A mature product solves a commodity discovery, lifecycle, or workflow need better than bespoke code.", guardrail: "Validate interoperability, data ownership, exit path, and operating cost." },
  { id: "build", title: "Build targeted capability", useWhen: "A material normalization, correlation, orchestration, or discovery gap remains after integration and product evaluation.", guardrail: "Bound the gap; avoid rebuilding commodity platforms." },
] as const;

export function DecisionsSection() {
  const [capabilityIndex, setCapabilityIndex] = useState(0);
  const [answer, setAnswer] = useState<DecisionAnswer>("yes");
  const [buildChoice, setBuildChoice] = useState<BuildChoice>("integrate");
  const capability = CAPABILITY_QUESTIONS[capabilityIndex];
  const choice = BUILD_CHOICES.find((candidate) => candidate.id === buildChoice) ?? BUILD_CHOICES[0];

  return (
    <section className="page-section" aria-labelledby="decisions-title">
      <SectionHeader
        section={sectionById("decisions")}
        summary="Ask whether a usable capability exists, whether it can be extended, and only then select integration, acquisition, or a deliberately narrow build."
      />

      <div className="decision-layout">
        <article className="decision-tree-card">
          <div className="block-heading">
            <div><p className="eyebrow">Capability decision tree</p><h2>Start with evidence</h2></div>
            <span>{capabilityIndex + 1} / {CAPABILITY_QUESTIONS.length}</span>
          </div>
          <label className="capability-select">
            <span>Capability</span>
            <select value={capabilityIndex} onChange={(event) => setCapabilityIndex(Number(event.target.value))}>
              {CAPABILITY_QUESTIONS.map((item, index) => <option key={item.capability} value={index}>{item.capability}</option>)}
            </select>
          </label>
          <div className="tree-question">
            <span>01</span>
            <h3>Do we have usable {capability.capability.toLowerCase()}?</h3>
            <div className="binary-toggle" role="group" aria-label={`Availability of ${capability.capability}`}>
              <button type="button" onClick={() => setAnswer("yes")} aria-pressed={answer === "yes"}>Yes</button>
              <button type="button" onClick={() => setAnswer("no")} aria-pressed={answer === "no"}>No</button>
            </div>
          </div>
          <div className="tree-result">
            <span>{answer === "yes" ? "INTEGRATE" : "GAP PATH"}</span>
            <strong>{answer === "yes" ? capability.yes : capability.no}</strong>
            {answer === "no" ? <p>If extension is not supportable: <b>{capability.fallback}</b>.</p> : <p>Verify coverage, provenance, ownership, and operational support before relying on it.</p>}
          </div>
          <div className="stepper-buttons">
            <button type="button" className="secondary-button" disabled={capabilityIndex === 0} onClick={() => setCapabilityIndex((index) => Math.max(0, index - 1))}>Previous gap</button>
            <button type="button" className="secondary-button" disabled={capabilityIndex === CAPABILITY_QUESTIONS.length - 1} onClick={() => setCapabilityIndex((index) => Math.min(CAPABILITY_QUESTIONS.length - 1, index + 1))}>Next gap</button>
          </div>
        </article>

        <article className="build-buy-card">
          <p className="eyebrow">Build-vs-buy decision</p>
          <h2>Prefer commodity capability. Engineer the differentiating gap.</h2>
          <div className="choice-list">
            {BUILD_CHOICES.map((candidate) => (
              <button
                type="button"
                key={candidate.id}
                onClick={() => setBuildChoice(candidate.id)}
                aria-pressed={buildChoice === candidate.id}
              >
                <span>{candidate.id.toUpperCase()}</span>
                <strong>{candidate.title}</strong>
              </button>
            ))}
          </div>
          <div className="choice-detail">
            <span>Use when</span><p>{choice.useWhen}</p>
            <span>Guardrail</span><p>{choice.guardrail}</p>
          </div>
        </article>
      </div>
    </section>
  );
}

export function PatternsSection() {
  return (
    <section className="page-section" aria-labelledby="patterns-title">
      <SectionHeader
        section={sectionById("patterns")}
        summary="Migration patterns are selected by cryptographic use, protocol, implementation support, dependencies, and assurance needs—not by one universal algorithm prescription."
      />

      <div className="pattern-intro">
        <div><span>01</span><p>Discover the current dependency</p></div>
        <div><span>02</span><p>Determine supported target patterns</p></div>
        <div><span>03</span><p>Pilot interoperability + rollback</p></div>
        <div><span>04</span><p>Stage, rediscover, validate</p></div>
      </div>

      <div className="pattern-list">
        {MIGRATION_PATTERNS.map((pattern, index) => (
          <details key={pattern.id} open={index === 0}>
            <summary>
              <span>{String(index + 1).padStart(2, "0")}</span>
              <div><h2>{pattern.title}</h2><p>{pattern.scope}</p></div>
              <b aria-hidden="true">+</b>
            </summary>
            <div className="pattern-body">
              <ol>{pattern.steps.map((step) => <li key={step}>{step}</li>)}</ol>
              <div>
                <span>Validation focus</span><p>{pattern.validation}</p>
                <span>Evidence caveat</span><p>{pattern.caveat}</p>
              </div>
            </div>
          </details>
        ))}
      </div>

      <Callout label="Algorithm boundary" tone="warning">
        <p>ML-KEM, ML-DSA, and SLH-DSA are separate standardized primitives for different uses. A standard’s existence is not evidence that a given protocol, product, cryptographic module, or deployment supports it.</p>
      </Callout>
    </section>
  );
}
