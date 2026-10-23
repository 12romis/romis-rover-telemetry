---
id: T12
title: "Скрипт Оператора: створити БД rover і ролі owner, ingest, viewer"
layer: "infra"
deps: []
blocks: ["T13"]
acs: ["AC-15", "AC-16"]
files_hint: ["ops/bootstrap_db.sh", "ops/README.md"]
owner: "12romis"
estimate: "S"
context_budget: "M"
status: "todo"
step: ""
---

## Why (user story)

> **As a** Оператор сервера
> **I want** щоб ровер, сервіс приймання й дашборд мали лише ті права, що потрібні для їхньої ролі
> **So that** витік одного пароля не дозволяє підробити звіт чи змінити збережені дані
>
> — `spec.md §4, US-08, verbatim` · full text: [spec.md](../spec.md)

Забезпечує ролі, на які спираються GRANT міграцій: `owner` — схема, `ingest` — лише вставка, `viewer` — лише читання.

## Inlined context

> **Hard rule:** **Секрети поза git.** Паролі, токени, рядки підключення — лише в `~/.config/claude-secrets/rover.env` (chmod 600) або `.env`, що ігнорується git. У репозиторії — `.env.example` з назвами змінних.
>
> — `constitution.md, №9, verbatim` · full text: [constitution.md](../../../constitution.md)

> **Hard rule:** **Найменші права.** Окремі облікові записи брокера (ровер — лише запис у `rover/+/session`; ingest — лише читання) і окремі ролі Postgres (ingest — лише вставка; дашборд — лише читання).
>
> — `constitution.md, №10, verbatim` · full text: [constitution.md](../../../constitution.md)

> 1. Скрипт Оператора від суперкористувача Postgres створює БД `rover` і ролі `owner`, `ingest`, `viewer`; паролі беруться з `~/.config/claude-secrets/rover.env`.
> 2. `yoyo` від `owner` застосовує `0002` (таблиці, представлення, GRANT).
>
> — `sad.md §7, Launch checklist, steps 1–2, verbatim` · full text: [sad.md](../sad.md)

> - Postgres 16 у наявному контейнері `postgres` (образ `pgvector/pgvector:pg16`), окрема БД `rover`; ролі `owner` (міграції), `ingest` (лише INSERT), `viewer` (лише SELECT) — конституція №10.
>
> — `sad.md §2, Technical, verbatim` · full text: [sad.md](../sad.md)

> - Docker-мережа `infra`: `postgres` (pgvector/pg16), `mosquitto` (eclipse-mosquitto:2, `/opt/mosquitto`), `n8n-caddy-1` (Caddy, `/opt/n8n/Caddyfile`), `pgadmin`.
> - Секрети: `~/.config/claude-secrets/rover.env`, `~/.config/claude-secrets/mqtt.env`.
>
> — `CLAUDE.md, Інфраструктура сервера, verbatim` · full text: [CLAUDE.md](../../../../CLAUDE.md)

**Fallback:** insufficient or contradicted by the code → read the named file in full ([spec.md](../spec.md) · [sad.md](../sad.md) · [data-model.md](../data-model.md) · [adr/](../adr/)) and follow it. Do not guess.

## Data delta

Створює БД `rover` і ролі `owner` (власник схеми), `ingest`, `viewer` — прав на таблиці не видає (їх дають `GRANT` у міграціях T1–T3). Схему не змінює.

— `sad.md §7, Launch checklist, step 1, abridged` · full text: [sad.md](../sad.md)

## API contract

Internal — no API surface.

## Acceptance criteria

### AC-15 (US-08) — authorization

> **Given** облікові дані дашборду (лише читання сховища)
> **When** вони використані, щоб змінити або видалити збережену сесію чи відхилений звіт
> **Then** сховище відмовляє, і збережені дані лишаються без змін
>
> — `spec.md §5, AC-15, verbatim` · full text: [spec.md](../spec.md)

### AC-16 (US-08) — authorization

> **Given** облікові дані сервісу приймання
> **When** вони використані, щоб змінити чи видалити вже збережену сесію або щоб надіслати звіт брокеру
> **Then** сховище чи брокер відмовляє: сервіс лише читає звіти з брокера й дописує нові записи
>
> — `spec.md §5, AC-16, verbatim` · full text: [spec.md](../spec.md)

## Checklist

- [ ] `ops/bootstrap_db.sh`: `set -euo pipefail`; читає `ROVER_OWNER_PASSWORD`, `ROVER_INGEST_PASSWORD`, `ROVER_VIEWER_PASSWORD` із `~/.config/claude-secrets/rover.env` (назви змінних; значень у скрипті немає); виконує `docker exec -i postgres psql -U postgres` з ідемпотентним `CREATE ROLE`/`CREATE DATABASE rover OWNER owner` (повторний запуск не ламається).
- [ ] Скрипт друкує, що створено, і не друкує паролі.
- [ ] `ops/README.md`: порядок кроків 1–2 з Launch checklist і команда `yoyo apply` від `owner`; назви змінних у `.env.example` / `rover.env` (без значень).
- [ ] `.env.example`: додати назви `ROVER_*_PASSWORD` (якщо T6 їх ще не додав — узгодити, без дублю).

## Edge cases

| Case | Behaviour |
|---|---|
| Повторний запуск | Нічого не ламає: існуючі ролі й БД пропускаються |
| Немає змінної пароля | Скрипт зупиняється з повідомленням про назву змінної, нічого не створюючи |
| Ролі вже мають інші права | Скрипт прав на таблиці не чіпає; їх визначають міграції |

## Definition of Done

- [ ] `shellcheck ops/bootstrap_db.sh` без зауважень (або `bash -n`, якщо shellcheck відсутній)
- [ ] повторний запуск на тестовому Postgres нічого не ламає
- [ ] у скрипті й README немає значень паролів
- [ ] every Hard Rule inlined above still holds
- [ ] lint + vet clean (`ruff check . && ruff format --check . && mypy src`)
