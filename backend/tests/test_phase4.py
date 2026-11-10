import pytest
from httpx import ASGITransport, AsyncClient

from app.database.session import init_db
from app.main import app


@pytest.mark.asyncio
async def test_revisions_dependencies_schedules_and_analytics():
    await init_db()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first = (await client.post("/api/tasks", json={"instruction": "Research Web3 events"})).json()
        second = (await client.post("/api/tasks", json={"instruction": "Prepare a project brief"})).json()

        revision = await client.post(
            f"/api/tasks/{first['id']}/revisions",
            json={"reason": "The primary source was unavailable.", "affected_step": "Gather required information"},
        )
        assert revision.status_code == 200
        assert revision.json()["version"] == 1

        link = await client.post(
            f"/api/tasks/{second['id']}/dependencies",
            json={"depends_on_task_id": first["id"]},
        )
        assert link.status_code == 200
        graph = await client.get("/api/orchestration")
        assert any(item["task_id"] == second["id"] for item in graph.json()["dependencies"])

        schedule = await client.post("/api/schedules", json={
            "instruction": "Research weekly Web3 events",
            "recurrence": "weekly",
            "timezone": "UTC",
            "run_at": "2027-01-01T09:00:00",
        })
        assert schedule.status_code == 201
        schedule_id = schedule.json()["id"]
        paused = await client.post(f"/api/schedules/{schedule_id}/pause")
        assert paused.json()["status"] == "paused"
        resumed = await client.post(f"/api/schedules/{schedule_id}/resume")
        assert resumed.json()["status"] == "active"

        analytics = await client.get("/api/analytics")
        assert analytics.status_code == 200
        assert analytics.json()["total_tasks"] >= 2
        export = await client.get("/api/analytics/export?format=csv")
        assert export.status_code == 200
        assert "metric,value" in export.text
