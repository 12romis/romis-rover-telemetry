# romis-rover-telemetry

Збір звітів сесій ровера з MQTT у Postgres і дашборд для їх аналізу. Майбутній публічний репозиторій на GitHub.

@docs/constitution.md

## Джерела

- Контракт події: `docs/contracts/events.md` (канонічний, копія з репозиторію ровера).
- Контекст для споживача: `docs/inputs/CONTEXT.md`.
- Початковий план: `docs/inputs/initial-plan.md`.
- Відповіді власника на відкриті питання: `docs/inputs/owner-decisions.md`.

## Порядок роботи (SDD)

- Плагін `sdd@sdd` (genkovich/sdd), налаштування — `.claude/sdd.local.md` (не в git).
- Одна фіча = один слаг у `docs/features/<slug>/`. Між стадіями — `/clear`.
- Старт: `/sdd:interview` → `/sdd:survey` (greenfield) → `/sdd:roadmap` → `/sdd:scaffold`.
- Конвеєр фічі: `/sdd:specify` → `/sdd:clarify` → `/sdd:classify-size` → `/sdd:design` → `/sdd:sequences` → `/sdd:data-model` → `/sdd:api` → `/sdd:plan-tests` → `/sdd:tasks` → `/sdd:implement` → `/sdd:review` → `/sdd:ship`.
- Для дашборду додатково: `/sdd:design-system` (раз на репозиторій), `/sdd:ux-flows`, `/sdd:screens`.
- Відкриті питання — у spec §8 з власником і терміном.
- Локальні коміти дозволені (англійською); push — лише за прямою вказівкою.
- Remote: `git@github.com:12romis/romis-rover-telemetry.git`.

## Команди

Збірку й тести ще не налаштовано: їх визначить `/sdd:survey` + `/sdd:scaffold` і запише сюди та в `docs/architecture-map.md`.

## Інфраструктура сервера (VPS)

- Docker-мережа `infra`: `postgres` (pgvector/pg16), `mosquitto` (eclipse-mosquitto:2, `/opt/mosquitto`), `n8n-caddy-1` (Caddy, `/opt/n8n/Caddyfile`), `pgadmin`.
- MQTT усередині мережі: `mosquitto:1883`; ззовні: `mqtts://mqtt.romis.cloud:8883` (Let's Encrypt).
- ACL брокера: `/opt/mosquitto/config/acl`, паролі — `/opt/mosquitto/config/passwd`; перечитування — `docker kill --signal=SIGHUP mosquitto`.
- Секрети: `~/.config/claude-secrets/rover.env`, `~/.config/claude-secrets/mqtt.env`.
