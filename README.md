# romis-rover-telemetry

**EN** · Collects per-session JSON reports from an ESP32-S3 rover over MQTT, stores them in PostgreSQL and shows them on a read-only dashboard (FastAPI + ECharts).

**UA** · Збирає JSON-звіти сесій ровера на ESP32-S3 через MQTT, зберігає їх у PostgreSQL і показує на дашборді лише для читання (FastAPI + ECharts).

## Status / Стан

**EN** · Ingest and the public read-only dashboard (summary, session table, battery / obstacles / motion charts) are shipped; remaining charts and a daily `pg_dump` are planned (see `docs/roadmap.md`).

**UA** · Ingest і публічний дашборд лише для читання (підсумки, таблиця виїздів, графіки «Акумулятор» / «Перешкоди» / «Рух і борти») готові; решта графіків і щоденний `pg_dump` заплановані (див. `docs/roadmap.md`).

## What the data means / Що означають дані

**EN** · The rover (ESP32-S3, tracked drive, four ToF range sensors) sends one report per session: from arming to leaving motion (disarm or failsafe), only while disarmed, over MQTT/TLS (QoS 1). An obstacle hold is the rover stopping before an obstacle (threshold 190 mm) until it clears. The rover has no clock, so the dashboard shows the server's "received" time, an upper bound. Distance comes from wheel counters at a 44 mm wheel diameter, slip not counted. Battery is voltage only (no current or charge percent); the rover stops below 6.0 V. A missing value is "no data", not zero; a gap in `seq` is a lost session and is shown.

**UA** · Ровер (ESP32-S3, танковий привід, чотири далекоміри) надсилає один звіт за сесію: від озброєння до виходу з руху (роззброєння чи FAILSAFE), лише в DISARMED, через MQTT/TLS (QoS 1). Утримання — зупинка ровера перед перешкодою (поріг 190 мм), доки вона не зникне. Годинника в ровера немає, тому дашборд показує серверний час «отримано» — верхню межу. Пробіг рахується за лічильниками коліс при діаметрі 44 мм, проковзування не враховано. Акумулятор — лише напруга (струму й відсотка заряду немає); нижче 6.0 В ровер зупиняється. Відсутнє значення — «немає даних», а не нуль; пропуск у `seq` — втрачена сесія, її показують.

## Documents / Документи

- `docs/contracts/events.md` — event contract `rover.session.v1` / контракт події
- `docs/constitution.md` — project rules / правила проєкту
- `docs/inputs/` — context, initial plan, owner decisions / контекст, план, рішення власника

## License / Ліцензія

MIT — see `LICENSE` / див. `LICENSE`.
