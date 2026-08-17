from __future__ import annotations

from app.db.database import SessionLocal
from app.models.project import ProjectRecord
from app.schemas.agent import AgentResult, PipelineState


STAGE_ORDER = [
    "ingest",
    "analyze",
    "understand",
    "generate",
    "execute",
    "verify",
    "explain",
]


def _load_pipeline_state(project_id: str) -> PipelineState:
    with SessionLocal() as session:
        project = session.query(ProjectRecord).filter_by(project_id=project_id).first()
        if project is None:
            raise ValueError("Project not found")
        payload = project.pipeline_state or {}
    return PipelineState(project_id=project_id, **payload)


def _persist_pipeline_state(project_id: str, state: PipelineState) -> None:
    with SessionLocal() as session:
        project = session.query(ProjectRecord).filter_by(project_id=project_id).first()
        if project is None:
            raise ValueError("Project not found")
        project.pipeline_state = state.model_dump(mode="json")
        session.add(project)
        session.commit()


def run_pipeline(project_id: str, *, initial_state: PipelineState | None = None) -> PipelineState:
    state = initial_state or _load_pipeline_state(project_id)

    # Stage order is deliberately explicit and lightweight.
    # Each stage may add state and short-circuit if it flags needs_human_review.
    for stage in STAGE_ORDER:
        if stage in state.stages:
            continue

        if stage == "ingest":
            from app.services.ingest_service import ingest_project
            result = ingest_project([], project_id=project_id, pipeline_state=state)
        elif stage == "analyze":
            from app.services.analysis_service import analyze_project
            result = analyze_project(project_id, pipeline_state=state)
        elif stage == "understand":
            from app.services.understand_service import understand_project
            result = understand_project(project_id, pipeline_state=state)
        elif stage == "generate":
            from app.services.generate_agent import generate_agentic
            result = generate_agentic(project_id, state)
        elif stage == "execute":
            from app.services.execute_agent import ExecuteAgent
            agent = ExecuteAgent()
            result = agent.execute(project_id, state)
        elif stage == "verify":
            from app.services.verify_agent import VerifyAgent
            agent = VerifyAgent()
            result = agent.execute(project_id, state)
        elif stage == "explain":
            from app.services.explain_service import explain_project
            result = explain_project(project_id, pipeline_state=state)
        else:
            continue

        state.set_stage(result)
        _persist_pipeline_state(project_id, state)

        if result.needs_human_review:
            break

    return state
