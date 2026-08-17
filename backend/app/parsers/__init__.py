"""Parser adapters for legacy languages.

Start with a lightweight COBOL parser adapter. These parsers return a
normalized "AST-like" dict that the rest of the pipeline can consume.
"""

from .cobol_parser import CobolParser  # noqa: F401
