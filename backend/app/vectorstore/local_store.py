from __future__ import annotations
from typing import List, Dict, Any
import threading
import numpy as np
import os
import json

# Simple in-memory (with optional on-disk persistence) vector store for dev fallback
class LocalVectorStore:
    def __init__(self, persist_path: str | None = None):
        self.lock = threading.Lock()
        self.vectors: Dict[str, Dict[str, Any]] = {}
        self.persist_path = persist_path
        if persist_path and os.path.exists(persist_path):
            try:
                with open(persist_path, "r", encoding="utf-8") as fh:
                    self.vectors = json.load(fh)
            except Exception:
                self.vectors = {}

    def _persist(self):
        if not self.persist_path:
            return
        try:
            with open(self.persist_path, "w", encoding="utf-8") as fh:
                json.dump(self.vectors, fh)
        except Exception:
            pass

    def upsert(self, id: str, project_id: str, content: str, metadata: dict, vector: List[float]):
        with self.lock:
            self.vectors[id] = {"project_id": project_id, "content": content, "metadata": metadata, "vector": vector}
            self._persist()

    def search(self, query_vector: List[float], top_k: int = 10) -> List[Dict[str, Any]]:
        with self.lock:
            if not self.vectors:
                return []
            q = np.array(query_vector, dtype=float)
            items = []
            for k, v in self.vectors.items():
                vec = np.array(v["vector"], dtype=float)
                # use cosine similarity
                denom = (np.linalg.norm(q) * np.linalg.norm(vec))
                score = float(np.dot(q, vec) / denom) if denom > 0 else 0.0
                items.append((k, v, score))
            items.sort(key=lambda x: x[2], reverse=True)
            results = []
            for k, v, score in items[:top_k]:
                results.append({"id": k, "project_id": v["project_id"], "content": v["content"], "metadata": v["metadata"], "score": score})
            return results
