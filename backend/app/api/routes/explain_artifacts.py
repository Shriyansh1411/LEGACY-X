from fastapi import APIRouter, HTTPException
import os
import json
from fastapi.responses import JSONResponse, PlainTextResponse

router = APIRouter(prefix="/api/explain", tags=["explain"])

ARTIFACTS_DIR = os.path.join(os.getcwd(), "backend", "tmp_artifacts")


@router.get("/artifacts")
def list_explain_artifacts():
    if not os.path.exists(ARTIFACTS_DIR):
        return {"artifacts": []}
    files = [f for f in os.listdir(ARTIFACTS_DIR) if f.startswith("explain_")]
    return {"artifacts": sorted(files)}


@router.get("/artifacts/{name}")
def get_explain_artifact(name: str):
    path = os.path.join(ARTIFACTS_DIR, name)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Artifact not found")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = fh.read()
        try:
            return JSONResponse(status_code=200, content=json.loads(data))
        except Exception:
            return PlainTextResponse(status_code=200, content=data)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
