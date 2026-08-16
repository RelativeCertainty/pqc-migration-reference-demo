import type { CryptoIssueType } from "../domain/model";
import type { EvidenceObservationV1 } from "../domain/evidenceFusion";
import type {
  AdapterDiagnostic,
  EvidenceBatchAdapter,
  EvidenceImportContext,
  EvidenceImportRunV1,
} from "../ports/evidenceIngestion";
import {
  asRecord,
  assertImportContext,
  boundedText,
  canonicalAssetKey,
  EvidenceAdapterError,
  isRecord,
  stableSafeId,
} from "./adapterSupport";

const MAX_CERTIFICATES = 30;
const CERTIFICATE_IDENTITY_KEYS = [
  "id",
  "certificateId",
  "certificateID",
  "thumbprint",
  "subject",
  "subjectDN",
  "commonName",
  "certificateName",
  "name",
] as const;

function certificateRows(root: Record<string, unknown>): readonly unknown[] {
  for (const key of ["certificates", "certificateDetails", "items", "results"]) {
    if (Array.isArray(root[key])) return root[key] as readonly unknown[];
  }
  throw new EvidenceAdapterError("Venafi import must contain a certificates, certificateDetails, items, or results array.");
}

function firstText(record: Record<string, unknown>, keys: readonly string[], fallback: string): string {
  for (const key of keys) {
    const value = record[key];
    if (typeof value === "string" && value.trim()) return boundedText(value, fallback, 180);
  }
  return fallback;
}

function firstNumber(record: Record<string, unknown>, keys: readonly string[]): number | null {
  for (const key of keys) {
    const value = record[key];
    if (typeof value === "number" && Number.isSafeInteger(value) && value >= 0) return value;
  }
  return null;
}

function hasCertificateIdentity(record: Record<string, unknown>): boolean {
  return CERTIFICATE_IDENTITY_KEYS.some((key) => typeof record[key] === "string" && record[key].trim().length > 0);
}

function algorithmFamily(value: string): "RSA" | "ELLIPTIC_CURVE" | "DSA" | "ML_DSA" | "SLH_DSA" | "UNSPECIFIED" {
  const normalized = value.toUpperCase();
  if (/\bML[-_ ]?DSA\b/u.test(normalized)) return "ML_DSA";
  if (/\bSLH[-_ ]?DSA\b/u.test(normalized)) return "SLH_DSA";
  if (/\b(?:ECDSA|ECDH|EC|ED25519|ED448|ELLIPTIC)\b/u.test(normalized)) return "ELLIPTIC_CURVE";
  if (/\bRSA\b/u.test(normalized)) return "RSA";
  if (/\bDSA\b/u.test(normalized)) return "DSA";
  return "UNSPECIFIED";
}

function observationsForCertificate(
  certificate: Record<string, unknown>,
  context: EvidenceImportContext,
  ordinal: number,
): EvidenceObservationV1[] {
  const keyAlgorithm = firstText(certificate, ["keyAlgorithm", "publicKeyAlgorithm", "encryptionType"], "");
  const keySize = firstNumber(certificate, ["keySize", "keyLength"]);
  const signatureAlgorithm = firstText(certificate, ["signatureAlgorithm", "signatureHashAlgorithm"], "");
  const instanceCount = firstNumber(certificate, ["instanceCount", "certificateInstanceCount", "installations"]);
  const managed = typeof certificate.managed === "boolean" ? certificate.managed : null;
  const synthetic = context.synthetic;
  const candidateKey = canonicalAssetKey(context.assetKey);
  const sourceIdentity = `${candidateKey}\u0000${ordinal}`;

  const base = (issueType: CryptoIssueType, suffix: string, fact: string): EvidenceObservationV1 => ({
    schemaVersion: "pqc.evidence-observation.v1",
    observationId: stableSafeId(`obs:pki:venafi:${suffix}`, sourceIdentity),
    feedId: "pki-inventory",
    adapter: { name: "venafi-certificate-search-adapter", version: "1.0.0" },
    source: {
      recordRef: stableSafeId(`venafi-cert:${suffix}`, sourceIdentity),
      collectedAt: synthetic ? null : context.collectedAt,
    },
    subject: {
      candidateKey,
      assetHint: synthetic ? boundedText(context.assetName, "Synthetic relying party", 160) : null,
      estateClass: context.estateClass,
    },
    classification: { issueType },
    finding: { fact: boundedText(fact, "Venafi certificate inventory finding.", 500) },
    provenance: {
      assessment: synthetic ? "assumption" : "unresolved",
      confidence: synthetic ? "illustrative" : "low",
      sourceLocator: `local-import:venafi-certificate-search:${stableSafeId("certificate", sourceIdentity)}`,
    },
    safety: { synthetic, containsSecret: false, rawPayloadRetained: false },
  });

  const keyDescription = `${algorithmFamily(keyAlgorithm)}${keySize === null ? "" : ` ${keySize}-bit`}`;
  const signatureDescription = algorithmFamily(signatureAlgorithm);
  const dependencyDescription = instanceCount === null ? "instance count unavailable" : `${instanceCount} observed certificate instance${instanceCount === 1 ? "" : "s"}`;
  return [
    base("certificate-trust", "trust", "Certificate inventory contains a trust relationship that requires migration review; native certificate identifiers, subjects, and issuers were withheld from export."),
    base("algorithm-key-strength", "algorithm", `Certificate inventory reports ${keyDescription} public-key material with ${signatureDescription} signature family; native algorithm strings and certificate identifiers were withheld from export.`),
    base("cryptographic-dependency", "dependency", `Certificate inventory reports ${dependencyDescription}; managed state is ${managed === null ? "not supplied" : managed ? "managed" : "unmanaged"}. Native relying-party and certificate identifiers were withheld from export.`),
  ];
}

export const VenafiCertificateSearchAdapter: EvidenceBatchAdapter = {
  id: "venafi-certificate-search",
  name: "venafi-certificate-search-adapter",
  version: "1.0.0",
  feedId: "pki-inventory",
  adapt(payload: unknown, context: EvidenceImportContext): EvidenceImportRunV1 {
    assertImportContext(context);
    const root = asRecord(payload, "Venafi certificate-search import must be a JSON object.");
    const rows = certificateRows(root);
    if (rows.length > MAX_CERTIFICATES) {
      throw new EvidenceAdapterError(`Venafi import exceeds the ${MAX_CERTIFICATES}-certificate safety limit.`);
    }

    const diagnostics: AdapterDiagnostic[] = [];
    const observations: EvidenceObservationV1[] = [];
    let skippedCount = 0;
    for (const [index, nativeCertificate] of rows.entries()) {
      if (!isRecord(nativeCertificate)) {
        skippedCount += 1;
        diagnostics.push({ level: "warning", code: "invalid-certificate", message: "A non-object certificate record was skipped.", sourceRef: null });
        continue;
      }
      if (!hasCertificateIdentity(nativeCertificate)) {
        skippedCount += 1;
        diagnostics.push({ level: "warning", code: "invalid-certificate", message: "A certificate record without a recognized identity field was skipped.", sourceRef: null });
        continue;
      }
      observations.push(...observationsForCertificate(nativeCertificate, context, index + 1));
    }
    if (rows.length === 0) {
      diagnostics.push({ level: "information", code: "empty-inventory", message: "The Venafi search result contains no certificate records.", sourceRef: null });
    }

    return {
      schemaVersion: "pqc.evidence-import-run.v1",
      adapterId: "venafi-certificate-search",
      adapterName: "venafi-certificate-search-adapter",
      adapterVersion: "1.0.0",
      feedId: "pki-inventory",
      sourceName: context.synthetic ? "synthetic-venafi-certificate-search" : "local-venafi-certificate-search",
      acceptedCount: observations.length,
      skippedCount,
      observations,
      diagnostics,
      safety: { synthetic: context.synthetic, containsSecret: false, rawPayloadRetained: false },
    };
  },
};
