from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.config import get_settings
from app.database.session import SessionLocal
from app.models.task import Task, TaskEvent
from app.schemas.task import TaskCreate
from app.services.scheduling import claim_due_schedules
from app.services.task_service import create_task


class GhostScheduler:
    def __init__(self) -> None:
        self.scheduler = AsyncIOScheduler(timezone="UTC")

    async def tick(self) -> None:
        async with SessionLocal() as session:
            schedules = await claim_due_schedules(session, datetime.utcnow())
            for schedule in schedules:
                task = await create_task(
                    session,
                    TaskCreate(instruction=schedule.instruction),
                    get_settings().effective_planner_provider,
                )
                task.events.append(TaskEvent(
                    event_type="schedule.triggered",
                    message=f"Created from schedule {schedule.id}; approval remains required.",
                ))
            await session.commit()

    def start(self) -> None:
        self.scheduler.add_job(self.tick, "interval", seconds=30, id="schedule-poll", replace_existing=True)
        self.scheduler.start()

    async def shutdown(self) -> None:
        self.scheduler.shutdown(wait=False)
