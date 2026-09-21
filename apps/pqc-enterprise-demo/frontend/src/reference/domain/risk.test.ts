import { calculateRisk, DEFAULT_RISK_INPUTS, priorityForScore } from "./risk";
import type { RiskInputs } from "./model";

function uniformInputs(driverValue: number, reductionValue: number): RiskInputs {
  return {
    algorithmRisk: driverValue,
    dataSensitivity: driverValue,
    retentionLifetime: driverValue,
    harvestNowRelevance: driverValue,
    publicExposure: driverValue,
    businessCriticality: driverValue,
    dependencyDepth: driverValue,
    migrationComplexity: driverValue,
    vendorDependency: driverValue,
    platformReadiness: reductionValue,
    cryptoAgility: reductionValue,
    compensatingControls: reductionValue,
  };
}

describe("illustrative risk scoring", () => {
  it("clamps scores to a 0–100 range", () => {
    expect(calculateRisk(uniformInputs(1, 5)).score).toBe(0);
    expect(calculateRisk(uniformInputs(5, 1)).score).toBe(100);
  });

  it("increases when a risk driver increases", () => {
    const baseline = calculateRisk(DEFAULT_RISK_INPUTS).score;
    const increased = calculateRisk({ ...DEFAULT_RISK_INPUTS, algorithmRisk: 5 }).score;
    expect(increased).toBeGreaterThan(baseline);
  });

  it("decreases when readiness and agility improve", () => {
    const baseline = calculateRisk(DEFAULT_RISK_INPUTS).score;
    const mitigated = calculateRisk({
      ...DEFAULT_RISK_INPUTS,
      platformReadiness: 5,
      cryptoAgility: 5,
      compensatingControls: 5,
    }).score;
    expect(mitigated).toBeLessThan(baseline);
  });

  it("uses stable priority thresholds", () => {
    expect(priorityForScore(75)).toBe("Urgent");
    expect(priorityForScore(74)).toBe("High");
    expect(priorityForScore(55)).toBe("High");
    expect(priorityForScore(35)).toBe("Moderate");
    expect(priorityForScore(34)).toBe("Low");
  });
});
