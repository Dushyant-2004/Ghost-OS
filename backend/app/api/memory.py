from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.models.memory import Memory
from app.services.memory import MEMORY_CATEGORIES, create_memory, delete_memory, search_memories

router = APIRouter(prefix="/api/memories", tags=["memory"])


class MemoryCreateRequest(BaseModel):
    category: str
    content: str = Field(min_length=1, max_length=10_000)
    source_task_id: str | None = None
    importance: int = Field(default=5, ge=1, le=10)
    confidence: int = Field(default=5, ge=1, le=10)
    expiration_at: datetime | None = None


class MemoryUpdateRequest(BaseModel):
    content: str | None = Field(default=None, min_length=1, max_length=10_000)
    importance: int | None = Field(default=None, ge=1, le=10)
    confidence: int | None = Field(default=None, ge=1, le=10)
    expiration_at: datetime | None = None


def _serialize(memory: Memory) -> dict:
    return {
        "memory_id": memory.memory_id,
        "category": memory.category,
        "content": memory.content,
        "source_task_id": memory.source_task_id,
        "importance": memory.importance,
        "confidence": memory.confidence,
        "created_at": memory.created_at,
        "updated_at": memory.updated_at,
        "last_accessed_at": memory.last_accessed_at,
        "expiration_at": memory.expiration_at,
        "access_count": memory.access_count,
    }


@router.get("")
async def list_memories(
    query: str | None = Query(default=None, max_length=500),
    category: str | None = None,
    session: AsyncSession = Depends(get_db),
) -> list[dict]:
    if query:
        memories = await search_memories(session, query)
    else:
        statement = select(Memory).where(
            (Memory.expiration_at.is_(None)) | (Memory.expiration_at > datetime.utcnow())
        ).order_by(Memory.updated_at.desc())
        if category:
            statement = statement.where(Memory.category == category)
        memories = list((await session.execute(statement)).scalars())
    await session.commit()
    return [_serialize(memory) for memory in memories]


@router.post("", status_code=201)
async def add_memory(request: MemoryCreateRequest, session: AsyncSession = Depends(get_db)) -> dict:
    try:
        memory = await create_memory(session, **request.model_dump())
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
    await session.commit()
    return _serialize(memory)


@router.get("/stats")
async def memory_stats(session: AsyncSession = Depends(get_db)) -> dict:
    total = await session.scalar(select(func.count()).select_from(Memory))
    by_category = dict((await session.execute(
        select(Memory.category, func.count()).group_by(Memory.category)
    )).all())
    return {"total": total or 0, "by_category": by_category}


@router.get("/categories")
async def memory_categories() -> dict:
    return {"categories": sorted(MEMORY_CATEGORIES)}


@router.get("/{memory_id}")
async def get_memory(memory_id: str, session: AsyncSession = Depends(get_db)) -> dict:
    memory = await session.get(Memory, memory_id)
    if memory is None:
        raise HTTPException(404, "Memory not found")
    return _serialize(memory)


@router.patch("/{memory_id}")
async def update_memory(
    memory_id: str, request: MemoryUpdateRequest, session: AsyncSession = Depends(get_db)
) -> dict:
    memory = await session.get(Memory, memory_id)
    if memory is None:
        raise HTTPException(404, "Memory not found")
    values = request.model_dump(exclude_unset=True)
    if "content" in values:
        from app.services.memory import sanitize_content
        try:
            values["content"] = sanitize_content(values["content"])
        except ValueError as error:
            raise HTTPException(400, str(error)) from error
    for key, value in values.items():
        setattr(memory, key, value)
    memory.updated_at = datetime.utcnow()
    await session.commit()
    return _serialize(memory)


@router.delete("/{memory_id}", status_code=204)
async def remove_memory(memory_id: str, session: AsyncSession = Depends(get_db)) -> None:
    if not await delete_memory(session, memory_id):
        raise HTTPException(404, "Memory not found")
    await session.commit()
