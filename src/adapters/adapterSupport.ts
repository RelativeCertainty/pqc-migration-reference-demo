import type { EvidenceImportContext } from "../ports/evidenceIngestion";

const SAFE_TIMESTAMP = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?Z$/u;

export class EvidenceAdapterError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "EvidenceAdapterError";
  }
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function asRecord(value: unknown, message: string): Record<string, unknown> {
  if (!isRecord(value)) throw new EvidenceAdapterError(message);
  return value;
}

export function asArray(value: unknown): readonly unknown[] {
  return Array.isArray(value) ? value : [];
}

export function boundedText(value: unknown, fallback: string, maxLength: number): string {
  if (typeof value !== "string") return fallback;
  const normalized = value.replaceAll(/[\r\n\t]+/gu, " ").replaceAll(/\s+/gu, " ").trim();
  return normalized ? normalized.slice(0, maxLength) : fallback;
}

export function canonicalAssetKey(value: string): string {
  const normalized = value.trim().toLowerCase().replaceAll(/[^a-z0-9._:-]+/gu, "-").replaceAll(/^-+|-+$/gu, "");
  if (normalized.length < 3 || normalized.length > 127) {
    throw new EvidenceAdapterError("Asset correlation key must normalize to 3–127 safe characters.");
  }
  return normalized;
}

function fnv1a64(value: string): string {
  let hash = 0xcbf29ce484222325n;
  for (const character of value) {
    hash ^= BigInt(character.codePointAt(0) ?? 0);
    hash = BigInt.asUintN(64, hash * 0x100000001b3n);
  }
  return hash.toString(16).padStart(16, "0");
}

export function stableSafeId(prefix: string, source: string): string {
  const safePrefix = prefix.toLowerCase().replaceAll(/[^a-z0-9._:-]+/gu, "-").slice(0, 80);
  return `${safePrefix}:${fnv1a64(source)}`;
}

export function validTimestamp(value: unknown): string | null {
  if (typeof value !== "string" || !SAFE_TIMESTAMP.test(value) || value.length > 30) return null;
  const parsed = new Date(value);
  return Number.isNaN(parsed.valueOf()) ? null : value;
}

export function assertImportContext(context: EvidenceImportContext): EvidenceImportContext {
  canonicalAssetKey(context.assetKey);
  if (!["source-code", "ots-cots", "third-party-saas"].includes(context.estateClass)) {
    throw new EvidenceAdapterError("Evidence import requires a supported software-estate class.");
  }
  if (!context.assetName.trim() || context.assetName.length > 160) {
    throw new EvidenceAdapterError("Asset name must contain 1–160 characters.");
  }
  if (!context.sourceName.trim() || context.sourceName.length > 160) {
    throw new EvidenceAdapterError("Source name must contain 1–160 characters.");
  }
  if (context.collectedAt !== null && validTimestamp(context.collectedAt) === null) {
    throw new EvidenceAdapterError("Collection time must be a canonical UTC timestamp or null.");
  }
  return context;
}
