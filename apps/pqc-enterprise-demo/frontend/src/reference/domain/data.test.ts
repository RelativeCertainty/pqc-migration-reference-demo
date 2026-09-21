import appSource from "../../App.tsx?raw";
import inventoryRiskSource from "../components/InventoryRisk.tsx?raw";
import overviewSource from "../components/OverviewArchitecture.tsx?raw";
import postureSource from "../components/PostureDashboard.tsx?raw";
import programSource from "../components/ProgramSections.tsx?raw";
import claimsSource from "./claims.ts?raw";
import dataSource from "./data.ts?raw";
import {
  CSF_2_CONCURRENT_OVERLAY,
  CRYPTO_SYSTEMS,
  INTERVIEW_SECTION_IDS,
  NAVIGATION_SECTIONS,
  NIST_ALIGNED_LIFECYCLE,
  QUESTION_GROUPS,
} from "./data";
import { SYNTHETIC_EVIDENCE_ARTIFACT } from "./syntheticEvidence.v1";

describe("reference demo data contracts", () => {
  it("defines exactly 12 unique navigable sections and a 10-step interview path", () => {
    expect(NAVIGATION_SECTIONS).toHaveLength(12);
    expect(new Set(NAVIGATION_SECTIONS.map((section) => section.id)).size).toBe(12);
    expect(INTERVIEW_SECTION_IDS).toHaveLength(10);
    expect(INTERVIEW_SECTION_IDS[0]).toBe("overview");
    expect(INTERVIEW_SECTION_IDS.at(-1)).toBe("questions");
  });

  it("uses the approved six-stage NIST-aligned label set", () => {
    expect(NIST_ALIGNED_LIFECYCLE.map((stage) => stage.stage)).toEqual([
      "Awareness & Preparation",
      "Discovery & Inventory",
      "Risk Assessment & Planning",
      "Migration Execution",
      "Migration Testing",
      "Validation & Monitoring",
    ]);
  });

  it("keeps the CSF 2.0 overlay concurrent and explicitly demo-defined", () => {
    expect(CSF_2_CONCURRENT_OVERLAY.map((item) => item.function)).toEqual([
      "GOVERN",
      "IDENTIFY",
      "PROTECT",
      "DETECT",
      "RESPOND",
      "RECOVER",
    ]);
    expect(CSF_2_CONCURRENT_OVERLAY[0].stageEmphasis).toBe("Stages 1–6");
    expect(overviewSource).toContain("CSF 2.0 Functions are concurrent");
    expect(overviewSource).toContain("not an official NIST crosswalk");
  });

  it("keeps required discovery categories and explicit infrastructure sources", () => {
    expect(overviewSource).toContain('label: "Cloud platforms"');
    for (const sourceLabel of ["AWS", "Azure", "GCP", "Cloud resource inventory", "Certificate discovery", "Load balancers"]) {
      expect(overviewSource).toContain(sourceLabel);
    }
  });

  it("keeps the synthetic work-item handoff contract complete", () => {
    for (const field of [
      "Application",
      "Asset / CI",
      "Owner",
      "Dependency",
      "Current algorithm",
      "Affected protocol",
      "Exposure",
      "Business criticality",
      "Priority",
      "Target date",
      "Recommended pattern",
      "Target state",
      "Validation",
      "Exception path",
    ]) {
      expect(programSource).toContain(field);
    }
  });

  it("keeps the full capability-gap question set", () => {
    for (const capability of ["Cloud inventory", "Application inventory", "Dependency mapping"]) {
      expect(dataSource).toContain(`capability: "${capability}"`);
    }
  });

  it("keeps vendor discovery questions explicit", () => {
    const vendors = QUESTION_GROUPS.find((group) => group.category === "Vendors");
    expect(vendors?.questions.join(" ")).toContain("installed versions");
    expect(vendors?.questions.join(" ")).toContain("evidence-backed roadmaps");
    expect(vendors?.questions.join(" ")).toContain("end-of-support dates");
  });

  it("keeps progressive inventory evidence fields visible", () => {
    for (const field of [
      "Credential or key role — no key material",
      "Declared issuer or manager",
      "Declared library or runtime",
      "Illustrative data sensitivity",
      "Protected-data retention horizon",
      "Synthetic seed assertions",
      "Derived fusion result",
      "Seed evidence envelope",
      "Known proof gaps",
      "Seed-record provenance",
      "Seed-record confidence",
      "Seed-record observation type",
      "Seed-record observation time",
      "Seed-record evidence assessment",
      "Evidence-review owner",
      "Evidence-review date",
      "Artifact test status",
      "Test source locator",
    ]) {
      expect(inventoryRiskSource).toContain(field);
    }
  });

  it("binds a versioned synthetic evidence artifact to lifecycle stage 2", () => {
    expect(SYNTHETIC_EVIDENCE_ARTIFACT).toMatchObject({
      schemaVersion: "pqc.synthetic-evidence.v1",
      artifactVersion: "1.0.0",
      synthetic: true,
      stage: {
        ref: "pqc-lifecycle-stage:2",
        ordinal: 2,
        label: "Discovery & Inventory",
      },
    });
    expect(SYNTHETIC_EVIDENCE_ARTIFACT.records).toHaveLength(10);
    expect(SYNTHETIC_EVIDENCE_ARTIFACT.records.map((record) => record.systemId)).toEqual(
      CRYPTO_SYSTEMS.map((system) => system.id),
    );

    for (const record of SYNTHETIC_EVIDENCE_ARTIFACT.records) {
      expect(record.provenance).toMatchObject({ kind: "synthetic_fixture", synthetic: true });
      expect(record.confidence.level).toBe("illustrative");
      expect(record.observation).toMatchObject({
        kind: "synthetic_fixture_declaration",
        observedAt: null,
        runtimeObserved: false,
      });
      expect(record.evidence.state).toBe("assumption");
      expect(record.evidence.owner).toBeTruthy();
      expect(record.evidence.reviewDate).toMatch(/^\d{4}-\d{2}-\d{2}$/);
      expect(record.test).toMatchObject({
        result: "not_executed_in_artifact",
        locator: "src/domain/data.test.ts",
      });
      expect(record.residualGaps.length).toBeGreaterThan(0);
    }
  });

  it("contains exactly 10 uniquely identified synthetic systems", () => {
    expect(CRYPTO_SYSTEMS).toHaveLength(10);
    expect(CRYPTO_SYSTEMS.every((system) => system.synthetic === true)).toBe(true);
    expect(CRYPTO_SYSTEMS.every((system) => system.evidence.systemId === system.id)).toBe(true);
    expect(new Set(CRYPTO_SYSTEMS.map((system) => system.id)).size).toBe(10);
  });

  it("keeps real-organization sentinel tokens out of rendered and data sources", () => {
    const searchableSource = [
      appSource,
      inventoryRiskSource,
      overviewSource,
      postureSource,
      programSource,
      claimsSource,
      dataSource,
      JSON.stringify(CRYPTO_SYSTEMS),
    ].join("\n");

    for (const prohibitedName of ["REAL_CUSTOMER_NAME", "EMPLOYER_NAME", "CLIENT_NAME"]) {
      expect(searchableSource).not.toContain(prohibitedName);
    }
  });
});
