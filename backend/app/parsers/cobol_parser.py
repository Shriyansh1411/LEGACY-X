"""Very small COBOL parser adapter.

This is a lightweight, heuristic parser intended as a scaffolding step.
It extracts paragraphs, perform calls, IF/ELSE blocks and simple MOVE/READ/WRITE
statements into a normalized structure usable by analysis and understanding stages.
"""
from __future__ import annotations
import re
from typing import Dict, List, Any


class CobolParser:
    def __init__(self, text: str) -> None:
        self.text = text

    def parse(self) -> Dict[str, Any]:
        lines = [ln.rstrip() for ln in self.text.splitlines()]
        paragraphs = self._extract_paragraphs(lines)
        performs = self._extract_performs(lines)
        conditionals = self._extract_conditionals("\n".join(lines))
        io_ops = self._extract_io(lines)

        return {
            "paragraphs": paragraphs,
            "performs": performs,
            "conditionals": conditionals,
            "io_ops": io_ops,
        }

    def _extract_paragraphs(self, lines: List[str]) -> List[str]:
        paras: List[str] = []
        for ln in lines:
            if re.match(r"^[A-Z0-9\-]+\.$", ln.strip()):
                paras.append(ln.strip().rstrip("."))
        return paras

    def _extract_performs(self, lines: List[str]) -> List[str]:
        performs: List[str] = []
        pattern = re.compile(r"\bPERFORM\s+([A-Z0-9\-]+)\b", re.IGNORECASE)
        for ln in lines:
            m = pattern.search(ln)
            if m:
                performs.append(m.group(1))
        return performs

    def _extract_conditionals(self, text: str) -> List[Dict[str, str]]:
        conds: List[Dict[str, str]] = []
        pattern = re.compile(
            r"IF\s+(.*?)(?:\s+THEN|\s*(?:ELSE|END-IF|\.|$))(.*?)(?:ELSE(.*?))?(?:END-IF|\.|$)",
            re.IGNORECASE | re.S,
        )
        for m in pattern.finditer(text):
            cond = m.group(1).strip()
            then_part = (m.group(2) or "").strip()
            else_part = (m.group(3) or "").strip()
            if cond:
                conds.append({"cond": cond, "then": then_part, "else": else_part})
        return conds

    def _extract_io(self, lines: List[str]) -> List[str]:
        ops: List[str] = []
        for ln in lines:
            if re.search(r"\b(READ|WRITE|OPEN|CLOSE)\b", ln, re.IGNORECASE):
                ops.append(ln.strip())
        return ops


def parse_cobol(text: str) -> Dict[str, Any]:
    return CobolParser(text).parse()
