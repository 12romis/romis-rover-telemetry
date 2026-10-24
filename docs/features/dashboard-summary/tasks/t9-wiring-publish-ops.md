---
id: T9
title: "Підготувати публікацію: alias rover-web у compose, фрагмент Caddyfile, runbook і скрипт перевірки"
layer: "wiring"
deps: ["T8"]
blocks: []
acs: ["AC-15"]
files_hint: ["docker-compose.yml", "ops/README.md", "ops/verify_dashboard.sh", "tests/integration/test_ops_dashboard.py"]
owner: "12romis"
estimate: "S"
context_budget: "M"
status: "done"
step: ""
---

# T9 — Підготувати публікацію: alias rover-web у compose, фрагмент Caddyfile, runbook і скрипт перевірки

## Place in the sequence

- **Blocked by:** T8 — Додати маршрут GET / з читанням знімка, 503 при недоступному сховищі, заголовками безпеки і /static · **Blocks:** — · **Wave:** 6 (після T8).
- **Lane:** own lane.

## Why (user story)

> **As a** Оператор сервера
> **I want** щоб сторінка відкривалася публічно через захищене з'єднання, нічого не змінювала й не залежала від зовнішніх вузлів
> **So that** її можна безпечно показувати на презентації, а збій дашборду не зачіпав збереження звітів
>
> — `spec.md §4, US-08, verbatim` · full text: [spec.md](../spec.md)

Готує репозиторій до публікації за `rover.romis.cloud` через HTTPS без опублікованих портів; саме застосування на сервері робить Оператор після DNS.

## Inlined context

> Сервіс `web` — уже оголошений сервіс у `docker-compose.yml` (той самий образ `rover-telemetry`, команда `python -m rover_telemetry.web`, мережа `infra`, `restart: unless-stopped`); порти на хост не публікуються (конституція №12). Для цієї фічі додаються: мережевий alias `rover-web` (ім'я `web` у спільній мережі `infra` може збігтися з чужим сервісом), `tzdata` у залежностях образу й блок у `/opt/n8n/Caddyfile`:
>
> — `sad.md §7, deployment view, verbatim` · full text: [sad.md](../sad.md)

> rover.romis.cloud {
>     reverse_proxy rover-web:8000
> }
>
> — `sad.md §7, блок Caddyfile, verbatim` · full text: [sad.md](../sad.md)

> Одна репліка. `web` залежить від Postgres, але не від `ingest`: зупинка `web` не зупиняє збереження звітів (AC-15), перевіряється зупинкою контейнера, надсиланням звіту й читанням збереженого. Рядок підключення `WEB_DATABASE_URL` (роль `viewer`) роздається лише контейнеру `web`. Перед публікацією: запис DNS для `rover.romis.cloud` (spec §8, у власника) і перезавантаження Caddy за процедурою стеку n8n. Роль `viewer` розумно обмежити за кількістю одночасних підключень (`ALTER ROLE viewer CONNECTION LIMIT …`, значення вибирає Оператор під час розгортання), щоб навал запитів до публічної сторінки не вичерпав підключення, потрібні `ingest`.
>
> — `sad.md §7, deployment view, ізоляція та CONNECTION LIMIT, verbatim` · full text: [sad.md](../sad.md)

> **Hard rule:** **Назовні — лише через Caddy з HTTPS.** Сервіси не публікують порти на хост; працюють у Docker-мережі `infra`. Дашборд наразі публічний без автентифікації (рішення власника 2026-10-23: лише читання, персональних даних і геопозиції немає); автентифікація додається окремим рішенням.
>
> — `constitution.md, №12, verbatim` · full text: [constitution.md](../../../constitution.md)

> | Ізоляція від приймання | зупинка дашборду не зупиняє збереження звітів | перевірка запуску: зупинити дашборд, надіслати звіт, звіт збережено |
>
> — `spec.md §6, Ізоляція від приймання, verbatim` · full text: [spec.md](../spec.md)

> | Зовнішні залежності | 0 запитів до сторонніх вузлів | перегляд мережевих запитів сторінки в тесті |
>
> — `spec.md §6, Зовнішні залежності, verbatim` · full text: [spec.md](../spec.md)

> - **Security review:** Required — розмір M і нова публічна поверхня; перед публікацією перевірити, що назовні відкрито лише захищене з'єднання, порти сервісу не опубліковано, а сховище доступне дашборду лише для читання.
>
> — `spec.md §6.1, Security review, verbatim` · full text: [spec.md](../spec.md)

> - [ ] Створити запис DNS для публічної адреси дашборду до розгортання (роудмап D4)? Default now: розробка й тести без нього, публікація блокується. — owner: 12romis, due: до `/sdd:ship`
>
> — `spec.md §8, відкрите питання DNS, verbatim` · full text: [spec.md](../spec.md)

**Fallback:** insufficient or contradicted by the code → read the named file in full ([spec.md](../spec.md) · [sad.md](../sad.md) · [screens.md](../screens.md) · [adr/](../adr/)) and follow it. Do not guess.

## Data delta

No DB changes.

## API contract

Internal — no API surface. (Публічна адреса `https://rover.romis.cloud/` віддає лише `GET /`, див. T8.)

## Acceptance criteria

### AC-15 — happy path

> **Given** Оператор сервера опублікував дашборд
> **When** Глядач відкриває публічну адресу дашборду
> **Then** сторінка відкривається через захищене з'єднання, працює без звернень до сторонніх вузлів, а збереження нових звітів триває, навіть якщо дашборд зупинено
>
> — `spec.md §5, AC-15, verbatim` · full text: [spec.md](../spec.md)

## Checklist

- [ ] Тести спочатку — `tests/integration/test_ops_dashboard.py`: `docker compose config --format json` (із заданою `WEB_DATABASE_URL`) — у сервісу `web` немає `ports`, у мережі `infra` є alias `rover-web`
- [ ] `docker-compose.yml`: `web.networks.infra.aliases: [rover-web]` (мережа лишається зовнішньою `infra`; порти не публікуються)
- [ ] `ops/README.md`: розділ «Публікація дашборду» — блок Caddyfile з SAD §7 (`/opt/n8n/Caddyfile`), перезавантаження Caddy за процедурою стеку n8n, `ALTER ROLE viewer CONNECTION LIMIT <N>` (значення вибирає Оператор), запис DNS (залежність від власника), перевірка ізоляції: зупинити `web` → надіслати звіт → звіт збережено
- [ ] `ops/verify_dashboard.sh [URL]`: перевіряє відсутність опублікованих портів `web`, а з аргументом — HTTPS 200, чотири заголовки безпеки, відсутність сторонніх хостів у HTML; не друкує секретів
- [ ] Чекліст security review зі spec §6.1 (HTTPS-вхід, порти, права `viewer`) — у тому ж розділі; виконувати Оператору до `/sdd:ship`

## Edge cases

| Case | Behaviour |
|---|---|
| DNS-запису ще немає | задача завершується без публікації; публікація заблокована до запису від власника (spec §8, SAD §11 High) |
| Ім'я `web` збігається з чужим сервісом у `infra` | Caddy звертається до alias `rover-web`, не до `web` |
| `web` зупинено | `ingest` продовжує зберігати звіти (AC-15); перевіряється в runbook |
| Скрипт без аргументу URL | перевіряє лише локальну конфігурацію compose, до мережі не ходить |

## Definition of Done

- [ ] `pytest -m integration tests/integration/test_ops_dashboard.py` проходить
- [ ] `ops/verify_dashboard.sh` без аргументів виходить із 0 на конфігурації репозиторію
- [ ] `ops/README.md` містить блок Caddyfile, `CONNECTION LIMIT`, DNS-залежність, чекліст security review та перевірку ізоляції
- [ ] жодні файли поза репозиторієм (`/opt/n8n/Caddyfile`) не змінено — застосування робить Оператор з дозволу власника
- [ ] кожне Hard Rule, процитоване вище, лишається дотриманим
- [ ] lint + type-check чисті (`ruff check . && ruff format --check . && mypy src`)
