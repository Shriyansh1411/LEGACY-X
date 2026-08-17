from dataclasses import dataclass, field


@dataclass
class AnalysisConfig:
    language_name: str = "COBOL-like"
    source_extensions: set[str] = field(default_factory=lambda: {".cbl", ".cob", ".cpy", ".cobol", ".pli"})
    doc_extensions: set[str] = field(default_factory=lambda: {".md", ".txt", ".rst", ".adoc"})
    log_extensions: set[str] = field(default_factory=lambda: {".log", ".out"})
    control_flow_signals: tuple[str, ...] = (
        "IF",
        "ELSE",
        "END-IF",
        "PERFORM",
        "MOVE",
        "EVALUATE",
        "WHEN",
        "READ",
        "WRITE",
    )
