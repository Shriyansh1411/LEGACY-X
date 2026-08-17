from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.db.database import SessionLocal
from app.models.project import ProjectRecord
from app.schemas.agent import AgentResult, PipelineState
from app.schemas.project import ProjectIngestResponse, ProjectManifest
from app.services.llm_service import LLMService

SOURCE_EXTENSIONS = {".cbl", ".cob", ".cpy", ".cobol", ".pli"}
DOC_EXTENSIONS = {".md", ".txt", ".rst", ".adoc"}
LOG_EXTENSIONS = {".log", ".out"}


def classify_file(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix in SOURCE_EXTENSIONS:
        return "source"
    if suffix in DOC_EXTENSIONS:
        return "docs"
    if suffix in LOG_EXTENSIONS:
        return "logs"
    return "other"


def detect_language_hint(filenames: list[str]) -> str:
    # simple heuristic: if any COBOL-like extension present, prefer COBOL
    for fn in filenames:
        if Path(fn).suffix.lower() in SOURCE_EXTENSIONS:
            return "cobol"
    return "unknown"


def _llm_classify_file(filename: str, content: str) -> str:
    if not (filename and content):
        return "other"
    try:
        import os

        if os.environ.get("ENABLE_AGENTIC", "false").lower() not in ("1", "true") or not LLMService.is_configured():
            return "other"
    except Exception:
        return "other"

    try:
        messages = [
            {"role": "system", "content": "Classify the file as one of: source, docs, logs, other. Be explicit when uncertain."},
            {"role": "user", "content": f"Filename: {filename}\nSample content:\n{content[:1200]}"},
        ]
        response = LLMService.chat(messages, temperature=0.0)
        cleaned = (response or "").strip().lower()
        for value in ("source", "docs", "logs", "other"):
            if value in cleaned:
                return value
    except Exception:
        return "other"
    return "other"


def ingest_project(files: list[UploadFile], project_id: str | None = None, pipeline_state: PipelineState | None = None) -> AgentResult:
    if not files:
        raise ValueError("No files provided")

    valid_files = [f for f in files if getattr(f, "filename", None)]
    project_id = project_id or uuid4().hex
    source_files: list[str] = []
    docs: list[str] = []
    logs: list[str] = []
    file_contents: dict[str, str] = {}
    reasoning_trace: list[str] = []
    tool_calls: list[dict] = []
    uncertain: bool = False

    for uploaded_file in valid_files:
        filename = uploaded_file.filename or ""
        content = uploaded_file.file.read() if hasattr(uploaded_file.file, "read") else b""
        text = content.decode("utf-8", errors="replace")
        file_contents[filename] = text

        kind = classify_file(filename)
        tool_calls.append({"name": "classify_file", "args": {"filename": filename, "classification": kind}})
        reasoning_trace.append(f"File '{filename}' classified as '{kind}' by extension heuristic.")

        if kind == "other":
            llm_kind = _llm_classify_file(filename, text)
            tool_calls.append({"name": "llm_classify_file", "args": {"filename": filename, "classification": llm_kind}})
            if llm_kind != "other":
                kind = llm_kind
                reasoning_trace.append(f"LLM fallback reclassified '{filename}' to '{kind}' because extension was ambiguous.")
            else:
                uncertain = True
                reasoning_trace.append(f"'{filename}' remains ambiguous and requires human review.")

        if kind == "source":
            source_files.append(filename)
        elif kind == "docs":
            docs.append(filename)
        elif kind == "logs":
            logs.append(filename)

    language_hint = detect_language_hint(source_files)
    manifest = ProjectManifest(
        file_count=len(valid_files),
        source_files=sorted(source_files),
        docs=sorted(docs),
        logs=sorted(logs),
        language_hint=language_hint,
    )

    with SessionLocal() as session:
        project_record = session.query(ProjectRecord).filter_by(project_id=project_id).first()
        if project_record is None:
            project_record = ProjectRecord(project_id=project_id)
        project_record.file_count = manifest.file_count
        project_record.source_files = manifest.source_files
        project_record.docs = manifest.docs
        project_record.logs = manifest.logs
        project_record.language_hint = manifest.language_hint
        project_record.file_contents = file_contents
        if pipeline_state is not None:
            project_record.pipeline_state = pipeline_state.model_dump(mode="json")
        session.add(project_record)
        session.commit()

    confidence = 0.95 if not uncertain else 0.55
    needs_human_review = uncertain
    result = AgentResult(
        project_id=project_id,
        stage="ingest",
        output={"project_id": project_id, "manifest": manifest.model_dump()},
        reasoning_trace=reasoning_trace,
        confidence=confidence,
        needs_human_review=needs_human_review,
        tool_calls=tool_calls,
    )
    if pipeline_state is not None:
        pipeline_state.set_stage(result)

    return result


def ingest_project_legacy(files: list[UploadFile]) -> ProjectIngestResponse:
    result = ingest_project(files)
    payload = result.output.get("manifest", {})
    return ProjectIngestResponse(project_id=result.output["project_id"], manifest=ProjectManifest(**payload))
