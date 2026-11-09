import pytest
from httpx import ASGITransport, AsyncClient

from app.database.session import init_db
from app.main import app
from app.coding.workspace import CodingWorkspace, WorkspaceViolation
from app.core.config import Settings


@pytest.fixture(autouse=True)
async def database():
    await init_db()


@pytest.mark.asyncio
async def test_health_and_task_lifecycle():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        health = await client.get("/api/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"

        created = await client.post("/api/tasks", json={"instruction": "Prepare a launch checklist"})
        assert created.status_code == 201
        task = created.json()
        assert task["status"] == "pending"
        assert task["plan"]["provider"] == "demo"
        assert len(task["steps"]) == 4

        listed = await client.get("/api/tasks")
        assert listed.status_code == 200
        assert listed.json()[0]["id"] == task["id"]

        detail = await client.get(f"/api/tasks/{task['id']}")
        assert detail.status_code == 200
        assert detail.json()["events"][0]["event_type"] == "task.created"

        executed = await client.post(f"/api/tasks/{task['id']}/execute", json={"approved": True})
        assert executed.status_code == 200
        assert executed.json()["status"] == "failed"
        assert any(event["event_type"] == "recovery.retry" for event in executed.json()["events"])


def test_workspace_rejects_traversal(tmp_path):
    workspace = CodingWorkspace(Settings(ghostos_workspace=str(tmp_path)))
    with pytest.raises(WorkspaceViolation):
        workspace.create_project("../outside", {"main.py": "print('no')"})
