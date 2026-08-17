"""
Base Agent class providing lifecycle, tool registry, and reasoning framework.
All stage agents should inherit from this and implement run().
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List

from app.schemas.agent import AgentResult, PipelineState

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Registry of available tools for an agent."""

    def __init__(self):
        self._tools: Dict[str, Callable] = {}

    def register(self, name: str, func: Callable, description: str = "") -> None:
        """Register a tool with the agent."""
        self._tools[name] = {"fn": func, "description": description}

    def call(self, name: str, *args: Any, **kwargs: Any) -> Any:
        """Call a registered tool by name."""
        if name not in self._tools:
            raise ValueError(f"Tool '{name}' not found in registry")
        tool_spec = self._tools[name]
        try:
            result = tool_spec["fn"](*args, **kwargs)
            return result
        except Exception as exc:
            logger.exception(f"Tool '{name}' failed: {exc}")
            raise

    def available(self) -> List[str]:
        """List all available tool names."""
        return list(self._tools.keys())


class BaseAgent(ABC):
    """
    Abstract base class for all pipeline agents.
    Provides common lifecycle, tool registry, reasoning framework.
    """

    def __init__(self, stage: str, name: str = ""):
        self.stage = stage
        self.name = name or stage.upper()
        self.tools = ToolRegistry()
        self.reasoning_trace: List[str] = []
        self.tool_calls: List[Dict[str, Any]] = []
        self.confidence: float = 0.5
        self.needs_human_review: bool = False

    def plan(self, project_id: str, state: PipelineState) -> Dict[str, Any]:
        """
        Optional planning phase. Override to customize pre-run strategy.
        Returns a plan dict that will be passed to run().
        """
        return {}

    def validate_preconditions(self, project_id: str, state: PipelineState) -> bool:
        """
        Validate that preconditions are met (e.g., previous stages completed).
        Override to add stage-specific validation.
        """
        return True

    def log_reasoning(self, message: str) -> None:
        """Add a line to the reasoning trace."""
        self.reasoning_trace.append(message)
        logger.debug(f"[{self.stage}] {message}")

    def log_tool_call(self, tool_name: str, args: Dict[str, Any], result: Any = None) -> None:
        """Record a tool call in the tool calls list."""
        self.tool_calls.append({
            "name": tool_name,
            "args": args,
            "result": result,
        })

    @abstractmethod
    def run(self, project_id: str, state: PipelineState, **kwargs: Any) -> AgentResult:
        """
        Execute the agent logic. Must return an AgentResult.
        Subclasses implement specific stage behavior here.
        """
        pass

    def execute(self, project_id: str, state: PipelineState, **kwargs: Any) -> AgentResult:
        """
        Full lifecycle: plan -> validate -> run -> finalize.
        Catches exceptions and returns a safe AgentResult.
        """
        try:
            self.log_reasoning(f"Starting {self.stage} agent execution for project {project_id}")

            # Validate preconditions
            if not self.validate_preconditions(project_id, state):
                self.needs_human_review = True
                self.confidence = 0.0
                self.log_reasoning(f"Preconditions not met for {self.stage}")
                return self._finalize(project_id, {})

            # Run planning phase
            plan = self.plan(project_id, state)
            if plan:
                self.log_reasoning(f"Execution plan: {plan}")

            # Run main agent logic
            result = self.run(project_id, state, **kwargs)

            # If result is already an AgentResult, return it directly
            if isinstance(result, AgentResult):
                return result

            # Otherwise finalize into an AgentResult
            return self._finalize(project_id, result or {})

        except Exception as exc:
            logger.exception(f"Agent {self.stage} failed with exception: {exc}")
            self.log_reasoning(f"Exception: {exc}")
            self.needs_human_review = True
            self.confidence = 0.0
            return self._finalize(project_id, {"error": str(exc)})

    def _finalize(self, project_id: str, output: Dict[str, Any]) -> AgentResult:
        """Wrap reasoning and tool calls into a final AgentResult."""
        result = AgentResult(
            project_id=project_id,
            stage=self.stage,
            output=output,
            reasoning_trace=self.reasoning_trace,
            confidence=self.confidence,
            needs_human_review=self.needs_human_review,
            tool_calls=self.tool_calls,
        )
        self.log_reasoning(f"Agent {self.stage} finalized with confidence={self.confidence}, needs_review={self.needs_human_review}")
        return result
