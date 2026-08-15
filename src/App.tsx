import { useEffect, useMemo, useState } from "react";

import {
  ArchitectureSection,
  OverviewSection,
  TvmMappingSection,
} from "./components/OverviewArchitecture";
import { InventorySection, PrioritizationSection } from "./components/InventoryRisk";
import {
  DecisionsSection,
  PatternsSection,
  ScenariosSection,
  WorkflowSection,
} from "./components/ProgramSections";
import {
  DashboardSection,
  PostureSection,
  QuestionsSection,
} from "./components/PostureDashboard";
import { INTERVIEW_SECTION_IDS, NAVIGATION_SECTIONS } from "./domain/data";
import type { SectionId } from "./domain/model";
import { useHashRoute } from "./hooks/useHashRoute";

const SECTION_COMPONENTS: Record<SectionId, () => React.JSX.Element> = {
  overview: OverviewSection,
  architecture: ArchitectureSection,
  "tvm-mapping": TvmMappingSection,
  inventory: InventorySection,
  prioritization: PrioritizationSection,
  workflow: WorkflowSection,
  scenarios: ScenariosSection,
  decisions: DecisionsSection,
  patterns: PatternsSection,
  posture: PostureSection,
  dashboard: DashboardSection,
  questions: QuestionsSection,
};

export default function App() {
  const { section, navigate } = useHashRoute();
  const [interviewMode, setInterviewMode] = useState(false);
  const CurrentSection = SECTION_COMPONENTS[section];
  const currentMeta = NAVIGATION_SECTIONS.find((candidate) => candidate.id === section) ?? NAVIGATION_SECTIONS[0];
  const interviewIndex = INTERVIEW_SECTION_IDS.indexOf(section);
  const effectiveInterviewIndex = interviewIndex >= 0 ? interviewIndex : 0;
  const interviewProgress = `${effectiveInterviewIndex + 1} / ${INTERVIEW_SECTION_IDS.length}`;

  const sectionOrdinal = useMemo(
    () => String(NAVIGATION_SECTIONS.findIndex((candidate) => candidate.id === section) + 1).padStart(2, "0"),
    [section],
  );

  useEffect(() => {
    const heading = document.getElementById(`${section}-title`);
    heading?.focus({ preventScroll: true });
  }, [section]);

  const navigateWithMode = (nextSection: SectionId) => {
    if (interviewMode && !INTERVIEW_SECTION_IDS.includes(nextSection)) {
      setInterviewMode(false);
    }
    navigate(nextSection);
  };

  const toggleInterviewMode = () => {
    const next = !interviewMode;
    setInterviewMode(next);
    if (next) navigate(INTERVIEW_SECTION_IDS[0]);
  };

  const moveInterview = (direction: -1 | 1) => {
    const nextIndex = Math.min(
      INTERVIEW_SECTION_IDS.length - 1,
      Math.max(0, effectiveInterviewIndex + direction),
    );
    navigate(INTERVIEW_SECTION_IDS[nextIndex]);
  };

  const skipToMain = (event: React.MouseEvent<HTMLAnchorElement>) => {
    event.preventDefault();
    document.getElementById("main-content")?.focus({ preventScroll: false });
    document.getElementById("main-content")?.scrollIntoView({ block: "start" });
  };

  return (
    <div className={interviewMode ? "app-shell is-interviewing" : "app-shell"}>
      <a className="skip-link" href="#main-content" onClick={skipToMain}>Skip to main content</a>
      <aside className="side-rail">
          <a className="brand-mark" href="#overview" onClick={(event) => { event.preventDefault(); navigateWithMode("overview"); }}>
          <span>PQ</span>
          <div><strong>MIGRATION</strong><small>REFERENCE LAB</small></div>
        </a>

        <nav aria-label="Reference architecture sections">
          <ol>
            {NAVIGATION_SECTIONS.map((item, index) => (
              <li key={item.id}>
                <a
                  href={`#${item.id}`}
                  aria-current={section === item.id ? "page" : undefined}
                  onClick={(event) => {
                    event.preventDefault();
                    navigateWithMode(item.id);
                  }}
                >
                  <span>{String(index + 1).padStart(2, "0")}</span>
                  <strong>{item.shortLabel}</strong>
                  {item.interviewStep ? <small>step {item.interviewStep}</small> : null}
                </a>
              </li>
            ))}
          </ol>
        </nav>

        <div className="rail-footer">
          <span className="rail-status"><i aria-hidden="true" />EVIDENCE BOUNDED · OWNER REVIEW DUE</span>
          <small>Synthetic data · no write path</small>
        </div>
      </aside>

      <div className="content-shell">
        <header className="top-bar">
          <div className="breadcrumb" aria-label="Current location">
            <span>{sectionOrdinal}</span>
            <i aria-hidden="true">/</i>
            <strong>{currentMeta.shortLabel}</strong>
          </div>
          <div className="top-actions">
            <span className="evidence-mode"><i aria-hidden="true" />BOUNDED EVIDENCE</span>
            <button
              type="button"
              className="interview-toggle"
              aria-pressed={interviewMode}
              onClick={toggleInterviewMode}
            >
              <span aria-hidden="true">▶</span>
              {interviewMode ? "Exit interview mode" : "Interview mode"}
            </button>
          </div>
        </header>

        <main id="main-content" tabIndex={-1}>
          <CurrentSection />
        </main>

        <footer className="site-footer">
          <span>Enterprise PQC Migration Reference Architecture</span>
          <span>Illustrative · synthetic · environment-dependent</span>
        </footer>
      </div>

      {interviewMode ? (
        <div className="interview-controls" role="region" aria-label="Interview mode controls">
          <div>
            <span>GUIDED WALKTHROUGH</span>
            <strong>Step {interviewProgress} · {currentMeta.shortLabel}</strong>
          </div>
          <progress
            value={effectiveInterviewIndex + 1}
            max={INTERVIEW_SECTION_IDS.length}
            aria-label={`Interview mode progress: ${interviewProgress}`}
          >{interviewProgress}</progress>
          <div className="interview-buttons">
            <button type="button" onClick={() => moveInterview(-1)} disabled={effectiveInterviewIndex === 0}>← Previous</button>
            <button type="button" onClick={() => moveInterview(1)} disabled={effectiveInterviewIndex === INTERVIEW_SECTION_IDS.length - 1}>Next →</button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
