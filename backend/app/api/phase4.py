import csv
import io
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.database.session import get_db
from app.models.phase4 import OrchestrationLink, PlanRevision, Schedule
from app.models.task import Task
from app.services.analytics import summary
from app.services.scheduling import next_run, normalize_run_at

router = APIRouter(prefix="/api", tags=["phase4"])


class RevisionRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=2_000)
    affected_step: str = Field(min_length=1, max_length=120)


class ScheduleRequest(BaseModel):
    instruction: str = Field(min_length=3, max_length=10_000)
    recurrence: str = "once"
    timezone: str = "UTC"
    run_at: datetime
    priority: int = Field(default=5, ge=1, le=10)


class LinkRequest(BaseModel):
    depends_on_task_id: str


@router.post("/tasks/{task_id}/revisions")
async def create_revision(task_id: str, request: RevisionRequest, session: AsyncSession = Depends(get_db)) -> dict:
    task = await session.get(Task, task_id)
    if task is None:
        raise HTTPException(404, "Task not found")
    current = await session.scalar(select(PlanRevision).where(PlanRevision.task_id == task_id).order_by(PlanRevision.version.desc()))
    version = (current.version if current else 0) + 1
    if version > get_settings().max_replans:
        raise HTTPException(409, "Maximum replanning attempts reached")
    revision = PlanRevision(task_id=task_id, version=version, reason=request.reason, affected_step=request.affected_step)
    session.add(revision)
    await session.commit()
    return {"id": revision.id, "task_id": task_id, "version": version, "reason": revision.reason, "affected_step": revision.affected_step}


@router.get("/tasks/{task_id}/revisions")
async def list_revisions(task_id: str, session: AsyncSession = Depends(get_db)) -> list[dict]:
    revisions = (await session.execute(select(PlanRevision).where(PlanRevision.task_id == task_id).order_by(PlanRevision.version))).scalars()
    return [{"id": item.id, "version": item.version, "reason": item.reason, "affected_step": item.affected_step, "created_at": item.created_at} for item in revisions]


@router.post("/tasks/{task_id}/dependencies")
async def add_dependency(task_id: str, request: LinkRequest, session: AsyncSession = Depends(get_db)) -> dict:
    if task_id == request.depends_on_task_id or await session.get(Task, task_id) is None or await session.get(Task, request.depends_on_task_id) is None:
        raise HTTPException(400, "Both distinct tasks must exist")
    link = OrchestrationLink(task_id=task_id, depends_on_task_id=request.depends_on_task_id)
    session.add(link)
    await session.commit()
    return {"id": link.id, "task_id": task_id, "depends_on_task_id": request.depends_on_task_id}


@router.get("/orchestration")
async def orchestration(session: AsyncSession = Depends(get_db)) -> dict:
    tasks = (await session.execute(select(Task).order_by(Task.created_at.desc()).limit(100))).scalars().all()
    links = (await session.execute(select(OrchestrationLink))).scalars().all()
    return {
        "tasks": [{"id": task.id, "title": task.title, "status": task.status, "priority": 5} for task in tasks],
        "dependencies": [{"task_id": link.task_id, "depends_on_task_id": link.depends_on_task_id} for link in links],
    }


@router.post("/schedules", status_code=201)
async def create_schedule(request: ScheduleRequest, session: AsyncSession = Depends(get_db)) -> dict:
    try:
        run_at = normalize_run_at(request.run_at, request.timezone)
        following = next_run(request.recurrence, run_at)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
    schedule = Schedule(**request.model_dump(exclude={"run_at"}), run_at=run_at, next_run_at=following)
    session.add(schedule)
    await session.commit()
    return {"id": schedule.id, "status": schedule.status, "next_run_at": schedule.next_run_at, "recurrence": schedule.recurrence}


@router.get("/schedules")
async def list_schedules(session: AsyncSession = Depends(get_db)) -> list[dict]:
    items = (await session.execute(select(Schedule).order_by(Schedule.next_run_at))).scalars()
    return [{"id": item.id, "instruction": item.instruction, "recurrence": item.recurrence, "timezone": item.timezone, "status": item.status, "next_run_at": item.next_run_at, "last_run_at": item.last_run_at} for item in items]


@router.post("/schedules/{schedule_id}/{action}")
async def schedule_action(schedule_id: str, action: str, session: AsyncSession = Depends(get_db)) -> dict:
    schedule = await session.get(Schedule, schedule_id)
    if schedule is None:
        raise HTTPException(404, "Schedule not found")
    if action not in {"pause", "resume", "cancel"}:
        raise HTTPException(400, "Action must be pause, resume, or cancel")
    schedule.status = {"pause": "paused", "resume": "active", "cancel": "cancelled"}[action]
    await session.commit()
    return {"id": schedule.id, "status": schedule.status}


@router.get("/analytics")
async def analytics(start: datetime | None = None, end: datetime | None = None, session: AsyncSession = Depends(get_db)) -> dict:
    return await summary(session, start, end)


@router.get("/analytics/export")
async def analytics_export(format: str = "json", start: datetime | None = None, end: datetime | None = None, session: AsyncSession = Depends(get_db)):
    data = await summary(session, start, end)
    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["metric", "value"])
        writer.writerows(data.items())
        return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=analytics.csv"})
    return data
