"""End-to-end tests for the Incident Lifecycle API.

These tests exercise the API through its public HTTP surface with in-memory
fake repositories, so they pin the request/response contract without needing a
database: created incidents carry persisted timestamps, invalid transitions
are refused with 400, reopen only accepts a RESOLVED incident, and every
mutating endpoint appends an audit event.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

from packages.contracts.audit import AuditEvent
from packages.contracts.common import Environment, ServiceRef, Severity
from packages.contracts.evidence import Evidence, EvidenceCollector, EvidenceKind
from packages.contracts.incidents import Incident, IncidentStatus
from packages.persistence.repositories import (
    AuditRepository,
    EvidenceRepository,
    IncidentRepository,
)
from services.incident_api.app import (
    create_app,
    get_audit_repo,
    get_evidence_repo,
    get_incident_repo,
)


class _FakeIncidentRepo(IncidentRepository):
    """In-memory incident repository for API contract tests."""

    def __init__(self) -> None:
        self._store: dict[str, Incident] = {}

    async def save(self, incident: Incident) -> None:
        self._store[incident.incident_id] = incident

    async def find_by_id(self, incident_id: str) -> Incident | None:
        return self._store.get(incident_id)

    async def find_by_service(
        self, service_name: str, environment: str, limit: int = 100
    ) -> list[Incident]:
        return [
            incident
            for incident in self._store.values()
            if incident.service.name == service_name
            and incident.service.environment.value == environment
        ][:limit]

    async def find_by_status(self, status: str, limit: int = 100) -> list[Incident]:
        return [i for i in self._store.values() if i.status.value == status][:limit]

    async def find_open_incidents(self, limit: int = 100) -> list[Incident]:
        return [i for i in self._store.values() if i.is_open][:limit]


class _FakeEvidenceRepo(EvidenceRepository):
    """In-memory evidence repository."""

    def __init__(self) -> None:
        self._store: dict[str, Evidence] = {}

    async def save(self, evidence: Evidence) -> None:
        self._store[evidence.evidence_id] = evidence

    async def find_by_id(self, evidence_id: str) -> Evidence | None:
        return self._store.get(evidence_id)

    async def find_by_incident(self, incident_id: str) -> list[Evidence]:
        return [e for e in self._store.values() if e.incident_id == incident_id]

    async def find_recent(
        self, service_name: str | None = None, limit: int = 100
    ) -> list[Evidence]:
        return list(self._store.values())[:limit]


class _FakeAuditRepo(AuditRepository):
    """In-memory audit trail capturing every appended event."""

    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    async def append(self, event: AuditEvent) -> AuditEvent:
        self.events.append(event)
        return event

    async def head(self) -> AuditEvent | None:
        return self.events[-1] if self.events else None

    async def find_oldest_first(self, limit: int = 100) -> list[AuditEvent]:
        return self.events[:limit]

    async def find_by_subject(self, subject: str, limit: int = 100) -> list[AuditEvent]:
        return [e for e in self.events if e.subject == subject][:limit]

    async def find_by_incident(self, incident_id: str, limit: int = 100) -> list[AuditEvent]:
        return [e for e in self.events if e.incident_id == incident_id][:limit]

    async def find_by_actor(self, actor_id: str, limit: int = 100) -> list[AuditEvent]:
        return [e for e in self.events if e.actor.actor_id == actor_id][:limit]

    async def find_recent(self, limit: int = 100) -> list[AuditEvent]:
        return list(reversed(self.events))[:limit]


def _new_incident(incident_id: str = "INC-TEST-001") -> Incident:
    now = datetime.now(tz=UTC)
    return Incident(
        incident_id=incident_id,
        title="API test incident",
        severity=Severity.HIGH,
        service=ServiceRef(name="checkout", environment=Environment.STAGING),
        status=IncidentStatus.OPEN,
        detected_at=now,
        opened_at=now,
    )


def _new_evidence(incident_id: str) -> Evidence:
    return Evidence(
        evidence_id="EV-TEST-001",
        kind=EvidenceKind.LOG,
        collector=EvidenceCollector.AGENT,
        collected_at=datetime.now(tz=UTC),
        summary="Test log excerpt",
        excerpt="Test log excerpt",
        incident_id=incident_id,
    )


def _make_client() -> tuple[TestClient, _FakeIncidentRepo, _FakeAuditRepo]:
    incident_repo = _FakeIncidentRepo()
    evidence_repo = _FakeEvidenceRepo()
    audit_repo = _FakeAuditRepo()
    app: FastAPI = create_app()
    app.dependency_overrides[get_incident_repo] = lambda: incident_repo
    app.dependency_overrides[get_evidence_repo] = lambda: evidence_repo
    app.dependency_overrides[get_audit_repo] = lambda: audit_repo
    return TestClient(app), incident_repo, audit_repo


def _create(client: TestClient, incident_id: str = "INC-TEST-001") -> Incident:
    payload = _new_incident(incident_id).model_dump(mode="json")
    response = client.post("/api/v1/incidents", json={"incident": payload})
    assert response.status_code == 201, response.text
    return Incident.model_validate(response.json())


def test_health_endpoint() -> None:
    client, _, _ = _make_client()
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


async def test_create_incident_persists_and_audits() -> None:
    client, repo, audit = _make_client()
    created = _create(client)

    stored = await repo.find_by_id(created.incident_id)
    assert stored is not None
    assert stored.status == IncidentStatus.OPEN
    assert stored.opened_at.tzinfo is not None
    assert len(audit.events) == 1


def test_create_duplicate_incident_returns_409() -> None:
    client, _, _ = _make_client()
    _create(client)
    payload = _new_incident().model_dump(mode="json")
    response = client.post("/api/v1/incidents", json={"incident": payload})
    assert response.status_code == 409


def test_get_incident_404_when_missing() -> None:
    client, _, _ = _make_client()
    response = client.get("/api/v1/incidents/INC-MISSING")
    assert response.status_code == 404


async def test_acknowledge_sets_timestamp_and_audits() -> None:
    client, repo, audit = _make_client()
    _create(client)

    response = client.post("/api/v1/incidents/INC-TEST-001/acknowledge")
    assert response.status_code == 200, response.text
    incident = Incident.model_validate(response.json())
    assert incident.status == IncidentStatus.ACKNOWLEDGED
    assert incident.acknowledged_at is not None
    assert len(audit.events) == 2

    stored = await repo.find_by_id("INC-TEST-001")
    assert stored is not None
    assert stored.acknowledged_at is not None


async def test_resolve_then_reopen_clears_resolution() -> None:
    client, repo, audit = _make_client()
    _create(client)
    for step in ("acknowledge", "investigate", "mitigate", "resolve"):
        response = client.post(f"/api/v1/incidents/INC-TEST-001/{step}")
        assert response.status_code == 200, f"{step}: {response.text}"

    resolved = client.get("/api/v1/incidents/INC-TEST-001").json()
    assert resolved["status"] == "resolved"
    assert resolved["resolved_at"] is not None

    response = client.post("/api/v1/incidents/INC-TEST-001/reopen")
    assert response.status_code == 200, response.text
    reopened = Incident.model_validate(response.json())
    assert reopened.status == IncidentStatus.REOPENED
    assert reopened.resolved_at is None
    assert reopened.resolution_summary is None

    stored = await repo.find_by_id("INC-TEST-001")
    assert stored is not None
    assert stored.status == IncidentStatus.REOPENED
    assert len(audit.events) == 6


def test_reopen_refused_from_open_state() -> None:
    client, _, _ = _make_client()
    _create(client)
    response = client.post("/api/v1/incidents/INC-TEST-001/reopen")
    assert response.status_code == 400


async def test_close_appends_post_incident_notes() -> None:
    client, _, _ = _make_client()
    _create(client)
    for step in ("acknowledge", "investigate", "mitigate", "resolve"):
        assert client.post(f"/api/v1/incidents/INC-TEST-001/{step}").status_code == 200

    response = client.post(
        "/api/v1/incidents/INC-TEST-001/close",
        json={"post_incident_notes": "Follow-up runbook written"},
    )
    assert response.status_code == 200, response.text
    incident = Incident.model_validate(response.json())
    assert incident.status == IncidentStatus.CLOSED
    assert incident.closed_at is not None
    assert incident.post_incident_notes == "Follow-up runbook written"


def test_attach_evidence_round_trip() -> None:
    client, _, audit = _make_client()
    _create(client)
    payload = _new_evidence("INC-TEST-001").model_dump(mode="json")

    response = client.post("/api/v1/incidents/INC-TEST-001/evidence", json={"evidence": payload})
    assert response.status_code == 201, response.text

    listed = client.get("/api/v1/incidents/INC-TEST-001/evidence")
    assert listed.status_code == 200
    body = listed.json()
    assert body["total"] == 1
    assert body["evidence"][0]["evidence_id"] == "EV-TEST-001"
    assert len(audit.events) == 2

