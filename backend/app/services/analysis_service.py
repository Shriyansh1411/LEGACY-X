from pathlib import Path

from app.core.analysis_config import AnalysisConfig
from app.db.database import SessionLocal
from app.models.project import ProjectRecord
from app.parsers.cobol_parser import parse_cobol
from app.schemas.agent import AgentResult, PipelineState
from app.schemas.analysis import LegacyAnalysis, ProjectAnalysisResponse
from app.services.graph_service import build_dependency_graph


analysis_config = AnalysisConfig()


def analyze_project(project_id: str, pipeline_state: PipelineState | None = None) -> ProjectAnalysisResponse:
    with SessionLocal() as session:
        project = session.query(ProjectRecord).filter_by(project_id=project_id).first()
        if project is None:
            raise ValueError("Project not found")

    source_files = list(project.source_files or [])
    file_contents = project.file_contents or {}
    all_signals = []
    business_rule_count = 0

    for file_name in source_files:
        text = file_contents.get(file_name, "")
        if not text:
            continue
        try:
            parsed = parse_cobol(text)
            signals = []
            if parsed.get("conditionals"):
                signals.append("IF")
            if parsed.get("performs"):
                signals.append("PERFORM")
            if parsed.get("io_ops"):
                signals.append("IO")
            upper_text = text.upper()
            if "MOVE" in upper_text:
                signals.append("MOVE")
            if "IF" in upper_text:
                signals.append("IF")
            if signals:
                all_signals.extend(signals)
                business_rule_count += 1
                continue
        except Exception:
            signal_hits = []
            upper_text = text.upper()
            for signal in analysis_config.control_flow_signals:
                if signal in upper_text:
                    signal_hits.append(signal)
            if signal_hits:
                all_signals.extend(signal_hits)
                business_rule_count += 1

    analysis = LegacyAnalysis(
        language=analysis_config.language_name,
        source_files=source_files,
        control_flow_signals=sorted(set(all_signals)),
        business_rule_count=business_rule_count,
    )

    try:
        graph_info = build_dependency_graph(file_contents, source_files)
        analysis.dependency_graph = graph_info.get("nodes", {})
        analysis.high_risk_modules = graph_info.get("high_risk_modules", [])
    except Exception:
        analysis.dependency_graph = None
        analysis.high_risk_modules = []

    response = ProjectAnalysisResponse(project_id=project_id, analysis=analysis)
    if pipeline_state is not None:
        pipeline_state.set_stage(AgentResult(
            project_id=project_id,
            stage="analyze",
            output={"project_id": project_id, "analysis": analysis.model_dump()},
            reasoning_trace=["Legacy analysis completed and persisted to the pipeline state."],
            confidence=0.9 if analysis.control_flow_signals else 0.55,
            needs_human_review=not analysis.control_flow_signals,
            tool_calls=[{"name": "parse_cobol", "args": {"files": source_files}}],
        ))
    return response


def analyze_agent(project_id: str, pipeline_state: PipelineState | None = None) -> AgentResult:
    response = analyze_project(project_id)
    reasoning_trace = [
        f"Parsed {len(response.analysis.source_files)} source files and detected signals: {', '.join(response.analysis.control_flow_signals) or 'none'}.",
        "Dependency risk was inferred from graph degree and IO intensity heuristics.",
    ]
    result = AgentResult(
        project_id=project_id,
        stage="analyze",
        output={"project_id": project_id, "analysis": response.analysis.model_dump()},
        reasoning_trace=reasoning_trace,
        confidence=0.9 if response.analysis.control_flow_signals else 0.55,
        needs_human_review=not response.analysis.control_flow_signals,
        tool_calls=[
            {"name": "parse_cobol", "args": {"files": response.analysis.source_files}},
            {"name": "build_dependency_graph", "args": {"source_files": response.analysis.source_files}},
        ],
    )
    if pipeline_state is not None:
        pipeline_state.set_stage(result)
    return result
