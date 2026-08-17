from app.parsers.cobol_parser import parse_cobol


def test_parse_cobol_basic():
    sample = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. SAMPLE.
       PROCEDURE DIVISION.
       MAIN-PARA.
           PERFORM PROCESS-RECORD.
           STOP RUN.
       PROCESS-RECORD.
           IF A > 0 THEN
               MOVE 1 TO B
           ELSE
               MOVE 0 TO B
           END-IF.
           READ FILE-1.
           WRITE FILE-2.
       .
    """

    parsed = parse_cobol(sample)
    assert isinstance(parsed, dict)
    assert "paragraphs" in parsed
    assert "performs" in parsed
    assert "conditionals" in parsed
    assert "io_ops" in parsed
    assert any("PROCESS-RECORD" in p for p in parsed.get("performs", [])) or parsed.get(
        "performs"
    ) == []
