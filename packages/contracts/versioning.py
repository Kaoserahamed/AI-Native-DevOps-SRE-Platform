"""Schema versioning, model registry and JSON Schema export.

Contracts are versioned, never mutated: ``SCHEMA_VERSION`` versions the whole contract set, and the
committed JSON Schemas under ``packages/contracts/schemas/<version>/`` are the machine-readable snapshot
that the contract test tier compares against. A schema change that is not accompanied by an intentional
snapshot update therefore fails CI, which is what makes "no silent breaking change" enforceable.
"""

from __future__ import annotations

from collections.abc import Mapping
import json
from pathlib import Path
from typing import Any, Final

from packages.contracts.agents import AgentDecision
from packages.contracts.alerts import Alert
from packages.contracts.audit import AuditEvent
from packages.contracts.common import SCHEMA_VERSION, PlatformModel
from packages.contracts.errors import ApiError
from packages.contracts.evidence import Evidence
from packages.contracts.incidents import Incident
from packages.contracts.remediation import Approval, RemediationProposal

SCHEMA_ID_BASE: Final[str] = (
    "https://raw.githubusercontent.com/Kaoserahamed/AI-Native-DevOps-SRE-Platform/main"
    "/packages/contracts/schemas"
)
JSON_SCHEMA_DIALECT: Final[str] = "https://json-schema.org/draft/2020-12/schema"
SNAPSHOT_DIRECTORY: Final[tuple[str, ...]] = ("packages", "contracts", "schemas")

CONTRACT_MODELS: Final[Mapping[str, type[PlatformModel]]] = {
    "agent_decision": AgentDecision,
    "alert": Alert,
    "api_error": ApiError,
    "approval": Approval,
    "audit_event": AuditEvent,
    "evidence": Evidence,
    "incident": Incident,
    "remediation_proposal": RemediationProposal,
}


def schema_snapshot_directory(root: Path) -> Path:
    """Return the directory that holds the committed schemas for the current version."""
    return root.joinpath(*SNAPSHOT_DIRECTORY, SCHEMA_VERSION)


def schema_document(name: str) -> dict[str, Any]:
    """Return the JSON Schema document for one contract, with a versioned ``$id``."""
    try:
        model = CONTRACT_MODELS[name]
    except KeyError as error:  # pragma: no cover - defensive, exercised by a unit test
        raise ValueError(f"unknown contract: {name!r}") from error
    document = model.model_json_schema()
    document["$id"] = f"{SCHEMA_ID_BASE}/{SCHEMA_VERSION}/{name}.json"
    document["$schema"] = JSON_SCHEMA_DIALECT
    return document


def serialize_document(document: Mapping[str, Any]) -> str:
    """Serialize a schema document deterministically, so snapshots diff cleanly."""
    return f"{json.dumps(document, indent=2, sort_keys=True, ensure_ascii=True)}\n"


def export_schemas(directory: Path) -> list[Path]:
    """Write every contract schema into ``directory`` and return the written paths."""
    directory.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name in sorted(CONTRACT_MODELS):
        path = directory / f"{name}.json"
        path.write_text(serialize_document(schema_document(name)), encoding="utf-8")
        written.append(path)
    return written


def load_snapshots(directory: Path) -> dict[str, str]:
    """Return the committed schema snapshots keyed by file name."""
    if not directory.is_dir():
        return {}
    return {
        path.name: path.read_text(encoding="utf-8") for path in sorted(directory.glob("*.json"))
    }


def schema_differences(directory: Path) -> list[str]:
    """Return a human-readable list of differences between generated and committed schemas."""
    committed = load_snapshots(directory)
    expected_names = {f"{name}.json" for name in CONTRACT_MODELS}
    differences = [
        f"missing committed schema: {name}" for name in sorted(expected_names - set(committed))
    ]
    differences += [
        f"stale committed schema: {name}" for name in sorted(set(committed) - expected_names)
    ]
    for name in sorted(expected_names & set(committed)):
        generated = serialize_document(schema_document(Path(name).stem))
        if generated != committed[name]:
            differences.append(
                f"schema {name} differs from the committed snapshot; "
                "run `python scripts/export_contract_schemas.py` and review the change"
            )
    return differences
