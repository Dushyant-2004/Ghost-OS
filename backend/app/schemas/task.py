from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.task import StepStatus, TaskStatus


class TaskCreate(BaseModel):
    instruction: str = Field(min_length=3, max_length=10_000)


class ExecutionRequest(BaseModel):
    approved: bool = False


class TaskStepResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    step_name: str
    description: str
    status: StepStatus
    order_index: int
    started_at: datetime | None
    completed_at: datetime | None


class TaskEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_type: str
    message: str
    timestamp: datetime


class PlanStep(BaseModel):
    step_id: str
    title: str
    description: str
    tool_name: str
    status: str = "pending"
    dependencies: list[str] = Field(default_factory=list)
    expected_result: str


class TaskPlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    objective: str
    steps: list[PlanStep]
    required_tools: list[str]
    dependencies: list[str]
    expected_outcome: str
    verification_criteria: list[str]
    requires_approval: bool
    provider: str


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    original_instruction: str
    status: TaskStatus
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None


class TaskDetailResponse(TaskResponse):
    steps: list[TaskStepResponse] = Field(default_factory=list)
    events: list[TaskEventResponse] = Field(default_factory=list)
    plan: TaskPlanResponse | None = None
    artifacts: list["ArtifactResponse"] = Field(default_factory=list)
    research_records: list["ResearchResponse"] = Field(default_factory=list)
    research_status: str = "not_started"
    verified_findings: int = 0
    unverified_findings: int = 0
    artifact_paths: list[str] = Field(default_factory=list)
    execution_summary: str | None = None


class ArtifactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    file_path: str
    content_type: str
    created_at: datetime


class ResearchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    query: str
    source_url: str
    source_title: str
    extracted_content: str
    key_findings: list[str]
    collected_links: list[str]
    collected_at: datetime
    status: str
    error_message: str | None
    verification_status: str


class HealthResponse(BaseModel):
    status: str
    planner_provider: str
    planner_configured: bool


class ErrorResponse(BaseModel):
    detail: str
