from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator

from .models import EvidenceStatus


DEFAULT_CONTRACT_ROOT = (
    Path(__file__).resolve().parents[2] / "integrations" / "pqc" / "contracts"
)
MAX_MANIFEST_BYTES = 128 * 1024
MAX_ARTIFACT_BYTES = 2 * 1024 * 1024
PACK_ID = re.compile(r"^[a-z][a-z0-9._-]{2,127}$")
ARTIFACT_PATH = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._/-]{0,239}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
ACCESS_CLASSES = {"live_local", "hosted_free", "time_limited_trial", "sales_gated"}
ARTIFACT_KINDS = {"json_schema", "synthetic_fixture", "simulator_scenarios"}


class ContractPackError(ValueError):
    def __init__(self, code: str = "PQC_CONTRACT_PACK_INVALID") -> None:
        super().__init__("contract pack failed validation")
        self.code = code


def _exact_keys(value: Mapping[str, Any], expected: set[str]) -> None:
    if set(value) != expected:
        raise ContractPackError()


def _require_text(value: object, *, maximum: int = 256) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ContractPackError()
    return value


def _safe_source_url(value: object) -> str:
    source = _require_text(value, maximum=1_024)
    parsed = urlsplit(source)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        raise ContractPackError()
    return source


@dataclass(frozen=True)
class ContractPack:
    root: Path
    manifest: Mapping[str, Any]

    @property
    def pack_id(self) -> str:
        return str(self.manifest["pack_id"])

    @property
    def adapter_id(self) -> str:
        return str(self.manifest["adapter_id"])

    @property
    def evidence_status(self) -> EvidenceStatus:
        return EvidenceStatus(str(self.manifest["evidence_status"]))

    @property
    def content_digest(self) -> str:
        canonical = json.dumps(
            self.manifest,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("ascii")
        return hashlib.sha256(canonical).hexdigest()

    def artifact_path(self, relative_path: str) -> Path:
        admitted = {str(item["path"]) for item in self.manifest["artifacts"]}
        if relative_path not in admitted:
            raise ContractPackError()
        candidate = (self.root / relative_path).resolve()
        if self.root.resolve() not in candidate.parents or not candidate.is_file():
            raise ContractPackError()
        return candidate

    def load_json_artifact(self, relative_path: str) -> object:
        path = self.artifact_path(relative_path)
        if path.stat().st_size > MAX_ARTIFACT_BYTES:
            raise ContractPackError()
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ContractPackError() from exc

    def validate_request(self, value: object) -> None:
        self._validate_against(str(self.manifest["request_schema"]), value)

    def validate_response(self, value: object) -> None:
        self._validate_against(str(self.manifest["response_schema"]), value)

    def _validate_against(self, schema_path: str, value: object) -> None:
        schema = self.load_json_artifact(schema_path)
        if not isinstance(schema, dict):
            raise ContractPackError()
        validator = Draft202012Validator(schema)
        if next(validator.iter_errors(value), None) is not None:
            # Never include a JSON path or source value in this error.
            raise ContractPackError("PQC_ADAPTER_SCHEMA_DRIFT")

    def simulator_scenario(self, name: str) -> Mapping[str, Any]:
        scenario_path = str(self.manifest["simulator_scenarios"])
        payload = self.load_json_artifact(scenario_path)
        if (
            not isinstance(payload, dict)
            or payload.get("schema_version") != "pba.pqc.simulator-scenarios.v1"
        ):
            raise ContractPackError()
        scenarios = payload.get("scenarios")
        if not isinstance(scenarios, dict) or not isinstance(scenarios.get(name), dict):
            raise ContractPackError()
        return scenarios[name]


class ContractPackLoader:
    def __init__(self, root: Path = DEFAULT_CONTRACT_ROOT) -> None:
        self.root = root.resolve()

    def discover(self) -> tuple[str, ...]:
        if not self.root.is_dir():
            return ()
        return tuple(
            sorted(
                path.name
                for path in self.root.iterdir()
                if path.is_dir() and (path / "manifest.json").is_file()
            )
        )

    def load(self, pack_id: str) -> ContractPack:
        if not PACK_ID.fullmatch(pack_id):
            raise ContractPackError()
        pack_root = (self.root / pack_id).resolve()
        if self.root not in pack_root.parents or not pack_root.is_dir():
            raise ContractPackError()
        manifest_path = pack_root / "manifest.json"
        if (
            not manifest_path.is_file()
            or manifest_path.stat().st_size > MAX_MANIFEST_BYTES
        ):
            raise ContractPackError()
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ContractPackError() from exc
        if not isinstance(manifest, dict):
            raise ContractPackError()
        self._validate_manifest(manifest, expected_pack_id=pack_id)
        pack = ContractPack(pack_root, manifest)
        self._validate_artifacts(pack)
        return pack

    def _validate_manifest(
        self, manifest: Mapping[str, Any], *, expected_pack_id: str
    ) -> None:
        _exact_keys(
            manifest,
            {
                "schema_version",
                "pack_id",
                "vendor",
                "product",
                "api_version",
                "adapter_id",
                "official_sources",
                "provenance",
                "license",
                "access_class",
                "evidence_status",
                "authentication",
                "transport",
                "limits",
                "request_schema",
                "response_schema",
                "fixture_paths",
                "simulator_scenarios",
                "artifacts",
            },
        )
        if manifest["schema_version"] != "pba.pqc.contract-pack.v1":
            raise ContractPackError()
        if manifest["pack_id"] != expected_pack_id or not PACK_ID.fullmatch(
            expected_pack_id
        ):
            raise ContractPackError()
        for key in ("vendor", "product", "api_version", "adapter_id"):
            _require_text(manifest[key])
        if manifest["access_class"] not in ACCESS_CLASSES:
            raise ContractPackError()
        try:
            EvidenceStatus(str(manifest["evidence_status"]))
        except ValueError as exc:
            raise ContractPackError() from exc

        sources = manifest["official_sources"]
        if not isinstance(sources, list) or not sources or len(sources) > 8:
            raise ContractPackError()
        for source in sources:
            if not isinstance(source, dict):
                raise ContractPackError()
            _exact_keys(
                source, {"url", "retrieved_at", "evidence_status", "source_note"}
            )
            _safe_source_url(source["url"])
            _require_text(source["retrieved_at"], maximum=10)
            if source["evidence_status"] != "documented":
                raise ContractPackError()
            _require_text(source["source_note"], maximum=160)

        provenance = manifest["provenance"]
        if not isinstance(provenance, dict):
            raise ContractPackError()
        _exact_keys(
            provenance,
            {"contract_origin", "fixture_origin", "raw_vendor_contract_included"},
        )
        if provenance != {
            "contract_origin": "official_documentation",
            "fixture_origin": "independently_authored",
            "raw_vendor_contract_included": False,
        }:
            raise ContractPackError()

        license_data = manifest["license"]
        if not isinstance(license_data, dict):
            raise ContractPackError()
        _exact_keys(
            license_data,
            {"vendor_material_status", "synthetic_fixture_status", "use_status"},
        )
        if license_data["vendor_material_status"] != "not_redistributed":
            raise ContractPackError()
        if license_data["synthetic_fixture_status"] != "repository_internal":
            raise ContractPackError()
        if license_data["use_status"] != "interoperability_development":
            raise ContractPackError()

        authentication = manifest["authentication"]
        if not isinstance(authentication, dict):
            raise ContractPackError()
        _exact_keys(authentication, {"mode", "secret_ref_names"})
        _require_text(authentication["mode"], maximum=80)
        refs = authentication["secret_ref_names"]
        if not isinstance(refs, list) or len(refs) > 4:
            raise ContractPackError()
        for ref in refs:
            if not isinstance(ref, str) or not re.fullmatch(
                r"[a-z][a-z0-9_]{2,79}_ref", ref
            ):
                raise ContractPackError()

        transport = manifest["transport"]
        if not isinstance(transport, dict):
            raise ContractPackError()
        _exact_keys(
            transport,
            {
                "method",
                "path",
                "pagination",
                "rate_limit",
                "idempotency",
                "concurrency",
            },
        )
        if transport["method"] not in {"FILE", "GET", "POST"}:
            raise ContractPackError()
        for key in ("path", "pagination", "rate_limit", "idempotency", "concurrency"):
            _require_text(transport[key], maximum=200)

        limits = manifest["limits"]
        if not isinstance(limits, dict):
            raise ContractPackError()
        _exact_keys(limits, {"max_page_size", "max_total_records", "max_pages"})
        for key in ("max_page_size", "max_total_records", "max_pages"):
            if (
                not isinstance(limits[key], int)
                or isinstance(limits[key], bool)
                or limits[key] < 1
            ):
                raise ContractPackError()
        if limits["max_page_size"] > 500 or limits["max_pages"] > 2_000:
            raise ContractPackError()

        artifact_paths: list[str] = []
        artifacts = manifest["artifacts"]
        if not isinstance(artifacts, list) or not artifacts or len(artifacts) > 32:
            raise ContractPackError()
        for artifact in artifacts:
            if not isinstance(artifact, dict):
                raise ContractPackError()
            _exact_keys(artifact, {"path", "sha256", "kind"})
            relative_path = _require_text(artifact["path"], maximum=240)
            if (
                not ARTIFACT_PATH.fullmatch(relative_path)
                or ".." in Path(relative_path).parts
            ):
                raise ContractPackError()
            if not SHA256.fullmatch(str(artifact["sha256"])):
                raise ContractPackError()
            if artifact["kind"] not in ARTIFACT_KINDS:
                raise ContractPackError()
            artifact_paths.append(relative_path)
        if len(set(artifact_paths)) != len(artifact_paths):
            raise ContractPackError()

        for key in ("request_schema", "response_schema", "simulator_scenarios"):
            if manifest[key] not in artifact_paths:
                raise ContractPackError()
        fixture_paths = manifest["fixture_paths"]
        if not isinstance(fixture_paths, list) or not fixture_paths:
            raise ContractPackError()
        if any(path not in artifact_paths for path in fixture_paths):
            raise ContractPackError()

    def _validate_artifacts(self, pack: ContractPack) -> None:
        for artifact in pack.manifest["artifacts"]:
            path = pack.artifact_path(str(artifact["path"]))
            if path.stat().st_size > MAX_ARTIFACT_BYTES:
                raise ContractPackError()
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest != artifact["sha256"]:
                raise ContractPackError()
            if artifact["kind"] == "json_schema":
                schema = pack.load_json_artifact(str(artifact["path"]))
                if not isinstance(schema, dict):
                    raise ContractPackError()
                try:
                    Draft202012Validator.check_schema(schema)
                except Exception as exc:
                    raise ContractPackError() from exc
