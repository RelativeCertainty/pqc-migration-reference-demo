// SPDX-License-Identifier: MIT

import type {
  CandidateObservation,
  EvidenceIssueType,
  InspectedFile,
  RulesetPort,
} from "./types.ts";

interface RuleSpecification {
  id: string;
  issueType: EvidenceIssueType;
  pattern: RegExp;
  fact: string;
  manifestsOnly?: boolean;
}

const dependencyManifests = new Set([
  "cargo.lock",
  "cargo.toml",
  "go.mod",
  "go.sum",
  "package-lock.json",
  "package.json",
  "pnpm-lock.yaml",
  "poetry.lock",
  "pyproject.toml",
  "requirements.txt",
  "yarn.lock",
]);

const specifications: RuleSpecification[] = [
  {
    id: "crypto-dependency",
    issueType: "cryptographic-dependency",
    pattern: /(?:node-forge|openssl|boringssl|libressl|libsodium|bouncycastle|cryptography|pycryptodome|ring|rustls)/iu,
    manifestsOnly: true,
    fact: "A dependency declaration matched a cryptographic-library indicator; confirm actual use, version, ownership, and migration relevance.",
  },
  {
    id: "rsa-indicator",
    issueType: "algorithm-key-strength",
    pattern: /\b(?:rsa|rsa-oaep|rsa-pss|pkcs1)\b/iu,
    fact: "A public-key algorithm indicator was detected; confirm the implementation, key use, data lifetime, and approved migration treatment.",
  },
  {
    id: "elliptic-curve-indicator",
    issueType: "algorithm-key-strength",
    pattern: /\b(?:ecdsa|ecdh|secp256r1|prime256v1|curve25519|ed25519)\b/iu,
    fact: "An elliptic-curve indicator was detected; confirm the implementation, protocol role, and approved migration treatment.",
  },
  {
    id: "pqc-indicator",
    issueType: "source-code-crypto-use",
    pattern: /\b(?:ml-kem|kyber|ml-dsa|dilithium|slh-dsa|sphincs\+?)\b/iu,
    fact: "A post-quantum algorithm indicator was detected; confirm implementation maturity, parameter profile, interoperability, and evidence.",
  },
  {
    id: "tls-indicator",
    issueType: "tls-protocol",
    pattern: /\b(?:tlsv?1(?:\.[0-3])?|sslcontext|tls_config|cipher_suites?)\b/iu,
    fact: "A TLS configuration or API indicator was detected; confirm negotiated behavior, endpoint ownership, dependencies, and fallback requirements.",
  },
  {
    id: "ssh-indicator",
    issueType: "implementation-configuration",
    pattern: /\b(?:kexalgorithms|hostkeyalgorithms|publickeyacceptedalgorithms|ssh-keyscan|ssh_config)\b/iu,
    fact: "An SSH cryptographic-configuration indicator was detected; confirm client/server support, administrative dependencies, and fallback requirements.",
  },
  {
    id: "certificate-indicator",
    issueType: "certificate-trust",
    pattern: /\b(?:x509|certificateauthority|certificates?|truststore|keystore)\b/iu,
    fact: "A certificate or trust-store indicator was detected; confirm certificate-chain ownership, algorithms, validity, and renewal dependencies.",
  },
  {
    id: "key-management-indicator",
    issueType: "implementation-configuration",
    pattern: /\b(?:kms|hsm|keyvault|key-management|pkcs11)\b/iu,
    fact: "A key-management API or service indicator was detected; confirm provider authority, key metadata, supported algorithms, and operational ownership.",
  },
];

function lineAt(content: string, index: number): number {
  let line = 1;
  for (let cursor = 0; cursor < index; cursor += 1) {
    if (content.charCodeAt(cursor) === 10) line += 1;
  }
  return line;
}

export class DefaultRuleset implements RulesetPort {
  readonly version = "0.1.0";

  evaluate(file: InspectedFile): CandidateObservation[] {
    const basename = file.relativePath.split("/").at(-1)?.toLowerCase() ?? "";
    const candidates: CandidateObservation[] = [];
    for (const specification of specifications) {
      if (specification.manifestsOnly && !dependencyManifests.has(basename)) continue;
      const match = specification.pattern.exec(file.content);
      if (!match || match.index === undefined) continue;
      candidates.push({
        ruleId: specification.id,
        issueType: specification.issueType,
        relativePath: file.relativePath,
        line: lineAt(file.content, match.index),
        fact: specification.fact,
      });
    }
    return candidates;
  }
}
