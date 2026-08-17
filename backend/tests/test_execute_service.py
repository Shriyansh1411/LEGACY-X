from app.services.execute_service import ExecuteService


def test_run_locally_simple():
    files = {"test_sample.py": "def test_true():\n    assert 1 == 1\n"}
    res = ExecuteService.run_locally(files, timeout=30)
    assert isinstance(res, dict)
    assert res.get("timed_out") is False
    assert res.get("exit_code") == 0
