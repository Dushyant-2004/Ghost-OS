from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.browser.manager import BrowserManager, BrowserUnavailable
from app.core.config import get_settings
from app.database.session import get_db
from app.models.browser import BrowserSession

router = APIRouter(prefix="/api/browser", tags=["browser"])
manager = BrowserManager(get_settings())


class OpenUrlRequest(BaseModel):
    url: str = Field(min_length=8, max_length=2_000)


@router.post("/sessions")
async def create_browser_session(session: AsyncSession = Depends(get_db)) -> dict:
    item = await manager.create_session(session)
    return {"id": item.id, "status": item.status}


@router.post("/sessions/{session_id}/open")
async def open_browser_url(session_id: str, request: OpenUrlRequest, session: AsyncSession = Depends(get_db)) -> dict:
    item = await session.get(BrowserSession, session_id)
    if item is None:
        raise HTTPException(404, "Browser session not found")
    try:
        return await manager.open_url(session, item, request.url)
    except (ValueError, BrowserUnavailable) as error:
        item.status = "error"
        item.last_error = str(error)
        await session.commit()
        raise HTTPException(503, str(error)) from error


@router.get("/sessions/{session_id}/content")
async def get_browser_content(session_id: str, session: AsyncSession = Depends(get_db)) -> dict:
    item = await session.get(BrowserSession, session_id)
    if item is None:
        raise HTTPException(404, "Browser session not found")
    try:
        return await manager.content(item)
    except BrowserUnavailable as error:
        raise HTTPException(503, str(error)) from error


@router.get("/sessions/{session_id}")
async def get_browser_session(session_id: str, session: AsyncSession = Depends(get_db)) -> dict:
    item = await session.get(BrowserSession, session_id)
    if item is None:
        raise HTTPException(404, "Browser session not found")
    return {
        "id": item.id,
        "status": item.status,
        "current_url": item.current_url,
        "page_title": item.page_title,
        "last_error": item.last_error,
    }


@router.post("/sessions/{session_id}/screenshot")
async def capture_browser_screenshot(session_id: str, session: AsyncSession = Depends(get_db)) -> dict:
    item = await session.get(BrowserSession, session_id)
    if item is None:
        raise HTTPException(404, "Browser session not found")
    try:
        path = await manager.screenshot(item, Path(get_settings().ghostos_workspace))
        return {"session_id": session_id, "screenshot_path": str(path)}
    except BrowserUnavailable as error:
        raise HTTPException(503, str(error)) from error
