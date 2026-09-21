"""Small owned document-signing reference application, not a production signer.

The two application versions demonstrate an ECDSA-to-ML-DSA API/algorithm
migration on ONE installed OpenSSL library. This is not a library upgrade.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

VERSIONS = {"legacy-v1": "ECDSA-P256-SHA256", "pqc-v2": "ML-DSA-65"}
POLICIES = {"legacy-only", "pqc-only", "legacy-readback"}
ENV = {"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"}
# DER AlgorithmIdentifier encodings from RFC 5480 and FIPS 204's assigned OID.
# Checking the actual key prevents algorithm labels being accepted on faith.
KEY_ALGORITHMS = {
    "legacy-v1": bytes.fromhex("301306072a8648ce3d020106082a8648ce3d030107"),
    "pqc-v2": bytes.fromhex("300b0609608648016503040312"),
}


def _tlv(data: bytes, position: int = 0) -> tuple[int, int]:
    """Return content offset/end for bounded DER; reject indefinite lengths."""
    if len(data) < position + 2:
        raise ValueError("invalid key encoding")
    first = data[position + 1]
    if first < 128:
        start, length = position + 2, first
    else:
        count = first & 127
        if not 1 <= count <= 4 or len(data) < position + 2 + count:
            raise ValueError("invalid key encoding")
        start = position + 2 + count
        length = int.from_bytes(data[position + 2:start], "big")
    if start + length > len(data):
        raise ValueError("invalid key encoding")
    return start, start + length


def key_algorithm_identifier(public_der: bytes) -> bytes:
    if not public_der or public_der[0] != 0x30:
        raise ValueError("invalid public key")
    start, end = _tlv(public_der)
    if end != len(public_der) or public_der[start] != 0x30:
        raise ValueError("invalid public key")
    _, algorithm_end = _tlv(public_der, start)
    return public_der[start:algorithm_end]


def _key_matches(key: Path, version: str, temporary: Path, *, public: bool) -> bool:
    destination = temporary / "key-public.der"
    arguments = ["pkey", "-in", str(key), "-pubout", "-outform", "DER", "-out", str(destination)]
    if public:
        arguments.append("-pubin")
    if not _openssl(arguments) or destination.stat().st_size > 32 * 1024:
        return False
    return key_algorithm_identifier(destination.read_bytes()) == KEY_ALGORITHMS[version]


def signing_input(version: str, document: bytes) -> bytes:
    if version not in VERSIONS:
        raise ValueError("unsupported application version")
    metadata = {"type": "pqc.reference.signed-document.v1", "application_version": version,
                "algorithm": VERSIONS[version], "document_sha256": hashlib.sha256(document).hexdigest()}
    return json.dumps(metadata, sort_keys=True, separators=(",", ":")).encode()


def _openssl(arguments: list[str]) -> bool:
    result = subprocess.run(["/usr/bin/openssl", *arguments], env=ENV, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, timeout=15, check=False)
    return result.returncode == 0


def sign(document: Path, private_key: Path, envelope_path: Path, version: str) -> None:
    if document.stat().st_size > 1024 * 1024:
        raise ValueError("document too large")
    material = signing_input(version, document.read_bytes())
    with tempfile.TemporaryDirectory(prefix="sign-", dir=envelope_path.parent) as directory:
        temporary = Path(directory)
        if not _key_matches(private_key, version, temporary, public=False):
            raise ValueError("algorithm key mismatch")
        source, signature = temporary / "input", temporary / "signature"
        source.write_bytes(material)
        arguments = ["pkeyutl", "-sign", "-rawin", "-inkey", str(private_key), "-in", str(source), "-out", str(signature)]
        if version == "legacy-v1":
            arguments.extend(["-digest", "sha256"])
        if not _openssl(arguments):
            raise ValueError("signing failed")
        envelope = json.loads(material)
        envelope["signature"] = base64.b64encode(signature.read_bytes()).decode("ascii")
        with os.fdopen(os.open(envelope_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), "w") as output:
            json.dump(envelope, output, sort_keys=True)


def verify(document: Path, public_key: Path, envelope_path: Path, policy: str) -> bool:
    if policy not in POLICIES:
        return False
    try:
        if envelope_path.stat().st_size > 32 * 1024 or document.stat().st_size > 1024 * 1024:
            return False
        envelope = json.loads(envelope_path.read_text())
        if not isinstance(envelope, dict) or set(envelope) != {"type", "application_version", "algorithm", "document_sha256", "signature"}:
            return False
        version = envelope["application_version"]
        if policy == "pqc-only" and version != "pqc-v2":
            return False
        if policy == "legacy-only" and version != "legacy-v1":
            return False
        expected = signing_input(version, document.read_bytes())
        if any(envelope[key] != value for key, value in json.loads(expected).items()):
            return False
        signature_bytes = base64.b64decode(envelope["signature"], validate=True)
        with tempfile.TemporaryDirectory(prefix="verify-", dir=envelope_path.parent) as directory:
            temporary = Path(directory)
            if not _key_matches(public_key, version, temporary, public=True):
                return False
            source, signature = temporary / "input", temporary / "signature"
            source.write_bytes(expected)
            signature.write_bytes(signature_bytes)
            arguments = ["pkeyutl", "-verify", "-rawin", "-pubin", "-inkey", str(public_key),
                         "-in", str(source), "-sigfile", str(signature)]
            if version == "legacy-v1":
                arguments.extend(["-digest", "sha256"])
            return _openssl(arguments)
    except (OSError, ValueError, TypeError, KeyError, subprocess.TimeoutExpired):
        return False


def main(argv: list[str] | None = None) -> int:
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("sign", "verify"))
    parser.add_argument("--document", required=True, type=Path)
    parser.add_argument("--key", required=True, type=Path)
    parser.add_argument("--envelope", required=True, type=Path)
    parser.add_argument("--version", choices=tuple(VERSIONS), default="pqc-v2")
    parser.add_argument("--policy", choices=tuple(sorted(POLICIES)), default="pqc-only")
    arguments = parser.parse_args(argv)
    try:
        if arguments.version == "legacy-v1" and arguments.operation == "verify" and arguments.policy != "legacy-only":
            print("rejected")
            return 2
        if arguments.operation == "sign":
            sign(arguments.document, arguments.key, arguments.envelope, arguments.version)
            print("signed")
            return 0
        success = verify(arguments.document, arguments.key, arguments.envelope, arguments.policy)
        print("verified" if success else "rejected")
        return 0 if success else 2
    except (OSError, ValueError, subprocess.TimeoutExpired):
        print("operation_failed")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
