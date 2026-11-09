from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.coding.workspace import CodingWorkspace, WorkspaceViolation
from app.core.config import get_settings

router = APIRouter(prefix="/api/coding", tags=["coding"])
workspace = CodingWorkspace(get_settings())


class GenerateProjectRequest(BaseModel):
    project_name: str = Field(min_length=1, max_length=64)
    files: dict[str, str] = Field(min_length=1, max_length=100)


@router.post("/projects")
async def generate_project(request: GenerateProjectRequest) -> dict:
    try:
        return workspace.create_project(request.project_name, request.files)
    except WorkspaceViolation as error:
        raise HTTPException(400, str(error)) from error
