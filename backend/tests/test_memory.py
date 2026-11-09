from datetime import datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from app.database.session import init_db
from app.main import app


@pytest.mark.asyncio
async def test_memory_persists_retrieves_safely_updates_and_deletes():
    await init_db()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post("/api/memories", json={
            "category": "user_preference",
            "content": "Prefer TypeScript and Tailwind for frontend projects.",
            "importance": 8,
            "confidence": 9,
        })
        assert created.status_code == 201
        memory = created.json()

        relevant = await client.get("/api/memories", params={"query": "TypeScript frontend"})
        assert [item["memory_id"] for item in relevant.json()] == [memory["memory_id"]]

        updated = await client.patch(
            f"/api/memories/{memory['memory_id']}",
            json={"content": "Prefer TypeScript, Tailwind, and strict type checking."},
        )
        assert updated.status_code == 200
        assert "strict type checking" in updated.json()["content"]

        duplicate = await client.post("/api/memories", json={
            "category": "user_preference",
            "content": "Prefer TypeScript, Tailwind, and strict type checking.",
        })
        assert duplicate.json()["memory_id"] == memory["memory_id"]

        secret = await client.post("/api/memories", json={
            "category": "technical_context",
            "content": "api_key=do-not-store",
        })
        assert secret.status_code == 400

        deleted = await client.delete(f"/api/memories/{memory['memory_id']}")
        assert deleted.status_code == 204
        assert (await client.get(f"/api/memories/{memory['memory_id']}")).status_code == 404


@pytest.mark.asyncio
async def test_expired_memory_is_not_retrieved():
    await init_db()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/api/memories", json={
            "category": "project",
            "content": "Temporary project context for expiration testing.",
            "expiration_at": (datetime.utcnow() - timedelta(minutes=1)).isoformat(),
        })
        result = await client.get("/api/memories", params={"query": "temporary project context"})
        assert result.json() == []
