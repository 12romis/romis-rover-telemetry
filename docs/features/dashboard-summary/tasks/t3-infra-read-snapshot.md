---
id: T3
title: "Додати читання одного знімка лише для читання (db/reading.py) і налаштування таймаутів web"
layer: "infra"
deps: ["T1"]
blocks: ["T8"]
acs: ["AC-08", "AC-14", "AC-16"]
files_hint: ["src/rover_telemetry/db/reading.py", "src/rover_telemetry/config.py", ".env.example", "tests/integration/test_reading.py", "tests/unit/test_config.py"]
owner: "12romis"
estimate: "M"
context_budget: "M"
status: "done"
step: ""
---

# T3 — Додати читання одного знімка лише для читання (db/reading.py) і налаштування таймаутів web

## Place in the sequence

- **Blocked by:** T1 — Додати в domain типи виїзду, підсумки з Total(sum, missing) і класифікацію причини завершення · **Blocks:** T8 — Додати маршрут GET / з читанням знімка, 503 при недоступному сховищі, заголовками безпеки і /static · **Wave:** 2 (після T1).
- **Lane:** own lane.

## Why (user story)

> **As a** Власник ровера
> **I want** бачити, які номери сесій не дійшли, і щоб відхилені повідомлення не рахувалися виїздами
> **So that** пропуски не виглядали як «ровер просто не їздив», а підсумки не завищувалися
>
> — `spec.md §4, US-05, verbatim` · full text: [spec.md](../spec.md)

> **As a** Оператор сервера
> **I want** щоб сторінка відкривалася публічно через захищене з'єднання, нічого не змінювала й не залежала від зовнішніх вузлів
> **So that** її можна безпечно показувати на презентації, а збій дашборду не зачіпав збереження звітів
>
> — `spec.md §4, US-08, verbatim` · full text: [spec.md](../spec.md)

Дає `web` єдину функцію читання: виїзди (без `raw`) і номери без виїзду з однієї транзакції `READ ONLY`, плюс з'єднання з таймаутами.

## Inlined context

> 1. **Один знімок читання, підсумки рахує `domain`** — запит сторінки відкриває одну транзакцію лише для читання, читає виїзди й облік пропусків, і чисті функції `domain` будують із цих самих рядків підсумки та список. Таблиця й підсумки узгоджені за побудовою, правило «`NULL` ≠ 0» живе в одному тестованому місці, нової міграції немає (QG-1, QG-3) — feature ADR-0001.
>
> — `sad.md §4, стратегічний вибір 1, verbatim` · full text: [sad.md](../sad.md)

> 3. **Дашборд лише читає на трьох рівнях** — роль БД `viewer` без права запису, транзакція `READ ONLY`, у застосунку немає жодного маршруту з побічним ефектом (конституція №10, №11, AC-14).
>
> — `sad.md §4, стратегічний вибір 3, verbatim` · full text: [sad.md](../sad.md)

> **Chosen:** варіант 1. Підсумки й таблиця будуються з одного набору рядків, тому узгоджені за побудовою; правило «сума лише за відомими значеннями + кількість без даних» живе в `domain` як `Total(sum, missing)` і тестується швидкими юніт-тестами на реальних фікстурах. Нова міграція не потрібна: `viewer` уже має `SELECT` на `sessions` і `session_gaps`. Це уточнення, а не скасування фундаментального ADR-0003: представлення лишаються способом агрегації для даних, яких сторінка не завантажує (графіки по днях у кроках 4–8). Свідомий відступ від його букви — `web` читає саму таблицю `sessions` (виїзди з `payload`, без `raw`), а не представлення; він записаний як Decision override у SAD §1 ¶4.
>
> — `adr/0001, Decision outcome, verbatim` · full text: [adr/0001](../adr/0001-compute-dashboard-summary-in-domain-from-one-read-only-snapshot.md)

> - Decision override: `web` читає таблицю `sessions` напряму, а не лише SQL-представлення — rationale: роль `viewer` уже має `SELECT`, сторінка й так завантажує всі виїзди, а підсумки з тих самих рядків узгоджені з таблицею без нової міграції; фундаментальний ADR-0003 лишається чинним для агрегацій, яких сторінка не завантажує (feature ADR-0001).
>
> — `sad.md §1, Decision override 1, verbatim` · full text: [sad.md](../sad.md)

> **Hard rule:** **Найменші права.** Окремі облікові записи брокера (ровер — лише запис у `rover/+/session`; ingest — лише читання) і окремі ролі Postgres (ingest — лише вставка; дашборд — лише читання).
>
> — `constitution.md, №10, verbatim` · full text: [constitution.md](../../../constitution.md)

> **Hard rule:** **Дашборд лише читає.** Жодного зворотного каналу до ровера; ровер нічого не отримує з сервера.
>
> — `constitution.md, №11, verbatim` · full text: [constitution.md](../../../constitution.md)

> - Postgres 16 у наявному контейнері `postgres`, БД `rover`; дашборд підключається роллю `viewer` (лише `SELECT` на `sessions`, `rejected`, `session_gaps` — міграції `0002`–`0004`); запису немає (конституція №10, №11).
>
> — `sad.md §2, Technical, БД, verbatim` · full text: [sad.md](../sad.md)

> Тактичні рішення цього етапу (без ADR, бо відкат — години, а не дні): з'єднання з БД на запит без пулу, з таймаутом підключення й таймаутом виконання запиту, меншими за таймаут Caddy, щоб недоступне сховище давало AC-12, а не зависання (значення вибирають `tasks`/Оператор, як у ingest, а не вимога специфікації)
>
> — `sad.md §4, тактичні рішення, таймаути з'єднання, abridged` · full text: [sad.md](../sad.md)

> | Logging | Рядки `key=value` у stdout; помилка сховища логується повністю (клас і текст), на сторінку потрапляє лише загальне повідомлення; вмісту звітів і паролів у логах немає | тут, за прикладом ingest |
>
> — `sad.md §8, Logging, verbatim` · full text: [sad.md](../sad.md)

**Fallback:** insufficient or contradicted by the code → read the named file in full ([spec.md](../spec.md) · [sad.md](../sad.md) · [screens.md](../screens.md) · [adr/](../adr/)) and follow it. Do not guess.

## Data delta

| Column | Type | Constraints | Change |
|---|---|---|---|
| `mac`, `seq` | `text`, `integer` | NOT NULL; ключ виїзду `(mac, seq)` | read-only |
| `received_at` | `timestamptz` | NOT NULL | read-only (єдиний час — «отримано») |
| `duration_ms`, `moving_ms`, `distance_cm`, `holds_count` | `integer` | nullable | read-only |
| `end_reason`, `fw_version` | `text` | nullable | read-only |
| `voltage_start_mv`, `voltage_end_mv`, `voltage_min_mv` | `integer` | nullable | read-only |
| `payload` | `jsonb` | NOT NULL | read-only (для розгорнутого звіту) |
| `raw` | `bytea` | NOT NULL | **не читається** (SAD §1, Decision override) |

— `migrations/0002_create_sessions.sql, table sessions, abridged` · full text: [0002_create_sessions.sql](../../../../migrations/0002_create_sessions.sql)

Представлення `session_gaps(mac, seq)` — номери між найменшим і найбільшим збереженим `seq` кожного `mac`, яких немає в `sessions`; `GRANT SELECT … TO viewer` уже є.

— `migrations/0004_create_session_gaps.sql, view session_gaps, abridged` · full text: [0004_create_session_gaps.sql](../../../../migrations/0004_create_session_gaps.sql)

Таблицю `rejected` задача **не читає**; нових міграцій немає.

## API contract

Internal — no API surface.

## Acceptance criteria

### AC-08 — domain invariant violation

> **Given** для ровера пропущено номери сесій між першим збереженим і найновішим
> **When** Власник ровера дивиться підсумки й таблицю
> **Then** підсумки показують кількість втрачених сесій, а на місці кожного номера, під яким виїзду немає, у таблиці є позначка «виїзду з цим номером немає» з цим номером
>
> — `spec.md §5, AC-08, verbatim` · full text: [spec.md](../spec.md)

### AC-14 — authorization

> **Given** дашборд має доступ до сховища лише для читання
> **When** у роботі дашборду трапляється помилка чи його використовують не за призначенням
> **Then** збережені виїзди залишаються без змін, бо сховище відмовляє будь-якій спробі запису від дашборду
>
> — `spec.md §5, AC-14, verbatim` · full text: [spec.md](../spec.md)

### AC-16 — cross-context

> **Given** серед відхилених повідомлень є невалідне
> **When** Глядач чи Власник ровера дивиться підсумки й таблицю
> **Then** відхилене повідомлення не рахується виїздом і не потрапляє в таблицю як виїзд; якщо воно мало номер сесії, дашборд не відрізняє його від втраченої, і цей номер позначений так само, як будь-який номер без виїзду
>
> — `spec.md §5, AC-16, verbatim` · full text: [spec.md](../spec.md)

## Checklist

- [ ] Тести спочатку — `tests/integration/test_reading.py` (`pytest.mark.integration`, фікстури `migrated_db`, `ingest_url`, `viewer_url`): сесії seq 26, 27 (+ одна з пропуском, одна з `NULL`-ами), відхилене повідомлення
- [ ] `src/rover_telemetry/db/reading.py`: `open_connection(settings)` (`connect_timeout`, `autocommit=False`); `read_snapshot(conn) -> Snapshot(sessions: list[StoredSession], gaps: list[GapNumber])`
- [ ] У `read_snapshot`: `REPEATABLE READ` + `READ ONLY`, `SET LOCAL statement_timeout`; один `SELECT` колонок `sessions` **без `raw`** і один `SELECT mac, seq FROM session_gaps`; сирий SQL, параметризація, жодного читання `rejected`
- [ ] `src/rover_telemetry/config.py`: `WebSettings` отримує `db_connect_timeout_s` (`WEB_DB_CONNECT_TIMEOUT_S`, за замовчуванням 3) і `db_statement_timeout_s` (`WEB_DB_STATEMENT_TIMEOUT_S`, за замовчуванням 5) — вибір розбиття задач за SAD §4, не вимога специфікації; пояснити коментарем; назви додати в `.env.example`; оновити `tests/unit/test_config.py`

## Edge cases

| Case | Behaviour |
|---|---|
| Спроба запису всередині знімка | `INSERT`/`UPDATE`/`DELETE` падає (`ReadOnlySqlTransaction` або відмова ролі) — дані без змін (AC-14) |
| Нових виїздів між двома `SELECT` не з'являється | обидва запити бачать один знімок (`REPEATABLE READ`): виїзд не потрапляє в список і водночас у пропуски |
| Відхилене повідомлення з номером сесії | у `gaps` номер потрапляє лише якщо в `sessions` його немає; `rejected` не читається (AC-16) |
| Сховище недоступне / запит завис | `psycopg.OperationalError` чи `QueryCanceled` піднімається до викликача без перехоплення тут (обробляє `web`, AC-12) |
| Колонка `NULL` | повертається `None`, не 0 і не порожній рядок |

## Definition of Done

- [ ] `pytest -m integration tests/integration/test_reading.py` проходить на реальному Postgres 16 (Docker)
- [ ] тест перевіряє `SHOW transaction_read_only == on` у знімку й падіння `INSERT` через з'єднання знімка
- [ ] запит у `reading.py` не містить `raw` і `rejected`
- [ ] `pytest -m 'not integration'` (включно з `test_config.py`) і `ruff`/`mypy --strict` без нових попереджень
- [ ] кожне Hard Rule, процитоване вище, лишається дотриманим
- [ ] lint + type-check чисті (`ruff check . && ruff format --check . && mypy src`)
