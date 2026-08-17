       PROCEDURE DIVISION.
           IF TOTAL > 100
               MOVE 'HIGH' TO STATUS
           ELSE
               MOVE 'LOW' TO STATUS
           END-IF.
