from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Set


@dataclass(frozen=True)
class Grant:
    capabilities: Set[str] = field(default_factory=set)
    limits: Dict[str, Any] = field(default_factory=dict)
    io: Dict[str, Any] = field(default_factory=dict)
    llm: Dict[str, Any] = field(default_factory=dict)
    audit: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def _from_grant_obj(cls, grant_obj: Any) -> Optional["Grant"]:
        if grant_obj is None or not isinstance(grant_obj, dict):
            return None

        raw_caps = grant_obj.get("capabilities")
        capabilities = {
            str(cap).strip()
            for cap in (raw_caps if isinstance(raw_caps, list) else [])
            if isinstance(cap, str) and str(cap).strip()
        }
        limits = grant_obj.get("limits") if isinstance(grant_obj.get("limits"), dict) else {}
        io = grant_obj.get("io") if isinstance(grant_obj.get("io"), dict) else {}
        llm = grant_obj.get("llm") if isinstance(grant_obj.get("llm"), dict) else {}
        audit = grant_obj.get("audit") if isinstance(grant_obj.get("audit"), dict) else {}

        return cls(
            capabilities=capabilities,
            limits=limits,
            io=io,
            llm=llm,
            audit=audit,
        )

    @classmethod
    def from_opa_result(cls, result: Dict[str, Any]) -> Optional["Grant"]:
        if not isinstance(result, dict):
            return None

        decision: Dict[str, Any] = result
        nested_result = result.get("result")
        if isinstance(nested_result, dict):
            decision = nested_result

        nested_decision = decision.get("decision")
        if isinstance(nested_decision, dict):
            decision = nested_decision

        return cls._from_grant_obj(decision.get("grant"))

    @classmethod
    def from_invocation(cls, invocation: Dict[str, Any]) -> Optional["Grant"]:
        if not isinstance(invocation, dict):
            return None
        return cls._from_grant_obj(invocation.get("grant"))

    def require(self, cap: str) -> None:
        if cap in self.capabilities:
            return
        available = ", ".join(sorted(self.capabilities)) if self.capabilities else "<none>"
        raise PermissionError(f"OPA grant missing capability '{cap}'. available={available}")


_current_grant: ContextVar[Optional[Grant]] = ContextVar("worker_runtime_current_grant", default=None)


def set_current_grant(grant: Optional[Grant]) -> None:
    _current_grant.set(grant)


def get_current_grant() -> Optional[Grant]:
    return _current_grant.get()
