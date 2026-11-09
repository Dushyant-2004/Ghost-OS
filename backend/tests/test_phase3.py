import pytest
from httpx import ASGITransport, AsyncClient

from app.database.session import init_db
from app.main import app


@pytest.mark.asyncio
async def test_approval_center_rejects_reuse_and_artifact_listing():
    await init_db()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post("/api/tasks", json={"instruction": "Prepare a Web3 research plan"})
        task = created.json()
        waiting = await client.post(f"/api/tasks/{task['id']}/execute", json={"approved": False})
        assert waiting.json()["status"] == "waiting_approval"
        approvals = await client.get("/api/approvals")
        approval = next(item for item in approvals.json() if item["task_id"] == task["id"])
        rejected = await client.post(
            f"/api/approvals/{approval['id']}/reject",
            json={"actor": "test", "reason": "Not authorized"},
        )
        assert rejected.json()["status"] == "rejected"
        reused = await client.post(
            f"/api/approvals/{approval['id']}/approve",
            json={"actor": "test"},
        )
        assert reused.status_code == 409
        artifacts = await client.get("/api/artifacts")
        assert artifacts.status_code == 200


@pytest.mark.asyncio
async def test_desktop_automation_is_disabled_by_default():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        status = await client.get("/api/desktop/status")
        assert status.json()["enabled"] is False
        screenshot = await client.post("/api/desktop/screenshot")
        assert screenshot.status_code == 503
