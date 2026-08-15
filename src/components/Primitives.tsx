import type { ReactNode } from "react";

import type { EvidenceState, InventoryPriority, NavigationSection } from "../domain/model";

export function SectionHeader({
  section,
  summary,
  aside,
}: {
  section: NavigationSection;
  summary: string;
  aside?: ReactNode;
}) {
  return (
    <header className="section-header">
      <div>
        <p className="eyebrow">{section.eyebrow}</p>
        <h1 id={`${section.id}-title`} tabIndex={-1}>{section.title}</h1>
        <p className="section-summary">{summary}</p>
      </div>
      {aside ? <div className="section-aside">{aside}</div> : null}
    </header>
  );
}

export function StatusPill({ state }: { state: EvidenceState }) {
  return (
    <span className="status-pill" data-state={state.toLowerCase().replaceAll(" ", "-")}>
      <span aria-hidden="true" className="status-dot" />
      {state}
    </span>
  );
}

export function PriorityPill({ priority }: { priority: InventoryPriority }) {
  return (
    <span className="priority-pill" data-priority={priority.toLowerCase()}>
      {priority}
    </span>
  );
}

export function FlowTrack({ items, compact = false }: { items: readonly string[]; compact?: boolean }) {
  return (
    <ol className={compact ? "flow-track flow-track--compact" : "flow-track"}>
      {items.map((item, index) => (
        <li key={item}>
          <span className="flow-number">{String(index + 1).padStart(2, "0")}</span>
          <span>{item}</span>
        </li>
      ))}
    </ol>
  );
}

export function MetricCard({
  label,
  value,
  detail,
  accent = "aqua",
}: {
  label: string;
  value: string | number;
  detail: string;
  accent?: "aqua" | "amber" | "violet" | "red";
}) {
  return (
    <article className="metric-card" data-accent={accent}>
      <p>{label}</p>
      <strong>{value}</strong>
      <span>{detail}</span>
    </article>
  );
}

export function Callout({
  label,
  children,
  tone = "info",
}: {
  label: string;
  children: ReactNode;
  tone?: "info" | "warning" | "success";
}) {
  return (
    <aside className="callout" data-tone={tone}>
      <span>{label}</span>
      <div>{children}</div>
    </aside>
  );
}

export function EmptyState({ children }: { children: ReactNode }) {
  return (
    <div className="empty-state" role="status">
      <span aria-hidden="true">∅</span>
      <p>{children}</p>
    </div>
  );
}
