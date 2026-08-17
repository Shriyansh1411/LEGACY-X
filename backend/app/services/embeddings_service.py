from __future__ import annotations
from typing import List, Dict, Any, Optional
import httpx
import logging

from app.vectorstore.pgvector_store import PgVectorStore
from app.core.config import get_settings, reset_settings_cache

logger = logging.getLogger(__name__)


class EmbeddingsService:
    def __init__(self):
        self.store = PgVectorStore()

    def create_embedding(self, text: str, model: Optional[str] = None) -> List[float]:
        # Use OpenAI embeddings if configured, fallback is unsupported here
        reset_settings_cache()
        settings = get_settings()
        prov = (settings.llm_provider or "").upper()
        model = model or getattr(settings, "embedding_model", "text-embedding-3-small")
        if prov == "GEMINI":
            api_key = settings.gemini_api_key
            base = settings.gemini_base_url.rstrip("/")
            if not api_key:
                raise RuntimeError("Gemini API key not configured for embedding generation")
            try:
                resp = httpx.post(
                    f"{base}/v1/models/{settings.gemini_model}:embed",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={"input": text, "model": model},
                    timeout=30,
                )
                resp.raise_for_status()
                data = resp.json()
                # try common keys
                if data.get("data"):
                    return data["data"][0]["embedding"]
                if data.get("embeddings"):
                    return data.get("embeddings")[0]
                raise RuntimeError("Unexpected Gemini embedding response")
            except Exception as exc:
                logger.error("Embedding generation (Gemini) failed: %s", exc)
                raise
        else:
            api_key = settings.openai_api_key
            base = settings.openai_base_url.rstrip("/")
            model = model or "text-embedding-3-small"
            if not api_key:
                raise RuntimeError("OpenAI API key not configured for embedding generation")

            try:
                resp = httpx.post(
                    f"{base}/embeddings",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={"input": text, "model": model},
                    timeout=30,
                )
                resp.raise_for_status()
                data = resp.json()
                emb = data["data"][0]["embedding"]
                return emb
            except Exception as exc:
                logger.error("Embedding generation failed: %s", exc)
                raise

    def upsert(self, id: str, project_id: str, text: str, metadata: dict, vector: Optional[List[float]] = None) -> None:
        if vector is None:
            vector = self.create_embedding(text)
        self.store.upsert(id=id, project_id=project_id, content=text, metadata=metadata, vector=vector)

    def search(self, query: str, top_k: int = 10, model: Optional[str] = None) -> List[Dict[str, Any]]:
        vec = self.create_embedding(query, model=model)
        return self.store.search(vec, top_k=top_k)
