import { useEffect, useRef, useState } from 'react';
import { ArchitectureSection, OverviewSection, TvmMappingSection } from './reference/components/OverviewArchitecture';
import { InventorySection, PrioritizationSection } from './reference/components/InventoryRisk';
import { DecisionsSection, PatternsSection, ScenariosSection, WorkflowSection } from './reference/components/ProgramSections';
import { DashboardSection, PostureSection, QuestionsSection } from './reference/components/PostureDashboard';
import { INTERVIEW_SECTION_IDS, NAVIGATION_SECTIONS } from './reference/domain/data';
import type { SectionId } from './reference/domain/model';
import './reference/reference.css';

const sections = { overview: OverviewSection, architecture: ArchitectureSection, 'tvm-mapping': TvmMappingSection,
  inventory: InventorySection, prioritization: PrioritizationSection, workflow: WorkflowSection,
  scenarios: ScenariosSection, decisions: DecisionsSection, patterns: PatternsSection,
  posture: PostureSection, dashboard: DashboardSection, questions: QuestionsSection };

export function ReferenceWorkspace() {
  const content = useRef<HTMLDivElement>(null);
  const [section, setSection] = useState<SectionId>(() => {
    const selected = new URLSearchParams(window.location.hash.split('?')[1]).get('section') as SectionId;
    return Object.hasOwn(sections, selected) ? selected : 'overview';
  });
  const [guided, setGuided] = useState(false);
  const Component = sections[section];
  const position = Math.max(0, INTERVIEW_SECTION_IDS.indexOf(section));
  useEffect(() => {
    const heading = content.current?.querySelector('h1');
    if (heading) { heading.tabIndex = -1; heading.focus({preventScroll:true}); }
  }, [section]);
  return <section className="reference-content">
    <div className="notice">Reference explanations and illustrative models. These examples do not change assessment records, determine an enterprise risk score, or authorize migration. Use Assessment work for evidence-backed conclusions.</div>
    <nav className="reference-tabs" aria-label="Reference topics">{NAVIGATION_SECTIONS.map(item =>
      <button className="button secondary" key={item.id} aria-pressed={item.id === section} onClick={() => { setSection(item.id); setGuided(false); }}>{item.shortLabel}</button>)}</nav>
    <button className="button secondary" aria-pressed={guided} onClick={() => { setGuided(!guided); setSection(INTERVIEW_SECTION_IDS[0]); }}>{guided ? 'Exit guided explanation' : 'Guided explanation'}</button>
    <div className="reference-section" key={section} ref={content}><Component /></div>
    {guided && <div className="reference-tabs" aria-label="Guided explanation controls">
      <span>Step {position + 1} of {INTERVIEW_SECTION_IDS.length}</span>
      <button className="button secondary" disabled={position === 0} onClick={() => setSection(INTERVIEW_SECTION_IDS[position - 1])}>Previous explanation</button>
      <button className="button secondary" disabled={position === INTERVIEW_SECTION_IDS.length - 1} onClick={() => setSection(INTERVIEW_SECTION_IDS[position + 1])}>Next explanation</button>
    </div>}
  </section>;
}
