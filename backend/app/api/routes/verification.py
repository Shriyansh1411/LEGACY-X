from fastapi import APIRouter, HTTPException

from app.schemas.agent import PipelineState
from app.services.verify_agent import VerifyAgent

router = APIRouter(prefix="/api", tags=["verification"])


@router.get("/projects/{project_id}/verify")
async def verify_project(project_id: str):
    """Verify modernized code using agentic VerifyAgent with structured diff and reasoning."""
    try:
        state = PipelineState(project_id=project_id)
        agent = VerifyAgent()
        result = agent.execute(project_id, state)
        return result.api_payload()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Verification failed: {str(exc)}") from exc
