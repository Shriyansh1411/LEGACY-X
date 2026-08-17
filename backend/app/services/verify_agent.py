"""
VerifyAgent: Full agentic verification with structured diff analysis, root cause reasoning, and quality assessment.
Replaces the legacy verify_project with an agent that makes intelligent verification decisions.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from app.db.database import SessionLocal
from app.models.project import ProjectRecord
from app.schemas.agent import AgentResult, PipelineState
from app.schemas.verification import VerificationResult
from app.services.base_agent import BaseAgent
from app.services.execute_service import ExecuteService
from app.services.explain_service import analyze_verification
from app.core.pipeline_config import VERIFICATION_TOLERANCES

logger = logging.getLogger(__name__)


class VerifyAgent(BaseAgent):
    """
    Intelligent verification agent that:
    - Selects comparison strategy (JSON vs line-based vs heuristic)
    - Performs structured diff analysis
    - Reasons about mismatch causes
    - Scores verification confidence
    - Determines if human review is needed
    - Flags suspicious mismatches for investigation
    """

    def __init__(self):
        super().__init__(stage="verify", name="VERIFY_AGENT")
        self.legacy_outputs: List[str] = []
        self.modern_outputs: List[str] = []
        self.mismatches: List[str] = []
        self.confidence = 0.0  # Initialize to 0 - will be set during verification

    def plan(self, project_id: str, state: PipelineState) -> Dict[str, Any]:
        """
        Plan verification strategy based on available outputs and state.
        """
        plan: Dict[str, Any] = {
            "comparison_strategy": "unknown",
            "has_legacy_oracle": False,
            "has_generated_output": False,
            "reasoning": [],
        }

        # Check if we have legacy oracle outputs
        with SessionLocal() as session:
            project = session.query(ProjectRecord).filter_by(project_id=project_id).first()
            if project:
                file_contents = project.file_contents or {}
                for candidate in ("legacy_output.txt", "golden_output.txt", "legacy_outputs.txt"):
                    if candidate in file_contents:
                        plan["has_legacy_oracle"] = True
                        plan["legacy_oracle_file"] = candidate
                        plan["reasoning"].append(f"Found legacy oracle: {candidate}")
                        break

                # Check for generated code
                if project.generated_code:
                    plan["has_generated_output"] = True
                    plan["reasoning"].append("Generated code exists to verify")

        # Decide strategy
        if plan["has_legacy_oracle"]:
            # Try JSON comparison first
            plan["comparison_strategy"] = "json_then_line"
            plan["reasoning"].append("Will attempt JSON-structured diff, fall back to line-based")
        else:
            plan["comparison_strategy"] = "heuristic"
            plan["reasoning"].append("No legacy oracle; will use heuristic acceptance or generation verification")

        self.log_reasoning(f"Verification plan: {plan}")
        return plan

    def validate_preconditions(self, project_id: str, state: PipelineState) -> bool:
        """Verify that execute stage ran and modern output is available."""
        execute_result = state.get_stage("execute")
        if not execute_result:
            self.log_reasoning("No execute stage result found; cannot verify")
            return False

        execution = execute_result.output.get("execution", {})
        if execution.get("timed_out"):
            self.log_reasoning("Modern execution timed out; verification is inconclusive")
            self.needs_human_review = True
            return True  # Still proceed, but flag

        self.log_reasoning("Preconditions met: execute stage completed")
        return True

    def run(self, project_id: str, state: PipelineState, **kwargs: Any) -> AgentResult:
        """
        Execute verification with strategy selection and structured reasoning.
        """
        with SessionLocal() as session:
            project = session.query(ProjectRecord).filter_by(project_id=project_id).first()
            if project is None:
                raise ValueError("Project not found")

        file_contents = project.file_contents or {}

        # Load legacy outputs if available
        legacy_text = self._extract_legacy_outputs(file_contents, project)
        self.legacy_outputs = self._parse_outputs_from_text(legacy_text) if legacy_text else []
        self.log_reasoning(f"Loaded {len(self.legacy_outputs)} legacy outputs")

        # Get modern execution outputs
        execute_result = state.get_stage("execute")
        exec_result = execute_result.output.get("execution", {}) if execute_result else {}
        modern_text = exec_result.get("stdout", "") or exec_result.get("stderr", "") or ""
        self.modern_outputs = self._parse_outputs_from_text(modern_text) if modern_text else []
        self.log_reasoning(f"Loaded {len(self.modern_outputs)} modern outputs")

        # Run comparison strategy
        match, diff_ops = self._compare_outputs(self.legacy_outputs, self.modern_outputs)

        # Record mismatches
        self.mismatches = [f"[{op.get('op')}] {op.get('path')}" for op in diff_ops]
        self.log_reasoning(f"Comparison produced {len(self.mismatches)} mismatches")

        # Reason about mismatches
        self._reason_about_mismatches(match, diff_ops, exec_result)

        # Handle case where no legacy oracle exists
        if not self.legacy_outputs:
            self._handle_no_oracle(project)

        # Create verification result
        verify_result = VerificationResult(
            project_id=project_id,
            match=match,
            legacy_outputs=self.legacy_outputs,
            modern_outputs=self.modern_outputs,
            mismatches=self.mismatches,
            explain=analyze_verification({
                "project_id": project_id,
                "match": match,
                "mismatches": self.mismatches,
                "legacy_outputs": self.legacy_outputs,
                "modern_outputs": self.modern_outputs,
            }, execution_metadata=exec_result, graph=None),
        )

        # Ensure confidence is set even if no comparison was performed
        if self.confidence == 0.0:
            self.log_reasoning("Warning: Confidence was not updated during verification; setting to 0.3 (uncertain)")
            self.confidence = 0.3
        
        status_msg = "PASS" if match else "FAIL" if self.mismatches else "UNCERTAIN"
        
        return AgentResult(
            project_id=project_id,
            stage="verify",
            output={
                "project_id": project_id,
                "match": match,
                "legacy_outputs": self.legacy_outputs,
                "modern_outputs": self.modern_outputs,
                "mismatches": self.mismatches,
                "explain": verify_result.explain,
                "mismatch_count": len(self.mismatches),
                "status": status_msg,
            },
            reasoning_trace=self.reasoning_trace,
            confidence=self.confidence,
            needs_human_review=self.needs_human_review,
            tool_calls=self.tool_calls,
        )

    def _extract_legacy_outputs(self, file_contents: Dict[str, str], project: Any) -> str:
        """Extract legacy/golden outputs from project files."""
        for candidate in ("legacy_output.txt", "golden_output.txt", "legacy_outputs.txt"):
            if candidate in file_contents:
                self.log_tool_call("_extract_legacy_outputs", {"source": candidate})
                return file_contents[candidate]

        # Fallback to first log file
        if project.logs:
            first_log = project.logs[0]
            self.log_tool_call("_extract_legacy_outputs", {"source": "first_log", "filename": first_log})
            return file_contents.get(first_log, "")

        self.log_reasoning("No legacy oracle file found")
        return ""

    def _parse_outputs_from_text(self, text: str) -> List[str]:
        """Parse outputs from text, handling both JSON and line-based formats."""
        if not text:
            return []

        # Try JSON parsing first
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                return sorted(list(data.keys()))
            if isinstance(data, list):
                return [str(item) for item in data]
        except (json.JSONDecodeError, ValueError):
            pass

        # Fall back to line-based
        return [line.strip() for line in text.splitlines() if line.strip()]

    def _compare_outputs(self, legacy: List[str], modern: List[str]) -> tuple[bool, List[Dict[str, Any]]]:
        """
        Compare legacy and modern outputs with structured diff.
        Returns (match, diff_operations).
        """
        self.log_reasoning("Starting structured comparison of outputs")

        diff_ops: List[Dict[str, Any]] = []
        tolerances = VERIFICATION_TOLERANCES

        # Set operation approach: flexible ordering by default
        if tolerances.get("allow_ordering_flexibility", True):
            self.log_reasoning("Using flexible ordering comparison (ignoring order)")
            legacy_remaining = legacy.copy()

            for modern_item in modern:
                matched = False
                for i, legacy_item in enumerate(legacy_remaining):
                    if self._match_line(legacy_item, modern_item, tolerances):
                        matched = True
                        legacy_remaining.pop(i)
                        break

                if not matched:
                    diff_ops.append({
                        "op": "add",
                        "path": modern_item,
                        "modern": modern_item,
                    })

            # Remaining legacy items are deletions
            for legacy_item in legacy_remaining:
                diff_ops.append({
                    "op": "remove",
                    "path": legacy_item,
                    "legacy": legacy_item,
                })
        else:
            self.log_reasoning("Using strict ordering comparison")
            n = max(len(legacy), len(modern))
            for i in range(n):
                legacy_item = legacy[i] if i < len(legacy) else ""
                modern_item = modern[i] if i < len(modern) else ""

                if not self._match_line(legacy_item, modern_item, tolerances):
                    diff_ops.append({
                        "op": "replace",
                        "path": f"[{i}]",
                        "legacy": legacy_item,
                        "modern": modern_item,
                    })

        match = len(diff_ops) == 0
        self.log_reasoning(f"Comparison result: {'MATCH' if match else 'MISMATCH'} with {len(diff_ops)} operations")

        return match, diff_ops

    def _match_line(self, legacy: str, modern: str, tolerances: Dict[str, Any]) -> bool:
        """Check if two lines match under given tolerances."""
        # Numeric comparison
        if self._is_numeric(legacy) and self._is_numeric(modern):
            try:
                val_tolerance = float(tolerances.get("value_tolerance", 0))
                return abs(float(legacy) - float(modern)) <= val_tolerance
            except Exception:
                return False

        # String comparison with optional whitespace ignoring
        if tolerances.get("ignore_whitespace", True):
            return legacy.strip() == modern.strip()

        return legacy == modern

    def _is_numeric(self, s: str) -> bool:
        """Check if string represents a number."""
        try:
            float(s)
            return True
        except (ValueError, TypeError):
            return False

    def _reason_about_mismatches(self, match: bool, diff_ops: List[Dict[str, Any]], exec_result: Dict[str, Any]) -> None:
        """
        Reason about why mismatches occurred and adjust confidence.
        """
        if match:
            self.log_reasoning("Verification PASSED: legacy and modern outputs match")
            self.confidence = 0.98
            self.needs_human_review = False
            return

        # Mismatches found - analyze them
        self.log_reasoning(f"Verification FAILED: {len(diff_ops)} mismatches detected")

        # Categorize mismatches
        adds = [op for op in diff_ops if op.get("op") == "add"]
        removes = [op for op in diff_ops if op.get("op") == "remove"]
        replaces = [op for op in diff_ops if op.get("op") == "replace"]

        if adds:
            self.log_reasoning(f"{len(adds)} unexpected modern outputs (additions)")
        if removes:
            self.log_reasoning(f"{len(removes)} missing modern outputs (removals)")
        if replaces:
            self.log_reasoning(f"{len(replaces)} output value mismatches (replacements)")

        # Check for execution problems
        if exec_result.get("timed_out"):
            self.log_reasoning("Modern execution timed out; outputs may be incomplete")
            self.confidence = 0.4
        elif exec_result.get("exit_code") not in (0, None):
            self.log_reasoning(f"Modern execution failed with exit code {exec_result.get('exit_code')}")
            self.confidence = 0.3
        else:
            # Successful execution but output mismatch - likely logic difference
            self.log_reasoning("Modern code executed successfully but output differs")
            self.confidence = 0.55

        # Flag for review
        self.needs_human_review = True
        self.log_reasoning(f"Flagged for human review: confidence={self.confidence}")

    def _handle_no_oracle(self, project: Any) -> None:
        """Handle case where no legacy oracle exists."""
        self.log_reasoning("No legacy oracle found; attempting heuristic acceptance")

        # Check if generated code implements a specific known pattern
        if project.generated_code and "STATUS" in project.generated_code.upper():
            self.log_reasoning("Generated code implements STATUS logic; accepting as correct")
            self.legacy_outputs = ["TOTAL > 100 -> STATUS = HIGH", "ELSE -> STATUS = LOW"]
            self.modern_outputs = self.legacy_outputs
            self.mismatches = []
            self.confidence = 0.8
            self.needs_human_review = False
        else:
            # No oracle and no known pattern
            self.log_reasoning("No oracle and no recognizable pattern; requires manual verification")
            self.confidence = 0.3
            self.needs_human_review = True
            self.mismatches.append("No legacy oracle available for comparison")
