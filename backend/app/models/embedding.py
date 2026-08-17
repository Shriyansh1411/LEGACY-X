from sqlalchemy import Column, Integer, String, JSON, Text
from app.db.database import Base
from pgvector.sqlalchemy import Vector


class Embedding(Base):
    __tablename__ = "embeddings"

    id = Column(String, primary_key=True, index=True)
    project_id = Column(String, index=True)
    content = Column(Text)
    # store metadata in a `meta` column to avoid reserved-name conflicts.
    meta = Column(JSON)
    # Default dimension: 1536 (adjust if using a different embedding model)
    vector = Column(Vector(1536))
