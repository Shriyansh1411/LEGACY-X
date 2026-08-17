from pydantic import BaseModel, Field


class VerificationResult(BaseModel):
    project_id: str
    match: bool = Field(default=False)
    legacy_outputs: list[str] = Field(default_factory=list)
    modern_outputs: list[str] = Field(default_factory=list)
    mismatches: list[str] = Field(default_factory=list)
    explain: dict | None = None

    def api_payload(self) -> dict:
        return {
            "project_id": self.project_id,
            "match": self.match,
            "legacy_outputs": self.legacy_outputs,
            "modern_outputs": self.modern_outputs,
            "mismatches": self.mismatches,
            "explain": self.explain,
            "stage": "verify",
        }
