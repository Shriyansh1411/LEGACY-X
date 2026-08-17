from fastapi import APIRouter, HTTPException

from app.services.understand_service import understand_project

router = APIRouter(prefix="/api", tags=["understand"])


@router.get("/projects/{project_id}/understand")
async def understand_legacy_project(project_id: str):
    try:
        result = understand_project(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return result.api_payload()
