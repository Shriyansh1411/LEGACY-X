"""
Tests for LEGACY-X Feature 1: Ingest

Covers:
- POST /projects/ingest accepts a zip upload and returns a project_id + manifest
- Uploaded files are extracted into the project's workspace
- File type detection (code / docs / logs) is correct
- Manifest is persisted and retrievable
- Basic error handling (empty upload, non-zip file)

Assumptions (adjust if your app structure differs):
- FastAPI app is importable as `app` from `main.py`
- Endpoint: POST /projects/ingest  (multipart/form-data, field name "file")
- Response JSON includes: {"project_id": str, "manifest": {...}}
- Manifest entries look like: {"filename": str, "type": "code"|"docs"|"logs", "size": int}
- A GET /projects/{project_id}/manifest endpoint exists to fetch the stored manifest

Run with: pytest test_ingest.py -v
"""

import io
import zipfile

import pytest
from fastapi.testclient import TestClient

from main import app  # adjust import path to match your project layout


client = TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_zip(files: dict[str, bytes]) -> io.BytesIO:
    """Build an in-memory zip file from {filename: content} pairs."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w") as zf:
        for filename, content in files.items():
            zf.writestr(filename, content)
    buf.seek(0)
    return buf


@pytest.fixture
def sample_project_zip():
    """A minimal legacy project: one COBOL file, one doc, one log."""
    files = {
        "billing.cbl": (
            b"IF ACCT-BAL > 10000\n"
            b"  COMPUTE FEE = AMT * 0.015\n"
            b"ELSE\n"
            b"  MOVE 0 TO FEE\n"
        ),
        "README.md": b"# Billing module\nComputes account fees.\n",
        "run.log": b"2026-08-01 12:00:00 INFO fee computed: 150.00\n",
    }
    return make_zip(files)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestIngestEndpoint:
    def test_ingest_accepts_zip_and_returns_project_id(self, sample_project_zip):
        response = client.post(
            "/projects/ingest",
            files={"file": ("project.zip", sample_project_zip, "application/zip")},
        )

        assert response.status_code == 200
        data = response.json()
        assert "project_id" in data
        assert isinstance(data["project_id"], str) and data["project_id"]

    def test_ingest_returns_manifest_with_all_files(self, sample_project_zip):
        response = client.post(
            "/projects/ingest",
            files={"file": ("project.zip", sample_project_zip, "application/zip")},
        )

        manifest = response.json()["manifest"]
        filenames = {entry["filename"] for entry in manifest["files"]}

        assert filenames == {"billing.cbl", "README.md", "run.log"}

    def test_ingest_classifies_file_types_correctly(self, sample_project_zip):
        response = client.post(
            "/projects/ingest",
            files={"file": ("project.zip", sample_project_zip, "application/zip")},
        )

        manifest = response.json()["manifest"]
        by_name = {entry["filename"]: entry["type"] for entry in manifest["files"]}

        assert by_name["billing.cbl"] == "code"
        assert by_name["README.md"] == "docs"
        assert by_name["run.log"] == "logs"

    def test_ingest_persists_manifest_retrievable_by_project_id(self, sample_project_zip):
        ingest_response = client.post(
            "/projects/ingest",
            files={"file": ("project.zip", sample_project_zip, "application/zip")},
        )
        project_id = ingest_response.json()["project_id"]

        fetch_response = client.get(f"/projects/{project_id}/manifest")

        assert fetch_response.status_code == 200
        assert fetch_response.json()["files"]

    def test_ingest_records_file_sizes(self, sample_project_zip):
        response = client.post(
            "/projects/ingest",
            files={"file": ("project.zip", sample_project_zip, "application/zip")},
        )

        manifest = response.json()["manifest"]
        for entry in manifest["files"]:
            assert entry["size"] > 0


# ---------------------------------------------------------------------------
# Edge cases / error handling
# ---------------------------------------------------------------------------

class TestIngestErrorHandling:
    def test_ingest_rejects_empty_zip(self):
        empty_zip = make_zip({})

        response = client.post(
            "/projects/ingest",
            files={"file": ("empty.zip", empty_zip, "application/zip")},
        )

        assert response.status_code == 400

    def test_ingest_rejects_non_zip_file(self):
        bad_file = io.BytesIO(b"this is not a zip archive")

        response = client.post(
            "/projects/ingest",
            files={"file": ("notes.txt", bad_file, "text/plain")},
        )

        assert response.status_code == 400

    def test_ingest_rejects_missing_file_field(self):
        response = client.post("/projects/ingest")

        assert response.status_code in (400, 422)

    def test_ingest_handles_unrecognized_extensions_gracefully(self):
        files = {"data.xyz": b"some binary-ish content"}
        zip_buf = make_zip(files)

        response = client.post(
            "/projects/ingest",
            files={"file": ("project.zip", zip_buf, "application/zip")},
        )

        assert response.status_code == 200
        manifest = response.json()["manifest"]
        entry = manifest["files"][0]
        # Should default to something sane rather than crash
        assert entry["type"] in {"code", "docs", "logs", "unknown"}


# ---------------------------------------------------------------------------
# Isolation between projects
# ---------------------------------------------------------------------------

class TestIngestIsolation:
    def test_two_ingests_get_different_project_ids(self, sample_project_zip):
        zip1 = sample_project_zip
        zip2 = make_zip({"other.cbl": b"MOVE 0 TO FEE\n"})

        r1 = client.post(
            "/projects/ingest",
            files={"file": ("project1.zip", zip1, "application/zip")},
        )
        r2 = client.post(
            "/projects/ingest",
            files={"file": ("project2.zip", zip2, "application/zip")},
        )

        assert r1.json()["project_id"] != r2.json()["project_id"]
