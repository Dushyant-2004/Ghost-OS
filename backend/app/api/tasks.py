from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.database.session import get_db
from app.execution.engine import execute_task
from app.models.task import TaskEvent, TaskStatus
from app.schemas.task import ExecutionRequest, TaskCreate, TaskDetailResponse, TaskResponse
from app.services.task_service import create_task, get_task, list_tasks

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _detail(task) -> TaskDetailResponse:
    response = TaskDetailResponse.model_validate(task)
    successful = [item for item in task.research_records if item.status == "collected"]
    verified = sum(len(item.key_findings) for item in task.research_records if item.verification_status == "verified")
    unverified = sum(len(item.key_findings) for item in task.research_records if item.verification_status != "verified")
    response.research_status = "completed" if successful and task.status == TaskStatus.COMPLETED else (
        "failed" if task.status == TaskStatus.FAILED else "pending"
    )
    response.verified_findings = verified
    response.unverified_findings = unverified
    response.artifact_paths = [item.file_path for item in task.artifacts]
    status_value = task.status.value if isinstance(task.status, TaskStatus) else str(task.status)
    response.execution_summary = (
        f"{len(successful)} source(s), {verified} verified finding(s), "
        f"{unverified} unverified finding(s); task status: {status_value}."
    )
    return response


@router.post("", response_model=TaskDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_task_endpoint(data: TaskCreate, session: AsyncSession = Depends(get_db)) -> TaskDetailResponse:
    task = await create_task(session, data, get_settings().effective_planner_provider)
    return _detail(task)


@router.get("", response_model=list[TaskResponse])
async def list_tasks_endpoint(session: AsyncSession = Depends(get_db)) -> list[TaskResponse]:
    return [TaskResponse.model_validate(task) for task in await list_tasks(session)]


@router.get("/{task_id}", response_model=TaskDetailResponse)
async def get_task_endpoint(task_id: str, session: AsyncSession = Depends(get_db)) -> TaskDetailResponse:
    task = await get_task(session, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return _detail(task)


@router.post("/{task_id}/execute", response_model=TaskDetailResponse)
async def execute_task_endpoint(task_id: str, request: ExecutionRequest, session: AsyncSession = Depends(get_db)) -> TaskDetailResponse:
    task = await execute_task(session, task_id, get_settings(), request.approved)
    task = await get_task(session, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return _detail(task)


@router.post("/{task_id}/pause", response_model=TaskResponse)
async def pause_task_endpoint(task_id: str, session: AsyncSession = Depends(get_db)) -> TaskResponse:
    task = await get_task(session, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    task.status = TaskStatus.PAUSED
    task.events.append(TaskEvent(event_type="execution.paused", message="Execution paused by user."))
    await session.commit()
    return TaskResponse.model_validate(task)


@router.post("/{task_id}/resume", response_model=TaskDetailResponse)
async def resume_task_endpoint(task_id: str, request: ExecutionRequest, session: AsyncSession = Depends(get_db)) -> TaskDetailResponse:
    task = await execute_task(session, task_id, get_settings(), request.approved)
    task = await get_task(session, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskDetailResponse.model_validate(task)


@router.post("/{task_id}/cancel", response_model=TaskResponse)
async def cancel_task_endpoint(task_id: str, session: AsyncSession = Depends(get_db)) -> TaskResponse:
    task = await get_task(session, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    task.status = TaskStatus.CANCELLED
    task.events.append(TaskEvent(event_type="execution.cancelled", message="Execution cancelled by user."))
    await session.commit()
    return TaskResponse.model_validate(task)


@router.get("/{task_id}/artifacts/{artifact_id}")
async def download_artifact(task_id: str, artifact_id: int, session: AsyncSession = Depends(get_db)) -> FileResponse:
    task = await get_task(session, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    artifact = next((item for item in task.artifacts if item.id == artifact_id), None)
    if artifact is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    from pathlib import Path
    path = Path(artifact.file_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Artifact file is unavailable")
    return FileResponse(path, media_type=artifact.content_type, filename=artifact.filename)


@router.get("/{task_id}/events")
async def task_events(task_id: str, after: int = 0, session: AsyncSession = Depends(get_db)) -> list[dict]:
    task = await get_task(session, task_id)
    if task is None:
        raise HTTPException(404, "Task not found")
    return [
        {
            "id": event.id,
            "task_id": task_id,
            "event_type": event.event_type,
            "message": event.message,
            "timestamp": event.timestamp,
        }
        for event in task.events
        if event.id > after
    ]
