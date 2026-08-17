from fastapi import APIRouter, File, HTTPException, UploadFile

from app.services.ingest_service import ingest_project

router = APIRouter(prefix="/api", tags=["projects"])


@router.post("/projects/ingest")
async def ingest_legacy_project(files: list[UploadFile] = File(default_factory=list)):
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    try:
        result = ingest_project(files)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return result.api_payload()
