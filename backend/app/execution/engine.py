import asyncio
import json
import re
from pathlib import Path
from datetime import datetime
from typing import TypedDict

from langgraph.graph import END, StateGraph
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.execution.tools import TOOLS, ToolResult
from app.models.artifact import Artifact
from app.models.approval import Approval, ApprovalStatus
from app.models.browser import BrowserSession
from app.models.research import ResearchRecord
from app.models.task import ExecutionCheckpoint, RecoveryEvent, Task, TaskEvent, TaskStatus, TaskStep, ToolCall
from app.browser.manager import BrowserManager
from app.services.approvals import create_approval


class ExecutionState(TypedDict):
    task_id: str
    step_index: int
    tool_calls: int
    last_result: dict
    last_error: str | None
    retries: int
    approved: bool
    status: str
    research_results: list[dict]
    analysis: dict


class ExecutionError(RuntimeError):
    def __init__(self, message: str, category: str) -> None:
        super().__init__(message)
        self.category = category


async def _load_task(session: AsyncSession, task_id: str) -> Task:
    from app.services.task_service import get_task

    task = await get_task(session, task_id)
    if task is None:
        raise ExecutionError("Task not found", "invalid_task")
    return task


def _next_step(task: Task, index: int) -> TaskStep | None:
    ordered = sorted(task.steps, key=lambda step: step.order_index)
    return ordered[index] if index < len(ordered) else None


async def execute_task(session: AsyncSession, task_id: str, settings: Settings, approved: bool = False) -> Task:
    task = await _load_task(session, task_id)
    if task.status in {TaskStatus.CANCELLED, TaskStatus.COMPLETED}:
        return task
    if task.plan is None:
        raise ExecutionError("Task has no saved plan", "invalid_task")
    prior_approval = await session.scalar(select(Approval).where(
        Approval.task_id == task.id,
        Approval.action == "execute_task",
        Approval.status == ApprovalStatus.REJECTED,
    ))
    if prior_approval is not None:
        task.status = TaskStatus.FAILED
        task.error_message = "Execution was rejected and cannot be reused."
        task.events.append(TaskEvent(event_type="execution.blocked", message=task.error_message))
        await session.commit()
        return task
    if task.plan.requires_approval and not approved:
        task.status = TaskStatus.WAITING_APPROVAL
        existing = await session.scalar(select(Approval).where(
            Approval.task_id == task.id,
            Approval.action == "execute_task",
            Approval.status == ApprovalStatus.PENDING,
        ))
        if existing is None:
            approval = await create_approval(
                session,
                task_id=task.id,
                action="execute_task",
                description="Approve execution of the generated task plan.",
                permissions=["execute_plan", "browse_public_sources", "write_workspace_artifacts"],
                agent_name="Execution Controller",
                risk_level="medium",
            )
            task.events.append(TaskEvent(
                event_type="approval.requested",
                message=f"Approval requested: {approval.id}",
            ))
        else:
            task.events.append(TaskEvent(
                event_type="approval.required",
                message="Human approval is required before execution.",
            ))
        await session.commit()
        return task

    checkpoint = await session.scalar(select(ExecutionCheckpoint).where(ExecutionCheckpoint.task_id == task.id))
    if checkpoint is None:
        checkpoint = ExecutionCheckpoint(task_id=task.id)
        session.add(checkpoint)
    task.status = TaskStatus.RUNNING
    task.started_at = task.started_at or datetime.utcnow()
    task.events.append(TaskEvent(event_type="execution.started", message="Execution started with safe tool limits."))
    await session.flush()

    browser_manager = BrowserManager(settings)
    browser_session = BrowserSession(status="created")
    session.add(browser_session)
    await session.flush()
    graph = _build_graph(session, task, checkpoint, settings, browser_manager, browser_session.id)
    state: ExecutionState = {
        "task_id": task.id, "step_index": checkpoint.current_step, "tool_calls": checkpoint.tool_calls, "last_result": {},
        "last_error": None, "retries": 0, "approved": approved, "status": "running",
        "research_results": [], "analysis": {},
    }
    try:
        final = await graph.ainvoke(state)
        task.status = TaskStatus(final["status"])
        if task.status == TaskStatus.COMPLETED:
            task.completed_at = datetime.utcnow()
            task.events.append(TaskEvent(event_type="execution.completed", message="All eligible steps completed."))
    except ExecutionError as error:
        task.status = TaskStatus.FAILED
        task.error_message = str(error)
        task.events.append(TaskEvent(event_type="execution.failed", message=str(error)))
    finally:
        await browser_manager.shutdown()
    await session.commit()
    refreshed = await _load_task(session, task_id)
    return refreshed


def _build_graph(session: AsyncSession, task: Task, checkpoint: ExecutionCheckpoint, settings: Settings, browser_manager: BrowserManager, browser_session_id: str):
    async def validate(state: ExecutionState) -> ExecutionState:
        if not task.steps:
            raise ExecutionError("Plan contains no executable steps", "invalid_plan")
        return state

    async def select_step(state: ExecutionState) -> ExecutionState:
        if state["tool_calls"] >= settings.max_tool_calls:
            raise ExecutionError("Maximum tool-call limit reached", "limit_exceeded")
        if _next_step(task, state["step_index"]) is None:
            state["status"] = "completed"
        return state

    async def execute(state: ExecutionState) -> ExecutionState:
        step = _next_step(task, state["step_index"])
        if step is None:
            return state
        plan_step = task.plan.steps[state["step_index"]]
        tool_name = plan_step["tool_name"]
        tool = TOOLS.get(tool_name)
        if tool is None:
            raise ExecutionError(f"Tool is not allowlisted: {tool_name}", "invalid_tool")
        step.status = "running"
        call = ToolCall(task_id=task.id, tool_name=tool_name, arguments=json.dumps({}))
        session.add(call)
        state["tool_calls"] += 1
        checkpoint.tool_calls = state["tool_calls"]
        source_urls = re.findall(r"https?://[^\s,)\]]+", task.original_instruction)
        arguments = {
            "instruction": task.original_instruction,
            "query": task.original_instruction,
            "criteria": task.plan.verification_criteria,
            "research_results": state["research_results"],
            "source_urls": source_urls,
            "browser_manager": browser_manager,
            "browser_session_id": browser_session_id,
            "db_session": session,
            "_retry": state["retries"] > 0,
        }
        result: ToolResult = await asyncio.wait_for(tool(arguments), settings.max_task_runtime_seconds)
        call.status = "completed" if result.success else "failed"
        call.result = json.dumps(result.output)
        call.error_category = result.error_category
        state["last_result"] = result.output
        if result.output.get("research_results"):
            state["research_results"].extend(
                item for item in result.output["research_results"]
                if item not in state["research_results"]
            )
            for item in result.output["research_results"]:
                session.add(ResearchRecord(
                    task_id=task.id,
                    query=item["query"],
                    source_url=item["source_url"],
                    source_title=item["source_title"],
                    extracted_content=item["extracted_content"],
                    key_findings=item["key_findings"],
                    collected_links=item.get("collected_links", []),
                    collected_at=datetime.fromisoformat(item["collected_at"]),
                    status=item["status"],
                    error_message=item.get("error_message"),
                ))
        if tool_name == "analysis":
            state["analysis"] = result.output
        if not result.success:
            state["last_error"] = result.output.get("message", "Tool failed")
            if state["retries"] >= settings.max_retries:
                raise ExecutionError(state["last_error"], result.error_category or "tool_error")
            return state
        step.status = "completed"
        step.completed_at = datetime.utcnow()
        task.events.append(TaskEvent(event_type="step.completed", message=f"{step.step_name} completed."))
        state["step_index"] += 1
        checkpoint.current_step = state["step_index"]
        await session.flush()
        return state

    async def observe(state: ExecutionState) -> ExecutionState:
        return state

    async def verify(state: ExecutionState) -> ExecutionState:
        if state["last_result"].get("verified") is False:
            raise ExecutionError("Result verification failed", "failed_verification")
        records = (await session.execute(
            select(ResearchRecord).where(ResearchRecord.task_id == task.id)
        )).scalars().all()
        for record in records:
            record.verification_status = "verified" if record.status == "collected" else "unverified"
        await session.flush()
        if _next_step(task, state["step_index"] - 1) and task.plan.steps[state["step_index"] - 1]["tool_name"] == "verification":
            await _generate_report(session, task, state)
        return state

    async def recover(state: ExecutionState) -> ExecutionState:
        if state["retries"] >= settings.max_retries:
            raise ExecutionError(state["last_error"] or "Recovery retry limit reached", "retry_limit")
        state["retries"] += 1
        session.add(RecoveryEvent(task_id=task.id, error_message=state["last_error"] or "tool failure", error_category="tool_error", strategy="bounded retry", retry_number=state["retries"], status="retrying"))
        task.events.append(TaskEvent(event_type="recovery.retry", message=f"Retry {state['retries']} selected."))
        state["last_error"] = None
        return state

    async def complete(state: ExecutionState) -> ExecutionState:
        state["status"] = "completed"
        return state

    async def approval(state: ExecutionState) -> ExecutionState:
        state["status"] = "waiting_approval"
        return state

    graph = StateGraph(ExecutionState)
    graph.add_node("plan_validation", validate)
    graph.add_node("tool_selection", select_step)
    graph.add_node("execution", execute)
    graph.add_node("observation", observe)
    graph.add_node("verification", verify)
    graph.add_node("recovery", recover)
    graph.add_node("human_approval", approval)
    graph.add_node("completion", complete)
    graph.set_entry_point("plan_validation")
    graph.add_edge("plan_validation", "tool_selection")
    graph.add_conditional_edges("tool_selection", lambda state: "completion" if state["status"] == "completed" else "execution")
    graph.add_conditional_edges("execution", lambda state: "recovery" if state["last_error"] else "observation")
    graph.add_edge("observation", "verification")
    graph.add_edge("verification", "tool_selection")
    graph.add_edge("recovery", "tool_selection")
    graph.add_edge("human_approval", END)
    graph.add_edge("completion", END)
    return graph.compile()


async def _generate_report(session: AsyncSession, task: Task, state: ExecutionState) -> None:
    workspace = Path(Settings().ghostos_workspace)
    report_dir = workspace / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    safe_id = task.id
    json_path = report_dir / f"web3_hackathon_research_{safe_id}.json"
    report_path = report_dir / "web3_hackathon_research.md"
    results = state["research_results"]
    verified = [finding for result in results if result["status"] == "collected" for finding in result["key_findings"]]
    unverified = [result for result in results if result["status"] != "collected"]
    limitations = [
        f"- {item.get('source_url', 'source')}: {item.get('error_message', 'No verified findings.')}"
        for item in unverified
    ] or ["- None recorded."]
    report = "\n".join([
        "# Web3 Hackathon Research",
        "",
        "## Executive summary",
        f"Research collected {len(results)} source record(s) and {len(verified)} evidence-backed finding(s).",
        "",
        "## Researched hackathons and official sources",
        *[f"- [{result['source_title'] or 'Unavailable'}]({result['source_url']})" for result in results],
        "",
        "## Eligibility, deadlines, and submission requirements",
        "Only information present in the collected source evidence is reported below; unavailable details remain unverified.",
        *[f"- {finding}" for result in results for finding in result["key_findings"]],
        "",
        "## Eligibility comparison",
        *[f"- {result['source_title'] or result['source_url']}: compare eligibility against the evidence above." for result in results],
        "",
        "## Recommendation",
        "Recommendation: prioritize the opportunity whose official source provides the strongest evidence for the requested criteria. This recommendation is AI-generated and is not a sourced fact.",
        "",
        "## Submission preparation checklist",
        "- Confirm eligibility from the official event rules.",
        "- Confirm deadline and submission format from the official source.",
        "- Preserve source links and evidence before submission.",
        "",
        "## Unverified information and limitations",
        *limitations,
    ])
    json_path.write_text(json.dumps({"query": task.original_instruction, "results": results, "analysis": state["analysis"]}, indent=2), encoding="utf-8")
    report_path.write_text(report, encoding="utf-8")
    session.add(Artifact(task_id=task.id, filename=report_path.name, file_path=str(report_path), content_type="text/markdown"))
    session.add(Artifact(task_id=task.id, filename=json_path.name, file_path=str(json_path), content_type="application/json"))
    await session.flush()
