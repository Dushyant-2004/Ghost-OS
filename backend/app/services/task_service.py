from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.planner import generate_plan
from app.models.plan import TaskPlan
from app.models.task import Task, TaskEvent, TaskStep
from app.models.artifact import Artifact
from app.models.research import ResearchRecord
from app.schemas.task import TaskCreate
from app.services.memory import search_memories


def _title(instruction: str) -> str:
    cleaned = " ".join(instruction.split())
    return cleaned[:97] + "..." if len(cleaned) > 100 else cleaned


async def create_task(session: AsyncSession, data: TaskCreate, provider: str) -> Task:
    task = Task(title=_title(data.instruction), original_instruction=data.instruction.strip())
    task.events.append(TaskEvent(event_type="task.created", message="Task received and queued."))
    memories = await search_memories(session, data.instruction)
    plan = await generate_plan(data.instruction, provider, [memory.content for memory in memories])
    task.plan = TaskPlan(
        objective=plan.objective,
        steps=[step.model_dump() for step in plan.steps],
        required_tools=plan.required_tools,
        dependencies=plan.dependencies,
        expected_outcome=plan.expected_outcome,
        verification_criteria=plan.verification_criteria,
        requires_approval=plan.requires_approval,
        provider=provider,
    )
    task.steps = [
        TaskStep(
            step_name=step.title,
            description=step.description,
            order_index=index,
        )
        for index, step in enumerate(plan.steps, start=1)
    ]
    task.events.append(TaskEvent(event_type="plan.created", message=f"Plan generated in {provider} mode."))
    if memories:
        task.events.append(TaskEvent(
            event_type="memory.retrieved",
            message=f"Retrieved {len(memories)} relevant memory item(s) as non-authoritative planning context.",
        ))
    session.add(task)
    await session.commit()
    return await get_task(session, task.id)


async def list_tasks(session: AsyncSession) -> list[Task]:
    result = await session.execute(select(Task).order_by(Task.created_at.desc()))
    return list(result.scalars().all())


async def get_task(session: AsyncSession, task_id: str) -> Task | None:
    result = await session.execute(
        select(Task)
        .options(
            selectinload(Task.steps),
            selectinload(Task.events),
            selectinload(Task.plan),
            selectinload(Task.artifacts),
            selectinload(Task.research_records),
        )
        .execution_options(populate_existing=True)
        .where(Task.id == task_id)
    )
    return result.scalar_one_or_none()
