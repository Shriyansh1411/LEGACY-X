from pydantic import BaseModel, Field


class ProjectManifest(BaseModel):
    file_count: int = Field(..., ge=0)
    source_files: list[str] = Field(default_factory=list)
    docs: list[str] = Field(default_factory=list)
    logs: list[str] = Field(default_factory=list)
    language_hint: str = "unknown"


class ProjectIngestResponse(BaseModel):
    project_id: str
    manifest: ProjectManifest
