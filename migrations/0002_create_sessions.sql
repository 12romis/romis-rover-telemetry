-- Збережені сесії ровера: один рядок = один валідний звіт rover.session.v1 (feature ingest, data-model.md).
-- depends: 0001_init
-- Ролі ingest і viewer створює скрипт Оператора ДО міграції (sad.md §7, крок 1).

CREATE TABLE IF NOT EXISTS sessions (
    mac                  text             NOT NULL,
    seq                  integer          NOT NULL,
    schema_version       integer          NOT NULL,
    received_at          timestamptz      NOT NULL,
    raw                  bytea            NOT NULL,
    payload              jsonb            NOT NULL,
    duration_ms          integer,
    end_reason           text,
    voltage_start_mv     integer,
    voltage_end_mv       integer,
    voltage_min_mv       integer,
    holds_count          integer,
    holds_total_ms       integer,
    holds_min_mm         integer,
    holds_min_sensor     text,
    holds_left_front     integer,
    holds_front          integer,
    holds_right_front    integer,
    holds_rear           integer,
    tof_control_off_ms   integer,
    moving_ms            integer,
    distance_cm          integer,
    speed_left_avg_rpm   double precision,
    speed_left_peak_rpm  double precision,
    speed_right_avg_rpm  double precision,
    speed_right_peak_rpm double precision,
    speed_imbalance_pct  double precision,
    encoders_left        boolean,
    encoders_right       boolean,
    fw_version           text,
    fw_git               text,
    fw_dirty             boolean,
    fw_idf               text,
    -- Єдине обмеження унікальності (feature ADR-0005): ON CONFLICT DO NOTHING без цілі
    -- трактує будь-який конфлікт як дубль, тож другого UNIQUE додавати не можна.
    PRIMARY KEY (mac, seq)
);

GRANT INSERT ON sessions TO ingest;
GRANT SELECT ON sessions TO viewer;
