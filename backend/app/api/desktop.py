from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.desktop.controller import DesktopController, DesktopSafetyError

router = APIRouter(prefix="/api/desktop", tags=["desktop"])
controller = DesktopController(get_settings())


class ActionRequest(BaseModel):
    action: str = Field(min_length=1, max_length=40)
    parameters: dict = Field(default_factory=dict)


def _safe(call):
    try:
        return call()
    except DesktopSafetyError as error:
        raise HTTPException(503, str(error)) from error


@router.get("/status")
async def status() -> dict:
    return controller.status()


@router.post("/enable")
async def enable() -> dict:
    return _safe(controller.enable)


@router.post("/stop")
async def stop() -> dict:
    return controller.stop()


@router.post("/screenshot")
async def screenshot() -> dict:
    try:
        return await controller.screenshot()
    except DesktopSafetyError as error:
        raise HTTPException(503, str(error)) from error


@router.post("/action")
async def action(request: ActionRequest) -> dict:
    try:
        return await controller.action(request.action, **request.parameters)
    except DesktopSafetyError as error:
        raise HTTPException(503, str(error)) from error
