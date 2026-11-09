from typing import TypedDict

from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field


class PlanStepModel(BaseModel):
    step_id: str
    title: str
    description: str
    tool_name: str
    status: str = "pending"
    dependencies: list[str] = Field(default_factory=list)
    expected_result: str


class GeneratedPlan(BaseModel):
    objective: str
    steps: list[PlanStepModel]
    required_tools: list[str]
    dependencies: list[str]
    expected_outcome: str
    verification_criteria: list[str]
    requires_approval: bool


class PlannerState(TypedDict):
    instruction: str
    memory_context: list[str]
    plan: GeneratedPlan | None


def _demo_plan(state: PlannerState) -> PlannerState:
    instruction = state["instruction"].strip()
    memory_note = (
        " Relevant remembered context (use only as a hint and prefer the current instruction): "
        + " | ".join(state.get("memory_context", []))
        if state.get("memory_context") else ""
    )
    plan = GeneratedPlan(
        objective=instruction,
        steps=[
            PlanStepModel(
                step_id="step-1",
                title="Clarify objective",
                description=f"Parse the requested outcome and identify constraints for: {instruction}.{memory_note}",
                tool_name="planner",
                expected_result="A bounded objective and constraints.",
            ),
            PlanStepModel(
                step_id="step-2",
                title="Gather required information",
                description="Collect the information needed to satisfy the objective using approved sources.",
                tool_name="research",
                dependencies=["step-1"],
                expected_result="Relevant source information is organized.",
            ),
            PlanStepModel(
                step_id="step-3",
                title="Analyze collected evidence",
                description="Use the structured research results and source evidence to prepare the requested outcome.",
                tool_name="analysis",
                dependencies=["step-2"],
                expected_result="An evidence-backed draft deliverable.",
            ),
            PlanStepModel(
                step_id="step-4",
                title="Verify result",
                description="Check the deliverable against the objective and verification criteria.",
                tool_name="verification",
                dependencies=["step-3"],
                expected_result="A verified plan ready for human review.",
            ),
        ],
        required_tools=["planner", "research", "verification"],
        dependencies=["step-1 before step-2", "step-2 before step-3", "step-3 before step-4"],
        expected_outcome="A reviewable deliverable aligned with the user's instruction.",
        verification_criteria=["All requested objectives are addressed.", "Sources and assumptions are explicit."],
        requires_approval=True,
    )
    return {"instruction": instruction, "plan": plan}


def build_planner_graph() -> StateGraph:
    graph = StateGraph(PlannerState)
    graph.add_node("generate", _demo_plan)
    graph.set_entry_point("generate")
    graph.add_edge("generate", END)
    return graph


async def generate_plan(
    instruction: str, provider: str = "demo", memory_context: list[str] | None = None
) -> GeneratedPlan:
    # The graph boundary makes provider replacement explicit without claiming demo output is model output.
    result = await build_planner_graph().compile().ainvoke({
        "instruction": instruction,
        "memory_context": memory_context or [],
        "plan": None,
    })
    plan = result["plan"]
    if plan is None:
        raise RuntimeError("Planner returned no plan")
    return plan
