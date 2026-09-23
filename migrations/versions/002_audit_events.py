"""Audit events: the append-only, hash-chained trail the control plane writes to.

The trail exists to answer "who did what, on whose behalf, and in what order" after the fact, which
is why it is a table of its own rather than a JSON blob on the aggregate it describes: an incident
row is updated as the incident moves through its lifecycle, while an audit event is *never* updated
or deleted. ``digest`` and ``previous_digest`` are what make a rewritten or reordered history
detectable, so both are stored in full (see ``packages.persistence.audit_writer``).

The table is created from the single definition in ``packages.persistence.tables`` instead of being
re-declared here: the schema and its data access must not drift apart.
"""

from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.schema import DropTable

from packages.persistence.tables import audit_events

version = 2
description = "Audit events: append-only, hash-chained audit trail"


async def up(conn: AsyncConnection, _metadata: MetaData) -> None:
    """Create the audit-events table and its indexes."""
    await conn.run_sync(audit_events.create, checkfirst=True)


async def down(conn: AsyncConnection, _metadata: MetaData) -> None:
    """Drop the audit-events table."""
    await conn.run_sync(DropTable(audit_events))
