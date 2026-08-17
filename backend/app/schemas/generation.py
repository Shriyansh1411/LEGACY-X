from pydantic import BaseModel, Field


class GeneratedProject(BaseModel):
    generated_code: str = Field(default="")
    generated_tests: str = Field(default="")


class ProjectGenerationResponse(BaseModel):
    project_id: str
    generated_code: str
    generated_tests: str

    def api_payload(self) -> dict:
        return {
            "project_id": self.project_id,
            "generated_code": self.generated_code,
            "generated_tests": self.generated_tests,
            "stage": "generate",
        }
