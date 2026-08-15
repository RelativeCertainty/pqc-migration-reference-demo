#!/usr/bin/env python3
"""Generate and validate scoped PQC demo SBOM and CBOM evidence.

Generated evidence is always written under the repository's ignored
``artifacts/pqc-reference-demo`` tree. The script does not access a registry,
cloud API, secret store, or Git remote.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence


SCRIPT = Path(__file__).resolve()
APP_ROOT = SCRIPT.parent.parent
REPO_ROOT = APP_ROOT
DEFAULT_OUTPUT = REPO_ROOT / "artifacts" / "pqc-reference-demo" / "portable-delivery" / "bom"
INVENTORY_PATH = APP_ROOT / "bom" / "crypto-inventory.v1.json"
INVENTORY_SCHEMA_PATH = APP_ROOT / "contracts" / "crypto-inventory.v1.schema.json"
HEX40_RE = re.compile(r"^[0-9a-f]{40}$")
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
SPDX_BINDING_RE = re.compile(
    r"; source commit: (?P<source>[0-9a-f]{40}); "
    r"release state: (?P<state>[a-z0-9_]+)\.$"
)
DIRTY_RELEASE_STATE = "development_candidate_dirty_worktree"
SUPERSEDED_RELEASE_STATE = "superseded_development_candidate"
CLEAN_RELEASE_STATE = "clean_release_commit"
SOURCE_RELEASE_STATES = (DIRTY_RELEASE_STATE, CLEAN_RELEASE_STATE)
IMAGE_RELEASE_STATES = (
    DIRTY_RELEASE_STATE,
    SUPERSEDED_RELEASE_STATE,
    CLEAN_RELEASE_STATE,
)
FORBIDDEN_CBOM_KEYS = {
    "privatekey",
    "private_key",
    "secret",
    "secretvalue",
    "secret_value",
    "password",
    "token",
    "credential",
    "keymaterial",
    "key_material",
    "rawproviderresponse",
    "raw_provider_response",
}
BOUNDARIES = {"source", "runtime", "edge"}
EVIDENCE_KINDS = {
    "source_detected",
    "binary_dependency",
    "runtime_observed",
    "provider_documented",
    "declared_unverified",
}


class BOMError(RuntimeError):
    """A bounded, non-sensitive BOM generation or validation failure."""


def _utc_from_epoch(epoch: int) -> str:
    return datetime.fromtimestamp(epoch, timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _source_date_epoch() -> int:
    raw = os.environ.get("SOURCE_DATE_EPOCH", "0")
    if not re.fullmatch(r"0|[1-9][0-9]*", raw):
        raise BOMError("SOURCE_DATE_EPOCH must be a non-negative integer")
    value = int(raw)
    try:
        _utc_from_epoch(value)
    except (OverflowError, OSError, ValueError) as exc:
        raise BOMError("SOURCE_DATE_EPOCH is outside the supported range") from exc
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BOMError(f"invalid JSON artifact: {path.name}") from exc
    if not isinstance(payload, dict):
        raise BOMError(f"JSON artifact must be an object: {path.name}")
    return payload


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    encoded = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        temporary = Path(handle.name)
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    temporary.chmod(0o600)
    temporary.replace(path)


def _run(command: Sequence[str], *, cwd: Path = APP_ROOT, stdout: Path | None = None) -> str:
    environment = dict(os.environ)
    environment.setdefault("NO_COLOR", "1")
    if stdout is None:
        result = subprocess.run(
            command,
            cwd=cwd,
            env=environment,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if result.returncode:
            raise BOMError(f"tool failed: {Path(command[0]).name} (exit {result.returncode})")
        return result.stdout.strip()

    stdout.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.NamedTemporaryFile(
        mode="wb",
        dir=stdout.parent,
        prefix=f".{stdout.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        temporary = Path(handle.name)
        result = subprocess.run(
            command,
            cwd=cwd,
            env=environment,
            check=False,
            stdout=handle,
            stderr=subprocess.PIPE,
        )
        handle.flush()
        os.fsync(handle.fileno())
    if result.returncode:
        temporary.unlink(missing_ok=True)
        raise BOMError(f"tool failed: {Path(command[0]).name} (exit {result.returncode})")
    temporary.chmod(0o600)
    temporary.replace(stdout)
    return ""


def _required_tool(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise BOMError(f"required tool unavailable: {name}")
    return path


def _tool_version(name: str) -> str:
    if name == "syft":
        payload = json.loads(_run([_required_tool(name), "version", "-o", "json"]))
        return str(payload.get("version") or "unknown")
    if name == "cyclonedx-npm":
        return _run([_required_tool(name), "--version"])
    if name == "cbomkit-theia":
        # This release has no version flag. Its locally verified install receipt
        # and command name are recorded; no version is invented.
        return "locally_verified_install_version_not_reported_by_cli"
    return "unknown"


def _validate_source_sha(source_sha: str) -> str:
    if not HEX40_RE.fullmatch(source_sha):
        raise BOMError("source SHA must be exact lowercase 40-hex")
    return source_sha


def _validate_digest(digest: str, label: str) -> str:
    if not DIGEST_RE.fullmatch(digest):
        raise BOMError(f"{label} must be sha256 plus 64 lowercase hex characters")
    return digest


def _assert_clean_checkout(source_sha: str) -> None:
    """Fail closed unless ``source_sha`` is the exact clean repository HEAD.

    Ignored release evidence is intentionally outside this check. Git's normal
    porcelain output includes tracked and untracked source changes but omits
    ignored artifacts. Paths and Git stderr are never echoed in failures.
    """

    source_sha = _validate_source_sha(source_sha)
    git = _required_tool("git")
    try:
        head = _run([git, "-C", str(REPO_ROOT), "rev-parse", "HEAD"], cwd=REPO_ROOT)
        status = _run(
            [
                git,
                "-C",
                str(REPO_ROOT),
                "status",
                "--porcelain=v1",
                "--untracked-files=all",
            ],
            cwd=REPO_ROOT,
        )
    except BOMError as exc:
        raise BOMError("unable to verify exact clean source checkout") from exc
    if head != source_sha or status:
        raise BOMError("clean release evidence requires the exact clean source checkout")


def _release_state(
    args: argparse.Namespace,
    *,
    source_sha: str,
    image: bool = False,
) -> str:
    state = str(getattr(args, "release_state", DIRTY_RELEASE_STATE))
    allowed = IMAGE_RELEASE_STATES if image else SOURCE_RELEASE_STATES
    if state not in allowed:
        raise BOMError("unsupported release state")
    if state == CLEAN_RELEASE_STATE:
        _assert_clean_checkout(source_sha)
    return state


def _components_recursive(components: Iterable[Any]) -> Iterable[dict[str, Any]]:
    for item in components:
        if not isinstance(item, dict):
            continue
        yield item
        children = item.get("components")
        if isinstance(children, list):
            yield from _components_recursive(children)


def _cdx_name(component: dict[str, Any]) -> str:
    name = str(component.get("name") or "")
    group = str(component.get("group") or "")
    return f"{group}/{name}" if group else name


def _lock_components() -> list[dict[str, Any]]:
    lock = _read_json(APP_ROOT / "package-lock.json")
    packages = lock.get("packages")
    if not isinstance(packages, dict):
        raise BOMError("package-lock.json has no packages object")
    rows: list[dict[str, Any]] = []
    for path, raw in sorted(packages.items()):
        if not path or not isinstance(raw, dict):
            continue
        name = raw.get("name")
        if not name and "node_modules/" in path:
            name = path.rsplit("node_modules/", 1)[1]
        version = raw.get("version")
        if not isinstance(name, str) or not isinstance(version, str):
            raise BOMError("package-lock dependency is missing name or version")
        rows.append(
            {
                "path": path,
                "name": name,
                "version": version,
                "optional": raw.get("optional") is True,
                "dev": raw.get("dev") is True,
                "os": raw.get("os", []),
                "cpu": raw.get("cpu", []),
            }
        )
    return rows


def _reconcile_source(cdx_path: Path, spdx_path: Path, output: Path) -> dict[str, Any]:
    cdx = _read_json(cdx_path)
    spdx = _read_json(spdx_path)
    lock_rows = _lock_components()
    cdx_ids = {
        (_cdx_name(component), str(component.get("version") or ""))
        for component in _components_recursive(cdx.get("components") or [])
    }
    spdx_ids = {
        (str(package.get("name") or ""), str(package.get("versionInfo") or ""))
        for package in spdx.get("packages") or []
        if isinstance(package, dict) and str(package.get("name") or "") != "pqc-migration-reference-demo"
    }

    def missing(identities: set[tuple[str, str]]) -> list[dict[str, Any]]:
        return [row for row in lock_rows if (row["name"], row["version"]) not in identities]

    cdx_missing = missing(cdx_ids)
    spdx_missing = missing(spdx_ids)
    unexplained = [
        row
        for row in cdx_missing + spdx_missing
        if not row["optional"]
    ]
    payload = {
        "schema": "pqc.reference_demo.sbom_reconciliation.v1",
        "status": "pass" if not unexplained else "fail",
        "lockfile": {
            "path": "apps/pqc-reference-demo/package-lock.json",
            "sha256": _sha256(APP_ROOT / "package-lock.json"),
            "dependency_instances": len(lock_rows),
            "unique_name_versions": len({(row["name"], row["version"]) for row in lock_rows}),
        },
        "cyclonedx": {
            "component_name_versions": len(cdx_ids),
            "missing_lockfile_instances": cdx_missing,
        },
        "spdx": {
            "package_name_versions": len(spdx_ids),
            "missing_lockfile_instances": spdx_missing,
        },
        "policy": {
            "missing_non_optional_lockfile_instances": len(unexplained),
            "optional_platform_packages_may_be_absent": True,
            "explanation": "npm installs only optional packages compatible with the current OS/CPU; every absent lockfile instance must be marked optional and remains listed here.",
        },
    }
    _write_json_atomic(output, payload)
    if unexplained:
        raise BOMError("source SBOM reconciliation found unexplained lockfile omissions")
    return payload


def _normalize_cdx(
    path: Path,
    *,
    subject_name: str,
    subject_version: str,
    source_sha: str,
    artifact_sha256: str | None,
    generation_context: str,
    epoch: int,
    release_state: str = DIRTY_RELEASE_STATE,
) -> None:
    payload = _read_json(path)
    if payload.get("bomFormat") != "CycloneDX":
        raise BOMError(f"not a CycloneDX BOM: {path.name}")
    metadata = payload.setdefault("metadata", {})
    if not isinstance(metadata, dict):
        raise BOMError(f"invalid CycloneDX metadata: {path.name}")
    metadata["timestamp"] = _utc_from_epoch(epoch)
    metadata["authors"] = [{"name": "PQC Reference Demo BOM Pipeline"}]
    component = metadata.setdefault(
        "component",
        {
            "bom-ref": f"urn:pqc-demo:component:pqc-demo:{subject_name}",
            "type": "application",
            "name": subject_name,
            "version": subject_version,
        },
    )
    if not isinstance(component, dict):
        raise BOMError(f"invalid CycloneDX root component: {path.name}")
    component["name"] = subject_name
    component["version"] = subject_version
    component["supplier"] = {"name": "Patrick Larsen"}
    if artifact_sha256:
        component["hashes"] = [{"alg": "SHA-256", "content": artifact_sha256}]
    properties = metadata.setdefault("properties", [])
    if not isinstance(properties, list):
        raise BOMError(f"invalid CycloneDX properties: {path.name}")
    properties.extend(
        [
            {"name": "portfolio:source:commit", "value": source_sha},
            {"name": "portfolio:generation:context", "value": generation_context},
            {"name": "portfolio:release:state", "value": release_state},
        ]
    )
    payload.pop("serialNumber", None)
    _write_json_atomic(path, payload)


def _normalize_spdx(
    path: Path,
    *,
    subject_name: str,
    source_sha: str,
    artifact_sha256: str | None,
    generation_context: str,
    epoch: int,
    release_state: str = DIRTY_RELEASE_STATE,
) -> None:
    payload = _read_json(path)
    if payload.get("spdxVersion") != "SPDX-2.3":
        raise BOMError(f"not SPDX-2.3 JSON: {path.name}")
    payload["name"] = subject_name
    namespace_seed = f"{subject_name}\0{source_sha}\0{artifact_sha256 or 'none'}\0{generation_context}".encode()
    payload["documentNamespace"] = (
        "https://github.com/RelativeCertainty/pqc-migration-reference-demo/"
        f"spdx/{hashlib.sha256(namespace_seed).hexdigest()}"
    )
    creation = payload.setdefault("creationInfo", {})
    if not isinstance(creation, dict):
        raise BOMError(f"invalid SPDX creationInfo: {path.name}")
    creators = creation.setdefault("creators", [])
    if not isinstance(creators, list):
        raise BOMError(f"invalid SPDX creators: {path.name}")
    creator = "Person: Patrick Larsen"
    if creator not in creators:
        creators.append(creator)
    creation["created"] = _utc_from_epoch(epoch)
    creation["comment"] = (
        f"Generation context: {generation_context}; source commit: {source_sha}; "
        f"release state: {release_state}."
    )
    if artifact_sha256:
        packages = payload.get("packages")
        if not isinstance(packages, list) or not packages:
            raise BOMError(f"SPDX document has no packages: {path.name}")
        root = packages[0]
        if not isinstance(root, dict):
            raise BOMError(f"SPDX root package invalid: {path.name}")
        checksums = root.setdefault("checksums", [])
        if not isinstance(checksums, list):
            raise BOMError(f"SPDX checksums invalid: {path.name}")
        checksums.append({"algorithm": "SHA256", "checksumValue": artifact_sha256})
    _write_json_atomic(path, payload)


def _semantic_validate_cdx(path: Path, expected_version: str) -> dict[str, int | str]:
    payload = _read_json(path)
    if payload.get("bomFormat") != "CycloneDX" or payload.get("specVersion") != expected_version:
        raise BOMError(f"unexpected CycloneDX version: {path.name}")
    components = list(_components_recursive(payload.get("components") or []))
    dependencies = payload.get("dependencies")
    if not isinstance(dependencies, list):
        raise BOMError(f"CycloneDX dependencies are missing: {path.name}")
    return {"format": "CycloneDX", "components": len(components), "dependencies": len(dependencies)}


def _semantic_validate_spdx(path: Path) -> dict[str, int | str]:
    payload = _read_json(path)
    if payload.get("spdxVersion") != "SPDX-2.3":
        raise BOMError(f"unexpected SPDX version: {path.name}")
    if payload.get("dataLicense") != "CC0-1.0":
        raise BOMError(f"unexpected SPDX data license: {path.name}")
    packages = payload.get("packages")
    relationships = payload.get("relationships")
    if not isinstance(packages, list) or not isinstance(relationships, list):
        raise BOMError(f"SPDX package/relationship data missing: {path.name}")
    return {"format": "SPDX-2.3", "packages": len(packages), "relationships": len(relationships)}


def _cyclonedx_schema_dir() -> Path:
    repository_schema = (
        APP_ROOT
        / "node_modules"
        / "@cyclonedx"
        / "cyclonedx-library"
        / "res"
        / "schema"
    )
    if repository_schema.is_dir():
        return repository_schema

    repository_executable = APP_ROOT / "node_modules" / ".bin" / "cyclonedx-npm"
    executable = (
        repository_executable.resolve()
        if repository_executable.is_file()
        else Path(_required_tool("cyclonedx-npm")).resolve()
    )
    for parent in executable.parents:
        candidate = parent / "@cyclonedx" / "cyclonedx-library" / "res" / "schema"
        if candidate.is_dir():
            return candidate
        candidate = parent / "node_modules" / "@cyclonedx" / "cyclonedx-library" / "res" / "schema"
        if candidate.is_dir():
            return candidate
    raise BOMError("CycloneDX 1.7 schema bundle was not found beside cyclonedx-npm")


def _validate_json_schema(instance_path: Path, schema_path: Path, *, schema_dir: Path | None = None) -> None:
    try:
        import jsonschema
        from referencing import Registry, Resource
    except ImportError as exc:
        raise BOMError("python jsonschema/referencing packages are required") from exc
    instance = _read_json(instance_path)
    schema = _read_json(schema_path)
    registry = Registry()
    if schema_dir:
        for candidate in schema_dir.glob("*.json"):
            candidate_payload = _read_json(candidate)
            registry = registry.with_resource(candidate.name, Resource.from_contents(candidate_payload))
    validator = jsonschema.Draft7Validator(schema, registry=registry)
    errors = sorted(validator.iter_errors(instance), key=lambda item: list(item.absolute_path))
    if errors:
        raise BOMError(f"schema validation failed: {instance_path.name} ({len(errors)} errors)")


def _validate_inventory(payload: dict[str, Any]) -> None:
    boundaries = payload.get("boundaries")
    if not isinstance(boundaries, list) or {row.get("id") for row in boundaries if isinstance(row, dict)} != BOUNDARIES:
        raise BOMError("crypto inventory must contain exactly source/runtime/edge boundaries")
    assets = payload.get("assets")
    if not isinstance(assets, list) or not assets:
        raise BOMError("crypto inventory must contain assets")
    refs: set[str] = set()
    for asset in assets:
        if not isinstance(asset, dict):
            raise BOMError("crypto inventory asset must be an object")
        ref = str(asset.get("bom_ref") or "")
        if ref in refs:
            raise BOMError("crypto inventory has duplicate bom_ref")
        refs.add(ref)
        if asset.get("boundary") not in BOUNDARIES or asset.get("evidence_kind") not in EVIDENCE_KINDS:
            raise BOMError("crypto inventory has an invalid boundary or evidence kind")
        if asset.get("boundary") == "edge" and asset.get("evidence_kind") != "declared_unverified":
            raise BOMError("edge assets require exact-host evidence before they may be represented as observed")
        locators = asset.get("evidence_locators")
        if not isinstance(locators, list) or not locators:
            raise BOMError("crypto inventory asset is missing evidence locators")
        for locator in locators:
            if not isinstance(locator, dict):
                raise BOMError("crypto inventory evidence locator must be an object")
            path = APP_ROOT / str(locator.get("path") or "")
            line = locator.get("line")
            needle = str(locator.get("needle") or "")
            if not path.is_file() or not isinstance(line, int):
                raise BOMError("crypto inventory evidence locator is invalid")
            lines = path.read_text(encoding="utf-8").splitlines()
            if line > len(lines) or needle not in lines[line - 1]:
                raise BOMError("crypto inventory evidence locator no longer matches source")
    if _contains_forbidden_key(payload):
        raise BOMError("crypto inventory contains a forbidden sensitive field name")


def _contains_forbidden_key(value: Any) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = re.sub(r"[^a-z0-9_]", "", str(key).lower())
            if normalized in FORBIDDEN_CBOM_KEYS:
                return True
            if _contains_forbidden_key(child):
                return True
    elif isinstance(value, list):
        return any(_contains_forbidden_key(item) for item in value)
    return False


def _cbom_from_inventory(
    inventory: dict[str, Any],
    *,
    source_sha: str,
    epoch: int,
    release_state: str = DIRTY_RELEASE_STATE,
) -> dict[str, Any]:
    version = str(inventory["product"]["version"])
    components: list[dict[str, Any]] = []
    for asset in sorted(inventory["assets"], key=lambda row: row["bom_ref"]):
        properties = [
            {"name": "portfolio:crypto:boundary", "value": asset["boundary"]},
            {"name": "portfolio:evidence:quality", "value": asset["evidence_quality"]},
            {"name": "portfolio:crypto:evidence-kind", "value": asset["evidence_kind"]},
            {"name": "portfolio:crypto:observation-state", "value": asset["observation_state"]},
            {"name": "portfolio:crypto:limitation", "value": asset["limitation"]},
        ]
        for locator in asset["evidence_locators"]:
            properties.append(
                {
                    "name": "portfolio:crypto:evidence-locator",
                    "value": f"apps/pqc-reference-demo/{locator['path']}:{locator['line']}",
                }
            )
        components.append(
            {
                "bom-ref": asset["bom_ref"],
                "type": "cryptographic-asset",
                "name": asset["name"],
                "version": asset["version"],
                "description": asset["limitation"],
                "cryptoProperties": asset["crypto_properties"],
                "properties": properties,
            }
        )
    dependencies = [{"ref": component["bom-ref"], "dependsOn": []} for component in components]
    boundaries = {row["id"]: row for row in inventory["boundaries"]}
    metadata_properties = [
        {"name": "portfolio:source:commit", "value": source_sha},
        {"name": "portfolio:release:state", "value": release_state},
        {"name": "portfolio:crypto:secrets-included", "value": "false"},
        {
            "name": "portfolio:crypto:scope",
            "value": "curated source/runtime boundary inventory; edge remains unresolved without exact-host evidence",
        },
    ]
    for boundary in sorted(BOUNDARIES):
        row = boundaries[boundary]
        metadata_properties.extend(
            [
                {"name": f"portfolio:crypto:boundary:{boundary}:quality", "value": row["evidence_quality"]},
                {"name": f"portfolio:crypto:boundary:{boundary}:state", "value": row["observation_state"]},
                {"name": f"portfolio:crypto:boundary:{boundary}:limitation", "value": row["limitation"]},
            ]
        )
    return {
        "$schema": "http://cyclonedx.org/schema/bom-1.7.schema.json",
        "bomFormat": "CycloneDX",
        "specVersion": "1.7",
        "version": 1,
        "metadata": {
            "timestamp": _utc_from_epoch(epoch),
            "lifecycles": [{"phase": "post-build"}],
            "authors": [{"name": "PQC Reference Demo BOM Pipeline"}],
            "tools": {
                "components": [
                    {
                        "type": "application",
                        "name": "pqc_bom.py",
                        "version": "1.0.0",
                    }
                ]
            },
            "component": {
                "bom-ref": "urn:pqc-demo:component:pqc-demo:cbom",
                "type": "application",
                "name": "pqc-reference-demo",
                "version": version,
                "supplier": {"name": "Patrick Larsen"},
            },
            "properties": metadata_properties,
        },
        "components": components,
        "dependencies": dependencies,
    }


def _source_command(args: argparse.Namespace) -> dict[str, Any]:
    source_sha = _validate_source_sha(args.source_sha)
    release_state = _release_state(args, source_sha=source_sha)
    epoch = _source_date_epoch()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    cdx = output / "node-source-build.cdx.json"
    spdx = output / "node-source-build.spdx.json"
    _run(
        [
            _required_tool("cyclonedx-npm"),
            "--spec-version",
            "1.7",
            "--output-reproducible",
            "--validate",
            "--output-format",
            "JSON",
            "--output-file",
            str(cdx),
            str(APP_ROOT / "package.json"),
        ]
    )
    _run(
        [
            _required_tool("npm"),
            "sbom",
            "--sbom-format=spdx",
            "--sbom-type=application",
        ],
        stdout=spdx,
    )
    context = "lockfile-backed installed Node source/build dependency graph"
    _normalize_cdx(
        cdx,
        subject_name="pqc-reference-demo-node-source-build",
        subject_version="0.1.0",
        source_sha=source_sha,
        artifact_sha256=None,
        generation_context=context,
        epoch=epoch,
        release_state=release_state,
    )
    _normalize_spdx(
        spdx,
        subject_name="pqc-reference-demo-node-source-build",
        source_sha=source_sha,
        artifact_sha256=None,
        generation_context=context,
        epoch=epoch,
        release_state=release_state,
    )
    reconciliation = output / "node-source-build.reconciliation.json"
    _reconcile_source(cdx, spdx, reconciliation)
    return {
        "scope": "node-source-build",
        "cyclonedx": _semantic_validate_cdx(cdx, "1.7"),
        "spdx": _semantic_validate_spdx(spdx),
        "artifacts": [path.name for path in (cdx, spdx, reconciliation)],
    }


def _syft_pair(
    source: str,
    *,
    output: Path,
    stem: str,
    subject_name: str,
    version: str,
    source_sha: str,
    artifact_sha256: str | None,
    generation_context: str,
    epoch: int,
    platform: str | None = None,
    release_state: str = DIRTY_RELEASE_STATE,
) -> dict[str, Any]:
    cdx = output / f"{stem}.cdx.json"
    spdx = output / f"{stem}.spdx.json"
    command = [
            _required_tool("syft"),
            "scan",
            source,
            "--source-name",
            subject_name,
            "--source-version",
            version,
            "--quiet",
            "-o",
            f"cyclonedx-json={cdx}",
            "-o",
            f"spdx-json={spdx}",
        ]
    if platform:
        command.extend(["--platform", platform])
    _run(command)
    _normalize_cdx(
        cdx,
        subject_name=subject_name,
        subject_version=version,
        source_sha=source_sha,
        artifact_sha256=artifact_sha256,
        generation_context=generation_context,
        epoch=epoch,
        release_state=release_state,
    )
    _normalize_spdx(
        spdx,
        subject_name=subject_name,
        source_sha=source_sha,
        artifact_sha256=artifact_sha256,
        generation_context=generation_context,
        epoch=epoch,
        release_state=release_state,
    )
    return {
        "cyclonedx": _semantic_validate_cdx(cdx, "1.6"),
        "spdx": _semantic_validate_spdx(spdx),
        "artifacts": [cdx.name, spdx.name],
    }


def _binary_command(args: argparse.Namespace) -> dict[str, Any]:
    source_sha = _validate_source_sha(args.source_sha)
    release_state = _release_state(args, source_sha=source_sha)
    binary = args.binary.resolve()
    if not binary.is_file():
        raise BOMError("portable binary does not exist")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    digest = _sha256(binary)
    result = _syft_pair(
        f"file:{binary}",
        output=output,
        stem="portable-binary",
        subject_name="pqc-reference-demo-portable",
        version="0.1.0",
        source_sha=source_sha,
        artifact_sha256=digest,
        generation_context="exact compiled portable Go binary",
        epoch=_source_date_epoch(),
        release_state=release_state,
    )
    result.update({"scope": "portable-binary", "subject_sha256": digest})
    return result


def _verify_oci_directory(
    layout: Path,
    *,
    index_digest: str,
    platform_digest: str,
    platform: str,
) -> None:
    if platform != "linux/amd64":
        raise BOMError("only the reviewed linux/amd64 image BOM platform is supported")
    index_path = layout / "index.json"
    if not index_path.is_file():
        raise BOMError("OCI directory is missing index.json")
    root = _read_json(index_path)
    descriptors = root.get("manifests")
    if not isinstance(descriptors, list) or not any(
        isinstance(item, dict) and item.get("digest") == index_digest for item in descriptors
    ):
        raise BOMError("OCI layout does not reference the supplied image index digest")

    def verified_blob(digest: str, label: str) -> Path:
        blob = layout / "blobs" / "sha256" / digest.split(":", 1)[1]
        if not blob.is_file() or _sha256(blob) != digest.split(":", 1)[1]:
            raise BOMError(f"OCI {label} blob is missing or fails digest verification")
        return blob

    index_blob = _read_json(verified_blob(index_digest, "index"))
    manifests = index_blob.get("manifests")
    if not isinstance(manifests, list):
        raise BOMError("OCI index has no platform manifest descriptors")
    match = [
        item
        for item in manifests
        if isinstance(item, dict)
        and item.get("digest") == platform_digest
        and isinstance(item.get("platform"), dict)
        and item["platform"].get("os") == "linux"
        and item["platform"].get("architecture") == "amd64"
    ]
    if len(match) != 1:
        raise BOMError("OCI index does not bind the supplied linux/amd64 platform digest")
    verified_blob(platform_digest, "linux/amd64 manifest")


def _oci_platform_descriptor(
    layout: Path,
    *,
    index_digest: str,
    platform_digest: str,
    platform: str,
) -> dict[str, Any]:
    """Return the digest-bound platform descriptor from a nested OCI index."""
    if platform != "linux/amd64":
        raise BOMError("only the reviewed linux/amd64 image BOM platform is supported")
    index_blob = _read_json(layout / "blobs" / "sha256" / index_digest.split(":", 1)[1])
    manifests = index_blob.get("manifests")
    if not isinstance(manifests, list):
        raise BOMError("OCI index has no platform manifest descriptors")
    matches = [
        item
        for item in manifests
        if isinstance(item, dict)
        and item.get("digest") == platform_digest
        and isinstance(item.get("platform"), dict)
        and item["platform"].get("os") == "linux"
        and item["platform"].get("architecture") == "amd64"
    ]
    if len(matches) != 1:
        raise BOMError("OCI index does not bind the supplied linux/amd64 platform digest")
    return dict(matches[0])


@contextmanager
def _oci_platform_projection(
    layout: Path,
    *,
    output: Path,
    index_digest: str,
    platform_digest: str,
    platform: str,
) -> Iterable[Path]:
    """Project a nested multi-platform OCI index for single-platform scanners.

    Syft expects the root ``index.json`` to point directly to an image
    manifest. Registry exports may instead preserve the remote image index as
    a nested descriptor. The projection changes no blobs: it reuses the
    digest-verified blob directory and writes a temporary root index containing
    only the already-verified platform descriptor.
    """
    descriptor = _oci_platform_descriptor(
        layout,
        index_digest=index_digest,
        platform_digest=platform_digest,
        platform=platform,
    )
    with tempfile.TemporaryDirectory(prefix=".oci-platform-", dir=output) as raw:
        projection = Path(raw)
        (projection / "blobs").symlink_to(layout / "blobs", target_is_directory=True)
        (projection / "oci-layout").write_text(
            '{"imageLayoutVersion":"1.0.0"}\n', encoding="utf-8"
        )
        _write_json_atomic(
            projection / "index.json",
            {"schemaVersion": 2, "manifests": [descriptor]},
        )
        yield projection


def _image_command(args: argparse.Namespace) -> dict[str, Any]:
    source_sha = _validate_source_sha(args.source_sha)
    release_state = _release_state(args, source_sha=source_sha, image=True)
    index_digest = _validate_digest(args.index_digest, "image index digest")
    platform_digest = _validate_digest(args.platform_digest, "platform manifest digest")
    if not args.source.startswith("oci-dir:"):
        raise BOMError("image source must be a local oci-dir: subject")
    raw_path = Path(args.source.split(":", 1)[1]).resolve()
    if not raw_path.is_dir():
        raise BOMError("local OCI image source does not exist")
    _verify_oci_directory(
        raw_path,
        index_digest=index_digest,
        platform_digest=platform_digest,
        platform="linux/amd64",
    )
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    with _oci_platform_projection(
        raw_path,
        output=output,
        index_digest=index_digest,
        platform_digest=platform_digest,
        platform="linux/amd64",
    ) as projection:
        result = _syft_pair(
            f"oci-dir:{projection}",
            output=output,
            stem="runtime-image",
            subject_name="pqc-reference-demo-runtime-image",
            version="0.1.0" if release_state == CLEAN_RELEASE_STATE else "0.1.0-candidate",
            source_sha=source_sha,
            artifact_sha256=platform_digest.split(":", 1)[1],
            generation_context=(
                f"local OCI copy of immutable index {index_digest}; linux/amd64 platform manifest {platform_digest}"
            ),
            epoch=_source_date_epoch(),
            platform="linux/amd64",
            release_state=release_state,
        )
    receipt = {
        "schema": "pqc.reference_demo.image_sbom_subject.v1",
        "release_state": release_state,
        "source_commit": source_sha,
        "image_index_digest": index_digest,
        "platform": "linux/amd64",
        "platform_manifest_digest": platform_digest,
        "scanner_source_kind": args.source.split(":", 1)[0],
        "registry_contacted_by_generator": False,
    }
    receipt_path = output / "runtime-image.subject.json"
    _write_json_atomic(receipt_path, receipt)
    result.update(
        {
            "scope": "runtime-image",
            "image_index_digest": index_digest,
            "platform_manifest_digest": platform_digest,
            "artifacts": result["artifacts"] + [receipt_path.name],
        }
    )
    return result


def _cbom_command(args: argparse.Namespace) -> dict[str, Any]:
    source_sha = _validate_source_sha(args.source_sha)
    release_state = _release_state(args, source_sha=source_sha)
    epoch = _source_date_epoch()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    _validate_json_schema(INVENTORY_PATH, INVENTORY_SCHEMA_PATH)
    inventory = _read_json(INVENTORY_PATH)
    _validate_inventory(inventory)

    # Supplemental discovery is deliberately constrained to detectors that do
    # not search or emit key/secret values. This installed theia release emits
    # CycloneDX 1.6, so it is retained as private corroboration, not converted
    # into or represented as the normative 1.7 CBOM.
    supplemental = output / "cbomkit-theia-source-discovery.cdx-1.6.json"
    _run(
        [
            _required_tool("cbomkit-theia"),
            "--log-level",
            "error",
            "--plugins",
            "certificates,opensslconf",
            "--ignore",
            "node_modules/,.wrangler/,dist/,portable/bin/,portable/generated-ui/",
            "dir",
            str(APP_ROOT),
        ],
        stdout=supplemental,
    )
    supplemental_payload = _read_json(supplemental)
    if supplemental_payload.get("specVersion") != "1.6":
        raise BOMError("unexpected CBOMkit-theia output version")
    if _contains_forbidden_key(supplemental_payload):
        raise BOMError("supplemental CBOM discovery contains forbidden sensitive field names")

    cbom = _cbom_from_inventory(
        inventory,
        source_sha=source_sha,
        epoch=epoch,
        release_state=release_state,
    )
    cbom_path = output / "pqc-reference-demo.cbom.cdx.json"
    _write_json_atomic(cbom_path, cbom)
    schema_dir = _cyclonedx_schema_dir()
    _validate_json_schema(cbom_path, schema_dir / "bom-1.7.SNAPSHOT.schema.json", schema_dir=schema_dir)
    _semantic_validate_cdx(cbom_path, "1.7")
    return {
        "scope": "cryptographic-assets",
        "normative_spec_version": "1.7",
        "asset_count": len(cbom["components"]),
        "boundaries": sorted(BOUNDARIES),
        "edge_observation_state": "unresolved",
        "sensitive_values_included": False,
        "supplemental_cbomkit_spec_version": "1.6",
        "artifacts": [cbom_path.name, supplemental.name],
    }


def _validate_command(args: argparse.Namespace) -> dict[str, Any]:
    output = args.output.resolve()
    required = {
        "node-source-build.cdx.json": ("cdx", "1.7"),
        "node-source-build.spdx.json": ("spdx", None),
        "portable-binary.cdx.json": ("cdx", "1.6"),
        "portable-binary.spdx.json": ("spdx", None),
        "pqc-reference-demo.cbom.cdx.json": ("cdx-schema", "1.7"),
    }
    if args.require_image:
        required.update(
            {
                "runtime-image.cdx.json": ("cdx", "1.6"),
                "runtime-image.spdx.json": ("spdx", None),
                "runtime-image.subject.json": ("image-receipt", None),
            }
        )
    results: dict[str, Any] = {}
    schema_dir = _cyclonedx_schema_dir()
    for name, (kind, version) in required.items():
        path = output / name
        if not path.is_file():
            raise BOMError(f"required BOM artifact is missing: {name}")
        if kind == "cdx":
            results[name] = _semantic_validate_cdx(path, str(version))
        elif kind == "cdx-schema":
            _validate_json_schema(path, schema_dir / "bom-1.7.SNAPSHOT.schema.json", schema_dir=schema_dir)
            results[name] = _semantic_validate_cdx(path, str(version))
        elif kind == "spdx":
            results[name] = _semantic_validate_spdx(path)
        else:
            receipt = _read_json(path)
            _validate_digest(str(receipt.get("image_index_digest") or ""), "image index digest")
            _validate_digest(str(receipt.get("platform_manifest_digest") or ""), "platform manifest digest")
            results[name] = {"format": "portfolio image subject receipt"}
    reconciliation = _read_json(output / "node-source-build.reconciliation.json")
    if reconciliation.get("status") != "pass":
        raise BOMError("source SBOM reconciliation does not pass")
    return {"scope": "validation", "status": "pass", "artifacts": results}


def _cyclonedx_release_binding(path: Path) -> tuple[str, str]:
    payload = _read_json(path)
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        raise BOMError(f"BOM release metadata is missing: {path.name}")
    properties = metadata.get("properties")
    if not isinstance(properties, list):
        raise BOMError(f"BOM release properties are missing: {path.name}")

    def exact_value(name: str) -> str:
        values = [
            item.get("value")
            for item in properties
            if isinstance(item, dict) and item.get("name") == name
        ]
        if len(values) != 1 or not isinstance(values[0], str):
            raise BOMError(f"BOM has an ambiguous release binding: {path.name}")
        return values[0]

    source_sha = _validate_source_sha(exact_value("portfolio:source:commit"))
    release_state = exact_value("portfolio:release:state")
    if release_state not in IMAGE_RELEASE_STATES:
        raise BOMError(f"BOM has an unsupported release state: {path.name}")
    return source_sha, release_state


def _spdx_release_binding(path: Path) -> tuple[str, str]:
    payload = _read_json(path)
    creation = payload.get("creationInfo")
    comment = creation.get("comment") if isinstance(creation, dict) else None
    match = SPDX_BINDING_RE.search(comment) if isinstance(comment, str) else None
    if not match:
        raise BOMError(f"SPDX release binding is missing: {path.name}")
    source_sha = _validate_source_sha(match.group("source"))
    release_state = match.group("state")
    if release_state not in IMAGE_RELEASE_STATES:
        raise BOMError(f"SPDX has an unsupported release state: {path.name}")
    return source_sha, release_state


def _validate_bundle_bindings(
    output: Path,
    *,
    source_sha: str,
    release_state: str,
) -> tuple[str, dict[str, Any]]:
    """Validate all normative BOM subjects before hashing a bundle manifest."""

    image_receipt_path = output / "runtime-image.subject.json"
    if not image_receipt_path.is_file():
        raise BOMError("runtime image subject receipt is required for a bundle manifest")
    receipt = _read_json(image_receipt_path)
    if receipt.get("source_commit") != source_sha:
        raise BOMError("runtime image subject does not match the requested source commit")
    image_state = receipt.get("release_state")
    if image_state not in IMAGE_RELEASE_STATES:
        raise BOMError("runtime image subject has an unsupported release state")
    index_digest = _validate_digest(
        str(receipt.get("image_index_digest") or ""),
        "image index digest",
    )
    _validate_digest(
        str(receipt.get("platform_manifest_digest") or ""),
        "platform manifest digest",
    )
    if receipt.get("platform") != "linux/amd64" or receipt.get("scanner_source_kind") != "oci-dir":
        raise BOMError("runtime image subject has an unsupported platform or source kind")
    if receipt.get("registry_contacted_by_generator") is not False:
        raise BOMError("runtime image subject does not preserve the offline generator boundary")

    if image_state == SUPERSEDED_RELEASE_STATE:
        if release_state != DIRTY_RELEASE_STATE:
            raise BOMError("a superseded image cannot be promoted into a clean release bundle")
        component_state = DIRTY_RELEASE_STATE
        bundle_state = "development_evidence_bundle_with_superseded_image"
    else:
        if image_state != release_state:
            raise BOMError("runtime image subject release state does not match the bundle")
        component_state = release_state
        bundle_state = release_state

    bindings = {
        "node-source-build.cdx.json": _cyclonedx_release_binding,
        "node-source-build.spdx.json": _spdx_release_binding,
        "portable-binary.cdx.json": _cyclonedx_release_binding,
        "portable-binary.spdx.json": _spdx_release_binding,
        "pqc-reference-demo.cbom.cdx.json": _cyclonedx_release_binding,
        "runtime-image.cdx.json": _cyclonedx_release_binding,
        "runtime-image.spdx.json": _spdx_release_binding,
    }
    for name, reader in bindings.items():
        path = output / name
        if not path.is_file():
            raise BOMError(f"required bound artifact is missing: {name}")
        observed_sha, observed_state = reader(path)
        expected_state = image_state if name.startswith("runtime-image.") else component_state
        if observed_sha != source_sha or observed_state != expected_state:
            raise BOMError(f"artifact release binding does not match the bundle: {name}")

    sbob_path = output / "pqc-reference-demo.sbob.observed.json"
    if sbob_path.is_file():
        sbob = _read_json(sbob_path)
        subject = sbob.get("subject")
        boundaries = sbob.get("release_boundaries")
        if not isinstance(subject, dict) or not isinstance(boundaries, dict):
            raise BOMError("SBOB subject or release boundary is missing")
        expected_subject_state = (
            "clean_release_commit"
            if component_state == CLEAN_RELEASE_STATE
            else "dirty_worktree_development_candidate"
        )
        expected_commit: str | None = source_sha if component_state == CLEAN_RELEASE_STATE else None
        expected_clean = component_state == CLEAN_RELEASE_STATE
        if (
            subject.get("source_state") != expected_subject_state
            or subject.get("source_commit") != expected_commit
            or subject.get("source_commit_bound") is not expected_clean
            or subject.get("image_revision_matches_source_commit") is not expected_clean
            or subject.get("oci_index_digest") != index_digest
            or boundaries.get("clean_release") is not expected_clean
        ):
            raise BOMError("SBOB release binding does not match the bundle")

    return bundle_state, receipt


def _manifest_command(args: argparse.Namespace) -> dict[str, Any]:
    source_sha = _validate_source_sha(args.source_sha)
    release_state = _release_state(args, source_sha=source_sha)
    output = args.output.resolve()
    bundle_state, _receipt = _validate_bundle_bindings(
        output,
        source_sha=source_sha,
        release_state=release_state,
    )
    files = sorted(path for path in output.iterdir() if path.is_file() and path.name != "manifest.json")
    if not files:
        raise BOMError("no BOM artifacts exist for manifest generation")
    payload = {
        "schema": "pqc.reference_demo.bom_manifest.v1",
        "release_state": bundle_state,
        "source_commit": source_sha,
        "generated_at": _utc_from_epoch(_source_date_epoch()),
        "tools": {
            "syft": _tool_version("syft"),
            "cyclonedx-npm": _tool_version("cyclonedx-npm"),
            "cbomkit-theia": _tool_version("cbomkit-theia"),
        },
        "claims": {
            "cisa_2025_11_field_compliance": "not_evaluated_not_claimed",
            "cyclonedx_1_7_cbom_schema": "validated",
            "keys_or_secret_values_in_cbom": False,
            "edge_runtime_observation": "unresolved",
        },
        "files": [
            {"name": path.name, "sha256": _sha256(path), "size": path.stat().st_size}
            for path in files
        ],
    }
    path = output / "manifest.json"
    _write_json_atomic(path, payload)
    return {"scope": "manifest", "status": "pass", "artifacts": [path.name]}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name in ("source", "cbom", "manifest"):
        child = subparsers.add_parser(name)
        child.add_argument("--source-sha", required=True)
        child.add_argument(
            "--release-state",
            choices=SOURCE_RELEASE_STATES,
            default=DIRTY_RELEASE_STATE,
        )
    binary = subparsers.add_parser("binary")
    binary.add_argument("--source-sha", required=True)
    binary.add_argument("--binary", required=True, type=Path)
    binary.add_argument(
        "--release-state",
        choices=SOURCE_RELEASE_STATES,
        default=DIRTY_RELEASE_STATE,
    )
    image = subparsers.add_parser("image")
    image.add_argument("--source-sha", required=True)
    image.add_argument("--source", required=True)
    image.add_argument("--index-digest", required=True)
    image.add_argument("--platform-digest", required=True)
    image.add_argument(
        "--release-state",
        "--candidate-state",
        dest="release_state",
        required=True,
        choices=IMAGE_RELEASE_STATES,
    )
    validate = subparsers.add_parser("validate")
    validate.add_argument("--require-image", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    commands = {
        "source": _source_command,
        "binary": _binary_command,
        "image": _image_command,
        "cbom": _cbom_command,
        "validate": _validate_command,
        "manifest": _manifest_command,
    }
    try:
        result = commands[args.command](args)
    except BOMError as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps({"status": "pass", **result}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
