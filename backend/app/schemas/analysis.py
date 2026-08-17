from pydantic import BaseModel, Field


class LegacyAnalysis(BaseModel):
    language: str = Field(default="COBOL-like")
    source_files: list[str] = Field(default_factory=list)
    control_flow_signals: list[str] = Field(default_factory=list)
    business_rule_count: int = Field(default=0)
    dependency_graph: dict | None = Field(default=None)
    high_risk_modules: list[str] = Field(default_factory=list)


class ProjectAnalysisResponse(BaseModel):
    project_id: str
    analysis: LegacyAnalysis

    def api_payload(self) -> dict:
        return {
            "project_id": self.project_id,
            "analysis": self.analysis.model_dump(),
            "stage": "analyze",
        }
