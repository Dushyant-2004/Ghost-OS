from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


def _async_url(url: str) -> str:
    return url.replace("sqlite:///", "sqlite+aiosqlite:///")


engine = create_async_engine(_async_url(get_settings().database_url), future=True)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session


async def init_db() -> None:
    from app.models import artifact, task  # noqa: F401
    from app.models import plan  # noqa: F401
    from app.models import browser, vision, research, approval, memory  # noqa: F401

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        if connection.dialect.name == "sqlite":
            columns = await connection.execute(text("PRAGMA table_info(research_records)"))
            names = {row[1] for row in columns}
            if "collected_links" not in names:
                await connection.execute(
                    text("ALTER TABLE research_records ADD COLUMN collected_links JSON DEFAULT '[]'")
                )
