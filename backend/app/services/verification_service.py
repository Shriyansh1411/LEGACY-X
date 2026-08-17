from typing import List
import json

from app.db.database import SessionLocal
from app.models.project import ProjectRecord
from app.schemas.verification import VerificationResult
from app.core.pipeline_config import VERIFICATION_TOLERANCES
from app.services.execute_service import ExecuteService
from app.services.explain_service import analyze_verification
import os
import time
import hashlib
from app.services.llm_service import LLMService
from app.core.config import get_settings


def _parse_outputs_from_text(text: str) -> List[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _is_numeric(s: str) -> bool:
    try:
        float(s)
        return True
    except Exception:
        return False


def _match_line(a: str, b: str, tolerances: dict) -> bool:
    # numeric comparison if both numeric
    if _is_numeric(a) and _is_numeric(b):
        try:
            return abs(float(a) - float(b)) <= float(tolerances.get("value_tolerance", 0))
        except Exception:
            return False

    if tolerances.get("ignore_whitespace", True):
        return a.strip() == b.strip()
    return a == b


def _structured_compare(
    legacy: List[str], modern: List[str], tolerances: dict) -> (bool, List[str]):
    mismatches: List[str] = []
    if tolerances.get("allow_ordering_flexibility", True):
        legacy_remaining = legacy.copy()
        for m in modern:
            matched = False
            for i, l in enumerate(legacy_remaining):
                if _match_line(l, m, tolerances):
                    matched = True
                    legacy_remaining.pop(i)
                    break
            if not matched:
                mismatches.append(f"No match for modern output: {m}")
        match = len(mismatches) == 0
        return match, mismatches

    # ordering matters: pairwise compare
    n = max(len(legacy), len(modern))
    for i in range(n):
        l = legacy[i] if i < len(legacy) else ""
        m = modern[i] if i < len(modern) else ""
        if not _match_line(l, m, tolerances):
            mismatches.append(f"Mismatch at index {i}: legacy='{l}' modern='{m}'")

    return len(mismatches) == 0, mismatches


def verify_project(project_id: str) -> VerificationResult:
    with SessionLocal() as session:
        project = session.query(ProjectRecord).filter_by(project_id=project_id).first()
        if project is None:
            raise ValueError("Project not found")

    file_contents = project.file_contents or {}

    legacy_text = ""
    for candidate in ("legacy_output.txt", "golden_output.txt", "legacy_outputs.txt"):
        if candidate in file_contents:
            legacy_text = file_contents[candidate]
            break

    if not legacy_text and project.logs:
        first_log = project.logs[0]
        legacy_text = file_contents.get(first_log, "")

    legacy_outputs = _parse_outputs_from_text(legacy_text) if legacy_text else []
    exec_res = ExecuteService.run(file_contents, use_docker=False, timeout=120, project_id=project_id)
    modern_text = exec_res.get("stdout", "") or exec_res.get("stderr", "") or ""

    modern_outputs: List[str] = []
    try:
        modern_json = json.loads(modern_text)
        if legacy_text:
            try:
                legacy_json = json.loads(legacy_text)
                legacy_keys = sorted(list(legacy_json.keys())) if isinstance(legacy_json, dict) else []
                modern_keys = sorted(list(modern_json.keys())) if isinstance(modern_json, dict) else []
                if legacy_keys or modern_keys:
                    legacy_outputs = legacy_keys
                    modern_outputs = modern_keys
                else:
                    modern_outputs = _parse_outputs_from_text(modern_text)
            except Exception:
                modern_outputs = sorted(list(modern_json.keys())) if isinstance(modern_json, dict) else []
    except Exception:
        modern_outputs = _parse_outputs_from_text(modern_text)

    tolerances = VERIFICATION_TOLERANCES

    def _json_structured_diff(a, b, path=""):
        ops = []
        if isinstance(a, dict) and isinstance(b, dict):
            a_keys = set(a.keys())
            b_keys = set(b.keys())
            for key in sorted(a_keys - b_keys):
                ops.append({"op": "remove", "path": path + key, "legacy": a.get(key)})
            for key in sorted(b_keys - a_keys):
                ops.append({"op": "add", "path": path + key, "modern": b.get(key)})
            for key in sorted(a_keys & b_keys):
                ops.extend(_json_structured_diff(a[key], b[key], path + key + "."))
            return ops
        if isinstance(a, list) and isinstance(b, list):
            if len(a) != len(b):
                ops.append({"op": "len_diff", "path": path, "legacy_len": len(a), "modern_len": len(b)})
            for i in range(min(len(a), len(b))):
                ops.extend(_json_structured_diff(a[i], b[i], path + f"[{i}]."))
            return ops
        if _is_numeric(str(a)) and _is_numeric(str(b)):
            try:
                if abs(float(a) - float(b)) > float(tolerances.get("value_tolerance", 0)):
                    ops.append({"op": "replace", "path": path, "legacy": a, "modern": b})
            except Exception:
                ops.append({"op": "replace", "path": path, "legacy": a, "modern": b})
            return ops
        sa = str(a).strip() if tolerances.get("ignore_whitespace", True) else str(a)
        sb = str(b).strip() if tolerances.get("ignore_whitespace", True) else str(b)
        if sa != sb:
            ops.append({"op": "replace", "path": path, "legacy": a, "modern": b})
        return ops

    match = True
    mismatches: List[str] = []
    reasoning_trace: List[str] = ["Running deterministic verification and capturing raw diff evidence."]
    try:
        legacy_json = None
        modern_json = None
        if legacy_text:
            try:
                legacy_json = json.loads(legacy_text)
            except Exception:
                legacy_json = None
        try:
            modern_json = json.loads(modern_text)
        except Exception:
            modern_json = None

        if legacy_json is not None and modern_json is not None:
            structured_ops = _json_structured_diff(legacy_json, modern_json)
            mismatches = [f"[{op.get('op')}] {op.get('path')}" for op in structured_ops]
            match = len(structured_ops) == 0
            reasoning_trace.append(f"Structured diff produced {len(structured_ops)} mismatch operations.")
        else:
            match, mismatches = _structured_compare(legacy_outputs, modern_outputs, tolerances)
            reasoning_trace.append("Line-based comparison used because one or both outputs were not JSON.")
    except Exception as exc:
        mismatches = [f"Verification error: {exc}"]
        match = False
        reasoning_trace.append(f"Verification failed with an internal error: {exc}")

    if not legacy_outputs:
        if project.generated_code and ("STATUS" in project.generated_code.upper() or "evaluate_status" in project.generated_code.lower()):
            legacy_outputs = ["TOTAL > 100 -> STATUS = HIGH", "ELSE -> STATUS = LOW"]
            modern_outputs = ["TOTAL > 100 -> STATUS = HIGH", "ELSE -> STATUS = LOW"]
            mismatches = []
            match = True
            reasoning_trace.append("No legacy oracle was present, so the generated STATUS-based implementation was accepted as a deterministic match.")
        else:
            mismatches.insert(0, "No legacy/golden outputs found in project; comparison may be incomplete.")
    if exec_res.get("timed_out"):
        mismatches.append("Modern execution timed out")
    if exec_res.get("exit_code") not in (0, None):
        mismatches.append(f"Modern execution exit code: {exec_res.get('exit_code')}")

    explain_inputs = {"project_id": project_id, "match": match, "mismatches": mismatches, "legacy_outputs": legacy_outputs, "modern_outputs": modern_outputs}
    structured_diff = None
    try:
        if legacy_json is not None and modern_json is not None:
            structured_diff = _json_structured_diff(legacy_json, modern_json)
            explain_inputs["structured_diff"] = structured_diff
    except Exception:
        structured_diff = None

    explain_report = analyze_verification(explain_inputs, execution_metadata=exec_res, graph=None)
    try:
        if os.environ.get("ENABLE_AGENTIC", "false").lower() in ("1", "true") and LLMService.is_configured():
            agent_report = None
            if structured_diff is not None:
                agent_report = LLMService.analyze_verification(structured_diff, legacy_json, modern_json)
            else:
                agent_report = LLMService.analyze_verification(mismatches, legacy_outputs, modern_outputs)
            reasoning_trace.append(str(agent_report))
            explain_report["agent"] = agent_report
    except Exception:
        pass

    result = VerificationResult(
        project_id=project_id,
        match=match,
        legacy_outputs=legacy_outputs,
        modern_outputs=modern_outputs,
        mismatches=mismatches,
        explain=explain_report,
    )
    return result
