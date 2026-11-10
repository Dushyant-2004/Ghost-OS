from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base


class PlanRevision(Base):
    __tablename__ = "plan_revisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(Text)
    affected_step: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Schedule(Base):
    __tablename__ = "schedules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    instruction: Mapped[str] = mapped_column(Text)
    recurrence: Mapped[str] = mapped_column(String(20))
    timezone: Mapped[str] = mapped_column(String(80), default="UTC")
    run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    priority: Mapped[int] = mapped_column(Integer, default=5)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class OrchestrationLink(Base):
    __tablename__ = "orchestration_links"
    __table_args__ = (UniqueConstraint("task_id", "depends_on_task_id", name="uq_orchestration_link"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), index=True)
    depends_on_task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
