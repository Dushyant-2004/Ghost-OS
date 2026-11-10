from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.approval import Approval, ApprovalStatus
from app.models.task import RecoveryEvent, Task, TaskStatus, ToolCall


async def summary(session: AsyncSession, start: datetime | None = None, end: datetime | None = None) -> dict:
    task_filter = []
    if start:
        task_filter.append(Task.created_at >= start)
    if end:
        task_filter.append(Task.created_at <= end)
    scoped = select(Task).where(*task_filter).subquery()
    total = await session.scalar(select(func.count()).select_from(scoped)) or 0
    completed = await session.scalar(select(func.count()).select_from(scoped).where(scoped.c.status == TaskStatus.COMPLETED)) or 0
    failed = await session.scalar(select(func.count()).select_from(scoped).where(scoped.c.status == TaskStatus.FAILED)) or 0
    cancelled = await session.scalar(select(func.count()).select_from(scoped).where(scoped.c.status == TaskStatus.CANCELLED)) or 0
    task_ids = select(scoped.c.id)
    tools = await session.scalar(select(func.count()).select_from(ToolCall).where(ToolCall.task_id.in_(task_ids))) or 0
    recoveries = await session.scalar(select(func.count()).select_from(RecoveryEvent).where(RecoveryEvent.task_id.in_(task_ids))) or 0
    successful_recoveries = await session.scalar(select(func.count()).select_from(RecoveryEvent).where(
        RecoveryEvent.status == "recovered", RecoveryEvent.task_id.in_(task_ids)
    )) or 0
    approved = await session.scalar(select(func.count()).select_from(Approval).where(Approval.status == ApprovalStatus.APPROVED)) or 0
    durations = await session.scalar(select(func.avg(
        func.julianday(scoped.c.completed_at) - func.julianday(scoped.c.started_at)
    )).where(scoped.c.completed_at.is_not(None), scoped.c.started_at.is_not(None))) 
    return {
        "total_tasks": total,
        "completed_tasks": completed,
        "failed_tasks": failed,
        "cancelled_tasks": cancelled,
        "success_rate": completed / total if total else None,
        "tool_calls": tools,
        "recovery_attempts": recoveries,
        "successful_recoveries": successful_recoveries,
        "approved_requests": approved,
        "average_duration_seconds": round(float(durations or 0) * 86400, 3),
        "model_usage": "unavailable: provider usage telemetry is not configured",
    }
