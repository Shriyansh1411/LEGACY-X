from __future__ import annotations
import tempfile
import shutil
import subprocess
import pathlib
import sys
import json
import os
import uuid
import time
import hashlib
import resource
from typing import Dict, Any, List
from app.db.database import SessionLocal
from app.models.project import ProjectRecord
from app.services.llm_service import LLMService
from app.core.config import get_settings


class ExecuteService:
    @staticmethod
    def run_in_docker(
        workspace_files: Dict[str, str],
        image: str = "python:3.11-slim",
        command: str | None = None,
        timeout: int = 60,
        cpus: float = 0.5,
        memory: str = "512m",
    ) -> Dict[str, Any]:
        tmpdir = pathlib.Path(tempfile.mkdtemp(prefix="execsvc_"))
        docker_cmd = []
        try:
            for relpath, content in workspace_files.items():
                p = tmpdir / relpath
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(content, encoding="utf-8")

            cmd = (
                command
                or "python -m pip install -q pytest >/dev/null 2>&1 || true; pytest -q"
            )

            docker_cmd = [
                "docker",
                "run",
                "--rm",
                "--network",
                "none",
                "--cpus",
                str(cpus),
                "--memory",
                memory,
                "-v",
                f"{str(tmpdir)}:/workspace:rw",
                "-w",
                "/workspace",
                image,
                "bash",
                "-lc",
                cmd,
            ]

            proc = subprocess.run(
                docker_cmd, capture_output=True, text=True, timeout=timeout
            )

            return {
                "exit_code": proc.returncode,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
                "timed_out": False,
                "cmd": " ".join(docker_cmd),
            }
        except subprocess.TimeoutExpired as e:
            return {
                "exit_code": None,
                "stdout": e.stdout or "",
                "stderr": e.stderr or "",
                "timed_out": True,
                "cmd": " ".join(docker_cmd),
            }
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    @staticmethod
    def run_locally(
        workspace_files: Dict[str, str],
        python_executable: str | None = None,
        command: str | None = None,
        timeout: int = 60,
        project_id: str | None = None,
    ) -> Dict[str, Any]:
        """Run workspace files locally using the current Python interpreter.

        This assumes the host environment already has required test tooling (pytest).
        Prefer running the backend inside a virtualenv for isolation.
        """
        tmpdir = pathlib.Path(tempfile.mkdtemp(prefix="execsvc_"))
        try:
            for relpath, content in workspace_files.items():
                p = tmpdir / relpath
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(content, encoding="utf-8")

            py = python_executable or sys.executable
            cmd = command or f"{py} -m pytest -q"
            # resource limits applied to child process
            def _limit_resources():
                try:
                    # limit CPU seconds to timeout + 1
                    resource.setrlimit(resource.RLIMIT_CPU, (max(1, int(timeout) + 1), max(1, int(timeout) + 1)))
                    # limit file size to 100MB
                    resource.setrlimit(resource.RLIMIT_FSIZE, (100 * 1024 * 1024, 100 * 1024 * 1024))
                except Exception:
                    pass

            start = time.time()
            try:
                proc = subprocess.run(
                    cmd,
                    shell=True,
                    cwd=str(tmpdir),
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    env={**dict(), **{"PYTHONUNBUFFERED": "1"}},
                    preexec_fn=_limit_resources,
                )
                timed_out = False
            except subprocess.TimeoutExpired as e:
                proc = e
                timed_out = True

            duration = time.time() - start

            metadata = {
                "exit_code": getattr(proc, "returncode", None),
                "stdout": getattr(proc, "stdout", "") or "",
                "stderr": getattr(proc, "stderr", "") or "",
                "cmd": cmd,
                "timed_out": timed_out,
                "duration_seconds": duration,
                "artifacts": [],
            }

            # Collect produced artifact files from tmpdir
            artifacts_dir = pathlib.Path(os.path.join(os.getcwd(), "backend", "tmp_artifacts"))
            artifacts_dir.mkdir(parents=True, exist_ok=True)
            meta_name = f"execution_metadata_{project_id or uuid.uuid4().hex}.json"
            meta_path = artifacts_dir / meta_name

            # Copy artifact files (non-hidden) into artifacts dir under a subfolder
            artifacts_subdir = artifacts_dir / f"artifacts_{meta_path.stem}"
            artifacts_subdir.mkdir(parents=True, exist_ok=True)

            copied: List[str] = []
            for f in tmpdir.rglob("*"):
                if f.is_file():
                    rel = f.relative_to(tmpdir)
                    dest = artifacts_subdir / rel
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(f, dest)
                    # compute sha256 for artifact
                    with dest.open("rb") as fh:
                        h = hashlib.sha256(fh.read()).hexdigest()
                    copied.append({"path": str(dest), "relpath": str(rel), "size": dest.stat().st_size, "sha256": h})

            metadata["artifacts"] = copied

            # persist metadata
            meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
            # include metadata path as first artifact
            metadata["artifacts"].insert(0, {"path": str(meta_path), "relpath": meta_path.name, "size": meta_path.stat().st_size})

            # Optionally run agentic post-run analysis via LLM when enabled
            try:
                settings = get_settings()
                if os.environ.get("ENABLE_AGENTIC", "false").lower() in ("1", "true") and LLMService.is_configured():
                    agent_out = LLMService.summarize_execution(metadata)
                    metadata["agent_summary"] = agent_out
            except Exception:
                pass

            return {
                "exit_code": metadata.get("exit_code"),
                "stdout": metadata.get("stdout"),
                "stderr": metadata.get("stderr"),
                "timed_out": metadata.get("timed_out"),
                "cmd": cmd,
                "execution_metadata": metadata,
            }
        except subprocess.TimeoutExpired as e:
            return {
                "exit_code": None,
                "stdout": getattr(e, "stdout", "") or "",
                "stderr": getattr(e, "stderr", "") or "",
                "timed_out": True,
                "cmd": command or "",
            }
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    @staticmethod
    def run(workspace_files: Dict[str, str], use_docker: bool = False, **kwargs) -> Dict[str, Any]:
        if use_docker:
            return ExecuteService.run_in_docker(workspace_files, **kwargs)
        return ExecuteService.run_locally(workspace_files, **kwargs)
