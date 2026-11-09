import re
from datetime import datetime

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.memory import Memory

MEMORY_CATEGORIES = {
    "user_preference",
    "project",
    "task_history",
    "successful_workflow",
    "error_recovery",
    "technical_context",
}
SENSITIVE_PATTERNS = (
    re.compile(r"(?i)(api[_ -]?key|password|secret|token)\s*[:=]\s*\S+"),
    re.compile(r"(?i)\b(sk|ghp|github_pat)_[A-Za-z0-9_-]+"),
)


def sanitize_content(content: str) -> str:
    sanitized = content.strip()
    for pattern in SENSITIVE_PATTERNS:
        if pattern.search(sanitized):
            raise ValueError("Memory cannot contain credentials, secrets, or access tokens.")
    if not sanitized:
        raise ValueError("Memory content cannot be empty.")
    return sanitized


def _terms(query: str) -> set[str]:
    return {term.lower() for term in re.findall(r"[A-Za-z0-9_]+", query) if len(term) >= 3}


def relevance(memory: Memory, query: str) -> int:
    terms = _terms(query)
    content = set(_terms(memory.content))
    category = set(_terms(memory.category))
    return len(terms & content) * 10 + len(terms & category) * 5 + memory.importance + memory.confidence


async def create_memory(
    session: AsyncSession,
    *,
    category: str,
    content: str,
    source_task_id: str | None = None,
    importance: int = 5,
    confidence: int = 5,
    expiration_at: datetime | None = None,
) -> Memory:
    if category not in MEMORY_CATEGORIES:
        raise ValueError(f"Unsupported memory category: {category}")
    content = sanitize_content(content)
    duplicate = await session.scalar(
        select(Memory).where(Memory.category == category, Memory.content == content)
    )
    if duplicate is not None:
        duplicate.updated_at = datetime.utcnow()
        duplicate.importance = max(duplicate.importance, importance)
        duplicate.confidence = max(duplicate.confidence, confidence)
        return duplicate
    memory = Memory(
        category=category,
        content=content,
        source_task_id=source_task_id,
        importance=max(1, min(10, importance)),
        confidence=max(1, min(10, confidence)),
        expiration_at=expiration_at,
    )
    session.add(memory)
    await session.flush()
    return memory


async def search_memories(session: AsyncSession, query: str, limit: int = 8) -> list[Memory]:
    now = datetime.utcnow()
    terms = _terms(query)
    if not terms:
        return []
    filters = [Memory.content.ilike(f"%{term}%") for term in terms]
    result = await session.execute(
        select(Memory).where(
            or_(*filters),
            or_(Memory.expiration_at.is_(None), Memory.expiration_at > now),
        )
    )
    memories = sorted(result.scalars().all(), key=lambda item: relevance(item, query), reverse=True)[:limit]
    for memory in memories:
        memory.last_accessed_at = now
        memory.access_count += 1
    await session.flush()
    return memories


async def delete_memory(session: AsyncSession, memory_id: str) -> bool:
    result = await session.execute(delete(Memory).where(Memory.memory_id == memory_id))
    return result.rowcount > 0
