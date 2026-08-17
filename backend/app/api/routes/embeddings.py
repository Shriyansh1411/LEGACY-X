from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.embeddings_service import EmbeddingsService

router = APIRouter(prefix="/api/embeddings", tags=["embeddings"])

emb_service = EmbeddingsService()


class UpsertPayload(BaseModel):
    id: str
    project_id: str
    content: str
    metadata: dict | None = None


@router.post("/upsert")
def upsert_embedding(payload: UpsertPayload):
    try:
        emb_service.upsert(payload.id, payload.project_id, payload.content, payload.metadata or {})
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"status": "ok", "id": payload.id}


class SearchPayload(BaseModel):
    query: str
    top_k: int = 10


@router.post("/search")
def search_embeddings(payload: SearchPayload):
    try:
        results = emb_service.search(payload.query, top_k=payload.top_k)
        return {"results": results}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
