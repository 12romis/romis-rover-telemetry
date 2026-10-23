---
id: T7
title: "Записувати сесії й відхилені: db.sessions.insert_session / insert_rejected"
layer: "infra"
deps: ["T2", "T5"]
blocks: ["T8", "T9"]
acs: ["AC-01", "AC-03", "AC-03b", "AC-05b"]
files_hint: ["src/rover_telemetry/db/sessions.py", "tests/integration/test_db_inserts.py"]
owner: "12romis"
estimate: "M"
context_budget: "M"
status: "todo"
step: ""
---

## Why (user story)

> **As a** Ровер
> **I want** щоб кожен звіт сесії, який я надсилаю, потрапляв у сховище сесій
> **So that** виїзд не втрачається, а мій буфер із двох недоставлених звітів не витісняє старі звіти
>
> — `spec.md §4, US-01, verbatim` · full text: [spec.md](../spec.md)

> **As a** Власник ровера
> **I want** щоб повторно доставлений звіт не створював другу сесію
> **So that** пробіг і кількість виїздів не завищуються через неминучі дублікати доставки
>
> — `spec.md §4, US-02, verbatim` · full text: [spec.md](../spec.md)

Дає шар запису: `ON CONFLICT DO NOTHING` без цілі повертає «нова» чи «дубль», відхилене пишеться окремим записом; роль `ingest` лише вставляє.

## Inlined context

> **Chosen:** варіант 1. Роль `ingest` має лише `INSERT` на `sessions` і `rejected`. Безпека варіанту тримається на тому, що `sessions` має рівно одне обмеження унікальності, первинний ключ `(mac, seq)` (міграція і тест це перевіряють), тож «будь-який конфлікт» означає «дубль». Варіант 2 віддає ролі читання ключів (мінімальне, але розширення прав), варіант 3 вимагає повного `SELECT` і має гонку між перевіркою й вставкою.
>
> — `adr/0005, Decision outcome, verbatim` · full text: [adr/0005-insert-sessions-with-on-conflict-do-nothing-without-target.md](../adr/0005-insert-sessions-with-on-conflict-do-nothing-without-target.md)

> **Hard rule:** **Дедублікація за `(mac, seq)`.** Запис — `ON CONFLICT DO NOTHING`. Пропуск у `seq` для одного `mac` — втрачена сесія, її показують, а не приховують.
>
> — `constitution.md, №6, verbatim` · full text: [constitution.md](../../../constitution.md)

> **Hard rule:** **Найменші права.** Окремі облікові записи брокера (ровер — лише запис у `rover/+/session`; ingest — лише читання) і окремі ролі Postgres (ingest — лише вставка; дашборд — лише читання).
>
> — `constitution.md, №10, verbatim` · full text: [constitution.md](../../../constitution.md)

> │   └── sessions.py      # insert_session, insert_rejected; з'єднання з таймаутами; лише INSERT
>
> — `sad.md §5, Internal decomposition, abridged` · full text: [sad.md](../sad.md)

> Ingest->>Db: INSERT у sessions ON CONFLICT DO NOTHING і COMMIT
> Db-->>Ingest: 1 рядок (нова сесія) або 0 рядків (дубль)
> Ingest->>Db: INSERT у rejected з кодом причини і COMMIT
>
> — `sad.md §6, flow 1, abridged` · full text: [sad.md](../sad.md)

**Fallback:** insufficient or contradicted by the code → read the named file in full ([spec.md](../spec.md) · [sad.md](../sad.md) · [data-model.md](../data-model.md) · [adr/](../adr/)) and follow it. Do not guess.

## Data delta

Вставка в `sessions` (усі колонки `ParsedSession`) і `rejected` (без `id`). Права ролі `ingest`: лише `INSERT`; читання, зміна, видалення — відмова.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `topic` | text | NOT NULL | Топік доставки `rover/<mac>/session`; потрібен, бо `mac` з невалідного вмісту недовіряний (AC-06) |
| `reason_code` | text | NOT NULL | Один із: `too_large`, `not_json`, `unknown_event`, `unsupported_schema`, `missing_id`, `id_mismatch`, `bad_type` (SAD §8 «Reason codes»). Без `CHECK`: перелік може рости, а запис відхиленого не має падати |
| `reason_text` | text | NOT NULL | Причина простою мовою (AC-05) |
| `raw` | bytea | NOT NULL | Перші ≤ 1024 байти повідомлення, дослівно (ADR-0002). `bytea`, бо сміття може бути не UTF-8 і містити нуль-байти |
| `raw_size` | integer | NOT NULL | Початковий розмір повідомлення в байтах |
| `raw_truncated` | boolean | NOT NULL | Позначка обрізання; до ліміту 1024 не входить (AC-07). Явного `DEFAULT` немає: значення ставить `domain` |
| `received_at` | timestamptz | NOT NULL | Час «отримано» (AC-05) |

— `data-model.md §Entities, tables sessions/rejected, abridged` · full text: [data-model.md](../data-model.md)

## API contract

Internal — no API surface.

## Acceptance criteria

### AC-01 (US-01) — happy path

> **Given** Ровер завершив виїзд і надсилає коректний звіт сесії, якого ще немає серед збережених
> **When** сервіс приймання отримує цей звіт
> **Then** сесія з'являється серед збережених разом із часом «отримано», і лише після цього отримання підтверджується брокеру
>
> — `spec.md §5, AC-01, verbatim` · full text: [spec.md](../spec.md)

### AC-03 (US-02) — domain invariant violation

> **Given** серед збережених є сесія ровера з номером N
> **When** звіт з тим самим ровером і номером N надходить повторно
> **Then** сесія лишається єдиною, її час «отримано» не змінюється, повтор підтверджується брокеру і не потрапляє до відхилених
>
> — `spec.md §5, AC-03, verbatim` · full text: [spec.md](../spec.md)

### AC-03b (US-02) — domain invariant violation

> **Given** серед збережених є сесія ровера з номером N
> **When** надходить звіт з тим самим ровером і номером N, але з іншим вмістом
> **Then** збережена сесія не змінюється, а повтор обробляється так само, як звичайний дубль
>
> — `spec.md §5, AC-03b, verbatim` · full text: [spec.md](../spec.md)

### AC-05b (US-03) — domain invariant violation

> **Given** серед відхилених є повідомлення ровера A з номером N
> **When** надходить коректний звіт того самого ровера з тим самим номером N
> **Then** він зберігається як сесія, бо відхилений звіт не займає номер сесії
>
> — `spec.md §5, AC-05b, verbatim` · full text: [spec.md](../spec.md)

## Checklist

- [ ] `db/sessions.py`: `connect(url, timeout_s)` (psycopg 3, `connect_timeout`, `autocommit=False`).
- [ ] `insert_session(conn, s: ParsedSession) -> bool`: `INSERT INTO sessions (…) VALUES (…) ON CONFLICT DO NOTHING` без цілі конфлікту, параметризований SQL; повертає `cur.rowcount == 1`; `commit()` робить викликач (T9), щоб `ack` ішов після COMMIT.
- [ ] `insert_rejected(conn, r: Rejection) -> None`: `INSERT INTO rejected (…)`; `id` не називається.
- [ ] `tests/integration/test_db_inserts.py` під роллю `ingest`: AC-01 (вставка нової сесії → `True`, рядок із `received_at`), AC-03/03b (повтор того ж `(mac, seq)`, у т.ч. з іншим вмістом → `False`, рядок не змінився, `received_at` старий, `rejected` порожня), AC-05b (запис у `rejected` з `(mac, N)`, потім валідна сесія `(mac, N)` → `True`).
- [ ] Тест: роль `ingest` не може `SELECT`, `UPDATE`, `DELETE` на `sessions`/`rejected` (дотична до T8, але тут доводить, що `INSERT … ON CONFLICT DO NOTHING` без `SELECT` працює).

## Edge cases

| Case | Behaviour |
|---|---|
| Повтор `(mac, seq)` з тим самим вмістом | `insert_session` → `False`, `received_at` першого запису не змінюється (AC-03) |
| Повтор `(mac, seq)` з іншим вмістом | Те саме, що звичайний дубль; збережена сесія незмінна (AC-03b, ADR-0005) |
| Той самий `seq`, інший `mac` | Нова сесія (AC-04) |
| Відхилений звіт із номером N, потім валідний N | Сесія зберігається: `rejected` не займає номер (AC-05b) |
| БД недоступна чи таймаут | Виняток піднімається до викликача; нічого не ковтається (T9/T10 завершують процес) |

## Definition of Done

- [ ] `pytest tests/integration/test_db_inserts.py` проходить на ефемерному Postgres 16
- [ ] `insert_session` не використовує `SELECT` і не має цілі в `ON CONFLICT`
- [ ] `ruff`, `mypy src` без попереджень
- [ ] `db` залежить лише від `domain` (фундаментальний ADR-0002)
- [ ] every Hard Rule inlined above still holds
- [ ] lint + vet clean (`ruff check . && ruff format --check . && mypy src`)
