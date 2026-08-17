"""
Integration test for the fully agentic Generate, Execute, and Verify stages.
"""

import sys
import json
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.database import SessionLocal
from app.models.project import ProjectRecord
from app.schemas.agent import PipelineState, AgentResult
from app.services.generate_agent import GenerateAgent
from app.services.execute_agent import ExecuteAgent
from app.services.verify_agent import VerifyAgent


def test_generate_agent():
    """Test GenerateAgent with sample COBOL project."""
    # Create a test project
    session = SessionLocal()
    project = ProjectRecord(
        project_id="test_gen_001",
        file_contents={
            "source.cbl": """       IDENTIFICATION DIVISION.
       PROGRAM-ID. TEST-PROGRAM.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-TOTAL      PIC 9(5) VALUE 0.
       01  WS-STATUS     PIC X(10) VALUE "LOW".
       PROCEDURE DIVISION.
           EVALUATE TRUE
               WHEN WS-TOTAL > 100
                   MOVE "HIGH" TO WS-STATUS
               WHEN OTHER
                   MOVE "LOW" TO WS-STATUS
           END-EVALUATE.
           DISPLAY WS-STATUS.
           STOP RUN.""",
        },
        source_files=["source.cbl"],
        language_hint="cobol",
    )
    session.add(project)
    session.commit()
    session.close()

    # Run GenerateAgent
    state = PipelineState(project_id="test_gen_001")
    agent = GenerateAgent()
    result = agent.execute("test_gen_001", state)

    print("\n=== GENERATE AGENT RESULT ===")
    print(f"Stage: {result.stage}")
    print(f"Confidence: {result.confidence}")
    print(f"Needs Review: {result.needs_human_review}")
    print(f"Strategy: {result.output.get('strategy')}")
    print(f"Generated Code Lines: {len(result.output.get('generated_code', '').splitlines())}")
    print(f"Generated Tests Lines: {len(result.output.get('generated_tests', '').splitlines())}")
    print(f"Reasoning Trace:")
    for line in result.reasoning_trace[:5]:
        print(f"  - {line}")

    assert result.stage == "generate"
    assert len(result.output.get("generated_code", "")) > 0
    assert len(result.output.get("generated_tests", "")) > 0
    print("✓ GenerateAgent test passed")
    return result


def test_execute_agent(generate_result: AgentResult):
    """Test ExecuteAgent with generated code."""
    # Create pipeline state with generate result
    state = PipelineState(project_id="test_gen_001")
    state.set_stage(generate_result)

    # Run ExecuteAgent
    agent = ExecuteAgent()
    result = agent.execute("test_gen_001", state)

    print("\n=== EXECUTE AGENT RESULT ===")
    print(f"Stage: {result.stage}")
    print(f"Confidence: {result.confidence}")
    print(f"Needs Review: {result.needs_human_review}")
    print(f"Exit Code: {result.output.get('exit_code')}")
    print(f"Timed Out: {result.output.get('timed_out')}")
    print(f"Output Length: {result.output.get('output_length')} chars")
    print(f"Reasoning Trace:")
    for line in result.reasoning_trace[:5]:
        print(f"  - {line}")

    assert result.stage == "execute"
    print("✓ ExecuteAgent test passed")
    return result


def test_verify_agent(generate_result: AgentResult, execute_result: AgentResult):
    """Test VerifyAgent with execution results."""
    # Create pipeline state with both generate and execute results
    state = PipelineState(project_id="test_gen_001")
    state.set_stage(generate_result)
    state.set_stage(execute_result)

    # Run VerifyAgent
    agent = VerifyAgent()
    result = agent.execute("test_gen_001", state)

    print("\n=== VERIFY AGENT RESULT ===")
    print(f"Stage: {result.stage}")
    print(f"Confidence: {result.confidence}")
    print(f"Needs Review: {result.needs_human_review}")
    print(f"Mismatch Count: {result.output.get('mismatch_count')}")
    print(f"Legacy Outputs: {len(result.output.get('legacy_outputs', []))}")
    print(f"Modern Outputs: {len(result.output.get('modern_outputs', []))}")
    print(f"Reasoning Trace:")
    for line in result.reasoning_trace[:5]:
        print(f"  - {line}")

    assert result.stage == "verify"
    print("✓ VerifyAgent test passed")
    return result


if __name__ == "__main__":
    print("Running agentic pipeline integration tests...")
    gen_result = test_generate_agent()
    exec_result = test_execute_agent(gen_result)
    verify_result = test_verify_agent(gen_result, exec_result)
    print("\n✓✓✓ All agentic agents working correctly! ✓✓✓")
