"""
ExecuteAgent: Full agentic execution orchestration with resource planning, monitoring, and failure reasoning.
Replaces the legacy execute_agentic_stage with an agent that makes intelligent runtime decisions.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from app.db.database import SessionLocal
from app.models.project import ProjectRecord
from app.schemas.agent import AgentResult, PipelineState
from app.services.base_agent import BaseAgent
from app.services.execute_service import ExecuteService

logger = logging.getLogger(__name__)


class ExecuteAgent(BaseAgent):
    """
    Intelligent execution agent that:
    - Plans resource allocation and execution strategy
    - Validates generated code is available
    - Executes in sandboxed environment
    - Monitors for timeouts, crashes, resource issues
    - Reasons about failures and success
    - Flags concerning execution patterns for review
    """

    def __init__(self):
        super().__init__(stage="execute", name="EXECUTE_AGENT")
        self.execution_result: Dict[str, Any] = {}

    def plan(self, project_id: str, state: PipelineState) -> Dict[str, Any]:
        """
        Plan execution strategy based on generated code and available resources.
        """
        plan: Dict[str, Any] = {
            "use_docker": False,
            "timeout_seconds": 120,
            "expected_tests": False,
            "reasoning": [],
        }

        # Check for generated code and tests
        generate_result = state.get_stage("generate")
        if generate_result:
            generated_code = generate_result.output.get("generated_code", "")
            generated_tests = generate_result.output.get("generated_tests", "")

            if "def test_" in generated_tests:
                plan["expected_tests"] = True
                plan["reasoning"].append("Generated tests detected; will run pytest")
            else:
                plan["reasoning"].append("No generated tests found; will run generated code")

            if len(generated_code) > 500:
                plan["timeout_seconds"] = 180
                plan["reasoning"].append("Large generated code; increasing timeout to 180s")

        # Docker execution decision: for now, we stick with local execution in Docker container
        plan["use_docker"] = False
        plan["reasoning"].append("Using local execution within Docker container")

        self.log_reasoning(f"Execution plan: {plan}")
        return plan

    def validate_preconditions(self, project_id: str, state: PipelineState) -> bool:
        """Verify that generated code exists to execute."""
        generate_result = state.get_stage("generate")
        if not generate_result:
            self.log_reasoning("No generate stage result found in pipeline")
            return False

        generated_code = generate_result.output.get("generated_code", "")
        if not generated_code:
            self.log_reasoning("Generated code is empty; cannot execute")
            return False

        self.log_reasoning(f"Preconditions met: found {len(generated_code)} chars of generated code")
        return True

    def run(self, project_id: str, state: PipelineState, **kwargs: Any) -> AgentResult:
        """
        Execute generated code in a sandboxed environment with monitoring and reasoning.
        """
        with SessionLocal() as session:
            project = session.query(ProjectRecord).filter_by(project_id=project_id).first()
            if project is None:
                raise ValueError("Project not found")

        # Gather workspace files
        workspace_files = project.file_contents or {}
        self.log_reasoning(f"Workspace has {len(workspace_files)} files")

        # Run planning phase for resource allocation
        plan = self.plan(project_id, state)
        timeout = plan.get("timeout_seconds", 120)
        use_docker = plan.get("use_docker", False)

        self.log_reasoning(f"Executing with timeout={timeout}s, docker={use_docker}")

        # Execute the code
        try:
            self.log_tool_call("ExecuteService.run", {
                "project_id": project_id,
                "use_docker": use_docker,
                "timeout": timeout,
            })

            execution_result = ExecuteService.run(
                workspace_files,
                use_docker=use_docker,
                timeout=timeout,
                project_id=project_id,
            )

            self.execution_result = execution_result
            self.log_tool_call("ExecuteService.run", {"result": "completed"})

        except Exception as exc:
            self.log_reasoning(f"Execution raised exception: {exc}")
            self.needs_human_review = True
            self.confidence = 0.0
            execution_result = {
                "exit_code": None,
                "stdout": "",
                "stderr": str(exc),
                "timed_out": False,
                "cmd": "",
            }
            self.execution_result = execution_result

        # Analyze execution results
        self._analyze_execution_result(execution_result)

        # Generate status message
        status_msg = self._generate_status_message(execution_result)
        
        return AgentResult(
            project_id=project_id,
            stage="execute",
            output={
                "project_id": project_id,
                "execution": execution_result,
                "exit_code": execution_result.get("exit_code"),
                "timed_out": execution_result.get("timed_out"),
                "output_length": len(execution_result.get("stdout", "")),
                "status": status_msg,
            },
            reasoning_trace=self.reasoning_trace,
            confidence=self.confidence,
            needs_human_review=self.needs_human_review,
            tool_calls=self.tool_calls,
        )

    def _generate_status_message(self, result: Dict[str, Any]) -> str:
        """Generate a human-readable status message for the execution."""
        exit_code = result.get("exit_code")
        timed_out = result.get("timed_out")
        stdout = result.get("stdout", "") or ""
        stderr = result.get("stderr", "") or ""
        
        if timed_out:
            return "TIMEOUT: Execution exceeded time limit"
        
        if exit_code == 0:
            if "passed" in stdout.lower() or "ok" in stdout.lower():
                return "SUCCESS: All tests passed"
            return "SUCCESS: Code executed without errors"
        
        if exit_code is not None:
            if exit_code == 1:
                return f"FAILED: Test or general error (exit code: {exit_code})"
            elif exit_code == 2:
                return f"FAILED: Import/Syntax error (exit code: {exit_code})"
            else:
                return f"FAILED: Execution error (exit code: {exit_code})"
        
        # No exit code
        if stdout or stderr:
            return "UNKNOWN: Execution produced output but no exit code"
        return "UNKNOWN: No execution output captured"
    
    def _analyze_execution_result(self, result: Dict[str, Any]) -> None:
        """
        Analyze execution result and update confidence/review flags.
        Reasons about success, failures, timeouts, and anomalies.
        """
        exit_code = result.get("exit_code")
        timed_out = result.get("timed_out")
        stdout = result.get("stdout", "") or ""
        stderr = result.get("stderr", "") or ""

        # Check for timeout
        if timed_out:
            self.log_reasoning("Execution TIMED OUT: code may have infinite loop or resource leak")
            self.needs_human_review = True
            self.confidence = 0.2
            return

        # Check for successful execution (exit code 0)
        if exit_code == 0:
            self.log_reasoning("Execution succeeded with exit code 0")
            self.confidence = 0.95
            self.needs_human_review = False

            # Additional checks for output
            if stdout:
                self.log_reasoning(f"Captured {len(stdout)} chars of stdout")
                if "passed" in stdout.lower() or "ok" in stdout.lower():
                    self.log_reasoning("Output suggests test success (found 'passed' or 'ok')")
                    self.confidence = 0.98

            if stderr and "warning" not in stderr.lower():
                self.log_reasoning(f"Captured stderr output ({len(stderr)} chars); investigating")
                if "error" in stderr.lower():
                    self.log_reasoning("Stderr contains 'error'; downgrading confidence")
                    self.confidence = 0.75
                    self.needs_human_review = True
            return

        # Check for failure exit codes
        if exit_code is not None:
            self.log_reasoning(f"Execution failed with exit code {exit_code}")
            self.confidence = 0.4
            self.needs_human_review = True

            # Try to reason about the failure
            if exit_code == 1:
                self.log_reasoning("Exit code 1: likely test failure or general error")
            elif exit_code == 2:
                self.log_reasoning("Exit code 2: possibly import error or syntax error")
            elif exit_code > 128:
                self.log_reasoning(f"Exit code {exit_code}: possibly killed by signal")

            # Check stderr for clues
            if stderr:
                self.log_reasoning(f"Stderr output ({len(stderr)} chars) may contain error details")
                if "ModuleNotFoundError" in stderr or "ImportError" in stderr:
                    self.log_reasoning("Detected import error; check dependencies")
                if "SyntaxError" in stderr:
                    self.log_reasoning("Detected syntax error in generated code")
                if "AssertionError" in stderr:
                    self.log_reasoning("Detected assertion failure in tests")

            return

        # Unknown state - no exit code available
        if not stdout and not stderr:
            self.log_reasoning("No execution output captured; code may not have run or produced no output")
            self.confidence = 0.2
            self.needs_human_review = True
        else:
            self.log_reasoning(f"Execution completed but exit code unavailable. Stdout: {len(stdout)} chars, Stderr: {len(stderr)} chars")
            self.confidence = 0.6  # Moderate confidence when we have output but no exit code
            self.needs_human_review = False
        self.needs_human_review = True
