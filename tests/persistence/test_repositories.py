"""Contract tests for repository interfaces using test doubles.

These tests verify the repository contracts without requiring a live database,
allowing fast unit-style testing of business logic that depends on persistence.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from packages.contracts.audit import AuditActor, AuditEvent, AuditEventType, AuditResult
from packages.contracts.common import (
    ActorType,
    Environment,
    Identifier,
    ServiceRef,
    Severity,
)
from packages.contracts.evidence import Evidence, EvidenceCollector, EvidenceKind
from packages.contracts.incidents import Incident, IncidentStatus
from packages.persistence.repositories import (
    AuditRepository,
    EvidenceRepository,
    IncidentRepository,
)


class InMemoryIncidentRepository(IncidentRepository):
    """In-memory test double for incident repository."""

    def __init__(self) -> None:
        self.incidents: dict[Identifier, Incident] = {}

    async def save(self, incident: Incident) -> None:
        """Save incident to memory."""
        self.incidents[incident.incident_id] = incident

    async def find_by_id(self, incident_id: Identifier) -> Incident | None:
        """Find incident by ID."""
        return self.incidents.get(incident_id)

    async def find_by_service(
        self, service_name: str, environment: str, limit: int = 100
    ) -> list[Incident]:
        """Find incidents for a service."""
        matches = [
            inc
            for inc in self.incidents.values()
            if inc.service.name == service_name and inc.service.environment.value == environment
        ]
        return sorted(matches, key=lambda x: x.opened_at, reverse=True)[:limit]

    async def find_by_status(self, status: str, limit: int = 100) -> list[Incident]:
        """Find incidents by status."""
        matches = [inc for inc in self.incidents.values() if inc.status.value == status]
        return sorted(matches, key=lambda x: x.opened_at, reverse=True)[:limit]

    async def find_open_incidents(self, limit: int = 100) -> list[Incident]:
        """Find open incidents."""
        open_statuses = {"open", "acknowledged", "investigating", "mitigating", "reopened"}
        matches = [inc for inc in self.incidents.values() if inc.status.value in open_statuses]
        return sorted(matches, key=lambda x: x.opened_at, reverse=True)[:limit]


class InMemoryEvidenceRepository(EvidenceRepository):
    """In-memory test double for evidence repository."""

    def __init__(self) -> None:
        self.evidence: dict[Identifier, Evidence] = {}

    async def save(self, evidence: Evidence) -> None:
        """Save evidence to memory."""
        self.evidence[evidence.evidence_id] = evidence

    async def find_by_id(self, evidence_id: Identifier) -> Evidence | None:
        """Find evidence by ID."""
        return self.evidence.get(evidence_id)

    async def find_by_incident(self, incident_id: Identifier) -> list[Evidence]:
        """Find evidence for an incident."""
        matches = [ev for ev in self.evidence.values() if ev.incident_id == incident_id]
        return sorted(matches, key=lambda x: x.collected_at, reverse=True)

    async def find_recent(
        self, service_name: str | None = None, limit: int = 100
    ) -> list[Evidence]:
        """Find recent evidence."""
        if service_name:
            matches = [
                ev
                for ev in self.evidence.values()
                if ev.service and ev.service.name == service_name
            ]
        else:
            matches = list(self.evidence.values())

        return sorted(matches, key=lambda x: x.collected_at, reverse=True)[:limit]


class InMemoryAuditRepository(AuditRepository):
    """In-memory test double for the append-only audit repository."""

    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    async def append(self, event: AuditEvent) -> AuditEvent:
        """Append an audit event, sealing it onto the chain like the real store does."""
        head = await self.head()
        expected = head.digest if head is not None else None
        sealed = (
            event
            if event.previous_digest == expected
            else event.model_copy(update={"previous_digest": expected})
        )
        self.events.append(sealed)
        return sealed

    async def head(self) -> AuditEvent | None:
        """Return the most recent event."""
        return self.events[-1] if self.events else None

    async def find_oldest_first(self, limit: int = 100) -> list[AuditEvent]:
        """Find stored events oldest first."""
        return self.events[:limit]

    async def find_by_subject(self, subject: Identifier, limit: int = 100) -> list[AuditEvent]:
        """Find audit events about one subject."""
        matches = [event for event in self.events if event.subject == subject]
        return sorted(matches, key=lambda event: event.occurred_at, reverse=True)[:limit]

    async def find_by_incident(self, incident_id: Identifier, limit: int = 100) -> list[AuditEvent]:
        """Find audit events recorded against one incident."""
        matches = [event for event in self.events if event.incident_id == incident_id]
        return sorted(matches, key=lambda event: event.occurred_at, reverse=True)[:limit]

    async def find_by_actor(self, actor_id: str, limit: int = 100) -> list[AuditEvent]:
        """Find audit events by actor."""
        matches = [event for event in self.events if event.actor.actor_id == actor_id]
        return sorted(matches, key=lambda event: event.occurred_at, reverse=True)[:limit]

    async def find_recent(self, limit: int = 100) -> list[AuditEvent]:
        """Find recent audit events, newest first."""
        return sorted(self.events, key=lambda event: event.occurred_at, reverse=True)[:limit]


@pytest.fixture
def incident_repo() -> InMemoryIncidentRepository:
    """Create in-memory incident repository."""
    return InMemoryIncidentRepository()


@pytest.fixture
def evidence_repo() -> InMemoryEvidenceRepository:
    """Create in-memory evidence repository."""
    return InMemoryEvidenceRepository()


@pytest.fixture
def audit_repo() -> InMemoryAuditRepository:
    """Create in-memory audit repository."""
    return InMemoryAuditRepository()


@pytest.fixture
def sample_incident() -> Incident:
    """Create a sample incident."""
    now = datetime.now(tz=UTC)
    return Incident(
        incident_id="INC-2024-001",
        title="API latency degradation",
        severity=Severity.SEV2,
        service=ServiceRef(
            name="demo-api",
            environment=Environment.PRODUCTION,
            namespace="default",
        ),
        status=IncidentStatus.OPEN,
        detected_at=now,
        opened_at=now,
    )


@pytest.fixture
def sample_evidence() -> Evidence:
    """Create sample evidence."""
    now = datetime.now(tz=UTC)
    return Evidence(
        evidence_id="evidence-001",
        kind=EvidenceKind.METRIC_SERIES,
        collector=EvidenceCollector.PROMETHEUS,
        collected_at=now,
        summary="P95 latency increased to 1200ms",
        excerpt="p95_latency_ms: 1200",
    )


@pytest.fixture
def sample_audit_event() -> AuditEvent:
    """Create a sample audit event."""
    return AuditEvent(
        event_id="AUD-2024-0001",
        occurred_at=datetime.now(tz=UTC),
        actor=AuditActor(actor_type=ActorType.HUMAN, actor_id="user@example.com"),
        event_type=AuditEventType.INCIDENT_TRANSITIONED,
        subject="INC-2024-001",
        result=AuditResult.SUCCEEDED,
        correlation_id="corr-2024-0001",
        incident_id="INC-2024-001",
    )


class TestIncidentRepositoryContract:
    """Contract tests for IncidentRepository."""

    @pytest.mark.asyncio
    async def test_save_and_retrieve_incident(
        self, incident_repo: InMemoryIncidentRepository, sample_incident: Incident
    ) -> None:
        """Test saving and retrieving an incident."""
        await incident_repo.save(sample_incident)

        retrieved = await incident_repo.find_by_id(sample_incident.incident_id)

        assert retrieved is not None
        assert retrieved.incident_id == sample_incident.incident_id
        assert retrieved.title == sample_incident.title
        assert retrieved.severity == sample_incident.severity

    @pytest.mark.asyncio
    async def test_find_by_id_returns_none_when_not_found(
        self, incident_repo: InMemoryIncidentRepository
    ) -> None:
        """Test that find_by_id returns None for non-existent incident."""
        result = await incident_repo.find_by_id("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_find_by_service(
        self, incident_repo: InMemoryIncidentRepository, sample_incident: Incident
    ) -> None:
        """Test finding incidents by service."""
        await incident_repo.save(sample_incident)

        incidents = await incident_repo.find_by_service("demo-api", "production")

        assert len(incidents) == 1
        assert incidents[0].incident_id == sample_incident.incident_id

    @pytest.mark.asyncio
    async def test_find_by_status(
        self, incident_repo: InMemoryIncidentRepository, sample_incident: Incident
    ) -> None:
        """Test finding incidents by status."""
        await incident_repo.save(sample_incident)

        incidents = await incident_repo.find_by_status("open")

        assert len(incidents) == 1
        assert incidents[0].incident_id == sample_incident.incident_id

    @pytest.mark.asyncio
    async def test_find_open_incidents(
        self, incident_repo: InMemoryIncidentRepository, sample_incident: Incident
    ) -> None:
        """Test finding open incidents."""
        await incident_repo.save(sample_incident)

        # Add a resolved incident
        resolved_incident = Incident(
            incident_id="INC-2024-002",
            title="Resolved incident",
            severity=Severity.SEV3,
            service=sample_incident.service,
            status=IncidentStatus.RESOLVED,
            detected_at=datetime.now(tz=UTC),
            opened_at=datetime.now(tz=UTC),
            acknowledged_at=datetime.now(tz=UTC),
            resolved_at=datetime.now(tz=UTC),
            resolution_summary="Fixed",
        )
        await incident_repo.save(resolved_incident)

        open_incidents = await incident_repo.find_open_incidents()

        assert len(open_incidents) == 1
        assert open_incidents[0].incident_id == sample_incident.incident_id

    @pytest.mark.asyncio
    async def test_update_incident(
        self, incident_repo: InMemoryIncidentRepository, sample_incident: Incident
    ) -> None:
        """Test updating an existing incident."""
        await incident_repo.save(sample_incident)

        # Update incident
        sample_incident.status = IncidentStatus.ACKNOWLEDGED
        sample_incident.acknowledged_at = datetime.now(tz=UTC)
        await incident_repo.save(sample_incident)

        # Retrieve and verify
        retrieved = await incident_repo.find_by_id(sample_incident.incident_id)

        assert retrieved is not None
        assert retrieved.status == IncidentStatus.ACKNOWLEDGED
        assert retrieved.acknowledged_at is not None


class TestEvidenceRepositoryContract:
    """Contract tests for EvidenceRepository."""

    @pytest.mark.asyncio
    async def test_save_and_retrieve_evidence(
        self, evidence_repo: InMemoryEvidenceRepository, sample_evidence: Evidence
    ) -> None:
        """Test saving and retrieving evidence."""
        await evidence_repo.save(sample_evidence)

        retrieved = await evidence_repo.find_by_id(sample_evidence.evidence_id)

        assert retrieved is not None
        assert retrieved.evidence_id == sample_evidence.evidence_id
        assert retrieved.summary == sample_evidence.summary

    @pytest.mark.asyncio
    async def test_find_by_incident(
        self, evidence_repo: InMemoryEvidenceRepository, sample_evidence: Evidence
    ) -> None:
        """Test finding evidence by incident."""
        sample_evidence.incident_id = "INC-2024-001"
        await evidence_repo.save(sample_evidence)

        evidence_list = await evidence_repo.find_by_incident("INC-2024-001")

        assert len(evidence_list) == 1
        assert evidence_list[0].evidence_id == sample_evidence.evidence_id

    @pytest.mark.asyncio
    async def test_find_recent_evidence(self, evidence_repo: InMemoryEvidenceRepository) -> None:
        """Test finding recent evidence."""
        # Create multiple evidence items
        for i in range(3):
            evidence = Evidence(
                evidence_id=f"evidence-{i:03d}",
                kind=EvidenceKind.LOG_EXCERPT,
                collector=EvidenceCollector.OPENTELEMETRY_LOGS,
                collected_at=datetime.now(tz=UTC) - timedelta(hours=i),
                summary=f"Log entry {i}",
                excerpt=f"Log content {i}",
            )
            await evidence_repo.save(evidence)

        recent = await evidence_repo.find_recent(limit=2)

        assert len(recent) == 2
        # Should be ordered by most recent first
        assert recent[0].evidence_id == "evidence-000"


class TestAuditRepositoryContract:
    """Contract tests for AuditRepository."""

    @pytest.mark.asyncio
    async def test_append_and_retrieve_audit_event(
        self, audit_repo: InMemoryAuditRepository, sample_audit_event: AuditEvent
    ) -> None:
        """Test appending and retrieving audit events."""
        stored = await audit_repo.append(sample_audit_event)

        events = await audit_repo.find_recent(limit=10)

        assert len(events) == 1
        assert events[0].event_id == sample_audit_event.event_id
        # The first event starts the chain: it must not claim a predecessor.
        assert stored.previous_digest is None
        assert await audit_repo.head() == stored

    @pytest.mark.asyncio
    async def test_append_seals_each_event_onto_the_previous_digest(
        self, audit_repo: InMemoryAuditRepository, sample_audit_event: AuditEvent
    ) -> None:
        """Each stored event must carry the digest of the event before it."""
        first = await audit_repo.append(sample_audit_event)
        second = await audit_repo.append(
            sample_audit_event.model_copy(update={"event_id": "AUD-2024-0002"})
        )

        assert second.previous_digest == first.digest

    @pytest.mark.asyncio
    async def test_find_by_subject(
        self, audit_repo: InMemoryAuditRepository, sample_audit_event: AuditEvent
    ) -> None:
        """Test finding audit events by subject."""
        await audit_repo.append(sample_audit_event)

        events = await audit_repo.find_by_subject("INC-2024-001")

        assert len(events) == 1
        assert events[0].subject == "INC-2024-001"

    @pytest.mark.asyncio
    async def test_find_by_incident(
        self, audit_repo: InMemoryAuditRepository, sample_audit_event: AuditEvent
    ) -> None:
        """Test finding audit events by incident."""
        await audit_repo.append(sample_audit_event)

        events = await audit_repo.find_by_incident("INC-2024-001")

        assert len(events) == 1
        assert events[0].incident_id == "INC-2024-001"

    @pytest.mark.asyncio
    async def test_find_by_actor(
        self, audit_repo: InMemoryAuditRepository, sample_audit_event: AuditEvent
    ) -> None:
        """Test finding audit events by actor."""
        await audit_repo.append(sample_audit_event)

        events = await audit_repo.find_by_actor("user@example.com")

        assert len(events) == 1
        assert events[0].actor.actor_id == "user@example.com"

    @pytest.mark.asyncio
    async def test_audit_events_ordered_by_occurred_at(
        self, audit_repo: InMemoryAuditRepository, sample_audit_event: AuditEvent
    ) -> None:
        """Test that audit events are returned newest first."""
        now = datetime.now(tz=UTC)

        for i in range(3):
            await audit_repo.append(
                sample_audit_event.model_copy(
                    update={
                        "event_id": f"AUD-2024-000{i}",
                        "occurred_at": now - timedelta(minutes=i),
                    }
                )
            )

        events = await audit_repo.find_recent()

        # Should be in reverse chronological order
        assert events[0].event_id == "AUD-2024-0000"
        assert events[1].event_id == "AUD-2024-0001"
        assert events[2].event_id == "AUD-2024-0002"

    @pytest.mark.asyncio
    async def test_find_oldest_first_returns_chain_order(
        self, audit_repo: InMemoryAuditRepository, sample_audit_event: AuditEvent
    ) -> None:
        """The chain can only be re-walked in the order events were appended."""
        now = datetime.now(tz=UTC)
        for i in range(3):
            await audit_repo.append(
                sample_audit_event.model_copy(
                    update={
                        "event_id": f"AUD-2024-010{i}",
                        "occurred_at": now + timedelta(minutes=i),
                    }
                )
            )

        ordered = await audit_repo.find_oldest_first()

        assert [event.event_id for event in ordered] == [
            "AUD-2024-0100",
            "AUD-2024-0101",
            "AUD-2024-0102",
        ]


class TestRepositoryLimits:
    """Test that repository methods respect limit parameters."""

    @pytest.mark.asyncio
    async def test_find_by_service_respects_limit(
        self, incident_repo: InMemoryIncidentRepository
    ) -> None:
        """Test that find_by_service respects limit."""
        # Create 10 incidents
        for i in range(10):
            incident = Incident(
                incident_id=f"INC-{i:03d}",
                title=f"Incident {i}",
                severity=Severity.SEV3,
                service=ServiceRef(name="test-service", environment=Environment.PRODUCTION),
                status=IncidentStatus.OPEN,
                detected_at=datetime.now(tz=UTC),
                opened_at=datetime.now(tz=UTC),
            )
            await incident_repo.save(incident)

        # Request only 5
        incidents = await incident_repo.find_by_service("test-service", "production", limit=5)

        assert len(incidents) == 5
