"""
GenerateAgent: Full agentic code generation with planning, strategy selection, and quality reasoning.
Replaces the legacy generate_project with an agent that makes intelligent decisions.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from app.db.database import SessionLocal
from app.models.project import ProjectRecord
from app.parsers.cobol_parser import parse_cobol
from app.schemas.agent import AgentResult, PipelineState
from app.services.base_agent import BaseAgent
from app.services.llm_service import LLMService
from app.services.generation_service import (
    _codegen_from_parsed,
    _testgen_from_parsed,
    _review_generated,
    _generate_with_llm,
    _fallback_generation,
)

logger = logging.getLogger(__name__)


class GenerateAgent(BaseAgent):
    """
    Intelligent generation agent that:
    - Analyzes project state and blueprint rules
    - Chooses LLM or heuristic strategy
    - Generates modernized code and tests
    - Scores quality and confidence
    - Flags uncertain generations for review
    """

    def __init__(self):
        super().__init__(stage="generate", name="GENERATE_AGENT")

    def plan(self, project_id: str, state: PipelineState) -> Dict[str, Any]:
        """
        Plan the generation strategy based on pipeline state and behavior graph.
        """
        plan: Dict[str, Any] = {
            "use_llm": False,
            "use_heuristic_fallback": True,
            "blueprint_available": False,
            "behavior_graph_available": False,
            "risk_level": "unknown",
            "reasoning": [],
        }

        # Check for blueprint rules from understand stage
        understand_result = state.get_stage("understand")
        if understand_result:
            blueprint = understand_result.output.get("blueprint", {})
            rules = blueprint.get("rules", [])
            if rules:
                plan["blueprint_available"] = True
                plan["blueprint_rules"] = rules[:5]  # Top 5 rules
                plan["reasoning"].append(f"Blueprint available with {len(rules)} rules to preserve")
            
            # Check for behavior graph from understand stage
            behavior_graph = understand_result.output.get("behavior_graph", {})
            if behavior_graph:
                plan["behavior_graph_available"] = True
                stats = behavior_graph.get("stats", {})
                high_risk = stats.get("high_risk_nodes", 0)
                avg_confidence = stats.get("avg_confidence", 0.5)
                
                if high_risk > 2:
                    plan["risk_level"] = "high"
                elif high_risk > 0:
                    plan["risk_level"] = "medium"
                else:
                    plan["risk_level"] = "low"
                
                plan["reasoning"].append(f"Behavior graph available: {stats.get('total_nodes', 0)} nodes, {high_risk} high-risk, confidence: {avg_confidence:.2f}")
                plan["behavior_graph_stats"] = stats

        # Check if LLM is available
        if LLMService.is_configured():
            plan["use_llm"] = True
            plan["reasoning"].append("LLM is configured; will attempt LLM-based generation")
        else:
            plan["reasoning"].append("LLM not configured; will fall back to heuristic generation")

        self.log_reasoning(f"Generation strategy plan: {plan}")
        return plan

    def validate_preconditions(self, project_id: str, state: PipelineState) -> bool:
        """Verify that the project has source files to generate from."""
        with SessionLocal() as session:
            project = session.query(ProjectRecord).filter_by(project_id=project_id).first()
            if project is None:
                self.log_reasoning("Project not found")
                return False
            if not project.file_contents:
                self.log_reasoning("No file contents to generate from")
                return False
        return True

    def run(self, project_id: str, state: PipelineState, **kwargs: Any) -> AgentResult:
        """
        Execute generation with intelligent strategy selection and quality reasoning.
        """
        with SessionLocal() as session:
            project = session.query(ProjectRecord).filter_by(project_id=project_id).first()
            if project is None:
                raise ValueError("Project not found")

        source_content = "\n".join((project.file_contents or {}).values())
        self.log_reasoning(f"Loaded {len(source_content)} chars of source content")

        # Extract blueprint rules if available
        blueprint_rules: list[str] = []
        understand_result = state.get_stage("understand")
        if understand_result:
            blueprint = understand_result.output.get("blueprint", {})
            blueprint_rules = [
                rule
                for rule in (blueprint.get("rules", []) or [])
            ]
            self.log_reasoning(f"Using {len(blueprint_rules)} blueprint rules to guide generation")

        generated_code: str = ""
        generated_tests: str = ""
        strategy_used: str = "unknown"
        quality_score: float = 0.5

        # Strategy 1: Try LLM-based generation first
        if LLMService.is_configured():
            self.log_reasoning("Attempting LLM-based generation with blueprint rules")
            try:
                generated_code, generated_tests = self._generate_with_llm_strategy(
                    source_content, blueprint_rules
                )
                if generated_code and generated_tests:
                    strategy_used = "llm"
                    quality_score = self._score_generation_quality(generated_code, generated_tests, True)
                    self.log_reasoning(f"LLM generation succeeded with quality score {quality_score}")
                else:
                    self.log_reasoning("LLM generation produced empty output; attempting fallback")
            except Exception as exc:
                self.log_reasoning(f"LLM generation failed: {exc}; attempting fallback")

        # Strategy 2: Fallback to heuristic if LLM didn't succeed
        if not generated_code or not generated_tests:
            self.log_reasoning("Falling back to heuristic code generation")
            generated_code, generated_tests = self._generate_heuristic_strategy(
                source_content, blueprint_rules
            )
            strategy_used = "heuristic"
            quality_score = self._score_generation_quality(generated_code, generated_tests, False)
            self.log_reasoning(f"Heuristic generation completed with quality score {quality_score}")

        # Persist generated code
        with SessionLocal() as session:
            project = session.query(ProjectRecord).filter_by(project_id=project_id).first()
            if project:
                project.generated_code = generated_code
                project.generated_tests = generated_tests
                session.add(project)
                session.commit()
                self.log_reasoning("Generated code and tests persisted to database")

        # Set confidence and review flags
        self.confidence = quality_score
        self.needs_human_review = strategy_used == "heuristic" or quality_score < 0.7
        if self.needs_human_review:
            self.log_reasoning(f"Flagged for human review: strategy={strategy_used}, quality={quality_score}")

        return AgentResult(
            project_id=project_id,
            stage="generate",
            output={
                "project_id": project_id,
                "generated_code": generated_code,
                "generated_tests": generated_tests,
                "strategy": strategy_used,
                "quality_score": quality_score,
                "blueprint_rules_applied": len(blueprint_rules),
            },
            reasoning_trace=self.reasoning_trace,
            confidence=self.confidence,
            needs_human_review=self.needs_human_review,
            tool_calls=self.tool_calls,
        )

    def _generate_with_llm_strategy(self, source_content: str, blueprint_rules: list[str]) -> tuple[str, str]:
        """Execute LLM-based generation with tool calls."""
        self.log_tool_call("_generate_with_llm", {
            "source_length": len(source_content),
            "blueprint_rules_count": len(blueprint_rules),
        })
        generated_code, generated_tests = _generate_with_llm(source_content, blueprint_rules)
        self.log_tool_call("_generate_with_llm", {"result": "success" if generated_code else "empty"})
        return generated_code, generated_tests

    def _generate_heuristic_strategy(self, source_content: str, blueprint_rules: list[str]) -> tuple[str, str]:
        """Execute heuristic-based generation with tool calls."""
        self.log_reasoning("Parsing COBOL structure for heuristic generation")

        parsed: Dict[str, Any] = {}
        try:
            self.log_tool_call("parse_cobol", {"source_length": len(source_content)})
            parsed = parse_cobol(source_content)
            self.log_reasoning(f"Parsed {len(parsed.get('paragraphs', []))} paragraphs from source")
        except Exception as exc:
            self.log_reasoning(f"COBOL parse failed: {exc}; proceeding with empty structure")
            parsed = {}

        # Generate code from parsed structure
        self.log_tool_call("_codegen_from_parsed", {"paragraphs": len(parsed.get("paragraphs", []))})
        generated_code = _codegen_from_parsed(parsed, blueprint_rules)

        # Generate tests
        self.log_tool_call("_testgen_from_parsed", {"code_length": len(generated_code)})
        generated_tests = _testgen_from_parsed(parsed, generated_code)

        # Review generated output for consistency
        self.log_tool_call("_review_generated", {"code_length": len(generated_code)})
        generated_code, generated_tests = _review_generated(generated_code, generated_tests)
        self.log_reasoning("Heuristic generation review completed")

        return generated_code, generated_tests

    def _score_generation_quality(self, code: str, tests: str, is_llm: bool) -> float:
        """
        Score the quality of generated code and tests.
        Factors: code/test length, function definitions, test assertions, LLM vs heuristic.
        """
        score = 0.5

        # Baseline: has content
        if code and tests:
            score = 0.6

        # Has function definitions
        if "def " in code:
            score += 0.1

        # Has test assertions
        if "assert " in tests:
            score += 0.1

        # Longer code = potentially more comprehensive
        if len(code) > 200:
            score += 0.05

        if len(tests) > 200:
            score += 0.05

        # LLM results get a confidence boost
        if is_llm:
            score += 0.1

        return min(score, 1.0)


def generate_agentic(project_id: str, state: PipelineState) -> AgentResult:
    """Convenience function to run the GenerateAgent."""
    agent = GenerateAgent()
    return agent.execute(project_id, state)
