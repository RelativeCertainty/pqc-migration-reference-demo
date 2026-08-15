import type { InventoryPriority, RiskContribution, RiskInputs, RiskResult } from "./model";

const DRIVER_WEIGHTS: ReadonlyArray<{
  key: keyof RiskInputs;
  label: string;
  weight: number;
}> = [
  { key: "algorithmRisk", label: "Algorithm exposure", weight: 20 },
  { key: "dataSensitivity", label: "Data sensitivity", weight: 15 },
  { key: "retentionLifetime", label: "Retention lifetime", weight: 12 },
  { key: "harvestNowRelevance", label: "Harvest-now relevance", weight: 12 },
  { key: "publicExposure", label: "External exposure", weight: 12 },
  { key: "businessCriticality", label: "Business criticality", weight: 14 },
  { key: "dependencyDepth", label: "Dependency depth", weight: 7 },
  { key: "migrationComplexity", label: "Migration complexity", weight: 4 },
  { key: "vendorDependency", label: "Vendor dependency", weight: 4 },
] as const;

const REDUCTION_WEIGHTS: ReadonlyArray<{
  key: keyof RiskInputs;
  label: string;
  weight: number;
}> = [
  { key: "platformReadiness", label: "Platform readiness", weight: 7 },
  { key: "cryptoAgility", label: "Crypto agility", weight: 7 },
  { key: "compensatingControls", label: "Compensating controls", weight: 6 },
] as const;

export const DEFAULT_RISK_INPUTS: RiskInputs = Object.freeze({
  algorithmRisk: 4,
  dataSensitivity: 4,
  retentionLifetime: 4,
  harvestNowRelevance: 4,
  publicExposure: 4,
  businessCriticality: 5,
  dependencyDepth: 3,
  migrationComplexity: 3,
  vendorDependency: 2,
  platformReadiness: 2,
  cryptoAgility: 2,
  compensatingControls: 2,
});

function normalizedRating(value: number): number {
  const bounded = Math.min(5, Math.max(1, value));
  return (bounded - 1) / 4;
}

export function priorityForScore(score: number): InventoryPriority {
  if (score >= 75) return "Urgent";
  if (score >= 55) return "High";
  if (score >= 35) return "Moderate";
  return "Low";
}

export function calculateRisk(inputs: RiskInputs): RiskResult {
  const drivers: RiskContribution[] = DRIVER_WEIGHTS.map(({ key, label, weight }) => ({
    key,
    label,
    points: normalizedRating(inputs[key]) * weight,
    kind: "driver",
  }));
  const reductions: RiskContribution[] = REDUCTION_WEIGHTS.map(({ key, label, weight }) => ({
    key,
    label,
    points: normalizedRating(inputs[key]) * -weight,
    kind: "reduction",
  }));
  const rawScore = [...drivers, ...reductions].reduce((sum, item) => sum + item.points, 0);
  const score = Math.round(Math.min(100, Math.max(0, rawScore)));
  const primaryDrivers = [...drivers].sort((a, b) => b.points - a.points).slice(0, 3);

  return {
    score,
    priority: priorityForScore(score),
    contributions: [...drivers, ...reductions],
    primaryDrivers,
  };
}

export const RISK_INPUT_LABELS: Record<keyof RiskInputs, string> = {
  algorithmRisk: "Algorithm risk",
  dataSensitivity: "Data sensitivity",
  retentionLifetime: "Retention lifetime",
  harvestNowRelevance: "Harvest-now relevance",
  publicExposure: "Public exposure",
  businessCriticality: "Business criticality",
  dependencyDepth: "Dependency depth",
  migrationComplexity: "Migration complexity",
  vendorDependency: "Vendor dependency",
  platformReadiness: "Platform readiness",
  cryptoAgility: "Crypto agility",
  compensatingControls: "Compensating controls",
};
