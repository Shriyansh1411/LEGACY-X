from fastapi import APIRouter, HTTPException

from app.schemas.agent import PipelineState
from app.services.execute_agent import ExecuteAgent
from app.db.database import SessionLocal
from app.models.project import ProjectRecord

router = APIRouter(prefix="/api", tags=["execution"])


@router.post("/projects/{project_id}/execute")
async def execute_project(project_id: str):
    """Execute generated code using agentic ExecuteAgent with monitoring and failure reasoning."""
    try:
        with SessionLocal() as session:
            project = session.query(ProjectRecord).filter_by(project_id=project_id).first()
            if project is None:
                raise ValueError(f"Project {project_id} not found")

        state = PipelineState(project_id=project_id)
        agent = ExecuteAgent()
        result = agent.execute(project_id, state)
        return result.api_payload()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Execution failed: {str(exc)}") from exc
