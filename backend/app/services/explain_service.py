import json
import os
import re

from app.db.database import SessionLocal
from app.models.project import ProjectRecord
from app.schemas.agent import AgentResult, PipelineState
from app.schemas.explain import ExplainResult
from app.services.llm_service import LLMService


def _extract_rule_variables(source_text: str) -> tuple[str | None, str | None]:
    """Extract a conditional variable and target assignment from COBOL-like logic."""
    lines = [line.strip() for line in source_text.splitlines() if line.strip()]
    for line in lines:
        upper_line = line.upper()
        if not any(keyword in upper_line for keyword in ("IF ", "WHEN ", "EVALUATE")):
            continue

        cond_match = re.search(r"(?:IF|WHEN)\s+([A-Z0-9_-]+)\s*(?:>|>=|=|<|<=|<>|NOT|IS|EQUALS)?", line, re.IGNORECASE)
        target_match = re.search(r"MOVE\s+(?:'([^']*)'|\"([^\"]*)\"|([^\s]+))\s+TO\s+([A-Z0-9_-]+)", line, re.IGNORECASE)
        if cond_match:
            var_name = cond_match.group(1)
            target_name = target_match.group(4) if target_match else None
            return var_name, target_name

    for line in lines:
        target_match = re.search(r"MOVE\s+(?:'([^']*)'|\"([^\"]*)\"|([^\s]+))\s+TO\s+([A-Z0-9_-]+)", line, re.IGNORECASE)
        if target_match:
            return None, target_match.group(4)

    for line in lines:
        if "IF" in line.upper() or "WHEN" in line.upper():
            cond_match = re.search(r"(?:IF|WHEN)\s+([A-Z0-9_-]+)", line, re.IGNORECASE)
            if cond_match:
                return cond_match.group(1), None

    return None, None


def _build_conditional_summary(source_text: str) -> tuple[str, str, str]:
    variable_name, target_name = _extract_rule_variables(source_text)
    if variable_name and target_name:
        summary = f"The legacy flow evaluates {variable_name} against the branch condition and assigns {target_name} accordingly; this is the most likely root cause behind the observed mismatch."
        root_cause = f"The source logic compares {variable_name} to a threshold or rule condition and writes the result to {target_name}. A modernized implementation must preserve that branch condition and output assignment exactly."
        suggested_fix = f"Review the comparison logic for {variable_name} and ensure both branches still assign {target_name} consistently."
        return summary, root_cause, suggested_fix
    if variable_name:
        summary = f"The legacy flow evaluates {variable_name} through a conditional branch; this is the most likely root cause behind the observed mismatch."
        root_cause = f"The source logic is driven by a conditional rule on {variable_name}. A modernized implementation must preserve the branching semantics exactly."
        suggested_fix = f"Review the conditional checks and output assignments tied to {variable_name} to keep the legacy behavior consistent."
        return summary, root_cause, suggested_fix
    if target_name:
        summary = f"The legacy flow applies a conditional assignment to {target_name}; this is the most likely root cause behind the observed mismatch."
        root_cause = f"The source logic updates {target_name} based on business conditions. A modernized implementation must preserve the branch order and assignment behavior exactly."
        suggested_fix = f"Review the branch conditions that feed into {target_name} and ensure the assignment is produced consistently."
        return summary, root_cause, suggested_fix

    summary = "The legacy flow applies a conditional business rule to transform input values into a status or decision output; this is the most likely cause behind the observed mismatch."
    root_cause = "The source logic uses branch-based data flow rather than a simple linear assignment. A modernized implementation must preserve the original rule and output mapping exactly."
    suggested_fix = "Inspect the conditional logic, branch ordering, and output assignments to confirm the rewritten version matches the original behavior."
    return summary, root_cause, suggested_fix


def explain_project(project_id: str, pipeline_state: PipelineState | None = None) -> ExplainResult:
    with SessionLocal() as session:
        project = session.query(ProjectRecord).filter_by(project_id=project_id).first()
        if project is None:
            raise ValueError("Project not found")

    source_text = "\n".join((project.file_contents or {}).values())
    reasoning_trace: list[str] = ["Tracing mismatch evidence back through the dependency graph and behavioral blueprint."]
    graph_context = {}
    blueprint_context = {}

    if pipeline_state is not None:
        analyze_result = pipeline_state.get_stage("analyze")
        understand_result = pipeline_state.get_stage("understand")
        verify_result = pipeline_state.get_stage("verify")
        if analyze_result:
            graph_context = analyze_result.output.get("analysis", {}).get("dependency_graph", {})
            reasoning_trace.append("Used analysis-stage dependency graph to contextualize the root cause.")
        if understand_result:
            blueprint_context = understand_result.output.get("blueprint", {})
            reasoning_trace.append("Used understand-stage blueprint to anchor the likely business rule involved.")
        if verify_result:
            reasoning_trace.append(f"Verification evidence indicates: {verify_result.output.get('mismatches', [])}")

    summary = "No automated explanation available; enable agentic LLM to receive structured explanations."
    root_cause = "Agentic explanations are disabled or no LLM is configured."
    suggested_fix = "Set ENABLE_AGENTIC=true and configure an LLM provider to obtain a detailed explanation."

    try:
        if os.environ.get("ENABLE_AGENTIC", "false").lower() in ("1", "true") and LLMService.is_configured():
            prompt_payload = {
                "summary": "Explain the likely root cause behind the observed mismatch.",
                "source_text": source_text[:4000],
                "dependency_graph": graph_context,
                "blueprint": blueprint_context,
            }
            messages = [
                {"role": "system", "content": "You are an assistant that explains legacy code behavior and maps likely root causes for mismatches."},
                {"role": "user", "content": json.dumps(prompt_payload, indent=2)},
            ]
            resp = LLMService.chat(messages, temperature=0.0)
            try:
                parsed = json.loads(resp)
                summary = parsed.get("summary", summary)
                root_cause = parsed.get("root_cause", root_cause)
                suggested_fix = parsed.get("suggested_fix", suggested_fix)
                reasoning_trace.append("LLM explanation generated using graph and blueprint context.")
            except Exception:
                summary = "No automated explanation available in structured form."
                root_cause = "Insufficient structured explanation from LLM."
                suggested_fix = "Enable agentic LLM explanations or inspect source files manually."
                reasoning_trace.append("LLM output was not valid JSON; the explanation remains conservative.")
    except Exception:
        summary = "Explanation generation failed."
        root_cause = "An internal error prevented generating an explanation."
        suggested_fix = "Check backend logs and LLM configuration."
        reasoning_trace.append("The explanation stage encountered an internal error.")

    if not summary or summary.startswith("No automated explanation") or summary.startswith("Explanation generation failed.") or summary.startswith("No automated explanation available in structured form."):
        summary, root_cause, suggested_fix = _build_conditional_summary(source_text)
        reasoning_trace.append("Used source-level conditional logic to build a rule-specific explanation fallback.")

    result = ExplainResult(project_id=project_id, summary=summary, root_cause=root_cause, suggested_fix=suggested_fix)
    if pipeline_state is not None:
        pipeline_state.set_stage(AgentResult(
            project_id=project_id,
            stage="explain",
            output={"project_id": project_id, "summary": summary, "root_cause": root_cause, "suggested_fix": suggested_fix, "graph_context": graph_context, "blueprint_context": blueprint_context},
            reasoning_trace=reasoning_trace,
            confidence=0.8 if root_cause and suggested_fix else 0.4,
            needs_human_review=not bool(root_cause and summary and suggested_fix),
            tool_calls=[{"name": "LLMService.chat", "args": {"graph": bool(graph_context), "blueprint": bool(blueprint_context)}}],
        ))
    return result


def explain_project_legacy(project_id: str) -> ExplainResult:
    result = explain_project(project_id)
    payload = result.output
    return ExplainResult(
        project_id=project_id,
        summary=payload.get("summary", ""),
        root_cause=payload.get("root_cause", ""),
        suggested_fix=payload.get("suggested_fix", ""),
    )


def analyze_verification(verification_result: dict, execution_metadata: dict | None = None, graph: object | None = None) -> dict:
    """Produce a human-friendly analysis from verification mismatches and execution metadata.

    Returns a dict with `summary`, `causes`, and `suggestions`.
    """
    mismatches = verification_result.get("mismatches") or []
    causes = []
    suggestions = []

    if not mismatches:
        return {"summary": "No mismatches", "causes": [], "suggestions": []}

    for m in mismatches:
        causes.append(f"Mismatch detected: {m}")
        suggestions.append("Check parsing, type conversions, and boundary conditions for the affected outputs.")

    # If structured diff present, map diff paths to graph modules
    structured = verification_result.get("structured_diff") or verification_result.get("structured_ops") or None
    path_module_map = {}
    if structured and isinstance(structured, list):
        # build a simple index of file/module names from graph
        module_index = []
        try:
            if isinstance(graph, dict):
                for n in graph.get("nodes", []):
                    nid = n.get("id")
                    attrs = n.get("attrs", {}) if isinstance(n, dict) else {}
                    module_index.append({"id": nid, "file": attrs.get("file") if isinstance(attrs, dict) else None})
            else:
                # unknown graph shape: ignore
                module_index = []
        except Exception:
            module_index = []

        for op in structured:
            p = op.get("path") or ""
            matched = []
            # heuristic: if a filename appears in path, associate it
            for mi in module_index:
                if not mi.get("id"):
                    continue
                if mi["id"] and mi["id"] in p:
                    matched.append(mi["id"])
                elif mi.get("file") and mi.get("file") in p:
                    matched.append(mi["id"])
            if not matched:
                # fallback: look for key tokens in path and match paragraph/file names
                token = p.split(".")[0].strip("[]") if p else ""
                for mi in module_index:
                    if token and token.lower() in (mi.get("id") or "").lower():
                        matched.append(mi["id"])
            path_module_map[p] = matched

    # turn path_module_map into causes/suggestions
    for path, modules in path_module_map.items():
        if modules:
            causes.append(f"Mismatch at '{path}' maps to modules: {', '.join(modules)}")
            suggestions.append(f"Review implementation and IO in modules: {', '.join(modules)} for '{path}'")
        else:
            causes.append(f"Mismatch at '{path}' could not be mapped to a specific module")
            suggestions.append(f"Investigate parsing and mapping for '{path}' across source files.")

    # If execution metadata contains artifacts or trace files, suggest inspecting them
    if execution_metadata:
        if execution_metadata.get("artifacts"):
            suggestions.append("Review execution artifacts and test output traces referenced in execution metadata.")

    # Use graph to prioritize modules if available (dict form)
    if graph is not None:
        try:
            if isinstance(graph, dict):
                high_risk = graph.get("high_risk_modules", [])
                if high_risk:
                    suggestions.append(f"High-risk modules: {', '.join(high_risk)}")
        except Exception:
            pass

    out = {"summary": f"{len(mismatches)} mismatches", "causes": causes, "suggestions": suggestions}
    if path_module_map:
        out["path_module_map"] = path_module_map
    # Optionally augment with LLM-produced explain text
    try:
        from app.core.config import get_settings
        from app.services.llm_service import LLMService
        settings = get_settings()
        if os.environ.get("ENABLE_AGENTIC", "false").lower() in ("1", "true") and LLMService.is_configured():
            agent = LLMService.explain(verification_result, graph)
            out["agent_explain"] = agent
    except Exception:
        pass

    return out
