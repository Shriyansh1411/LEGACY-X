from __future__ import annotations
from typing import List, Dict, Any, Optional
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from app.db.database import SessionLocal, engine
from app.models.embedding import Embedding
import logging
from app.vectorstore.local_store import LocalVectorStore

logger = logging.getLogger(__name__)


class PgVectorStore:
    def __init__(self):
        # create table if not exists via SQLAlchemy metadata
        try:
            Embedding.__table__.create(bind=engine, checkfirst=True)
        except Exception as exc:
            logger.warning("Could not create embeddings table: %s", exc)
            # Fallback to local in-memory store for development environments
            self._local = LocalVectorStore(persist_path="backend/tmp_artifacts/local_vectors.json")
            self._use_local = True
            return
        self._use_local = False
        self._local = None

    def upsert(self, id: str, project_id: str, content: str, metadata: dict, vector: List[float]) -> None:
        if getattr(self, "_use_local", False) and self._local is not None:
            self._local.upsert(id, project_id, content, metadata, vector)
            return

        with SessionLocal() as session:
            try:
                # delete if exists
                session.execute(text("DELETE FROM embeddings WHERE id = :id"), {"id": id})
                # insert
                # Map `metadata` argument into the model's `meta` attribute to avoid
                # reserved-name conflicts with SQLAlchemy.
                session.add(
                    Embedding(id=id, project_id=project_id, content=content, meta=metadata, vector=vector)
                )
                session.commit()
            except SQLAlchemyError as exc:
                session.rollback()
                logger.error("Failed to upsert embedding: %s", exc)

    def search(self, query_vector: List[float], top_k: int = 10) -> List[Dict[str, Any]]:
        if getattr(self, "_use_local", False) and self._local is not None:
            return self._local.search(query_vector, top_k=top_k)

        with SessionLocal() as session:
            try:
                # Use pgvector distance operator <-> for nearest neighbors
                sql = text(
                    "SELECT id, project_id, content, meta, vector <-> :q as distance FROM embeddings ORDER BY distance LIMIT :k"
                )
                res = session.execute(sql, {"q": query_vector, "k": top_k})
                results = []
                for row in res:
                    results.append({
                        "id": row[0],
                        "project_id": row[1],
                        "content": row[2],
                        "metadata": row[3],
                        "distance": float(row[4]),
                    })
                return results
            except SQLAlchemyError as exc:
                logger.error("Search failed: %s", exc)
                return []
