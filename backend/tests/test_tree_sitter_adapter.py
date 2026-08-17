import pytest

from app.parsers import tree_sitter_adapter as tsa


def test_tree_sitter_adapter_not_configured():
    # If Tree-sitter is not configured, available() should be False and parse should raise
    if not tsa.available():
        with pytest.raises(RuntimeError):
            tsa.parse_with_tree_sitter("IDENTIFICATION DIVISION.")
    else:
        # If available, ensure it returns a dict with 'root'
        res = tsa.parse_with_tree_sitter("IDENTIFICATION DIVISION.")
        assert isinstance(res, dict)
        assert "root" in res
