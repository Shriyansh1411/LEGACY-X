from __future__ import annotations
import os


# Priority order for legacy languages to support. Start with COBOL as first-class.
SUPPORTED_LEGACY_LANGUAGES = ["cobol", "pl1", "fortran", "pascal"]

# Verification tolerances: used by the Verify stage to determine acceptable differences.
# - value_tolerance: numeric absolute tolerance
# - allow_ordering_flexibility: whether lists/outputs may reorder
# - ignore_whitespace: whether whitespace-only differences are ignored
VERIFICATION_TOLERANCES = {
    "value_tolerance": 1e-6,
    "allow_ordering_flexibility": True,
    "ignore_whitespace": True,
}

# RAG / embeddings storage config. Use the local pgvector Postgres instance from docker-compose.
PGVECTOR = {
    "enabled": True,
    "database_url": os.environ.get(
        "DATABASE_URL", "postgresql+psycopg://legacyx:legacyx@db:5432/legacyx"
    ),
    "table_name": "embeddings",
}

# Embedding model config used by embeddings service when generating vectors
EMBEDDING_MODEL = os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
