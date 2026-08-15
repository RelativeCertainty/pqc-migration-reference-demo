from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest


SCRIPT = Path(__file__).with_name("pqc_bom.py")
SPEC = importlib.util.spec_from_file_location("pqc_bom", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _clean_repo(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "--quiet")
    _git(repo, "config", "user.name", "PQC BOM Test")
    _git(repo, "config", "user.email", "pqc-bom-test@example.invalid")
    (repo / ".gitignore").write_text("evidence/\n", encoding="utf-8")
    (repo / "tracked.txt").write_text("clean\n", encoding="utf-8")
    _git(repo, "add", ".gitignore", "tracked.txt")
    _git(repo, "commit", "--quiet", "-m", "fixture")
    return repo, _git(repo, "rev-parse", "HEAD")


def _write_bound_bundle(
    output: Path,
    *,
    source_sha: str,
    source_state: str,
    image_state: str,
) -> None:
    output.mkdir(parents=True)

    def cdx(name: str, state: str) -> None:
        (output / name).write_text(
            json.dumps(
                {
                    "metadata": {
                        "properties": [
                            {"name": "portfolio:source:commit", "value": source_sha},
                            {"name": "portfolio:release:state", "value": state},
                        ]
                    }
                }
            ),
            encoding="utf-8",
        )

    def spdx(name: str, state: str) -> None:
        (output / name).write_text(
            json.dumps(
                {
                    "creationInfo": {
                        "comment": (
                            "Generation context: fixture; source commit: "
                            f"{source_sha}; release state: {state}."
                        )
                    }
                }
            ),
            encoding="utf-8",
        )

    for name in (
        "node-source-build.cdx.json",
        "portable-binary.cdx.json",
        "pqc-reference-demo.cbom.cdx.json",
    ):
        cdx(name, source_state)
    for name in ("node-source-build.spdx.json", "portable-binary.spdx.json"):
        spdx(name, source_state)
    cdx("runtime-image.cdx.json", image_state)
    spdx("runtime-image.spdx.json", image_state)
    (output / "runtime-image.subject.json").write_text(
        json.dumps(
            {
                "schema": "pqc.reference_demo.image_sbom_subject.v1",
                "release_state": image_state,
                "source_commit": source_sha,
                "image_index_digest": "sha256:" + "a" * 64,
                "platform": "linux/amd64",
                "platform_manifest_digest": "sha256:" + "b" * 64,
                "scanner_source_kind": "oci-dir",
                "registry_contacted_by_generator": False,
            }
        ),
        encoding="utf-8",
    )


def test_crypto_inventory_validates_and_locators_match() -> None:
    payload = MODULE._read_json(MODULE.INVENTORY_PATH)
    MODULE._validate_json_schema(MODULE.INVENTORY_PATH, MODULE.INVENTORY_SCHEMA_PATH)
    MODULE._validate_inventory(payload)


def test_cbom_is_deterministic_and_has_explicit_boundaries() -> None:
    inventory = MODULE._read_json(MODULE.INVENTORY_PATH)
    source_sha = "a" * 40

    first = MODULE._cbom_from_inventory(inventory, source_sha=source_sha, epoch=0)
    second = MODULE._cbom_from_inventory(inventory, source_sha=source_sha, epoch=0)

    assert first == second
    assert first["bomFormat"] == "CycloneDX"
    assert first["specVersion"] == "1.7"
    assert {item["type"] for item in first["components"]} == {"cryptographic-asset"}
    properties = {
        item["name"]: item.get("value") for item in first["metadata"]["properties"]
    }
    assert properties["portfolio:crypto:boundary:source:quality"] == "verified"
    assert properties["portfolio:crypto:boundary:runtime:quality"] == "partially_verified"
    assert properties["portfolio:crypto:boundary:edge:quality"] == "unresolved"
    assert properties["portfolio:crypto:secrets-included"] == "false"
    assert MODULE._contains_forbidden_key(first) is False


def test_inventory_rejects_edge_asset_misrepresented_as_observed() -> None:
    payload = json.loads(json.dumps(MODULE._read_json(MODULE.INVENTORY_PATH)))
    edge = next(item for item in payload["assets"] if item["boundary"] == "edge")
    edge["evidence_kind"] = "runtime_observed"

    with pytest.raises(MODULE.BOMError, match="edge assets require exact-host evidence"):
        MODULE._validate_inventory(payload)


@pytest.mark.parametrize(
    "payload",
    [
        {"privateKey": "fixture"},
        {"nested": {"secret_value": "fixture"}},
        {"array": [{"password": "fixture"}]},
        {"key-material": "fixture"},
    ],
)
def test_forbidden_sensitive_field_names_are_detected(payload: dict) -> None:
    assert MODULE._contains_forbidden_key(payload) is True


def test_source_sha_and_digest_validation_are_fail_closed() -> None:
    assert MODULE._validate_source_sha("a" * 40) == "a" * 40
    assert MODULE._validate_digest("sha256:" + "b" * 64, "fixture") == "sha256:" + "b" * 64
    for invalid in ("", "A" * 40, "a" * 39, "dirty"):
        with pytest.raises(MODULE.BOMError):
            MODULE._validate_source_sha(invalid)
    for invalid in ("", "sha256:" + "B" * 64, "sha512:" + "b" * 64, "sha256:" + "b" * 63):
        with pytest.raises(MODULE.BOMError):
            MODULE._validate_digest(invalid, "fixture")


def test_cyclonedx_schema_bundle_is_available() -> None:
    schema_dir = MODULE._cyclonedx_schema_dir()
    assert (schema_dir / "bom-1.7.SNAPSHOT.schema.json").is_file()


def test_clean_release_requires_exact_clean_checkout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, source_sha = _clean_repo(tmp_path)
    monkeypatch.setattr(MODULE, "REPO_ROOT", repo)

    MODULE._assert_clean_checkout(source_sha)
    with pytest.raises(MODULE.BOMError, match="exact clean source checkout"):
        MODULE._assert_clean_checkout("f" * 40)

    (repo / "tracked.txt").write_text("changed\n", encoding="utf-8")
    with pytest.raises(MODULE.BOMError, match="exact clean source checkout"):
        MODULE._assert_clean_checkout(source_sha)
    _git(repo, "restore", "tracked.txt")

    (repo / "untracked.txt").write_text("untracked\n", encoding="utf-8")
    with pytest.raises(MODULE.BOMError, match="exact clean source checkout"):
        MODULE._assert_clean_checkout(source_sha)


def test_cbom_clean_release_state_is_explicit() -> None:
    inventory = MODULE._read_json(MODULE.INVENTORY_PATH)
    payload = MODULE._cbom_from_inventory(
        inventory,
        source_sha="a" * 40,
        epoch=0,
        release_state=MODULE.CLEAN_RELEASE_STATE,
    )
    properties = {
        item["name"]: item.get("value") for item in payload["metadata"]["properties"]
    }
    assert properties["portfolio:source:commit"] == "a" * 40
    assert properties["portfolio:release:state"] == MODULE.CLEAN_RELEASE_STATE


def test_clean_bundle_manifest_requires_matching_bound_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, source_sha = _clean_repo(tmp_path)
    monkeypatch.setattr(MODULE, "REPO_ROOT", repo)
    tool_versions = {
        "syft": "test-syft",
        "cyclonedx-npm": "test-cyclonedx-npm",
        "cbomkit-theia": "test-cbomkit-theia",
    }
    monkeypatch.setattr(MODULE, "_tool_version", tool_versions.__getitem__)
    output = repo / "evidence" / "bom"
    _write_bound_bundle(
        output,
        source_sha=source_sha,
        source_state=MODULE.CLEAN_RELEASE_STATE,
        image_state=MODULE.CLEAN_RELEASE_STATE,
    )
    result = MODULE._manifest_command(
        SimpleNamespace(
            output=output,
            source_sha=source_sha,
            release_state=MODULE.CLEAN_RELEASE_STATE,
        )
    )
    assert result["status"] == "pass"
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["source_commit"] == source_sha
    assert manifest["release_state"] == MODULE.CLEAN_RELEASE_STATE
    assert manifest["tools"] == tool_versions

    node_cdx = json.loads((output / "node-source-build.cdx.json").read_text(encoding="utf-8"))
    node_cdx["metadata"]["properties"][1]["value"] = MODULE.DIRTY_RELEASE_STATE
    (output / "node-source-build.cdx.json").write_text(json.dumps(node_cdx), encoding="utf-8")
    with pytest.raises(MODULE.BOMError, match="does not match the bundle"):
        MODULE._manifest_command(
            SimpleNamespace(
                output=output,
                source_sha=source_sha,
                release_state=MODULE.CLEAN_RELEASE_STATE,
            )
        )


def test_superseded_image_remains_development_evidence(tmp_path: Path) -> None:
    output = tmp_path / "bom"
    _write_bound_bundle(
        output,
        source_sha="a" * 40,
        source_state=MODULE.DIRTY_RELEASE_STATE,
        image_state=MODULE.SUPERSEDED_RELEASE_STATE,
    )
    state, _receipt = MODULE._validate_bundle_bindings(
        output,
        source_sha="a" * 40,
        release_state=MODULE.DIRTY_RELEASE_STATE,
    )
    assert state == "development_evidence_bundle_with_superseded_image"
    with pytest.raises(MODULE.BOMError, match="cannot be promoted"):
        MODULE._validate_bundle_bindings(
            output,
            source_sha="a" * 40,
            release_state=MODULE.CLEAN_RELEASE_STATE,
        )


def test_cli_rejects_registry_image_source_without_contacting_network(tmp_path: Path) -> None:
    rc = MODULE.main(
        [
            "--output",
            str(tmp_path),
            "image",
            "--source-sha",
            "a" * 40,
            "--source",
            "registry:example.invalid/private/image@sha256:" + "b" * 64,
            "--index-digest",
            "sha256:" + "c" * 64,
            "--platform-digest",
            "sha256:" + "d" * 64,
            "--candidate-state",
            "development_candidate_dirty_worktree",
        ]
    )
    assert rc == 2


def test_oci_directory_verification_binds_index_and_platform(tmp_path: Path) -> None:
    layout = tmp_path / "layout"
    blobs = layout / "blobs" / "sha256"
    blobs.mkdir(parents=True)
    platform_payload = b'{"schemaVersion":2}'
    platform_hex = MODULE.hashlib.sha256(platform_payload).hexdigest()
    (blobs / platform_hex).write_bytes(platform_payload)
    index_payload = json.dumps(
        {
            "schemaVersion": 2,
            "manifests": [
                {
                    "digest": f"sha256:{platform_hex}",
                    "platform": {"os": "linux", "architecture": "amd64"},
                }
            ],
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    index_hex = MODULE.hashlib.sha256(index_payload).hexdigest()
    (blobs / index_hex).write_bytes(index_payload)
    (layout / "index.json").write_text(
        json.dumps({"schemaVersion": 2, "manifests": [{"digest": f"sha256:{index_hex}"}]}),
        encoding="utf-8",
    )

    MODULE._verify_oci_directory(
        layout,
        index_digest=f"sha256:{index_hex}",
        platform_digest=f"sha256:{platform_hex}",
        platform="linux/amd64",
    )

    with pytest.raises(MODULE.BOMError, match="does not bind"):
        MODULE._verify_oci_directory(
            layout,
            index_digest=f"sha256:{index_hex}",
            platform_digest="sha256:" + "f" * 64,
            platform="linux/amd64",
        )


def test_oci_platform_projection_points_directly_to_verified_manifest(
    tmp_path: Path,
) -> None:
    layout = tmp_path / "layout"
    blobs = layout / "blobs" / "sha256"
    blobs.mkdir(parents=True)
    platform_payload = b'{"schemaVersion":2}'
    platform_hex = MODULE.hashlib.sha256(platform_payload).hexdigest()
    (blobs / platform_hex).write_bytes(platform_payload)
    descriptor = {
        "mediaType": "application/vnd.oci.image.manifest.v1+json",
        "size": len(platform_payload),
        "digest": f"sha256:{platform_hex}",
        "platform": {"os": "linux", "architecture": "amd64"},
    }
    index_payload = json.dumps(
        {"schemaVersion": 2, "manifests": [descriptor]},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    index_hex = MODULE.hashlib.sha256(index_payload).hexdigest()
    (blobs / index_hex).write_bytes(index_payload)

    with MODULE._oci_platform_projection(
        layout,
        output=tmp_path,
        index_digest=f"sha256:{index_hex}",
        platform_digest=f"sha256:{platform_hex}",
        platform="linux/amd64",
    ) as projection:
        root = json.loads((projection / "index.json").read_text(encoding="utf-8"))
        assert root == {"schemaVersion": 2, "manifests": [descriptor]}
        assert (projection / "blobs" / "sha256" / platform_hex).read_bytes() == platform_payload

    assert not list(tmp_path.glob(".oci-platform-*"))
