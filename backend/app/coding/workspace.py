import re
from pathlib import Path

from app.core.config import Settings


class WorkspaceViolation(ValueError):
    pass


class CodingWorkspace:
    def __init__(self, settings: Settings) -> None:
        self.root = Path(settings.ghostos_workspace).resolve()
        self.projects = (self.root / "generated-projects").resolve()
        self.artifacts = (self.root / "artifacts").resolve()
        self.reports = (self.root / "reports").resolve()
        for directory in (self.projects, self.artifacts, self.reports):
            directory.mkdir(parents=True, exist_ok=True)

    def project_path(self, project_name: str) -> Path:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", project_name):
            raise WorkspaceViolation("Project name contains unsupported characters")
        path = (self.projects / project_name).resolve()
        if path.parent != self.projects:
            raise WorkspaceViolation("Project path escapes the approved workspace")
        return path

    def create_project(self, project_name: str, files: dict[str, str]) -> dict:
        project = self.project_path(project_name)
        project.mkdir(exist_ok=True)
        written: list[str] = []
        for relative, content in files.items():
            path = (project / relative).resolve()
            if project not in path.parents or path.is_symlink():
                raise WorkspaceViolation("File path escapes the approved project workspace")
            if len(content.encode("utf-8")) > 1_000_000:
                raise WorkspaceViolation("File exceeds the 1 MB safety limit")
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                raise WorkspaceViolation(f"Refusing to overwrite existing file: {relative}")
            path.write_text(content, encoding="utf-8")
            written.append(str(path.relative_to(project)))
        return {"project": project_name, "path": str(project), "files": written, "execution": "disabled_without_isolation"}
