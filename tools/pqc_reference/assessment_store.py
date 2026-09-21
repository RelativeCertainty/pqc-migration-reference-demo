"""Durable, synthetic-only evidence-to-report reference composition.

This deliberately cannot open a production database, ingest an arbitrary export,
grant approval, or perform provider actions. It exercises application-owned state
and custody on disposable SQLite files. Enterprise SQL/identity/custody bindings
remain separate implementation and authorization gates.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import stat
from contextlib import contextmanager
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from workers.pqc.assessment_sources import normalize_page


APPLICATION_ID = 0x50514352
MAX_PAGE_BYTES = 256 * 1024
MAX_TOTAL_PAGES = 100
PROOF_KIND = "pqc.reference.assessment.v1"


class ReferenceError(ValueError):
    """Stable error codes only; never echo source or database content."""


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("ascii")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def timestamp(value: str) -> datetime:
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError) as exc:
        raise ReferenceError("invalid_timestamp") from exc
    if result.tzinfo is None:
        raise ReferenceError("timezone_required")
    return result.astimezone(timezone.utc)


def record_dependencies(record: dict[str, Any]) -> list[dict[str, Any]]:
    """Project only explicit, source-normalized relationships; never infer joins."""
    facts = record["facts"]
    links = {
        (field, facts[field])
        for field in ("application_ref", "certificate_ref")
        if facts.get(field)
    }
    links.update(
        (item["relationship"], item["target_ref"])
        for item in facts.get("relationships", [])
        if item.get("target_ref")
    )
    links.update(
        ("protected_data_ref", use["protected_data_ref"])
        for use in facts.get("cryptographic_uses", [])
        if use.get("protected_data_ref")
    )
    return [
        {
            "from_ref": record["subject_ref"],
            "relationship": relationship,
            "to_ref": target,
            "observation_ref": record["observation_id"],
        }
        for relationship, target in sorted(links)
    ]


def _tenant(value: str) -> None:
    if (
        not isinstance(value, str)
        or not value.startswith("synthetic-")
        or len(value) > 80
    ):
        raise ReferenceError("synthetic_tenant_required")
    if any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in value):
        raise ReferenceError("invalid_tenant")


def _owned_directory(path: Path, *, create: bool = False) -> None:
    if any(component.is_symlink() for component in (path, *path.parents)):
        raise ReferenceError("invalid_reference_directory")
    if create:
        path.mkdir(mode=0o700, parents=True, exist_ok=False)
    if path.is_symlink() or not path.is_dir():
        raise ReferenceError("invalid_reference_directory")
    stat = path.stat()
    if stat.st_uid != os.getuid() or stat.st_mode & 0o077:
        raise ReferenceError("private_reference_directory_required")


def write_new(path: Path, content: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())


def _read_private(path: Path, maximum: int) -> bytes:
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as stream:
            metadata = os.fstat(stream.fileno())
            if (
                not stat.S_ISREG(metadata.st_mode)
                or metadata.st_uid != os.getuid()
                or metadata.st_mode & 0o077
                or metadata.st_size > maximum
            ):
                raise ReferenceError("invalid_private_artifact")
            return stream.read(maximum + 1)
    except OSError as exc:
        raise ReferenceError("private_artifact_unavailable") from exc


_SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE reference_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
INSERT INTO reference_metadata VALUES ('boundary','synthetic-only-v1');
CREATE TABLE pages (
 tenant TEXT NOT NULL, source TEXT NOT NULL, page_id TEXT NOT NULL,
 kind TEXT NOT NULL, payload_digest TEXT NOT NULL, artifact_ref TEXT NOT NULL,
 observed_at TEXT NOT NULL, record_count INTEGER NOT NULL, complete INTEGER NOT NULL,
 PRIMARY KEY(tenant,source,page_id)
);
CREATE TABLE observations (
 tenant TEXT NOT NULL, observation_id TEXT NOT NULL, source TEXT NOT NULL,
 page_id TEXT NOT NULL, subject_ref TEXT NOT NULL, fact_type TEXT NOT NULL,
 record_json TEXT NOT NULL, record_digest TEXT NOT NULL,
 PRIMARY KEY(tenant,observation_id),
 FOREIGN KEY(tenant,source,page_id) REFERENCES pages(tenant,source,page_id)
);
CREATE TABLE cursors (
 tenant TEXT NOT NULL, source TEXT NOT NULL, page_id TEXT NOT NULL,
 PRIMARY KEY(tenant,source),
 FOREIGN KEY(tenant,source,page_id) REFERENCES pages(tenant,source,page_id)
);
CREATE TABLE events (
 event_id INTEGER PRIMARY KEY, tenant TEXT NOT NULL, event_type TEXT NOT NULL,
 subject_ref TEXT NOT NULL, content_digest TEXT NOT NULL
);
CREATE TABLE outbox (
 event_id INTEGER PRIMARY KEY REFERENCES events(event_id),
 projection_type TEXT NOT NULL
);
CREATE TABLE baselines (
 tenant TEXT NOT NULL, baseline_id TEXT NOT NULL, body_json TEXT NOT NULL,
 PRIMARY KEY(tenant,baseline_id)
);
CREATE TABLE reports (
 tenant TEXT NOT NULL, report_id TEXT NOT NULL, baseline_id TEXT NOT NULL,
 report_kind TEXT NOT NULL, body_json TEXT NOT NULL,
 PRIMARY KEY(tenant,report_id),
 FOREIGN KEY(tenant,baseline_id) REFERENCES baselines(tenant,baseline_id)
);
"""


class SyntheticAssessmentStore:
    """One controller-owned synthetic state store; no network/DSN constructor."""

    def __init__(self, root: Path, *, create: bool = False):
        self.root = Path(root).absolute()
        _owned_directory(self.root, create=create)
        self.db_path = self.root / "assessment.sqlite3"
        self.custody = self.root / "custody"
        self.key_path = self.root / "synthetic-custody.key"
        if create:
            self.custody.mkdir(mode=0o700)
            write_new(self.key_path, AESGCM.generate_key(bit_length=256))
            write_new(self.db_path, b"")
        else:
            for file in (self.db_path, self.key_path):
                if (
                    file.is_symlink()
                    or not file.is_file()
                    or file.stat().st_mode & 0o077
                    or file.stat().st_uid != os.getuid()
                ):
                    raise ReferenceError("invalid_reference_file")
            # Do not run any mutating PRAGMA against an unrecognized database.
            probe = sqlite3.connect(
                self.db_path.as_uri() + "?mode=ro", uri=True, timeout=2
            )
            try:
                if (
                    probe.execute("PRAGMA application_id").fetchone()[0]
                    != APPLICATION_ID
                ):
                    raise ReferenceError("not_a_reference_database")
                boundary = probe.execute(
                    "SELECT value FROM reference_metadata WHERE key='boundary'"
                ).fetchone()
                if boundary is None or boundary[0] != "synthetic-only-v1":
                    raise ReferenceError("not_a_reference_database")
            except sqlite3.Error as exc:
                raise ReferenceError("not_a_reference_database") from exc
            finally:
                probe.close()
        _owned_directory(self.custody)
        self.db = sqlite3.connect(
            self.db_path.as_uri() + "?mode=rw", uri=True, timeout=2
        )
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA journal_mode=DELETE")
        if create:
            self.db.executescript(_SCHEMA)
            self.db.execute(f"PRAGMA application_id={APPLICATION_ID}")
            self.db.execute("PRAGMA user_version=1")
            for table in (
                "pages",
                "observations",
                "events",
                "outbox",
                "baselines",
                "reports",
            ):
                for operation in ("UPDATE", "DELETE"):
                    self.db.execute(
                        f"CREATE TRIGGER immutable_{table}_{operation.lower()} BEFORE {operation} "
                        f"ON {table} BEGIN SELECT RAISE(ABORT,'immutable_reference_record'); END"
                    )
            self.db.commit()
        if self.db.execute("PRAGMA application_id").fetchone()[0] != APPLICATION_ID:
            self.db.close()
            raise ReferenceError("not_a_reference_database")
        boundary = self.db.execute(
            "SELECT value FROM reference_metadata WHERE key='boundary'"
        ).fetchone()
        if boundary is None or boundary[0] != "synthetic-only-v1":
            self.db.close()
            raise ReferenceError("not_a_reference_database")

    def close(self) -> None:
        self.db.close()

    def _artifact(self, tenant: str, payload: dict[str, Any]) -> tuple[str, str]:
        raw = canonical(payload)
        if len(raw) > MAX_PAGE_BYTES:
            raise ReferenceError("page_too_large")
        sha = hashlib.sha256(raw).hexdigest()
        name = digest({"tenant": tenant, "sha256": sha}) + ".aesgcm"
        target = self.custody / name
        aad = canonical({"tenant": tenant, "sha256": sha})
        cipher = AESGCM(_read_private(self.key_path, 32))
        if target.exists():
            if self.read_artifact(tenant, name, sha) != payload:
                raise ReferenceError("custody_conflict")
        else:
            if len(list(self.custody.iterdir())) >= MAX_TOTAL_PAGES * 2:
                raise ReferenceError("custody_budget_exceeded")
            nonce = os.urandom(12)
            write_new(target, nonce + cipher.encrypt(nonce, raw, aad))
        return sha, name

    def read_artifact(self, tenant: str, name: str, sha: str) -> dict[str, Any]:
        _tenant(tenant)
        if name != digest({"tenant": tenant, "sha256": sha}) + ".aesgcm":
            raise ReferenceError("invalid_artifact_reference")
        target = self.custody / name
        if (
            target.is_symlink()
            or not target.is_file()
            or target.stat().st_size > MAX_PAGE_BYTES + 64
        ):
            raise ReferenceError("invalid_artifact_reference")
        try:
            blob = _read_private(target, MAX_PAGE_BYTES + 64)
            raw = AESGCM(_read_private(self.key_path, 32)).decrypt(
                blob[:12], blob[12:], canonical({"tenant": tenant, "sha256": sha})
            )
            if hashlib.sha256(raw).hexdigest() != sha:
                raise ReferenceError("artifact_digest_mismatch")
            return json.loads(raw)
        except Exception as exc:
            raise ReferenceError("artifact_verification_failed") from exc

    def ingest_page(
        self,
        *,
        tenant: str,
        source: str,
        page_id: str,
        kind: str,
        payload: dict[str, Any],
        observed_at: str,
        complete: bool = True,
        expected_cursor: str | None = None,
        fail_before_cursor: bool = False,
    ) -> dict[str, Any]:
        _tenant(tenant)
        timestamp(observed_at)
        if (
            not isinstance(complete, bool)
            or not isinstance(page_id, str)
            or not 1 <= len(page_id) <= 128
        ):
            raise ReferenceError("invalid_page_metadata")
        if (
            not isinstance(source, str)
            or not source.startswith("synthetic-")
            or len(source) > 80
        ):
            raise ReferenceError("synthetic_source_required")
        raw = canonical(payload)
        if len(raw) > MAX_PAGE_BYTES:
            raise ReferenceError("page_too_large")
        records = normalize_page(
            kind,
            payload,
            tenant_id=tenant,
            source_instance_id=source,
            observed_at=observed_at,
        )
        sha = hashlib.sha256(raw).hexdigest()
        unique = {digest(record): record for record in records}
        try:
            self.db.execute("BEGIN IMMEDIATE")
            existing = self.db.execute(
                "SELECT * FROM pages WHERE tenant=? AND source=? AND page_id=?",
                (tenant, source, page_id),
            ).fetchone()
            if existing:
                if (
                    existing["payload_digest"],
                    existing["kind"],
                    existing["observed_at"],
                    existing["complete"],
                ) != (sha, kind, observed_at, int(complete)):
                    raise ReferenceError("page_replay_conflict")
                self.read_artifact(tenant, existing["artifact_ref"], sha)
                self.db.commit()
                return {
                    "result": "idempotent_replay",
                    "payload_digest": sha,
                    "record_count": existing["record_count"],
                }
            if (
                self.db.execute("SELECT count(*) FROM pages").fetchone()[0]
                >= MAX_TOTAL_PAGES
            ):
                raise ReferenceError("reference_page_budget_exceeded")
            cursor = self.db.execute(
                "SELECT page_id FROM cursors WHERE tenant=? AND source=?",
                (tenant, source),
            ).fetchone()
            if (cursor[0] if cursor else None) != expected_cursor:
                raise ReferenceError("cursor_revision_conflict")
            # The DB writer lock also serializes artifact create/reuse. Custody
            # must verify before page receipt, event and cursor are committed.
            sha, artifact = self._artifact(tenant, payload)
            self.read_artifact(tenant, artifact, sha)
            self.db.execute(
                "INSERT INTO pages VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    tenant,
                    source,
                    page_id,
                    kind,
                    sha,
                    artifact,
                    observed_at,
                    len(unique),
                    int(complete),
                ),
            )
            for record_sha, record in sorted(unique.items()):
                observation_id = digest(
                    {
                        "tenant": tenant,
                        "source": source,
                        "page": page_id,
                        "record": record_sha,
                    }
                )
                self.db.execute(
                    "INSERT INTO observations VALUES (?,?,?,?,?,?,?,?)",
                    (
                        tenant,
                        observation_id,
                        source,
                        page_id,
                        record["subject_ref"],
                        record["fact_type"],
                        canonical(record).decode(),
                        record_sha,
                    ),
                )
            event = self.db.execute(
                "INSERT INTO events(tenant,event_type,subject_ref,content_digest) VALUES (?,?,?,?)",
                (tenant, "source_page_committed", page_id, sha),
            )
            self.db.execute(
                "INSERT INTO outbox VALUES (?,?)", (event.lastrowid, "inventory")
            )
            if fail_before_cursor:
                raise ReferenceError("injected_transaction_failure")
            self.db.execute(
                "INSERT INTO cursors VALUES (?,?,?) ON CONFLICT(tenant,source) "
                "DO UPDATE SET page_id=excluded.page_id",
                (tenant, source, page_id),
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return {
            "result": "committed",
            "payload_digest": sha,
            "record_count": len(unique),
        }

    @contextmanager
    def _transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def freeze_baseline(
        self, tenant: str, *, as_of: str, freshness_days: int = 30
    ) -> dict[str, Any]:
        # One consistent snapshot includes observations, page receipts and freeze.
        with self._transaction():
            return self._freeze_baseline(
                tenant, as_of=as_of, freshness_days=freshness_days
            )

    def _freeze_baseline(
        self, tenant: str, *, as_of: str, freshness_days: int
    ) -> dict[str, Any]:
        _tenant(tenant)
        cutoff = timestamp(as_of)
        if not isinstance(freshness_days, int) or not 1 <= freshness_days <= 365:
            raise ReferenceError("invalid_freshness_policy")
        observations = self.db.execute(
            "SELECT o.*, p.artifact_ref,p.payload_digest,p.observed_at FROM observations o "
            "JOIN pages p USING(tenant,source,page_id) WHERE o.tenant=? ORDER BY o.observation_id",
            (tenant,),
        ).fetchall()
        records: list[dict[str, Any]] = []
        variants: dict[str, set[str]] = defaultdict(set)
        limitations: list[dict[str, Any]] = []
        for row in observations:
            when = timestamp(row["observed_at"])
            if when > cutoff:
                continue
            self.read_artifact(tenant, row["artifact_ref"], row["payload_digest"])
            record = json.loads(row["record_json"])
            if digest(record) != row["record_digest"]:
                raise ReferenceError("observation_digest_mismatch")
            variants[record["subject_ref"]].add(row["record_digest"])
            records.append(
                {
                    **record,
                    "observation_id": row["observation_id"],
                    "source_instance_id": row["source"],
                    "observed_at": row["observed_at"],
                    "evidence_ref": row["artifact_ref"],
                    "evidence_sha256": row["payload_digest"],
                }
            )
            facts = record["facts"]
            required_context = (
                {
                    "owner_ref",
                    "business_service_ref",
                    "criticality",
                    "confidentiality_until",
                }
                if record["fact_type"] == "application"
                else set()
            )
            for field in sorted(required_context):
                if facts.get(field) in (None, "unknown"):
                    limitations.append(
                        {
                            "code": "missing_business_context",
                            "subject_ref": record["subject_ref"],
                            "field": field,
                        }
                    )
            expected_relations = (
                {"application_ref", "certificate_ref"}
                if record["fact_type"] == "tls_endpoint"
                else {"application_ref"}
                if record["fact_type"] == "certificate"
                else set()
            )
            for field in sorted(expected_relations):
                if not facts.get(field):
                    limitations.append(
                        {
                            "code": "missing_relationship",
                            "subject_ref": record["subject_ref"],
                            "field": field,
                        }
                    )
            crypto_fields = (
                {"key_exchange_group", "certificate_signature_algorithm", "protocol"}
                if record["fact_type"] == "tls_endpoint"
                else {"signature_algorithm", "public_key_algorithm"}
                if record["fact_type"] == "certificate"
                else set()
            )
            for field in sorted(crypto_fields):
                if facts.get(field) in (None, "unknown", ""):
                    limitations.append(
                        {
                            "code": "cryptographic_parameters_unknown",
                            "subject_ref": record["subject_ref"],
                            "field": field,
                        }
                    )
            # Extended dialects supply closed metadata and explicit use facts.
            # Their reported policies/capabilities do not establish acceptance.
            for code in facts.get("limitations", []):
                limitations.append({"code": code, "subject_ref": record["subject_ref"]})
            for use in facts.get("cryptographic_uses", []):
                if use.get("algorithm") in (None, "unknown", ""):
                    limitations.append(
                        {
                            "code": "cryptographic_parameters_unknown",
                            "subject_ref": record["subject_ref"],
                            "field": use["role"],
                        }
                    )
                if use.get("purpose") in {
                    "authentication",
                    "digital_signature",
                    "signing",
                } and not use.get("trust_until"):
                    limitations.append(
                        {
                            "code": "signature_trust_lifetime_unknown",
                            "subject_ref": record["subject_ref"],
                            "field": use["role"],
                        }
                    )
            if (cutoff - when).days > freshness_days:
                limitations.append(
                    {"code": "stale_evidence", "subject_ref": record["subject_ref"]}
                )
        for subject, content in sorted(variants.items()):
            if len(content) > 1:
                limitations.append(
                    {"code": "conflicting_observations", "subject_ref": subject}
                )
        subjects = set(variants)
        dependencies = []
        for record in records:
            for edge in record_dependencies(record):
                dependencies.append(edge)
                if edge["to_ref"] not in subjects:
                    limitations.append(
                        {
                            "code": "unresolved_dependency",
                            "subject_ref": record["subject_ref"],
                        }
                    )
        pages = [
            dict(row)
            for row in self.db.execute(
                "SELECT source,kind,page_id,payload_digest,artifact_ref,observed_at,complete FROM pages WHERE tenant=? ORDER BY source,page_id",
                (tenant,),
            )
            if timestamp(row["observed_at"]) <= cutoff
        ]
        for page in pages:
            # Empty results are evidence too; never let their custody disappear.
            self.read_artifact(tenant, page["artifact_ref"], page["payload_digest"])
            if not page["complete"]:
                limitations.append(
                    {
                        "code": "partial_source_collection",
                        "source_instance_id": page["source"],
                    }
                )
        present = {page["kind"] for page in pages}
        for kind in sorted({"cmdb", "pki", "tls"} - present):
            limitations.append({"code": "missing_source", "source_kind": kind})
        if not records:
            limitations.append({"code": "no_observations"})
        # An imported page is never an authoritative whole-estate denominator.
        limitations.append({"code": "enterprise_coverage_denominator_unavailable"})
        limitations = [
            json.loads(item)
            for item in sorted({canonical(item).decode() for item in limitations})
        ]
        body = {
            "type": "pqc.reference.baseline.v1",
            "synthetic": True,
            "tenant_id": tenant,
            "as_of": as_of,
            "freshness_days": freshness_days,
            "human_acceptance": "not_requested",
            "analysis_eligibility": "synthetic_reference_only",
            "sources": pages,
            "observations": records,
            "dependencies": dependencies,
            "limitations": limitations,
            "counts": {
                "source_instances": len({p["source"] for p in pages}),
                "observations": len(records),
                "subjects": len(subjects),
                "dependencies": len(dependencies),
                "enterprise_coverage_percent": None,
            },
        }
        baseline_id = digest(body)
        self.db.execute(
            "INSERT OR IGNORE INTO baselines VALUES (?,?,?)",
            (tenant, baseline_id, canonical(body).decode()),
        )
        return {"baseline_id": baseline_id, **body}

    def get_baseline(self, tenant: str, baseline_id: str) -> dict[str, Any]:
        _tenant(tenant)
        row = self.db.execute(
            "SELECT body_json FROM baselines WHERE tenant=? AND baseline_id=?",
            (tenant, baseline_id),
        ).fetchone()
        if row is None:
            raise ReferenceError("baseline_not_found")
        body = json.loads(row[0])
        if digest(body) != baseline_id:
            raise ReferenceError("baseline_digest_mismatch")
        return {"baseline_id": baseline_id, **body}

    def report(self, tenant: str, baseline_id: str, phase: int) -> dict[str, Any]:
        if phase not in (1, 2):
            raise ReferenceError("assessment_phase_required")
        baseline = self.get_baseline(tenant, baseline_id)
        # Retaining an immutable report snapshot does not establish current custody.
        # New report generation fails if any cited artifact cannot be verified.
        for page in baseline["sources"]:
            self.read_artifact(tenant, page["artifact_ref"], page["payload_digest"])
        for observation in baseline["observations"]:
            self.read_artifact(
                tenant, observation["evidence_ref"], observation["evidence_sha256"]
            )
        body: dict[str, Any] = {
            "type": "pqc.reference.report.v1",
            "synthetic": True,
            "tenant_id": tenant,
            "phase": phase,
            "baseline_id": baseline_id,
            "title": "Current-State Assessment" if phase == 1 else "PQC Risk Register",
            "counts": baseline["counts"],
            "limitations": baseline["limitations"],
            "human_acceptance": "not_requested",
            "source_system_write_authority": False,
            "production_risk_method_approved": False,
        }
        if phase == 1:
            body["inventory"] = baseline["observations"]
            body["dependencies"] = baseline["dependencies"]
        else:
            body["method"] = {
                "id": "reference-evidence-review",
                "version": 1,
                "status": "illustrative_not_enterprise_approved",
                "numerical_scoring": False,
                "rule": "Keep observed exposure, evidence gaps and migration feasibility separate.",
            }
            entries = []
            for record in baseline["observations"]:
                if "cryptographic_uses" in record["facts"]:
                    entries.append(
                        {
                            "risk_candidate_id": digest(
                                {
                                    "baseline": baseline_id,
                                    "record": record["observation_id"],
                                }
                            ),
                            "subject_ref": record["subject_ref"],
                            "observation_refs": [record["observation_id"]],
                            "evidence_refs": [record["evidence_ref"]],
                            "rationale_code": "explicit_uses_require_purpose_specific_review"
                            if record["facts"]["cryptographic_uses"]
                            else "context_only_no_cryptographic_use_evidenced",
                            "evidence_basis": record["assertion_kind"],
                            "assessment_status": "human_review_required",
                            "negotiation_observed": False,
                            "risk_rating": None,
                            "business_impact": "requires_owner_evidence",
                            "migration_feasibility": "not_assessed",
                            "residual_risk_accepted": False,
                            "execution_authorized": False,
                            "source_claim_is_approval": False,
                        }
                    )
                    continue
                if record["fact_type"] not in {"certificate", "tls_endpoint"}:
                    continue
                facts = record["facts"]
                group = facts.get("key_exchange_group")
                signature = facts.get("signature_algorithm")
                hybrid_groups = {
                    "X25519MLKEM768",
                    "SecP256r1MLKEM768",
                    "SecP384r1MLKEM1024",
                }
                reason = (
                    "hybrid_key_establishment_evidence_authentication_separate"
                    if group in hybrid_groups
                    else "key_establishment_requires_method_review"
                    if group
                    else "certificate_signature_requires_separate_review"
                    if signature
                    else "cryptographic_parameters_unknown"
                )
                entries.append(
                    {
                        "risk_candidate_id": digest(
                            {
                                "baseline": baseline_id,
                                "record": record["observation_id"],
                            }
                        ),
                        "subject_ref": record["subject_ref"],
                        "observation_refs": [record["observation_id"]],
                        "evidence_refs": [record["evidence_ref"]],
                        "rationale_code": reason,
                        "evidence_basis": record["assertion_kind"],
                        "assessment_status": "human_review_required",
                        "negotiation_observed": record["fact_type"] == "tls_endpoint"
                        and record["assertion_kind"] == "observed"
                        and facts.get("protocol") in {"TLSv1.2", "TLSv1.3"}
                        and group not in (None, "", "unknown"),
                        "risk_rating": None,
                        "business_impact": "requires_owner_evidence",
                        "migration_feasibility": "not_assessed",
                        "residual_risk_accepted": False,
                    }
                )
            body["risk_candidates"] = entries
        report_id = digest(body)
        with self.db:
            self.db.execute(
                "INSERT OR IGNORE INTO reports VALUES (?,?,?,?,?)",
                (
                    tenant,
                    report_id,
                    baseline_id,
                    f"phase{phase}",
                    canonical(body).decode(),
                ),
            )
        return {"report_id": report_id, **body}

    def backup(self, target: Path) -> None:
        target = Path(target)
        _owned_directory(target, create=True)
        backup_path = target / "assessment.sqlite3"
        write_new(backup_path, b"")
        destination = sqlite3.connect(backup_path)
        try:
            self.db.backup(destination)
        finally:
            destination.close()
        (target / "custody").mkdir(mode=0o700)
        write_new(target / "synthetic-custody.key", _read_private(self.key_path, 32))
        for file in self.custody.iterdir():
            if file.is_symlink() or not file.name.endswith(".aesgcm"):
                raise ReferenceError("invalid_custody_backup")
            shutil.copyfile(file, target / "custody" / file.name)
            (target / "custody" / file.name).chmod(0o600)


def report_markdown(report: dict[str, Any]) -> str:
    """Owner-readable synthetic projection; never a claim of accepted delivery."""
    lines = [
        f"# {report['title']} — synthetic reference",
        "",
        "Development proof only. No enterprise assessment or migration has been accepted.",
        "",
        f"Baseline: `{report['baseline_id']}`",
        "",
        f"Report: `{report['report_id']}`",
        "",
        "## Coverage and evidence",
        "",
        f"- Source instances: {report['counts']['source_instances']}",
        f"- Source-derived observations: {report['counts']['observations']}",
        f"- Correlated subjects: {report['counts']['subjects']}",
        f"- Evidence-linked dependencies: {report['counts']['dependencies']}",
        "- Enterprise completeness: unknown; no approved denominator.",
        "",
        "## Limitations",
        "",
    ]
    for item in report["limitations"]:
        lines.append("- " + item["code"].replace("_", " "))
    if report["phase"] == 2:
        lines += [
            "",
            "## Evidence-linked analysis candidates",
            "",
            "The reference method does not assign numerical risk or fabricate business impact.",
            "",
        ]
        for item in report["risk_candidates"]:
            lines += [
                f"- `{item['risk_candidate_id'][:16]}`: {item['rationale_code'].replace('_', ' ')}.",
                f"  Evidence basis: {item['evidence_basis']}. Owner review required.",
            ]
    else:
        lines += ["", "## Observed inventory", ""]
        for item in report["inventory"]:
            lines.append(
                f"- {item['fact_type']}: `{item['subject_ref']}` ({item['assertion_kind']})."
            )
    lines += [
        "",
        "## Authority boundary",
        "",
        "Human acceptance: not requested. Source-system writes and migration execution: unavailable.",
        "The SQLite and encrypted-file custody adapters are synthetic lab bindings, not selected enterprise services.",
        "",
    ]
    return "\n".join(lines)
