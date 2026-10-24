---
id: T8
title: "Додати маршрут GET / з читанням знімка, 503 при недоступному сховищі, заголовками безпеки і /static"
layer: "ports"
deps: ["T3", "T6", "T7"]
blocks: ["T9", "T10"]
acs: ["AC-11", "AC-12", "AC-13"]
files_hint: ["src/rover_telemetry/web/app.py", "tests/unit/test_dashboard_route.py", "tests/unit/test_smoke.py"]
owner: "12romis"
estimate: "M"
context_budget: "M"
status: "done"
step: ""
---

# T8 — Додати маршрут GET / з читанням знімка, 503 при недоступному сховищі, заголовками безпеки і /static

## Place in the sequence

- **Blocked by:** T3 — Додати читання одного знімка лише для читання (db/reading.py) і налаштування таймаутів web, T6 — Побудувати сторінку dashboard.html: опис, вісім карток підсумків, стани empty і error, T7 — Побудувати список виїздів: розгортуваний рядок (details), позначка пропуску, блок повного звіту · **Blocks:** T9 — Підготувати публікацію: alias rover-web у compose, фрагмент Caddyfile, runbook і скрипт перевірки, T10 — Додати інтеграційні тести сторінки на реальному Postgres: свіжість, дубль, запис, затримка, зовнішні запити · **Wave:** 5 (після T3, T6, T7).
- **Lane:** own lane.

## Why (user story)

> **As a** Глядач
> **I want** бачити зрозумілу сторінку, коли виїздів ще немає або дані тимчасово недоступні
> **So that** порожній чи зламаний екран не псував враження від презентації
>
> — `spec.md §4, US-09, verbatim` · full text: [spec.md](../spec.md)

> **As a** Оператор сервера
> **I want** щоб сторінка відкривалася публічно через захищене з'єднання, нічого не змінювала й не залежала від зовнішніх вузлів
> **So that** її можна безпечно показувати на презентації, а збій дашборду не зачіпав збереження звітів
>
> — `spec.md §4, US-08, verbatim` · full text: [spec.md](../spec.md)

З'єднує читання, домен і шаблони в єдину сторінку лише для читання, яка не ламається без даних і без сховища.

## Inlined context

> **Flow 1 — показ сторінки з даними (AC-01, AC-03, AC-08, AC-17).** Web просить db прочитати виїзди й номери без виїзду; db відкриває знімок лише для читання, вибирає виїзди без сирих байтів і номери без виїзду з `session_gaps`; Web просить domain порахувати підсумки й скласти хронологію; Web віддає сторінку з описом, підсумками і виїздами. Розгортання виїзду — нативний `details` у браузері, нового запиту немає.
> **Flow 2 — сховище недоступне (AC-12).** Якщо сховище не відповідає або запит перевищив час, db повідомляє «сховище недоступне»; Web записує причину в лог, без подробиць для сторінки, і віддає сторінку з описом та повідомленням, що дані тимчасово недоступні; технічних подробиць на сторінці немає.
>
> — `sad.md §6, critical flows 1–2, abridged (пересказ sequenceDiagram)` · full text: [sad.md](../sad.md)

> | Error handling | `psycopg.OperationalError`, перевищення таймаутів підключення чи запиту та інші збої читання ловляться на межі `web`: повна сторінка з описом і блоком «дані тимчасово недоступні», статус 503, без технічних подробиць; невідомий маршрут — стандартна відповідь FastAPI | `docs/architecture-map.md`, spec AC-12 |
>
> — `sad.md §8, Error handling, verbatim` · full text: [sad.md](../sad.md)

> | Authentication / AuthZ | Автентифікації немає (конституція №12, рішення №4). Право читання забезпечує роль Postgres `viewer` (без `INSERT/UPDATE/DELETE`), транзакція `READ ONLY` і відсутність маршрутів з побічним ефектом; дозволений лише `GET` | конституція №10, №11, feature ADR-0001 |
>
> — `sad.md §8, Authentication / AuthZ, verbatim` · full text: [sad.md](../sad.md)

> | Security headers | `Content-Security-Policy: default-src 'self'` (без inline-скриптів і стилів), `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`; жодних запитів до сторонніх вузлів | тут, spec §6 |
>
> — `sad.md §8, Security headers, verbatim` · full text: [sad.md](../sad.md)

> | Caching | Немає: кожен запит читає актуальний знімок, `Cache-Control: no-store` (spec §6 «кешування даних — 0 с») | spec §6 |
>
> — `sad.md §8, Caching, verbatim` · full text: [sad.md](../sad.md)

> | Logging | Рядки `key=value` у stdout; помилка сховища логується повністю (клас і текст), на сторінку потрапляє лише загальне повідомлення; вмісту звітів і паролів у логах немає | тут, за прикладом ingest |
>
> — `sad.md §8, Logging, verbatim` · full text: [sad.md](../sad.md)

> Тактичні рішення цього етапу (без ADR, бо відкат — години, а не дні): з'єднання з БД на запит без пулу, з таймаутом підключення й таймаутом виконання запиту, меншими за таймаут Caddy, щоб недоступне сховище давало AC-12, а не зависання (значення вибирають `tasks`/Оператор, як у ingest, а не вимога специфікації); список виїздів — елементи `<details>`, а не `<table>` (рядок `<tr>` не може бути розгортуваним, а таблиця в 11 колонок не вміщується в 360 px); `HTTP 503` при недоступному сховищі; назва «RomisRover» для `288485922c94` (рішення власника №10) — константа в `web`, інші `mac` показуються як є; порядок рядків — `seq` ↓, потім `mac`; заголовки безпеки (CSP `default-src 'self'`, `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`) ставить сам застосунок, щоб їх перевіряв тест; київський час через `zoneinfo`, `tzdata` додається в залежності, бо в `python:3.12-slim` бази зон може не бути.
>
> — `sad.md §4, тактичні рішення, abridged` · full text: [sad.md](../sad.md)

> **Hard rule:** **Дашборд лише читає.** Жодного зворотного каналу до ровера; ровер нічого не отримує з сервера.
>
> — `constitution.md, №11, verbatim` · full text: [constitution.md](../../../constitution.md)

> **Hard rule:** **Назовні — лише через Caddy з HTTPS.** Сервіси не публікують порти на хост; працюють у Docker-мережі `infra`. Дашборд наразі публічний без автентифікації (рішення власника 2026-10-23: лише читання, персональних даних і геопозиції немає); автентифікація додається окремим рішенням.
>
> — `constitution.md, №12, verbatim` · full text: [constitution.md](../../../constitution.md)

**Fallback:** insufficient or contradicted by the code → read the named file in full ([spec.md](../spec.md) · [sad.md](../sad.md) · [screens.md](../screens.md) · [adr/](../adr/)) and follow it. Do not guess.

## Data delta

No DB changes.

## API contract

- `GET /` → `200 text/html` (стан ok/empty) · `503 text/html` (сховище недоступне; та сама сторінка зі станом `error`).
- `GET /static/app.css` → `200 text/css` · `GET /healthz` → `200 {"status": "ok"}` (без змін).
- Інші методи на `/` → `405`; `openapi_url`, `/docs`, `/redoc` вимкнені → `404`.
- Заголовки кожної відповіді: `Content-Security-Policy: default-src 'self'`, `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`.

— `sad.md §4/§8, тактичні рішення та Security headers, abridged` (`contracts/openapi.yaml` для фічі немає: маршрут — HTML-сторінка, не програмний API) · full text: [sad.md](../sad.md)

## Acceptance criteria

### AC-11 — happy path

> **Given** жодного виїзду ще не збережено
> **When** Глядач відкриває дашборд
> **Then** він бачить, що виїздів ще немає, кількість виїздів показана як нуль (це виміряне число), а решта підсумків як «немає даних», і сторінка лишається цілою
>
> — `spec.md §5, AC-11, verbatim` · full text: [spec.md](../spec.md)

### AC-12 — error

> **Given** сховище виїздів тимчасово недоступне
> **When** Глядач відкриває дашборд
> **Then** у місці підсумків і таблиці він бачить повідомлення простою мовою, що дані тимчасово недоступні, опис на сторінці лишається, а технічних подробиць про збій немає
>
> — `spec.md §5, AC-12, verbatim` · full text: [spec.md](../spec.md)

### AC-13 — authorization

> **Given** Глядач не має облікового запису
> **When** він відкриває дашборд
> **Then** він бачить усі підсумки й виїзди, але не має жодної дії, що змінює збережені дані або щось надсилає ровер, а ровер від дашборду нічого не отримує
>
> — `spec.md §5, AC-13, verbatim` · full text: [spec.md](../spec.md)

## Checklist

- [ ] Тести спочатку — `tests/unit/test_dashboard_route.py` (`TestClient`, читання підмінене через `app.dependency_overrides` без Docker): ok, empty, `psycopg.OperationalError` → 503, POST/PUT/DELETE → 405, заголовки безпеки
- [ ] `src/rover_telemetry/web/app.py`: `FastAPI(..., docs_url=None, redoc_url=None, openapi_url=None)`; монтування `/static`; залежність `get_settings()` (`WebSettings.from_env`, кеш; відсутня змінна — помилка конфігурації, не «сховище недоступне»)
- [ ] Маршрут `GET /` (синхронний `def`): `open_connection` → `read_snapshot` → `build_summary` + `build_timeline` → `dashboard.html`; `state` = `empty` при нуль виїздів, інакше `ok`; з'єднання закривається у `finally`
- [ ] Перехоплення `psycopg.Error` на межі `web`: `logger.error` рядком `key=value` (клас і текст помилки) — і відповідь `503` зі `state='error'`; у тілі відповіді немає тексту винятку, шляхів, класів
- [ ] Middleware/залежність заголовків безпеки на всі відповіді; жодного маршруту з побічним ефектом; `test_smoke.py` лишається зеленим

## Edge cases

| Case | Behaviour |
|---|---|
| Сховище не відповідає / перевищено час | статус 503; опис лишається, блок «Дані тимчасово недоступні…»; у тілі немає тексту винятку (AC-12) |
| Виїздів ще немає | статус 200; `Виїздів 0`, решта «немає даних», повідомлення замість списку (AC-11) |
| `WEB_DATABASE_URL` не задано | помилка конфігурації при першому зверненні, не 503 і не мовчазна порожня сторінка |
| `POST /`, `PUT /`, `DELETE /` | `405` — дії, що змінюють дані, відсутні (AC-13) |
| Помилка не `psycopg.Error` (баг у шаблоні) | не маскується під «сховище недоступне»; стандартна відповідь FastAPI 500 |
| Повторне оновлення сторінки | кожен запит читає новий знімок; `Cache-Control: no-store` |

## Definition of Done

- [ ] `pytest tests/unit/test_dashboard_route.py` проходить: 200 ok, 200 empty, 503 без технічних подробиць, 405 на запис, чотири заголовки
- [ ] лог 503-випадку містить клас і текст помилки, тіло відповіді — ні
- [ ] `/openapi.json`, `/docs`, `/redoc` повертають 404
- [ ] `pytest -m 'not integration'`, `ruff`, `mypy --strict` без нових попереджень
- [ ] кожне Hard Rule, процитоване вище, лишається дотриманим
- [ ] lint + type-check чисті (`ruff check . && ruff format --check . && mypy src`)
