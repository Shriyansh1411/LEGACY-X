from pydantic import BaseModel, Field


class ExplainResult(BaseModel):
    project_id: str
    summary: str = Field(default="")
    root_cause: str = Field(default="")
    suggested_fix: str = Field(default="")

    def api_payload(self) -> dict:
        return {
            "project_id": self.project_id,
            "summary": self.summary,
            "root_cause": self.root_cause,
            "suggested_fix": self.suggested_fix,
            "stage": "explain",
        }
