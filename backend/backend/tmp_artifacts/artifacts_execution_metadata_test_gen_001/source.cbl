       IDENTIFICATION DIVISION.
       PROGRAM-ID. TEST-PROGRAM.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-TOTAL      PIC 9(5) VALUE 0.
       01  WS-STATUS     PIC X(10) VALUE "LOW".
       PROCEDURE DIVISION.
           EVALUATE TRUE
               WHEN WS-TOTAL > 100
                   MOVE "HIGH" TO WS-STATUS
               WHEN OTHER
                   MOVE "LOW" TO WS-STATUS
           END-EVALUATE.
           DISPLAY WS-STATUS.
           STOP RUN.