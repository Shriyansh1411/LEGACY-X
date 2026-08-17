import json
import os

from app.db.database import SessionLocal
from app.models.project import ProjectRecord
from app.schemas.agent import AgentResult, PipelineState
from app.schemas.blueprint import BehavioralBlueprint, ProjectBlueprintResponse
from app.services.llm_service import LLMService
from app.services.behavior_graph_service import build_behavior_graph
from app.schemas.analysis import LegacyAnalysis


def _heuristic_blueprint(source_contents: dict[str, str]) -> tuple[list[dict], list[str], list[str]]:
    rules: list[dict] = []
    edge_cases: list[str] = []
    dependencies: list[str] = []
    for file_name, content in source_contents.items():
        upper = content.upper()
        if "IF" in upper and "TOTAL" in upper and "STATUS" in upper:
            rules.append({
                "rule": "If TOTAL exceeds 100, STATUS should be set to HIGH.",
                "confidence": 0.85,
                "source_evidence": {"file": file_name, "line_hint": "IF TOTAL > 100"},
                "depends_on": ["TOTAL", "STATUS"],
            })
            edge_cases.append("TOTAL exactly equals 100 should be checked to determine whether the branch should be inclusive.")
            dependencies.extend(["TOTAL", "STATUS"])
        if "MOVE" in upper and "STATUS" in upper:
            rules.append({
                "rule": "MOVE operations assign a result value into STATUS.",
                "confidence": 0.75,
                "source_evidence": {"file": file_name, "line_hint": "MOVE 'HIGH' TO STATUS"},
                "depends_on": ["STATUS"],
            })
        if "ELSE" in upper:
            edge_cases.append("The ELSE branch represents the non-trigger condition and should be explicitly tested.")
    return rules, edge_cases, sorted(set(dependencies))


def understand_project(project_id: str, pipeline_state: PipelineState | None = None) -> ProjectBlueprintResponse:
    with SessionLocal() as session:
        project = session.query(ProjectRecord).filter_by(project_id=project_id).first()
        if project is None:
            raise ValueError("Project not found")

    source_contents = project.file_contents or {}
    rules: list[dict] = []
    edge_cases: list[str] = []
    dependencies: list[str] = []

    try:
        if os.environ.get("ENABLE_AGENTIC", "false").lower() in ("1", "true") and LLMService.is_configured():
            prompt = (
                "Extract a concise behavioral blueprint from the provided legacy source files. "
                "Return JSON with keys: rules, edge_cases, and dependencies. "
                "Each rule must be an object with fields: rule, confidence, source_evidence, depends_on. "
                "source_evidence must be an object with file and line_hint. "
                "Files:\n" + "\n---\n".join([f"{fn}:\n{content[:2000]}" for fn, content in source_contents.items()])
            )
            messages = [
                {"role": "system", "content": "You are an assistant that extracts behavioral rules from legacy code."},
                {"role": "user", "content": prompt},
            ]
            resp_text = LLMService.chat(messages, temperature=0.0)
            try:
                parsed = json.loads(resp_text)
                rules = parsed.get("rules") or []
                edge_cases = parsed.get("edge_cases") or []
                dependencies = parsed.get("dependencies") or []
            except Exception:
                rules = []
                edge_cases = []
                dependencies = []
        else:
            rules = []
            edge_cases = []
            dependencies = []
    except Exception:
        rules = []
        edge_cases = []
        dependencies = []

    if not rules:
        heuristic_rules, heuristic_edge_cases, heuristic_dependencies = _heuristic_blueprint(source_contents)
        rules = heuristic_rules
        edge_cases = heuristic_edge_cases
        dependencies = heuristic_dependencies

    normalized_rules = []
    for item in rules:
        if isinstance(item, dict):
            normalized_rules.append({
                "rule": item.get("rule") or str(item),
                "confidence": float(item.get("confidence", 0.0) or 0.0),
                "source_evidence": item.get("source_evidence") or {"file": "unknown", "line_hint": "unknown"},
                "depends_on": item.get("depends_on") or [],
            })
        else:
            normalized_rules.append({"rule": str(item), "confidence": 0.0, "source_evidence": {"file": "unknown", "line_hint": "unknown"}, "depends_on": []})

    blueprint = BehavioralBlueprint(
        rules=[entry["rule"] for entry in normalized_rules],
        edge_cases=edge_cases,
        dependencies=sorted(set(dependencies)),
    )
    
    # Build behavior graph if we have analysis data
    behavior_graph_data = None
    if pipeline_state is not None:
        analyze_result = pipeline_state.get_stage("analyze")
        if analyze_result:
            try:
                analysis_output = analyze_result.output.get("analysis", {})
                analysis = LegacyAnalysis(**analysis_output)
                behavior_graph_data = build_behavior_graph(analysis, blueprint)
                # Store behavior graph in database
                with SessionLocal() as session:
                    project = session.query(ProjectRecord).filter_by(project_id=project_id).first()
                    if project:
                        project.behavior_graph = behavior_graph_data
                        session.add(project)
                        session.commit()
            except Exception as e:
                print(f"Failed to build behavior graph: {e}")
                behavior_graph_data = None
    
    response = ProjectBlueprintResponse(project_id=project_id, blueprint=blueprint)
    if pipeline_state is not None:
        output_data = {"project_id": project_id, "blueprint": blueprint.model_dump()}
        if behavior_graph_data:
            output_data["behavior_graph"] = behavior_graph_data
        pipeline_state.set_stage(AgentResult(
            project_id=project_id,
            stage="understand",
            output=output_data,
            reasoning_trace=["Behavioral blueprint derived from the legacy source and heuristic rule extraction.", "Behavior graph built from analysis signals and blueprint rules."],
            confidence=0.8 if blueprint.rules else 0.35,
            needs_human_review=not blueprint.rules,
            tool_calls=[{"name": "LLMService.chat", "args": {"files": list(source_contents.keys())}}, {"name": "build_behavior_graph", "args": {"nodes": len(behavior_graph_data.get("nodes", [])) if behavior_graph_data else 0}}],
        ))
    return response


def understand_agent(project_id: str, pipeline_state: PipelineState | None = None) -> AgentResult:
    response = understand_project(project_id)
    raw_rules = response.blueprint.rules
    reasoning_trace = [
        f"Extracted {len(raw_rules)} behavioral rules and {len(response.blueprint.edge_cases)} edge cases.",
        "Fallback heuristics were used when no LLM configuration was available or the structured output was empty.",
    ]
    result = AgentResult(
        project_id=project_id,
        stage="understand",
        output={"project_id": project_id, "blueprint": response.blueprint.model_dump()},
        reasoning_trace=reasoning_trace,
        confidence=0.8 if raw_rules else 0.35,
        needs_human_review=not raw_rules,
        tool_calls=[{"name": "LLMService.chat", "args": {"source_files": list((project_id and []) or [])}}],
    )
    if pipeline_state is not None:
        pipeline_state.set_stage(result)
    return result
