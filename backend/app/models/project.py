from sqlalchemy import JSON, Column, Integer, String

from app.db.database import Base


class ProjectRecord(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(String, unique=True, index=True, nullable=False)
    file_count = Column(Integer, nullable=False, default=0)
    source_files = Column(JSON, default=list)
    docs = Column(JSON, default=list)
    logs = Column(JSON, default=list)
    language_hint = Column(String, default="unknown")
    file_contents = Column(JSON, default=dict)
    generated_code = Column(String, default="")
    generated_tests = Column(String, default="")
    pipeline_state = Column(JSON, default=dict)
    behavior_graph = Column(JSON, default=dict)
