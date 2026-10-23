-- Облік втрат: пропуски в seq для кожного mac від найменшого збереженого номера (feature ADR-0004).
-- depends: <PREV>
-- Промоція (implement): <PREV> = фактична міграція 02_create_rejected після присвоєння номера.

CREATE OR REPLACE VIEW session_gaps AS
SELECT bounds.mac,
       series.seq
FROM (
    SELECT mac, min(seq) AS first_seq, max(seq) AS last_seq
    FROM sessions
    GROUP BY mac
) AS bounds
CROSS JOIN LATERAL generate_series(bounds.first_seq::bigint, bounds.last_seq::bigint) AS series(seq)
WHERE NOT EXISTS (
    SELECT 1
    FROM sessions AS stored
    WHERE stored.mac = bounds.mac
      AND stored.seq = series.seq
);

GRANT SELECT ON session_gaps TO viewer;
