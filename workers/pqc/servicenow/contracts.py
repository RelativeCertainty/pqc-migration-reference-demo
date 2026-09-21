from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012


EXPECTED_OPERATIONS = frozenset(
    {
        "capabilities.read",
        "cis.reconcile",
        "cis.read",
        "crypto_assets.reconcile",
        "crypto_assets.list",
        "changes.ensure",
        "changes.read",
        "change_tasks.transition",
        "approvals.read",
        "verifications.append",
        "changes.close",
        "events.read",
    }
)
_SCHEMA_REF = re.compile(
    r"^api-contracts\.v1\.schema\.json#/\$defs/([A-Za-z][A-Za-z0-9]+)$"
)
_DEFAULT_CONTRACT_ROOT = (
    Path(__file__).resolve().parents[3]
    / "integrations"
    / "pqc"
    / "servicenow_scoped_app"
)


class ContractConfigurationError(ValueError):
    pass


@dataclass(frozen=True)
class ScopedRoute:
    operation_id: str
    method: str
    path_template: str
    mutation: bool
    query_parameters: tuple[str, ...]
    request_validator: Draft202012Validator
    response_validator: Draft202012Validator


class ScopedContractRegistry:
    """Load and verify the exact default-deny ``x_pba_pqc`` route surface."""

    def __init__(self, contract_root: Path | None = None) -> None:
        root = contract_root or _DEFAULT_CONTRACT_ROOT
        registry_document = self._load_json(root / "routes.v1.json")
        schema = self._load_json(root / "api-contracts.v1.schema.json")
        try:
            Draft202012Validator.check_schema(schema)
            resource = Resource.from_contents(schema, default_specification=DRAFT202012)
            schema_registry = Registry().with_resource(schema["$id"], resource)
        except Exception:
            raise ContractConfigurationError(
                "ServiceNow contract schema is invalid"
            ) from None

        self._validate_registry(registry_document)
        routes: dict[str, ScopedRoute] = {}
        for native_route in registry_document["routes"]:
            request_name = self._definition_name(native_route["request_schema"])
            response_name = self._definition_name(native_route["response_schema"])
            request_validator = Draft202012Validator(
                {
                    "$schema": "https://json-schema.org/draft/2020-12/schema",
                    "$ref": f"{schema['$id']}#/$defs/{request_name}",
                },
                registry=schema_registry,
                format_checker=FormatChecker(),
            )
            response_validator = Draft202012Validator(
                {
                    "$schema": "https://json-schema.org/draft/2020-12/schema",
                    "$ref": f"{schema['$id']}#/$defs/{response_name}",
                },
                registry=schema_registry,
                format_checker=FormatChecker(),
            )
            operation_id = native_route["operation_id"]
            routes[operation_id] = ScopedRoute(
                operation_id=operation_id,
                method=native_route["method"],
                path_template=native_route["path_template"],
                mutation=native_route["effect"] == "mutation",
                query_parameters=tuple(native_route["query_parameters"]),
                request_validator=request_validator,
                response_validator=response_validator,
            )
        self._routes: Mapping[str, ScopedRoute] = MappingProxyType(routes)

    def route(self, operation_id: str) -> ScopedRoute:
        try:
            return self._routes[operation_id]
        except KeyError:
            raise ContractConfigurationError(
                "ServiceNow operation is not allowlisted"
            ) from None

    @staticmethod
    def _load_json(path: Path) -> dict[str, object]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            raise ContractConfigurationError(
                "ServiceNow contract could not be loaded"
            ) from None
        if not isinstance(value, dict):
            raise ContractConfigurationError("ServiceNow contract is invalid")
        return value

    @staticmethod
    def _definition_name(schema_ref: object) -> str:
        if not isinstance(schema_ref, str):
            raise ContractConfigurationError("ServiceNow schema reference is invalid")
        match = _SCHEMA_REF.fullmatch(schema_ref)
        if match is None:
            raise ContractConfigurationError("ServiceNow schema reference is invalid")
        return match.group(1)

    @staticmethod
    def _validate_registry(document: dict[str, object]) -> None:
        if (
            document.get("scope_name") != "x_pba_pqc"
            or document.get("base_path") != "/api/x_pba_pqc/v1"
            or document.get("default_action") != "deny"
            or document.get("unknown_method_action") != "deny"
            or document.get("unknown_path_action") != "deny"
            or document.get("query_policy") != "declared_parameters_only"
        ):
            raise ContractConfigurationError(
                "ServiceNow route registry is not default deny"
            )
        table_api = document.get("table_api")
        approval_boundary = document.get("approval_boundary")
        if not isinstance(table_api, dict) or not isinstance(approval_boundary, dict):
            raise ContractConfigurationError("ServiceNow safety boundary is missing")
        forbidden_prefixes = table_api.get("forbidden_path_prefixes")
        forbidden_targets = table_api.get("forbidden_write_targets")
        if (
            table_api.get("enabled") is not False
            or table_api.get("arbitrary_table_names_allowed") is not False
            or table_api.get("arbitrary_encoded_queries_allowed") is not False
            or not isinstance(forbidden_prefixes, list)
            or "/api/now/table" not in forbidden_prefixes
            or not isinstance(forbidden_targets, list)
            or "sysapproval_approver" not in forbidden_targets
            or approval_boundary.get("adapter_access") != "read_only"
            or approval_boundary.get("approval_create_route_present") is not False
            or approval_boundary.get("approval_update_route_present") is not False
            or approval_boundary.get("sysapproval_approver_write_allowed") is not False
        ):
            raise ContractConfigurationError(
                "ServiceNow restricted platform boundary is invalid"
            )
        native_routes = document.get("routes")
        if not isinstance(native_routes, list):
            raise ContractConfigurationError("ServiceNow route registry is invalid")
        operation_ids: set[str] = set()
        route_pairs: set[tuple[str, str]] = set()
        for route in native_routes:
            if not isinstance(route, dict):
                raise ContractConfigurationError("ServiceNow route registry is invalid")
            operation_id = route.get("operation_id")
            method = route.get("method")
            path = route.get("path_template")
            effect = route.get("effect")
            query_parameters = route.get("query_parameters")
            if (
                not isinstance(operation_id, str)
                or method not in {"GET", "POST"}
                or effect not in {"read", "mutation"}
                or not isinstance(path, str)
                or not path.startswith("/api/x_pba_pqc/v1/")
                or "?" in path
                or "*" in path
                or "{table" in path
                or any(path.startswith(prefix) for prefix in forbidden_prefixes)
                or not isinstance(query_parameters, list)
                or any(
                    not isinstance(parameter, str)
                    or re.fullmatch(r"[a-z][a-z0-9_]{1,63}", parameter) is None
                    for parameter in query_parameters
                )
                or len(query_parameters) != len(set(query_parameters))
                or (method != "GET" and query_parameters)
            ):
                raise ContractConfigurationError(
                    "ServiceNow route registry contains an unsafe route"
                )
            pair = (method, path)
            if operation_id in operation_ids or pair in route_pairs:
                raise ContractConfigurationError(
                    "ServiceNow route registry contains a duplicate"
                )
            operation_ids.add(operation_id)
            route_pairs.add(pair)
        if operation_ids != EXPECTED_OPERATIONS:
            raise ContractConfigurationError(
                "ServiceNow route allowlist does not match the admitted contract"
            )
