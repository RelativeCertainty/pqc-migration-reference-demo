from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012


def _resource_from(schema: Dict[str, Any]) -> Resource:
    return Resource.from_contents(schema, default_specification=DRAFT202012)


def _schema_keys(schema: Dict[str, Any], schema_path: Path) -> list[str]:
    keys: list[str] = []
    schema_id = schema.get("$id")
    if isinstance(schema_id, str) and schema_id:
        keys.append(schema_id)
    file_uri = schema_path.resolve().as_uri()
    keys.extend([file_uri, schema_path.name, f"./{schema_path.name}"])
    if schema_path.name.startswith("common.") and schema_path.name.endswith(".schema.json"):
        keys.append(f"https://upm.pba.io/schemas/{schema_path.name}")
        keys.append(f"https://pba.io/schemas/{schema_path.name}")
    return keys


def _register_resource(registry: Registry, resource: Resource, keys: Iterable[str]) -> Registry:
    for key in keys:
        if not key:
            continue
        registry = registry.with_resource(key, resource)
    return registry


def _register_schema(registry: Registry, schema: Dict[str, Any], schema_path: Path) -> Registry:
    if not isinstance(schema, dict):
        return registry
    resource = _resource_from(schema)
    return _register_resource(registry, resource, _schema_keys(schema, schema_path))


@lru_cache(maxsize=None)
def _dir_registry(schema_dir: str) -> Registry:
    registry = Registry()
    root = Path(schema_dir)
    if not root.exists():
        return registry
    for schema_path in sorted(root.rglob("*.schema.json")):
        try:
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        registry = _register_schema(registry, schema, schema_path)
    return registry


def build_registry(
    schema: Dict[str, Any],
    schema_path: Path,
    *,
    store: Optional[Dict[str, Dict[str, Any]]] = None,
    include_dir: bool = True,
) -> Registry:
    registry = _dir_registry(str(schema_path.parent.resolve())) if include_dir else Registry()
    registry = _register_schema(registry, schema, schema_path)
    if store:
        for key, value in store.items():
            if not key or not isinstance(value, dict):
                continue
            registry = _register_resource(registry, _resource_from(value), [key])
    return registry
