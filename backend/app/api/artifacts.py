from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.database.session import get_db
from app.models.artifact import Artifact

router = APIRouter(prefix="/api/artifacts", tags=["artifacts"])
MAX_PREVIEW_BYTES = 2_000_000
ALLOWED_PREVIEW = {".md", ".txt", ".json", ".py", ".js", ".ts", ".tsx", ".html", ".css", ".csv"}


def _workspace() -> Path:
    return Path(get_settings().ghostos_workspace).resolve()


def _safe_path(artifact: Artifact) -> Path:
    path = Path(artifact.file_path).resolve()
    workspace = _workspace()
    if workspace not in path.parents or path.is_symlink():
        raise HTTPException(403, "Artifact is outside the approved workspace")
    if path.name.lower() in {".env", ".env.local"} or path.name.startswith(".env."):
        raise HTTPException(403, "Sensitive files are not accessible")
    return path


def _metadata(artifact: Artifact, path: Path) -> dict:
    return {
        "id": artifact.id,
        "task_id": artifact.task_id,
        "filename": artifact.filename,
        "file_path": str(path.relative_to(_workspace())),
        "content_type": artifact.content_type,
        "size_bytes": path.stat().st_size if path.is_file() else 0,
        "created_at": artifact.created_at,
    }


@router.get("")
async def list_artifacts(session: AsyncSession = Depends(get_db)) -> list[dict]:
    result = await session.execute(select(Artifact).order_by(Artifact.created_at.desc()))
    items = []
    for artifact in result.scalars():
        try:
            path = _safe_path(artifact)
        except HTTPException:
            continue
        if path.is_file():
            items.append(_metadata(artifact, path))
    return items


@router.get("/{artifact_id}")
async def artifact_metadata(artifact_id: int, session: AsyncSession = Depends(get_db)) -> dict:
    artifact = await session.get(Artifact, artifact_id)
    if artifact is None:
        raise HTTPException(404, "Artifact not found")
    path = _safe_path(artifact)
    if not path.is_file():
        raise HTTPException(404, "Artifact file is unavailable")
    return _metadata(artifact, path)


@router.get("/{artifact_id}/preview")
async def preview_artifact(artifact_id: int, session: AsyncSession = Depends(get_db)) -> dict:
    artifact = await session.get(Artifact, artifact_id)
    if artifact is None:
        raise HTTPException(404, "Artifact not found")
    path = _safe_path(artifact)
    if path.suffix.lower() not in ALLOWED_PREVIEW:
        raise HTTPException(415, "Preview is not supported for this file type")
    if path.stat().st_size > MAX_PREVIEW_BYTES:
        raise HTTPException(413, "Artifact is too large to preview")
    return {"artifact": _metadata(artifact, path), "content": path.read_text(encoding="utf-8")}


@router.get("/{artifact_id}/download")
async def download_artifact(artifact_id: int, session: AsyncSession = Depends(get_db)) -> FileResponse:
    artifact = await session.get(Artifact, artifact_id)
    if artifact is None:
        raise HTTPException(404, "Artifact not found")
    path = _safe_path(artifact)
    if not path.is_file():
        raise HTTPException(404, "Artifact file is unavailable")
    return FileResponse(path, media_type=artifact.content_type, filename=artifact.filename)
