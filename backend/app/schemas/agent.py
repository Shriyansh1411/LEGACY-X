from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AgentResult(BaseModel):
    project_id: str | None = None
    stage: str
    output: dict[str, Any] = Field(default_factory=dict)
    reasoning_trace: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    needs_human_review: bool = False
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)

    def api_payload(self) -> dict[str, Any]:
        payload = dict(self.output)
        payload.setdefault("project_id", self.project_id)
        payload.setdefault("stage", self.stage)
        payload.setdefault("reasoning_trace", self.reasoning_trace)
        payload.setdefault("confidence", self.confidence)
        payload.setdefault("needs_human_review", self.needs_human_review)
        payload.setdefault("tool_calls", self.tool_calls)
        return payload


class PipelineState(BaseModel):
    project_id: str
    stages: dict[str, AgentResult] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def set_stage(self, result: AgentResult) -> None:
        self.stages[result.stage] = result

    def get_stage(self, stage: str) -> AgentResult | None:
        return self.stages.get(stage)
