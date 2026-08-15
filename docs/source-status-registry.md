# NIST source-status registry

Registry date: 2026-08-13

All sources were checked and accessed on 2026-08-13. Only official NIST web properties are included.

## Status semantics

- `Final standard`: a final Federal Information Processing Standard. Its scope is the algorithm or requirement stated in the publication, not an implementation, module, protocol, product, or deployment.
- `Final guidance`: a final NIST Special Publication or Cybersecurity White Paper. It remains bounded by its stated purpose.
- `Initial Public Draft`: nonfinal material expected to change after review. A closed comment period does not make it final.
- `Initial Preliminary Draft`: early, nonfinal project material. It is lower-authority than a Final publication and may reflect superseded technical inputs.
- `Living supplementary material`: an official NIST web resource that is periodically updated and is not a numbered final standard.
- `Active project page`: current project direction and status, not a normative publication.
- `Program page/database`: authoritative for program scope and current certificate records; individual entries must be checked when a validation claim is made.

`Status checked` records when the label was verified, not when the source was published. A source must not be silently promoted from draft to final.

## Registry entries

### SRC-NIST-001 — NCCoE PQC FAQ

- Title: Frequently Asked Questions about Post-Quantum Cryptography.
- URL: https://pages.nist.gov/nccoe-migration-post-quantum-cryptography/FAQ/
- Publisher: NIST National Cybersecurity Center of Excellence.
- Source date: last updated 2026-06-30.
- Status on 2026-08-13: `Living supplementary material`; explicitly non-exhaustive and periodically updated.
- Accessed: 2026-08-13.
- Supports: the six phase headings; current project terminology; inventory definition and representative inventory contents; current finalized PQC FIPS list; draft/final pointers; CAVP/CMVP overview.
- Does not support: treating the six headings as a mandatory NIST process, treating its third-party links as NIST endorsement, or claiming a final migration method.
- Revalidation trigger: page update, changed phase headings, changed standards list, or changed validation language.

### SRC-NIST-002 — NCCoE Migration to PQC project

- Title: Migration to Post-Quantum Cryptography.
- URL: https://www.nccoe.nist.gov/applied-cryptography/migration-to-pqc
- Publisher: NIST National Cybersecurity Center of Excellence.
- Source date: living project page; no single publication date displayed.
- Status on 2026-08-13: `Active project page`; project status shown as `Reviewing Comments`.
- Accessed: 2026-08-13.
- Supports: the need to understand quantum-vulnerable cryptography and develop prioritized roadmaps; cryptographic discovery/inventory and interoperability workstreams; controlled non-production interoperability testing; current handling of prior SP 1800-38 preliminary material.
- Does not support: final conformance criteria, production assurance, or claiming draft project outputs are final guidance.
- Revalidation trigger: project status change, new white paper/tech note/report, or replacement of preliminary SP 1800-38 content.

### SRC-NIST-003 — NIST CSF 2.0

- Title: The NIST Cybersecurity Framework (CSF) 2.0, CSWP 29.
- URL: https://csrc.nist.gov/pubs/cswp/29/the-nist-cybersecurity-framework-csf-20/final
- Publisher: National Institute of Standards and Technology.
- Publication date: 2024-02-26.
- Status on 2026-08-13: `Final guidance`.
- Accessed: 2026-08-13.
- Supports: a non-prescriptive taxonomy of high-level cybersecurity outcomes for managing and communicating cybersecurity risk.
- Does not support: claiming the demo's phase mapping is NIST-approved or that use of CSF labels establishes conformance.
- Revalidation trigger: revision, errata, or a new CSF version.

### SRC-NIST-004 — Crypto agility

- Title: Considerations for Achieving Crypto Agility: Strategies and Practices, CSWP 39upd1.
- URL: https://csrc.nist.gov/pubs/cswp/39/upd1/considerations-for-achieving-crypto-agility/final
- Publisher: National Institute of Standards and Technology.
- Publication record: published 2025-12-19 and includes updates as of 2026-06-29; document history identifies `06/29/26: CSWP 39upd1 (Final)`.
- Status on 2026-08-13: `Final guidance`; supersedes CSWP 39 dated 2025-12-19.
- Accessed: 2026-08-13.
- Supports: the NIST definition of crypto agility; discussion of approaches, tradeoffs, and operational mechanisms.
- Does not support: a demo-specific agility score, certification, or guarantee of disruption-free migration.
- Revalidation trigger: revision, errata, or superseding publication.

### SRC-NIST-005 — FIPS 203

- Title: Module-Lattice-Based Key-Encapsulation Mechanism Standard.
- URL: https://csrc.nist.gov/pubs/fips/203/final
- Publisher: National Institute of Standards and Technology.
- Publication date: 2024-08-13.
- Status on 2026-08-13: `Final standard`.
- Current notice: planning note dated 2025-11-17 says an identified issue will be corrected in a future update/revision and points to potential-update errata.
- Accessed: 2026-08-13.
- Supports: ML-KEM specification and its three parameter sets.
- Does not support: correctness or validation of a particular implementation, protocol, module, product, endpoint, or connection.
- Revalidation trigger: revised FIPS, updated planning note, or errata change.

### SRC-NIST-006 — FIPS 204

- Title: Module-Lattice-Based Digital Signature Standard.
- URL: https://csrc.nist.gov/pubs/fips/204/final
- Publisher: National Institute of Standards and Technology.
- Publication date: 2024-08-13.
- Status on 2026-08-13: `Final standard`.
- Current notice: planning note dated 2026-07-31 points to several minor issues in potential-update errata for a future update/revision.
- Accessed: 2026-08-13.
- Supports: the ML-DSA digital signature standard.
- Does not support: correctness or validation of a particular implementation, module, product, signing workflow, or deployment.
- Revalidation trigger: revised FIPS, updated planning note, or errata change.

### SRC-NIST-007 — FIPS 205

- Title: Stateless Hash-Based Digital Signature Standard.
- URL: https://csrc.nist.gov/pubs/fips/205/final
- Publisher: National Institute of Standards and Technology.
- Publication date: 2024-08-13.
- Status on 2026-08-13: `Final standard`.
- Current notice: no planning note was displayed on the publication record when checked.
- Accessed: 2026-08-13.
- Supports: the SLH-DSA digital signature standard.
- Does not support: correctness or validation of a particular implementation, module, product, signing workflow, or deployment.
- Revalidation trigger: planning note, errata, or revision.

### SRC-NIST-008 — SP 800-227

- Title: Recommendations for Key-Encapsulation Mechanisms.
- URL: https://csrc.nist.gov/pubs/sp/800/227/final
- Publisher: National Institute of Standards and Technology.
- Publication date: 2025-09-18, shown in document history; the page displays `September 2025`.
- Status on 2026-08-13: `Final guidance`.
- Accessed: 2026-08-13.
- Supports: KEM definitions, properties, applications, and recommendations for secure implementation and use.
- Does not support: protocol interoperability, deployment security, or validation of an implementation without matching evidence.
- Revalidation trigger: revision, errata, or superseding KEM guidance.

### SRC-NIST-009 — NIST IR 8547

- Title: Transition to Post-Quantum Cryptography Standards.
- URL: https://csrc.nist.gov/pubs/ir/8547/ipd
- Publisher: National Institute of Standards and Technology.
- Draft publication date: 2024-11-12.
- Status on 2026-08-13: `Initial Public Draft`; public comment period closed 2025-01-10. The page says comments will be used to revise the transition plan.
- Accessed: 2026-08-13.
- Supports: qualified descriptions of NIST's expected transition approach, draft migration considerations, and proposed transition plan.
- Does not support: final deadlines, settled requirements, or an unqualified statement of final NIST transition policy.
- Revalidation trigger: second draft, final publication, withdrawal, or updated planning note.

### SRC-NIST-010 — CSWP 48

- Title: Mappings of Migration to PQC Project Capabilities to NIST Cybersecurity Framework 2.0 and to Security and Privacy Controls for Information Systems and Organizations.
- URL: https://csrc.nist.gov/pubs/cswp/48/mapping-migration-to-pqc-project-capabilities-to-r/ipd
- Publisher: National Institute of Standards and Technology.
- Draft publication date: 2025-09-18.
- Status on 2026-08-13: `Initial Public Draft`; public comment period closed 2025-10-20. The related NCCoE project was `Reviewing Comments`.
- Accessed: 2026-08-13.
- Supports: qualified discussion of proposed mappings between NCCoE PQC capabilities, CSF 2.0, and SP 800-53.
- Does not support: a final official crosswalk, conformance claim, or claim that the demo's overlay was approved by NIST.
- Revalidation trigger: revised draft, final publication, withdrawal, or project status change.

### SRC-NIST-011 — SP 1800-38A/B/C preliminary material

- Title: Migration to Post-Quantum Cryptography: Preparation for Considering the Implementation and Adoption of Quantum Safe Cryptography.
- URL: https://csrc.nist.gov/pubs/sp/1800/38/iprd-%281%29
- Publisher: NIST National Cybersecurity Center of Excellence.
- Draft publication date: 2023-12-19.
- Status on 2026-08-13: `Initial Preliminary Draft`; comment period closed 2024-02-20.
- Accessed: 2026-08-13.
- Supports: historical exploration of discovery tools and controlled interoperability/performance testing.
- Does not support: final guidance, current final-standard conformance, or current implementation interoperability. The NCCoE FAQ says cited TLS results were produced before December 2023 using draft PQC KEM standards.
- Revalidation trigger: replacement or update through a white paper, tech note, informational report, or a later SP 1800-38 draft/final.

### SRC-NIST-012 — CAVP

- Title: Cryptographic Algorithm Validation Program.
- URL: https://csrc.nist.gov/Projects/cryptographic-algorithm-validation-program
- Publisher: National Institute of Standards and Technology.
- Page date: updated 2026-08-12.
- Status on 2026-08-13: `Program page/database`.
- Accessed: 2026-08-13.
- Supports: CAVP scope; ACVTS testing process; algorithm validation as a prerequisite for module validation; the scope fields in official algorithm validation entries.
- Does not support: treating Demo ACVTS or local tests as an official certificate; treating an algorithm certificate as FIPS 140 module or product validation.
- Revalidation trigger: any CAVP claim, program update, test-method update, or certificate-status change.

### SRC-NIST-013 — CMVP validated modules

- Title: Cryptographic Module Validation Program — Validated Modules.
- URL: https://csrc.nist.gov/Projects/cryptographic-module-validation-program/validated-modules
- Publisher: National Institute of Standards and Technology.
- Page date: updated 2026-08-07.
- Status on 2026-08-13: `Program page/database`.
- Accessed: 2026-08-13.
- Supports: CMVP scope; certificate status and scope; the distinction between an algorithm certificate and FIPS 140 module validation; limitations concerning product scope, supply chain, and suitability.
- Does not support: extending a certificate beyond its exact module/version/environment/mode, or inferring endorsement or overall product suitability.
- Revalidation trigger: every CMVP/FIPS 140 claim and any active, historical, or revoked status change.

### SRC-NIST-014 — CSF FAQ

- Title: NIST Cybersecurity Framework Frequently Asked Questions.
- URL: https://www.nist.gov/cyberframework/faqs
- Publisher: National Institute of Standards and Technology.
- Source date: living FAQ; no single publication date used by this registry.
- Status on 2026-08-13: `Living supplementary material`.
- Accessed: 2026-08-13.
- Supports: the six CSF 2.0 Functions — Govern, Identify, Protect, Detect, Respond, and Recover — as concurrent and continuous; the governance rationale; non-prescriptive outcomes.
- Does not support: treating CSF Functions as a sequential PQC lifecycle or the demo's phase associations as an official mapping.
- Revalidation trigger: FAQ update or CSF revision.

## Final-versus-draft posture snapshot

Final/current foundations:

- CSF 2.0, CSWP 29.
- CSWP 39upd1 on crypto agility.
- FIPS 203, FIPS 204, and FIPS 205, subject to current planning notes/errata where present.
- SP 800-227.
- Current CAVP and CMVP program pages and their official validation databases.

Nonfinal planning or project material:

- NIST IR 8547: Initial Public Draft.
- CSWP 48: Initial Public Draft.
- SP 1800-38A/B/C: Initial Preliminary Draft.
- NCCoE project and FAQ pages: active/living material, not numbered final publications.

## Status-change protocol

When a source changes:

1. Record the new source status, document date, status-check date, and direct official URL.
2. Preserve the prior status in version control; do not rewrite history as if a draft had always been final.
3. Identify every dependent claim and lifecycle decision.
4. Reassess wording, implementation assumptions, test evidence, and residual gaps.
5. Require new evidence before promoting a claim from draft-based or unresolved to verified.
6. For FIPS errata or validation-record changes, re-evaluate the exact affected implementation/module scope before continuing the claim.

## Watch list and unresolved status gaps

- Finalization or revision of NIST IR 8547.
- Finalization or revision of CSWP 48.
- Replacement of SP 1800-38 preliminary material with newer NCCoE outputs.
- Changes to the living NCCoE FAQ's six-phase grouping or inventory guidance.
- FIPS 203 and FIPS 204 errata or revisions.
- New planning notes or errata for FIPS 205 and SP 800-227.
- Changes in CAVP support, algorithm-validation entries, or ACVTS procedures.
- Changes in CMVP certificate status or validated scope for any future demo dependency.
- Future NIST standards for algorithms still under development or selected for future standardization must not be called Final until their official NIST publication records say so.
