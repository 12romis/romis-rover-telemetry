# romis-rover-telemetry

**EN** · Collects per-session JSON reports from an ESP32-S3 rover over MQTT, stores them in PostgreSQL and shows them on a read-only dashboard (FastAPI + ECharts).

**UA** · Збирає JSON-звіти сесій ровера на ESP32-S3 через MQTT, зберігає їх у PostgreSQL і показує на дашборді лише для читання (FastAPI + ECharts).

## Status / Стан

**EN** · Early stage: specification in progress (Spec-Driven Development, see `docs/`). No runnable code yet.

**UA** · Рання стадія: триває специфікація (Spec-Driven Development, див. `docs/`). Робочого коду ще немає.

## Documents / Документи

- `docs/contracts/events.md` — event contract `rover.session.v1` / контракт події
- `docs/constitution.md` — project rules / правила проєкту
- `docs/inputs/` — context, initial plan, owner decisions / контекст, план, рішення власника

## License / Ліцензія

MIT — see `LICENSE` / див. `LICENSE`.
