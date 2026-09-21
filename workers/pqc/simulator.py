from __future__ import annotations

import copy
import hashlib
import re
from dataclasses import dataclass
from typing import Any, Mapping

from .contract_pack import ContractPack, ContractPackError
from .errors import HTTPFailure, classify_http_failure


CURSOR = re.compile(r"^sim-v1\.(\d{1,4})\.([0-9a-f]{16})$")


@dataclass(frozen=True)
class SimulatedResponse:
    status_code: int
    payload: object | None
    headers: Mapping[str, str]
    next_cursor: str | None

    def failure(self) -> HTTPFailure | None:
        if 200 <= self.status_code < 300:
            return None
        return classify_http_failure(self.status_code, self.headers.get("Retry-After"))


class StatefulContractSimulator:
    """In-memory contract simulator; it never binds a socket or calls a provider."""

    def __init__(self, pack: ContractPack, scenario_name: str) -> None:
        self.pack = pack
        self.scenario = dict(pack.simulator_scenario(scenario_name))
        self._validate_scenario()
        self._call_count = 0
        self._page_index = 0

    @property
    def call_count(self) -> int:
        return self._call_count

    @property
    def page_index(self) -> int:
        return self._page_index

    def reset(self) -> None:
        self._call_count = 0
        self._page_index = 0

    def fetch(self, cursor: str | None = None) -> SimulatedResponse:
        self._call_count += 1
        fault = self._fault_for_call(self._call_count)
        if fault is not None:
            kind = fault["kind"]
            if kind == "rate_limit":
                return SimulatedResponse(
                    429,
                    None,
                    {"Retry-After": str(fault["retry_after_seconds"])},
                    cursor,
                )
            if kind == "server_error":
                return SimulatedResponse(int(fault["status_code"]), None, {}, cursor)
            if kind == "schema_drift":
                return SimulatedResponse(200, {"unsupportedEnvelope": []}, {}, cursor)

        index = self._decode_cursor(cursor) if cursor is not None else self._page_index
        page_artifacts = self.scenario["page_artifacts"]
        if index >= len(page_artifacts):
            return SimulatedResponse(204, None, {}, None)
        payload = copy.deepcopy(self.pack.load_json_artifact(page_artifacts[index]))
        if index in self.scenario["duplicate_first_record_on_pages"]:
            self._duplicate_first_record(payload)
        self._page_index = index + 1
        next_cursor = (
            self._cursor_for(index + 1) if index + 1 < len(page_artifacts) else None
        )
        return SimulatedResponse(200, payload, {}, next_cursor)

    def _validate_scenario(self) -> None:
        expected = {
            "page_artifacts",
            "record_array_path",
            "duplicate_first_record_on_pages",
            "faults",
        }
        if set(self.scenario) != expected:
            raise ContractPackError()
        admitted = {str(item["path"]) for item in self.pack.manifest["artifacts"]}
        pages = self.scenario["page_artifacts"]
        if (
            not isinstance(pages, list)
            or not pages
            or any(path not in admitted for path in pages)
        ):
            raise ContractPackError()
        array_path = self.scenario["record_array_path"]
        if not isinstance(array_path, list) or not array_path or len(array_path) > 8:
            raise ContractPackError()
        if any(
            not isinstance(part, (str, int)) or isinstance(part, bool)
            for part in array_path
        ):
            raise ContractPackError()
        duplicate_pages = self.scenario["duplicate_first_record_on_pages"]
        if not isinstance(duplicate_pages, list):
            raise ContractPackError()
        if any(
            not isinstance(page, int) or isinstance(page, bool) or page < 0
            for page in duplicate_pages
        ):
            raise ContractPackError()
        faults = self.scenario["faults"]
        if not isinstance(faults, list) or len(faults) > 32:
            raise ContractPackError()
        calls: set[int] = set()
        for fault in faults:
            if not isinstance(fault, dict) or not isinstance(fault.get("call"), int):
                raise ContractPackError()
            if fault["call"] < 1 or fault["call"] in calls:
                raise ContractPackError()
            calls.add(fault["call"])
            kind = fault.get("kind")
            if kind == "rate_limit":
                if set(fault) != {"call", "kind", "retry_after_seconds"}:
                    raise ContractPackError()
                if not isinstance(fault["retry_after_seconds"], int):
                    raise ContractPackError()
                if not 0 <= fault["retry_after_seconds"] <= 3_600:
                    raise ContractPackError()
            elif kind == "server_error":
                if set(fault) != {"call", "kind", "status_code"}:
                    raise ContractPackError()
                if fault["status_code"] not in {500, 502, 503, 504}:
                    raise ContractPackError()
            elif kind == "schema_drift":
                if set(fault) != {"call", "kind"}:
                    raise ContractPackError()
            else:
                raise ContractPackError()

    def _fault_for_call(self, call: int) -> Mapping[str, Any] | None:
        return next(
            (fault for fault in self.scenario["faults"] if fault["call"] == call), None
        )

    def _cursor_digest(self, index: int) -> str:
        material = (
            f"{self.pack.pack_id}\x00{self.pack.content_digest}\x00{index}".encode(
                "utf-8"
            )
        )
        return hashlib.sha256(material).hexdigest()[:16]

    def _cursor_for(self, index: int) -> str:
        return f"sim-v1.{index}.{self._cursor_digest(index)}"

    def _decode_cursor(self, cursor: str) -> int:
        match = CURSOR.fullmatch(cursor)
        if match is None:
            raise ContractPackError("PQC_ADAPTER_INVALID_INPUT")
        index = int(match.group(1))
        if match.group(2) != self._cursor_digest(index):
            raise ContractPackError("PQC_ADAPTER_INVALID_INPUT")
        return index

    def _duplicate_first_record(self, payload: object) -> None:
        target: object = payload
        for part in self.scenario["record_array_path"]:
            if (
                isinstance(part, int)
                and isinstance(target, list)
                and 0 <= part < len(target)
            ):
                target = target[part]
            elif isinstance(part, str) and isinstance(target, dict) and part in target:
                target = target[part]
            else:
                raise ContractPackError("PQC_ADAPTER_SCHEMA_DRIFT")
        if not isinstance(target, list) or not target:
            raise ContractPackError("PQC_ADAPTER_SCHEMA_DRIFT")
        target.append(copy.deepcopy(target[0]))
