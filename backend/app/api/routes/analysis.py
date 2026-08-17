from fastapi import APIRouter, HTTPException

from app.services.analysis_service import analyze_project

router = APIRouter(prefix="/api", tags=["analysis"])


@router.get("/projects/{project_id}/analyze")
async def analyze_legacy_project(project_id: str):
    try:
        result = analyze_project(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return result.api_payload()
