from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.browser.manager import BrowserManager, BrowserUnavailable
from app.models.browser import BrowserSession


class ResearchResult(BaseModel):
    query: str
    source_url: str
    source_title: str
    extracted_content: str
    key_findings: list[str] = Field(default_factory=list)
    collected_links: list[str] = Field(default_factory=list)
    collected_at: datetime
    status: str
    error_message: str | None = None


@dataclass(frozen=True)
class ToolResult:
    success: bool
    output: dict[str, Any]
    error_category: str | None = None


Tool = Callable[[dict[str, Any]], Awaitable[ToolResult]]


async def planner_tool(arguments: dict[str, Any]) -> ToolResult:
    return ToolResult(True, {"message": "Plan structure validated.", "instruction": arguments.get("instruction", "")})


async def analysis_tool(arguments: dict[str, Any]) -> ToolResult:
    results = arguments.get("research_results", [])
    findings = [finding for result in results for finding in result.get("key_findings", [])]
    return ToolResult(True, {"research_count": len(results), "evidence_findings": findings, "analysis_ready": bool(results)})


async def verification_tool(arguments: dict[str, Any]) -> ToolResult:
    results = arguments.get("research_results", [])
    verified = bool(results) and all(
        result.get("source_url") and result.get("extracted_content") and result.get("key_findings")
        for result in results
    )
    return ToolResult(True, {"verified": verified, "verified_findings": sum(len(r.get("key_findings", [])) for r in results), "criteria_checked": arguments.get("criteria", [])})


def _findings(text: str, query: str) -> list[str]:
    terms = {term.lower() for term in query.split() if len(term) > 3}
    sentences = [sentence.strip() for sentence in text.replace("\n", " ").split(".") if sentence.strip()]
    matching = [sentence + "." for sentence in sentences if any(term in sentence.lower() for term in terms)]
    return matching[:10] or sentences[:5]


async def research_tool(arguments: dict[str, Any]) -> ToolResult:
    query = str(arguments.get("query") or arguments.get("instruction") or "").strip()
    manager: BrowserManager | None = arguments.get("browser_manager")
    session_id = arguments.get("browser_session_id")
    db: AsyncSession | None = arguments.get("db_session")
    urls = arguments.get("source_urls", [])
    if not manager or not session_id or not db:
        return ToolResult(False, {"message": "Research requires an active browser session and database context."}, "configuration_error")
    if not urls:
        return ToolResult(False, {"message": "No approved source URLs were provided; research cannot invent sources."}, "invalid_research_input")
    results: list[dict[str, Any]] = []
    browser_session = await db.get(BrowserSession, session_id)
    if browser_session is None:
        return ToolResult(False, {"message": "Browser session not found."}, "invalid_browser_session")
    for url in dict.fromkeys(urls):
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            continue
        try:
            await manager.open_url(db, browser_session, url)
            content = await manager.content(browser_session)
            if not content["text"].strip():
                raise BrowserUnavailable("The page contained no visible content.")
            result = ResearchResult(
                query=query,
                source_url=content["url"],
                source_title=content["title"],
                extracted_content=content["text"][:20_000],
                key_findings=_findings(content["text"], query),
                collected_links=content.get("links", []),
                collected_at=datetime.utcnow(),
                status="collected",
            )
            results.append(result.model_dump(mode="json"))
        except BrowserUnavailable as error:
            results.append(ResearchResult(
                query=query, source_url=url, source_title="", extracted_content="",
                collected_at=datetime.utcnow(), status="failed", error_message=str(error),
            ).model_dump(mode="json"))
    successful = [item for item in results if item["status"] == "collected"]
    if not successful:
        return ToolResult(False, {"research_results": results, "message": "All research sources failed."}, "research_failed")
    return ToolResult(True, {"research_results": results, "sources_collected": len(successful)})


async def fail_once_tool(arguments: dict[str, Any]) -> ToolResult:
    if not arguments.get("_retry"):
        return ToolResult(False, {"message": "Deterministic failure for recovery testing."}, "temporary_network_error")
    return ToolResult(True, {"message": "Recovered on bounded retry."})


TOOLS: dict[str, Tool] = {
    "planner": planner_tool,
    "analysis": analysis_tool,
    "research": research_tool,
    "verification": verification_tool,
    "test_fail_once": fail_once_tool,
}
