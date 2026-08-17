from app.schemas.agent import AgentResult, PipelineState


def test_agent_result_shape():
    result = AgentResult(
        stage="ingest",
        output={"status": "ok"},
        reasoning_trace=["classified file by extension"],
        confidence=0.91,
        needs_human_review=False,
        tool_calls=[{"name": "classify_file", "args": {"filename": "interest_calc.cbl"}}],
    )

    assert result.stage == "ingest"
    assert result.output["status"] == "ok"
    assert result.confidence > 0.9
    assert result.needs_human_review is False


def test_pipeline_state_tracks_stage_results():
    state = PipelineState(project_id="proj-123")
    state.stages["ingest"] = AgentResult(
        stage="ingest",
        output={"status": "ok"},
        reasoning_trace=["ingest complete"],
        confidence=1.0,
        needs_human_review=False,
        tool_calls=[],
    )

    assert state.project_id == "proj-123"
    assert state.stages["ingest"].stage == "ingest"
