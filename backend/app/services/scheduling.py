from calendar import monthrange
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.phase4 import Schedule


def next_run(recurrence: str, now: datetime) -> datetime | None:
    if recurrence == "once":
        return now
    if recurrence == "daily":
        return now + timedelta(days=1)
    if recurrence == "weekly":
        return now + timedelta(weeks=1)
    if recurrence == "monthly":
        month = now.month + 1
        year = now.year + (month - 1) // 12
        month = (month - 1) % 12 + 1
        return now.replace(year=year, month=month, day=min(now.day, monthrange(year, month)[1]))
    raise ValueError("Unsupported recurrence. Use once, daily, weekly, or monthly.")


def normalize_run_at(value: datetime, timezone: str) -> datetime:
    try:
        zone = ZoneInfo(timezone)
    except Exception as error:
        raise ValueError(f"Unknown timezone: {timezone}") from error
    aware = value.replace(tzinfo=zone) if value.tzinfo is None else value
    return aware.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)


async def claim_due_schedules(session: AsyncSession, now: datetime) -> list[Schedule]:
    schedules = (await session.execute(
        select(Schedule).where(
            Schedule.status == "active",
            Schedule.next_run_at.is_not(None),
            Schedule.next_run_at <= now,
        )
    )).scalars().all()
    for schedule in schedules:
        schedule.last_run_at = now
        if schedule.recurrence == "once":
            schedule.status = "completed"
            schedule.next_run_at = None
        else:
            schedule.next_run_at = next_run(schedule.recurrence, now)
    await session.flush()
    return list(schedules)
