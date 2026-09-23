"""Asynchronous writer for the append-only audit trail.

:class:`packages.governance.audit.AuditTrail` writes to an in-process or file sink synchronously. The
control-plane services store the trail in the same database as the aggregates they describe, so the writer
has to be asynchronous — but it must keep the property that makes the trail trustworthy: **every stored event
carries the digest of the event before it**, so a rewritten or reordered history is detectable.

:class:`AsyncAuditWriter` is that writer. It reads the current head, seals the new event onto it and appends
through :class:`~packages.persistence.repositories.AuditRepository`, which never updates a stored row.
:meth:`AsyncAuditWriter.verify` re-walks the stored chain and raises :class:`AuditChainError` when it does not
verify, which is the assertion the integration tests make after an incident has been driven through its whole
lifecycle.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final

from packages.contracts.audit import (
    AuditActor,
    AuditEvent,
    AuditEventType,
    AuditResult,
)
from packages.contracts.common import Digest, Identifier
from packages.governance.audit import AuditLogError, bounded_attributes
from packages.governance.support import AUDIT_EVENT_PREFIX, Clock, IdSource, new_identifier, utc_now
from packages.persistence.repositories import AuditRepository

#: How many stored events a single verification walk reads. The trail is append-only, so verification is
#: bounded by policy rather than by memory: an operator verifying a longer history pages through it.
VERIFY_LIMIT: Final[int] = 10_000


class AuditChainError(AuditLogError):
    """Raised when the stored audit chain does not verify."""


class AsyncAuditWriter:
    """Write audit events to a repository, sealing each one onto the stored chain."""

    def __init__(
        self,
        repository: AuditRepository,
        *,
        clock: Clock = utc_now,
        id_source: IdSource | None = None,
    ) -> None:
        """Bind the writer to a repository.

        Parameters
        ----------
        repository
            Store the events are appended to. It must implement the append-only contract.
        clock
            Returns the current time; injectable so a test can pin the recorded timestamps.
        id_source
            Returns the random part of a new event identifier; injectable for reproducibility.
        """
        self._repository = repository
        self._clock = clock
        self._id_source = id_source

    @property
    def repository(self) -> AuditRepository:
        """Return the store this writer appends to."""
        return self._repository

    async def record(
        self,
        *,
        event_type: AuditEventType,
        actor: AuditActor,
        subject: Identifier,
        result: AuditResult,
        correlation_id: Identifier,
        incident_id: Identifier | None = None,
        approval_id: Identifier | None = None,
        action_hash: Digest | None = None,
        tool: Identifier | None = None,
        before: Mapping[str, Any] | None = None,
        after: Mapping[str, Any] | None = None,
        attributes: Mapping[str, str] | None = None,
    ) -> AuditEvent:
        """Append one event, chained onto the current head, and return the stored record."""
        head = await self._repository.head()
        event = AuditEvent(
            event_id=new_identifier(AUDIT_EVENT_PREFIX, source=self._id_source),
            occurred_at=self._clock(),
            actor=actor,
            event_type=event_type,
            subject=subject,
            result=result,
            correlation_id=correlation_id,
            incident_id=incident_id,
            approval_id=approval_id,
            action_hash=action_hash,
            tool=tool,
            before=dict(before) if before else None,
            after=dict(after) if after else None,
            attributes=bounded_attributes(attributes or {}),
            previous_digest=head.digest if head is not None else None,
        )
        return await self._repository.append(event)

    async def verify(self, limit: int = VERIFY_LIMIT) -> int:
        """Walk the stored chain and return the number of verified events.

        Raises
        ------
        AuditChainError
            When an event does not chain onto its predecessor, or when the store returns a history that is
            longer than ``limit`` (a caller that pages must verify the pages itself, never a truncated view).
        """
        events = await self._repository.find_oldest_first(limit=limit + 1)
        if len(events) > limit:
            raise AuditChainError(
                f"the audit chain is longer than the {limit} events this verification covers"
            )
        previous: AuditEvent | None = None
        for index, event in enumerate(events):
            if not event.follows(previous):
                raise AuditChainError(f"audit chain is broken at index {index} ({event.event_id})")
            previous = event
        return len(events)
