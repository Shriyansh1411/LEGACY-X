import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./legacyx_test.db")

from fastapi.testclient import TestClient

from app.main import app
from app.db.database import SessionLocal
from app.models.project import ProjectRecord

client = TestClient(app)


def test_upload_legacy_project_creates_manifest() -> None:
    files = [
        ("files", ("source.cbl", b"       IDENTIFICATION DIVISION.\n       PROGRAM-ID. HELLO.\n       PROCEDURE DIVISION.\n           DISPLAY 'HELLO'.\n           STOP RUN.\n")),
        ("files", ("README.md", b"# Sample legacy app\n")),
        ("files", ("run.log", b"2024-01-01 00:00:00 START\n")),
    ]

    response = client.post("/api/projects/ingest", files=files)

    assert response.status_code == 200
    payload = response.json()
    assert payload["project_id"]
    assert payload["manifest"]["file_count"] == 3
    assert payload["manifest"]["source_files"] == ["source.cbl"]
    assert payload["manifest"]["docs"] == ["README.md"]
    assert payload["manifest"]["logs"] == ["run.log"]


def test_ingested_project_is_persisted() -> None:
    files = [
        ("files", ("source.cbl", b"       IDENTIFICATION DIVISION.\n       PROGRAM-ID. HELLO.\n")),
        ("files", ("README.md", b"# Hello\n")),
    ]

    response = client.post("/api/projects/ingest", files=files)
    payload = response.json()

    with SessionLocal() as session:
        stored = session.query(ProjectRecord).filter_by(project_id=payload["project_id"]).first()

    assert stored is not None
    assert stored.file_count == 2
    assert stored.source_files == ["source.cbl"]
    assert stored.docs == ["README.md"]


def test_project_analysis_extracts_legacy_rules() -> None:
    files = [
        ("files", ("source.cbl", b"       IDENTIFICATION DIVISION.\n       PROGRAM-ID. HELLO.\n       PROCEDURE DIVISION.\n           IF TOTAL > 100\n               MOVE 'HIGH' TO STATUS\n           END-IF.\n")),
        ("files", ("README.md", b"# Legacy program\n")),
    ]

    response = client.post("/api/projects/ingest", files=files)
    project_id = response.json()["project_id"]

    analysis_response = client.get(f"/api/projects/{project_id}/analyze")

    assert analysis_response.status_code == 200
    payload = analysis_response.json()
    assert payload["project_id"] == project_id
    assert payload["analysis"]["language"] == "COBOL-like"
    assert payload["analysis"]["source_files"] == ["source.cbl"]
    assert "IF" in payload["analysis"]["control_flow_signals"]
    assert "MOVE" in payload["analysis"]["control_flow_signals"]
    assert payload["analysis"]["business_rule_count"] >= 1


def test_understand_stage_creates_behavioral_blueprint() -> None:
    files = [
        ("files", ("source.cbl", b"       PROCEDURE DIVISION.\n           IF TOTAL > 100\n               MOVE 'HIGH' TO STATUS\n           END-IF.\n")),
    ]

    response = client.post("/api/projects/ingest", files=files)
    project_id = response.json()["project_id"]

    blueprint_response = client.get(f"/api/projects/{project_id}/understand")

    assert blueprint_response.status_code == 200
    payload = blueprint_response.json()
    assert payload["project_id"] == project_id
    assert payload["blueprint"]["rules"]
    assert any("TOTAL" in rule and "STATUS" in rule for rule in payload["blueprint"]["rules"])
    assert payload["blueprint"]["edge_cases"]


def test_generation_stage_creates_python_implementation() -> None:
    files = [
        ("files", ("source.cbl", b"       PROCEDURE DIVISION.\n           IF TOTAL > 100\n               MOVE 'HIGH' TO STATUS\n           ELSE\n               MOVE 'LOW' TO STATUS\n           END-IF.\n")),
    ]

    response = client.post("/api/projects/ingest", files=files)
    project_id = response.json()["project_id"]

    generate_response = client.post(f"/api/projects/{project_id}/generate")

    assert generate_response.status_code == 200
    payload = generate_response.json()
    assert payload["project_id"] == project_id
    assert payload["generated_code"]
    assert "def" in payload["generated_code"]
    assert "STATUS" in payload["generated_code"]
    assert payload["generated_tests"]
    assert "assert" in payload["generated_tests"]


def test_verification_stage_compares_outputs() -> None:
    files = [
        ("files", ("source.cbl", b"       PROCEDURE DIVISION.\n           IF TOTAL > 100\n               MOVE 'HIGH' TO STATUS\n           ELSE\n               MOVE 'LOW' TO STATUS\n           END-IF.\n")),
    ]

    response = client.post("/api/projects/ingest", files=files)
    project_id = response.json()["project_id"]

    client.post(f"/api/projects/{project_id}/generate")
    verify_response = client.get(f"/api/projects/{project_id}/verify")

    assert verify_response.status_code == 200
    payload = verify_response.json()
    assert payload["project_id"] == project_id
    assert payload["match"] is True
    assert payload["legacy_outputs"]
    assert payload["modern_outputs"]


def test_explain_stage_reports_root_cause() -> None:
    files = [
        ("files", ("source.cbl", b"       PROCEDURE DIVISION.\n           IF TOTAL > 100\n               MOVE 'HIGH' TO STATUS\n           ELSE\n               MOVE 'LOW' TO STATUS\n           END-IF.\n")),
    ]

    response = client.post("/api/projects/ingest", files=files)
    project_id = response.json()["project_id"]

    explain_response = client.get(f"/api/projects/{project_id}/explain")

    assert explain_response.status_code == 200
    payload = explain_response.json()
    assert payload["project_id"] == project_id
    assert payload["summary"]
    assert "TOTAL" in payload["summary"] or "STATUS" in payload["summary"]
    assert payload["root_cause"]
    assert payload["suggested_fix"]


def test_explain_stage_generates_generic_summary_for_non_status_rule() -> None:
    files = [
        ("files", ("source.cbl", b"       PROCEDURE DIVISION.\n           IF NET-SALES > 1000\n               MOVE 'APPROVE' TO REVIEW-STATUS\n           ELSE\n               MOVE 'HOLD' TO REVIEW-STATUS\n           END-IF.\n")),
    ]

    response = client.post("/api/projects/ingest", files=files)
    project_id = response.json()["project_id"]

    explain_response = client.get(f"/api/projects/{project_id}/explain")

    assert explain_response.status_code == 200
    payload = explain_response.json()
    assert payload["project_id"] == project_id
    assert payload["summary"]
    assert "NET-SALES" in payload["summary"] or "REVIEW-STATUS" in payload["summary"] or "legacy" in payload["summary"].lower()
    assert payload["root_cause"]
    assert payload["suggested_fix"]


def test_gemini_chat_uses_supported_generate_content_payload(monkeypatch) -> None:
    import app.services.llm_service as llm_service

    monkeypatch.setenv("LLM_PROVIDER", "GEMINI")
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-flash")
    monkeypatch.setenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "candidates": [{
                    "content": {
                        "parts": [{"text": "ok from gemini"}]
                    }
                }]
            }

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return FakeResponse()

    monkeypatch.setattr(llm_service.httpx, "post", fake_post)

    result = llm_service.LLMService.chat([{"role": "user", "content": "hello"}], temperature=0.4)

    assert result == "ok from gemini"
    assert captured["url"] == "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
    assert "contents" in captured["json"]
    assert "generationConfig" in captured["json"]


def test_azure_openai_is_primary_provider(monkeypatch) -> None:
    import app.services.llm_service as llm_service

    monkeypatch.setenv("LLM_PROVIDER", "AZURE_OPENAI")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "azure-test-key")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini")
    monkeypatch.setenv("AZURE_OPENAI_API_VERSION", "2024-02-01")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [{
                    "message": {"content": "ok from azure"}
                }]
            }

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return FakeResponse()

    monkeypatch.setattr(llm_service.httpx, "post", fake_post)

    result = llm_service.LLMService.chat([{"role": "user", "content": "hello"}], temperature=0.4)

    assert result == "ok from azure"
    assert captured["url"] == "https://example.openai.azure.com/openai/deployments/gpt-4o-mini/chat/completions?api-version=2024-02-01"
    assert captured["headers"]["api-key"] == "azure-test-key"


def test_generation_uses_openai_compatible_llm_when_configured(monkeypatch) -> None:
    files = [
        ("files", ("source.cbl", b"       PROCEDURE DIVISION.\n           IF TOTAL > 100\n               MOVE 'HIGH' TO STATUS\n           END-IF.\n")),
    ]

    response = client.post("/api/projects/ingest", files=files)
    project_id = response.json()["project_id"]

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.test/v1")

    class FakeResponse:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    def fake_post(url, headers=None, json=None, timeout=None):
        assert url == "https://example.test/v1/chat/completions"
        assert headers["Authorization"] == "Bearer test-key"
        assert "legacy source" in json["messages"][0]["content"].lower()
        return FakeResponse({
            "choices": [{
                "message": {
                    "content": "```python\ndef evaluate_status(total: int) -> str:\n    status = \"LOW\"\n    if total > 100:\n        status = \"HIGH\"\n    return status\n```\n\n```python\ndef test_example():\n    assert evaluate_status(101) == \"HIGH\"\n```"
                }
            }]
        })

    import app.services.generation_service as generation_service
    monkeypatch.setattr(generation_service.httpx, "post", fake_post)

    payload = generation_service.generate_project(project_id)

    assert payload.project_id == project_id
    assert "def evaluate_status" in payload.generated_code
    assert "assert evaluate_status(101)" in payload.generated_tests


def test_generate_project_uses_understand_blueprint(monkeypatch):
    from app.services import generation_service
    from app.db.database import SessionLocal
    from app.models.project import ProjectRecord

    project_id = "bp_gen_001"
    session = SessionLocal()
    session.query(ProjectRecord).filter_by(project_id=project_id).delete()
    session.commit()

    project = ProjectRecord(
        project_id=project_id,
        file_contents={
            "source.cbl": """       IDENTIFICATION DIVISION.\n       PROGRAM-ID. ORDER-STATUS.\n       DATA DIVISION.\n       WORKING-STORAGE SECTION.\n       01 WS-TOTAL PIC 9(5) VALUE 0.\n       01 WS-STATUS PIC X(10) VALUE 'LOW'.\n       PROCEDURE DIVISION.\n           IF WS-TOTAL > 100\n               MOVE 'HIGH' TO WS-STATUS\n           ELSE\n               MOVE 'LOW' TO WS-STATUS\n           END-IF.\n           STOP RUN.\n"""
        },
        source_files=["source.cbl"],
        language_hint="cobol",
        pipeline_state={
            "project_id": project_id,
            "stages": {
                "understand": {
                    "stage": "understand",
                    "output": {
                        "blueprint": {
                            "rules": [
                                "When the total exceeds 100, set the order status to HIGH and require a manual review flag."
                            ]
                        }
                    }
                }
            }
        },
    )
    session.add(project)
    session.commit()
    session.close()

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)

    payload = generation_service.generate_project(project_id)

    assert payload.project_id == project_id
    assert "manual review flag" in payload.generated_code.lower()
    assert "order status" in payload.generated_code.lower()
