-- Відхилені повідомлення: усе, що доставлено, але не стало сесією (feature ingest, data-model.md).
-- depends: <PREV>
-- Промоція (implement): <PREV> = фактична міграція 01_create_sessions після присвоєння номера.

CREATE TABLE IF NOT EXISTS rejected (
    id            bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    topic         text        NOT NULL,
    reason_code   text        NOT NULL,
    reason_text   text        NOT NULL,
    raw           bytea       NOT NULL,
    raw_size      integer     NOT NULL,
    raw_truncated boolean     NOT NULL,
    received_at   timestamptz NOT NULL
);

GRANT INSERT ON rejected TO ingest;
GRANT SELECT ON rejected TO viewer;
