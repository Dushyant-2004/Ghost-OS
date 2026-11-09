import asyncio
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.database.session import init_db
from app.main import app
from app.execution.tools import ResearchResult, ToolResult, research_tool
from app.database.session import SessionLocal
from app.models.browser import BrowserSession
from app.browser.manager import BrowserStartupError


class _ResearchPage(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        body = (
            b"<html><title>Local Web3 Hackathon</title><body>"
            b"Applications close on 2026-12-01. Teams must submit a working demo and repository."
            b"</body></html>"
        )
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_: object) -> None:
        return


@pytest.fixture
def local_page():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _ResearchPage)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}/hackathon"
    server.shutdown()
    thread.join(timeout=2)


@pytest.mark.asyncio
async def test_web3_research_workflow_generates_verified_artifacts(local_page: str):
    await init_db()
    instruction = f"Research this Web3 hackathon and report eligibility, deadlines, and submission requirements: {local_page}"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post("/api/tasks", json={"instruction": instruction})
        assert created.status_code == 201
        task_id = created.json()["id"]
        waiting = await client.post(f"/api/tasks/{task_id}/execute", json={"approved": False})
        assert waiting.json()["status"] == "waiting_approval"
        completed = await client.post(f"/api/tasks/{task_id}/execute", json={"approved": True})
        result = completed.json()

    assert result["status"] == "completed"
    assert len(result["research_records"]) == 1
    assert result["research_records"][0]["status"] == "collected"
    assert result["research_records"][0]["verification_status"] == "verified"
    assert {artifact["content_type"] for artifact in result["artifacts"]} == {"text/markdown", "application/json"}
    assert Path(result["artifacts"][0]["file_path"]).is_file()


@pytest.mark.asyncio
async def test_research_tool_rejects_missing_sources():
    result = await research_tool({"query": "Web3 hackathon", "source_urls": []})
    assert result.success is False
    assert result.error_category == "configuration_error"


def test_research_result_requires_explicit_status():
    result = ResearchResult(
        query="Web3 hackathon",
        source_url="https://example.com",
        source_title="Example",
        extracted_content="Evidence",
        key_findings=["Evidence"],
        collected_at=__import__("datetime").datetime.utcnow(),
        status="collected",
    )
    assert result.status == "collected"


@pytest.mark.asyncio
async def test_research_preserves_failure_details_for_empty_content():
    class EmptyBrowser:
        async def open_url(self, *_args):
            return {}

        async def content(self, *_args):
            return {"url": "https://example.com", "title": "Empty", "text": "", "links": []}

    await init_db()
    async with SessionLocal() as session:
        browser_session = BrowserSession()
        session.add(browser_session)
        await session.commit()
        result = await research_tool({
            "query": "Web3 hackathon",
            "source_urls": ["https://example.com"],
            "browser_manager": EmptyBrowser(),
            "browser_session_id": browser_session.id,
            "db_session": session,
        })
    assert result.success is False
    assert result.error_category == "research_failed"
    assert result.output["research_results"][0]["status"] == "failed"


@pytest.mark.asyncio
async def test_research_reports_browser_startup_failure():
    class BrokenBrowser:
        async def open_url(self, *_args):
            raise BrowserStartupError("Chromium failed to launch")

    await init_db()
    async with SessionLocal() as session:
        browser_session = BrowserSession()
        session.add(browser_session)
        await session.commit()
        result = await research_tool({
            "query": "Web3 hackathon",
            "source_urls": ["https://example.com"],
            "browser_manager": BrokenBrowser(),
            "browser_session_id": browser_session.id,
            "db_session": session,
        })
    assert result.success is False
    assert "Chromium failed" in result.output["research_results"][0]["error_message"]
