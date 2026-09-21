"""Demo CRUD endpoints for the ``items`` resource.

These endpoints exercise the full stack: structured logging, metrics,
Redis caching, PostgreSQL persistence and the controllable failure mode.
The failure mode is gated behind the ``failure_mode`` setting and is only
permitted in development environments (enforced by the settings validator).
"""

from __future__ import annotations

import json
import logging
import random
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from services.demo_api.db.models import Item
from services.demo_api.db.session import get_session
from services.demo_api.observability.instrumentation import timed_db_operation
from services.demo_api.observability.metrics import (
    failures_injected_total,
    items_created_total,
    items_deleted_total,
)
from services.demo_api.redis_client import get_cache, set_cache

router = APIRouter(prefix="/items", tags=["items"])
logger = logging.getLogger("demo-api.items")


class ItemIn(BaseModel):
    """Create / update request body for an item."""

    name: str = Field(..., min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    is_active: bool = True


class ItemOut(BaseModel):
    """Serialised item representation returned to clients."""

    id: int
    name: str
    description: str | None
    is_active: bool
    created_at: str


def maybe_inject_failure(request: Request) -> bool:
    """Return ``True`` if the failure mode should be triggered for this request."""
    app = request.app
    settings = app.state.settings
    if settings.failure_mode is None:
        return False

    if random.random() >= settings.failure_rate:
        return False

    failures_injected_total.labels(failure_mode=settings.failure_mode.value).inc()
    logger.warning("Injecting failure mode=%s for path=%s", settings.failure_mode, request.url.path)
    return True


def _serialize_item(item: Item) -> ItemOut:
    """Convert a SQLAlchemy model to the API response model."""
    return ItemOut(
        id=item.id,
        name=item.name,
        description=item.description,
        is_active=item.is_active,
        created_at=item.created_at.isoformat(),
    )


SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.get("/", response_model=list[ItemOut])
async def list_items(
    request: Request,
    session: SessionDep,
) -> list[ItemOut]:
    """List all items, with results cached in Redis for 60 seconds."""
    if maybe_inject_failure(request):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="failure_mode=error_rate: service temporarily unavailable",
        )

    cache_key = "items:all"
    cached = await get_cache(cache_key)
    if cached is not None:
        logger.info("Cache hit for %s", cache_key)
        raw: list[dict[str, Any]] = json.loads(cached)
        return [ItemOut.model_validate(item) for item in raw]

    async with timed_db_operation("select"):
        result = await session.execute(select(Item))
    items = list(result.scalars().all())
    logger.info("Retrieved %d items from database", len(items))

    serialized = [_serialize_item(item) for item in items]
    await set_cache(cache_key, json.dumps([item.model_dump(mode="json") for item in serialized]))
    return serialized


@router.post("/", response_model=ItemOut, status_code=status.HTTP_201_CREATED)
async def create_item(
    request: Request,
    payload: ItemIn,
    session: SessionDep,
) -> ItemOut:
    """Create a new item."""
    if maybe_inject_failure(request):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="failure_mode=error_rate: service temporarily unavailable",
        )

    item = Item(name=payload.name, description=payload.description, is_active=payload.is_active)
    async with timed_db_operation("insert"):
        session.add(item)
        await session.commit()
        await session.refresh(item)
    items_created_total.inc()
    logger.info("Created item id=%s name=%s", item.id, item.name)
    return _serialize_item(item)


@router.get("/{item_id}", response_model=ItemOut)
async def get_item(
    request: Request,
    item_id: int,
    session: SessionDep,
) -> ItemOut:
    """Retrieve a single item by ID."""
    if maybe_inject_failure(request):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="failure_mode=error_rate: service temporarily unavailable",
        )

    async with timed_db_operation("select"):
        result = await session.execute(select(Item).where(Item.id == item_id))
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    return _serialize_item(item)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(
    request: Request,
    item_id: int,
    session: SessionDep,
) -> None:
    """Delete an item by ID."""
    if maybe_inject_failure(request):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="failure_mode=error_rate: service temporarily unavailable",
        )

    async with timed_db_operation("delete"):
        raw_result = await session.execute(delete(Item).where(Item.id == item_id))
    deleted: int = getattr(raw_result, "rowcount", 0) or 0
    if deleted == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    async with timed_db_operation("delete"):
        await session.commit()
    items_deleted_total.inc()
    logger.info("Deleted item id=%s", item_id)
