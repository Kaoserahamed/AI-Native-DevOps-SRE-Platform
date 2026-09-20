"""JSON Schema snapshot and structure tests for the versioned contracts.

The committed schemas are the machine-readable contract. ``test_committed_schemas_are_current`` fails
when the code and the snapshot disagree, which is what makes a schema change a reviewed decision.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
import pytest

import packages.contracts as contracts
from packages.contracts.versioning import (
    CONTRACT_MODELS,
    SCHEMA_ID_BASE,
    export_schemas,
    load_snapshots,
    schema_differences,
    schema_document,
    schema_snapshot_directory,
    serialize_document,
)

pytestmark = pytest.mark.contract

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
SCHEMA_DIRECTORY: Final[Path] = schema_snapshot_directory(REPO_ROOT)

PAYLOAD_FIXTURES: Final[tuple[tuple[str, str], ...]] = (
    ("alert", "alert"),
    ("evidence", "evidence"),
    ("incident", "incident"),
    ("proposal", "remediation_proposal"),
    ("approval", "approval"),
    ("decision", "agent_decision"),
    ("audit", "audit_event"),
    ("api_error", "api_error"),
)


def test_committed_schemas_are_current() -> None:
    """The committed snapshots must match the models in code."""
    assert schema_differences(SCHEMA_DIRECTORY) == []


@pytest.mark.parametrize("name", sorted(CONTRACT_MODELS))
def test_schema_is_a_valid_draft_2020_12_document(name: str) -> None:
    """Each exported schema is a valid JSON Schema document."""
    Draft202012Validator.check_schema(schema_document(name))


@pytest.mark.parametrize("name", sorted(CONTRACT_MODELS))
def test_schema_identifier_is_versioned(name: str) -> None:
    """The ``$id`` pins the schema version, so consumers can reference it unambiguously."""
    document = schema_document(name)

    assert document["$id"] == f"{SCHEMA_ID_BASE}/{contracts.SCHEMA_VERSION}/{name}.json"
    assert document["$schema"] == "https://json-schema.org/draft/2020-12/schema"


@pytest.mark.parametrize("name", sorted(CONTRACT_MODELS))
def test_schema_forbids_additional_properties(name: str) -> None:
    """Unknown fields must be rejected by any generated validator, not only by pydantic."""
    assert schema_document(name)["additionalProperties"] is False


@pytest.mark.parametrize("name", sorted(CONTRACT_MODELS))
def test_schema_declares_the_contract_version(name: str) -> None:
    """Every top-level contract exposes ``schema_version``."""
    properties = schema_document(name)["properties"]

    assert "schema_version" in properties
    assert properties["schema_version"]["default"] == contracts.SCHEMA_VERSION


@pytest.mark.parametrize(("fixture_name", "schema_name"), PAYLOAD_FIXTURES)
def test_payloads_validate_against_the_exported_schema(
    request: pytest.FixtureRequest, fixture_name: str, schema_name: str
) -> None:
    """A canonical payload is valid for the published JSON Schema, not only for the model."""
    payload: dict[str, Any] = request.getfixturevalue(f"{fixture_name}_payload")

    Draft202012Validator(schema_document(schema_name)).validate(payload)


def test_export_writes_every_contract(tmp_path: Path) -> None:
    """The exporter writes exactly one document per registered contract."""
    written = export_schemas(tmp_path)

    assert {path.name for path in written} == {f"{name}.json" for name in CONTRACT_MODELS}
    assert all(path.read_text(encoding="utf-8").endswith("\n") for path in written)


def test_unknown_contract_is_rejected() -> None:
    """Asking for a contract that does not exist is a programming error, not a silent empty schema."""
    with pytest.raises(ValueError, match="unknown contract"):
        schema_document("not_a_contract")


def test_schema_differences_detects_a_stale_snapshot(tmp_path: Path) -> None:
    """The drift detector must notice an edited snapshot."""
    for name, text in load_snapshots(SCHEMA_DIRECTORY).items():
        (tmp_path / name).write_text(text, encoding="utf-8")

    assert schema_differences(tmp_path) == []

    stale = tmp_path / "alert.json"
    stale.write_text(serialize_document({"title": "hand edited"}), encoding="utf-8")

    differences = schema_differences(tmp_path)
    assert any("alert.json" in difference for difference in differences)


def test_schema_differences_reports_missing_snapshots(tmp_path: Path) -> None:
    """A missing snapshot directory is reported as drift, never as a pass."""
    differences = schema_differences(tmp_path / "absent")

    assert len(differences) == len(CONTRACT_MODELS)


def test_invalid_schema_document_is_rejected() -> None:
    """Structural validation is a guard for the exporter itself."""
    with pytest.raises(SchemaError):
        Draft202012Validator.check_schema({"type": "not-a-type"})
