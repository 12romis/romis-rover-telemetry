# romis-rover-telemetry

**EN** · Collects per-session JSON reports from an ESP32-S3 rover over MQTT, stores them in PostgreSQL and shows them on a read-only dashboard (FastAPI + ECharts).

**UA** · Збирає JSON-звіти сесій ровера на ESP32-S3 через MQTT, зберігає їх у PostgreSQL і показує на дашборді лише для читання (FastAPI + ECharts).

## Status / Стан

**EN** · Early stage: project skeleton is in place (package, tests, migrations, Docker, CI); ingest and dashboard features are not implemented yet (Spec-Driven Development, see `docs/roadmap.md`).

**UA** · Рання стадія: готовий скелет проєкту (пакет, тести, міграції, Docker, CI); ingest і дашборд ще не реалізовано (Spec-Driven Development, див. `docs/roadmap.md`).

## Documents / Документи

- `docs/contracts/events.md` — event contract `rover.session.v1` / контракт події
- `docs/constitution.md` — project rules / правила проєкту
- `docs/inputs/` — context, initial plan, owner decisions / контекст, план, рішення власника

## License / Ліцензія

MIT — see `LICENSE` / див. `LICENSE`.
