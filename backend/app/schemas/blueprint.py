from pydantic import BaseModel, Field


class BehavioralBlueprint(BaseModel):
    rules: list[str] = Field(default_factory=list)
    edge_cases: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)


class ProjectBlueprintResponse(BaseModel):
    project_id: str
    blueprint: BehavioralBlueprint

    def api_payload(self) -> dict:
        return {
            "project_id": self.project_id,
            "blueprint": self.blueprint.model_dump(),
            "stage": "understand",
        }
