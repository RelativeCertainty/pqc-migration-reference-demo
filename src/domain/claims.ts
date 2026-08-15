export const APPROVED_PQC_BASELINE =
  "PQC migration reference package. The source models migration evidence, synthetic inventory, and bounded posture reporting. It is not deployed and makes no claim about a public hostname, provider configuration, or negotiated post-quantum session.";

export const CURRENT_ELIGIBILITY_CAVEAT =
  "Only source and automated-test evidence is included. Runtime, deployment, identity, DNS, provider, customer, and measured outcome evidence are absent and must not be inferred.";

export const CLAIM_BOUNDARIES = Object.freeze({
  deployment: "source_only_not_deployed",
  hostnameCapability: "no_deployed_hostname_no_observation",
  exactSessionKeyExchange: "not_observable",
  visitorEdgePostQuantumSignatures: "not_deployed",
  cryptographicModuleEvidence: "not_validated",
  identityAndProviderEvidence: "not_asserted",
  productEvidenceTier: "Development evidence",
});

export const PROHIBITED_BLANKET_CLAIMS = [
  "PQC compliant",
  "quantum safe",
  "this session negotiated post-quantum cryptography",
  "FIPS validated runtime",
] as const;
