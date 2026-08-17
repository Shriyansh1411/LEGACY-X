"""Tree-sitter adapter scaffold for COBOL.

This adapter attempts to use `tree_sitter` and a compiled COBOL language
shared library if available. It provides `available()` and `parse_with_tree_sitter()`
so other pipeline stages can optionally use a real AST when configured.

To enable Tree-sitter parsing locally:
  1. Install the Python binding: `pip install tree_sitter`
  2. Compile a COBOL grammar into a shared lib and set `TREE_SITTER_LIB`
     environment variable pointing to the `.so`/`.dylib` file.

If Tree-sitter is not configured, `available()` returns False and
`parse_with_tree_sitter()` raises a RuntimeError.
"""
from __future__ import annotations
import os
from typing import Dict, Any

try:
    from tree_sitter import Language, Parser  # type: ignore
    _HAS_TS = True
except Exception:
    _HAS_TS = False

_LIB_PATH = os.environ.get("TREE_SITTER_LIB", "")
_LANG_NAME = os.environ.get("TREE_SITTER_LANG", "cobol")


def available() -> bool:
    return _HAS_TS and bool(_LIB_PATH) and os.path.exists(_LIB_PATH)


def parse_with_tree_sitter(text: str) -> Dict[str, Any]:
    if not available():
        raise RuntimeError(
            "Tree-sitter not available or language library not configured. "
            "Set TREE_SITTER_LIB to a compiled grammar shared library and install `tree_sitter`."
        )

    lang = Language(_LIB_PATH, _LANG_NAME)
    parser = Parser()
    parser.set_language(lang)
    tree = parser.parse(bytes(text, "utf8"))

    # Walk the tree and collect node types and spans (minimal representation)
    root = tree.root_node
    def walk(node):
        node_repr = {"type": node.type, "start_byte": node.start_byte, "end_byte": node.end_byte}
        children = [walk(c) for c in node.children]
        if children:
            node_repr["children"] = children
        return node_repr

    return {"root": walk(root)}
