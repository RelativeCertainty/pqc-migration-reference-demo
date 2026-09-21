from __future__ import annotations

import hashlib
import re
from typing import Protocol

from ..contract_pack import ContractPack
from ..errors import PQCAdapterError
from ..models import ImportContext, ProviderPage, RetryClass
from ..safety import normalize_timestamp, stable_sha256_id, validate_context


PAGE_CURSOR = re.compile(r"^pqc-page-v1\.(\d{1,4})\.([0-9a-f]{16})$")


class EvidenceAdapter(Protocol):
    adapter_id: str
    pack: ContractPack

    def adapt(self, payload: object, context: ImportContext) -> ProviderPage: ...


def normalized_context_times(context: ImportContext) -> tuple[str | None, str, str]:
    validate_context(context)
    collected = normalize_timestamp(context.timestamps.collected_at)
    package_generated = normalize_timestamp(context.timestamps.package_generated_at)
    imported = normalize_timestamp(context.timestamps.imported_at)
    if package_generated is None or imported is None:
        raise PQCAdapterError("PQC_ADAPTER_INVALID_INPUT", RetryClass.INVALID_REQUEST)
    return collected, package_generated, imported


def source_ref(context: ImportContext) -> str:
    return stable_sha256_id("source", context.tenant_id, context.source_name)


def asset_scope_ref(context: ImportContext) -> str:
    return stable_sha256_id("asset-scope", context.tenant_id, context.asset_key)


def encode_page_cursor(
    pack: ContractPack, adapter_id: str, source_scope_ref: str, page_number: int
) -> str:
    material = (
        f"{pack.pack_id}\x00{pack.content_digest}\x00{adapter_id}\x00"
        f"{source_scope_ref}\x00{page_number}"
    ).encode("utf-8")
    digest = hashlib.sha256(material).hexdigest()[:16]
    return f"pqc-page-v1.{page_number}.{digest}"


def decode_page_cursor(
    pack: ContractPack, adapter_id: str, source_scope_ref: str, cursor: str
) -> int:
    match = PAGE_CURSOR.fullmatch(cursor)
    if match is None:
        raise PQCAdapterError("PQC_ADAPTER_INVALID_INPUT", RetryClass.INVALID_REQUEST)
    page_number = int(match.group(1))
    if encode_page_cursor(pack, adapter_id, source_scope_ref, page_number) != cursor:
        raise PQCAdapterError("PQC_ADAPTER_INVALID_INPUT", RetryClass.INVALID_REQUEST)
    return page_number
