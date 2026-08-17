from fastapi import APIRouter, HTTPException

from app.services.explain_service import explain_project

router = APIRouter(prefix="/api", tags=["explain"])


@router.get("/projects/{project_id}/explain")
async def explain_legacy_project(project_id: str):
    try:
        result = explain_project(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return result.api_payload()
