"""Contract tests for the items CRUD endpoints.

The app is served through ``httpx.ASGITransport`` against an in-memory SQLite database and an in-process Redis
double, so this tier stays fast and hermetic. The same handlers are exercised against real PostgreSQL and Redis
in the integration tier, which is why the connection string here is deliberately a file-less SQLite URL.
"""

from __future__ import annotations

from httpx import AsyncClient
import pytest

pytestmark = pytest.mark.contract


async def test_list_items(async_client: AsyncClient) -> None:
    """GET /items returns the seeded item."""
    response = await async_client.get("/items/")
    assert response.status_code == 200
    items = response.json()
    assert isinstance(items, list)
    assert len(items) >= 1


async def test_create_item(async_client: AsyncClient) -> None:
    """POST /items creates a new item."""
    response = await async_client.post(
        "/items/",
        json={"name": "created-item", "description": "A new item"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "created-item"
    assert data["is_active"] is True


async def test_get_item(async_client: AsyncClient) -> None:
    """GET /items/{id} returns the created item."""
    # First create an item
    create_resp = await async_client.post("/items/", json={"name": "gettable-item"})
    item_id = create_resp.json()["id"]

    # Then fetch it
    response = await async_client.get(f"/items/{item_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == item_id
    assert data["name"] == "gettable-item"


async def test_get_item_not_found(async_client: AsyncClient) -> None:
    """GET /items/{id} returns 404 for a missing item."""
    response = await async_client.get("/items/999999")
    assert response.status_code == 404


async def test_delete_item(async_client: AsyncClient) -> None:
    """DELETE /items/{id} removes the item."""
    create_resp = await async_client.post("/items/", json={"name": "to-delete"})
    item_id = create_resp.json()["id"]

    del_resp = await async_client.delete(f"/items/{item_id}")
    assert del_resp.status_code == 204

    # Confirm it is gone
    get_resp = await async_client.get(f"/items/{item_id}")
    assert get_resp.status_code == 404
