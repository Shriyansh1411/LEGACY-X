from fastapi import APIRouter, HTTPException

from app.schemas.agent import PipelineState
from app.services.generate_agent import GenerateAgent

router = APIRouter(prefix="/api", tags=["generation"])


@router.post("/projects/{project_id}/generate")
async def generate_project(project_id: str):
    """Generate modernized code using agentic GenerateAgent with reasoning and tool calls."""
    try:
        state = PipelineState(project_id=project_id)
        agent = GenerateAgent()
        result = agent.execute(project_id, state)
        return result.api_payload()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(exc)}") from exc
