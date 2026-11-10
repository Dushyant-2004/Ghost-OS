import asyncio
from collections.abc import Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.phase4 import OrchestrationLink
from app.models.task import Task, TaskStatus


async def dependency_ready(session: AsyncSession, task_id: str) -> bool:
    links = (await session.execute(
        select(OrchestrationLink).where(OrchestrationLink.task_id == task_id)
    )).scalars()
    for link in links:
        task = await session.get(Task, link.depends_on_task_id)
        if task is None or task.status != TaskStatus.COMPLETED:
            return False
    return True


async def run_parallel(
    session_factory,
    task_ids: list[str],
    execute: Callable[[AsyncSession, str], Awaitable[Task]],
    max_concurrent: int = 2,
) -> list[Task]:
    semaphore = asyncio.Semaphore(max(1, max_concurrent))

    async def worker(task_id: str) -> Task:
        async with semaphore:
            async with session_factory() as session:
                if not await dependency_ready(session, task_id):
                    raise RuntimeError(f"Task dependencies are not complete: {task_id}")
                return await execute(session, task_id)

    return await asyncio.gather(*(worker(task_id) for task_id in task_ids))
