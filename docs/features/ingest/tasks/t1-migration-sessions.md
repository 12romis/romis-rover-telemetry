---
id: T1
title: "Промотувати міграцію таблиці sessions у live migrations/ як 0002"
layer: "migration"
deps: []
blocks: ["T2"]
acs: ["AC-04", "AC-10", "AC-11"]
files_hint: ["docs/features/ingest/migrations/01_create_sessions.sql", "docs/features/ingest/migrations/01_create_sessions.rollback.sql", "migrations/", "tests/conftest.py", "tests/integration/test_migrations.py"]
owner: "12romis"
estimate: "S"
context_budget: "M"
status: "done"
step: "COMMIT"
---

## Why (user story)

> **As a** Власник ровера
> **I want** щоб відсутні у звіті значення лишалися відсутніми, а виміряний нуль нулем
> **So that** «немає даних» не плутається з «виміряно нуль»
>
> — `spec.md §4, US-05, verbatim` · full text: [spec.md](../spec.md)

Створює таблицю, в якій відсутнє значення — `NULL`, виміряний нуль — нуль, єдина часова мітка — `received_at`, а унікальність номера діє лише в межах ровера.

## Inlined context

> Обраний підхід (прийнято власником в інтерв'ю, `docs/idea-brief.md` §7): окремий фоновий сервіс-підписник приймає кожен звіт, перевіряє його за контрактом і зберігає або як сесію, або, якщо звіт невалідний, як відхилений із причиною; брокеру отримання підтверджується лише після збереження.
>
> — `spec.md §1, committed approach, abridged` · full text: [spec.md](../spec.md)

> **Hard rule:** **`null` ≠ 0.** Відсутнє значення зберігається як `NULL` і показується як «немає даних»; нуль — виміряне значення. Агрегації не перетворюють `NULL` на нуль.
>
> — `constitution.md, №4, verbatim` · full text: [constitution.md](../../../constitution.md)

> **Hard rule:** **Часу сесії немає.** `received_at` ставить сервер; це верхня межа часу сесії. В інтерфейсі й документах він називається «отримано», ніколи «час сесії». Час створення не вигадується, доки в контракті немає відповідних полів.
>
> — `constitution.md, №5, verbatim` · full text: [constitution.md](../../../constitution.md)

> **Hard rule:** **Канонічні файли.** `docs/constitution.md`, `docs/contracts/events.md` і вже застосовані міграції БД не змінюються без явної згоди власника; зміна схеми — нова міграція.
>
> — `constitution.md, №16, verbatim` · full text: [constitution.md](../../../constitution.md)

> | Authentication / AuthZ | Три облікові записи брокера (`RomisRover` лише `write rover/+/session`, `rover-ingest` лише `read`, `rover-viewer` лише `read`) і три ролі Postgres (`owner` — міграції, `ingest` — лише `INSERT` на `sessions`, `rejected`, `viewer` — лише `SELECT`); `ingest` не читає, не змінює, не видаляє | конституція №10, рішення власника №5, feature ADR-0003, ADR-0005 |
>
> — `sad.md §8, Authentication / AuthZ, verbatim` · full text: [sad.md](../sad.md)

> **Chosen:** варіант 1. Роль `ingest` має лише `INSERT` на `sessions` і `rejected`. Безпека варіанту тримається на тому, що `sessions` має рівно одне обмеження унікальності, первинний ключ `(mac, seq)` (міграція і тест це перевіряють), тож «будь-який конфлікт» означає «дубль». Варіант 2 віддає ролі читання ключів (мінімальне, але розширення прав), варіант 3 вимагає повного `SELECT` і має гонку між перевіркою й вставкою.
>
> — `adr/0005, Decision outcome, verbatim` · full text: [adr/0005-insert-sessions-with-on-conflict-do-nothing-without-target.md](../adr/0005-insert-sessions-with-on-conflict-do-nothing-without-target.md)

> - Ролі для інтеграційних тестів: фікстура створює `ingest` і `viewer` до застосування міграцій (GRANT потребує існування ролей, SAD §7 крок 1).
>
> — `data-model.md §Test fixtures, verbatim` · full text: [data-model.md](../data-model.md)

**Fallback:** insufficient or contradicted by the code → read the named file in full ([spec.md](../spec.md) · [sad.md](../sad.md) · [data-model.md](../data-model.md) · [adr/](../adr/)) and follow it. Do not guess.

## Data delta

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `mac` | text | PK (частина 1), NOT NULL | Ідентифікатор ровера, 12 hex нижнім регістром (контракт, «Доставка»); збігається з топіком, перевіряє `domain` (`id_mismatch`) |
| `seq` | integer | PK (частина 2), NOT NULL | Номер сесії (контракт, «Ідентифікатор для дедублікації») |
| `schema_version` | integer | NOT NULL | Завжди 1 для збереженого: інші версії відхиляються (`unsupported_schema`, AC-07). Колонка потрібна, щоб майбутня міграція версій не вгадувала її з `payload` |
| `received_at` | timestamptz | NOT NULL | Час сервісу UTC на вході в callback (SAD §8 «Time»). Єдина часова мітка (AC-11). `DEFAULT` немає: значення ставить `domain`, до розбору |
| `raw` | bytea | NOT NULL | Точні байти повідомлення, ≤ 1024 (feature ADR-0002, AC-12) |
| `payload` | jsonb | NOT NULL | Розбір `raw` для запитів; невідомі поля лишаються тут і в `raw` (конституція №8) |
| `holds_count` | integer | NULL | `holds.count`; 0 = виміряно «утримань не було», `NULL` = немає даних (AC-10) |
| `distance_cm` | integer | NULL | Контракт: `null`, якщо не було енкодера; 0 — виміряний нуль (AC-10) |

Решта колонок (`duration_ms` … `fw_idf`) — усі `NULL`-able за контрактом; повний перелік — у staged `01_create_sessions.sql`.

**Staged пара:** `docs/features/ingest/migrations/01_create_sessions.sql` / `01_create_sessions.rollback.sql` → `migrations/0002_create_sessions.sql` / `.rollback.sql`.

— `data-model.md §Entities, table sessions, abridged` · full text: [data-model.md](../data-model.md)

## API contract

Internal — no API surface.

## Acceptance criteria

### AC-04 (US-02) — domain invariant

> **Given** серед збережених є сесія ровера A з номером N
> **When** надходить коректний звіт іншого ровера B з тим самим номером N
> **Then** зберігається нова сесія ровера B, бо унікальність номера діє лише в межах одного ровера
>
> — `spec.md §5, AC-04, verbatim` · full text: [spec.md](../spec.md)

### AC-10 (US-05) — domain invariant

> **Given** надійшов звіт, у якому пробіг і швидкості борту відсутні, а в іншому полі виміряно нуль
> **When** сесію збережено
> **Then** збережені дані розрізняють відсутні значення (позначені як «немає даних») і виміряний нуль, а відсутні значення ніде не підставляються нулем
>
> — `spec.md §5, AC-10, verbatim` · full text: [spec.md](../spec.md)

### AC-11 (US-06) — happy path

> **Given** серед збережених є сесія
> **When** Власник ровера перевіряє, які часові відомості в ній збережено
> **Then** там є лише час «отримано», встановлений сервером, і жодного часу створення чи початку сесії
>
> — `spec.md §5, AC-11, verbatim` · full text: [spec.md](../spec.md)

## Checklist

- [ ] Скопіювати staged `01_create_sessions.sql` і `.rollback.sql` у `migrations/0002_create_sessions.sql` і `migrations/0002_create_sessions.rollback.sql`; `-- depends: 0001_init` лишити, рядки «Промоція (implement)» прибрати.
- [ ] У `tests/conftest.py` у фікстурі `postgres_url` створити ролі `ingest` і `viewer` (`CREATE ROLE … LOGIN PASSWORD …` для тестових паролів) одразу після готовності Postgres — до будь-яких міграцій.
- [ ] У `tests/integration/test_migrations.py` оновити очікування: тепер застосовано `0001_init`, `0002_create_sessions`; застосування й відкат проходять чисто.
- [ ] Додати інтеграційні тести: (а) два різні `mac` з однаковим `seq` вставляються (AC-04); (б) рядок з усіма `NULL`-able колонками `NULL` і окремий із нулями зберігаються й розрізняються (AC-10); (в) у `information_schema.columns` для `sessions` немає жодної колонки часу, крім `received_at` (AC-11); (г) `sessions` має рівно одне обмеження унікальності — PK `(mac, seq)` (ADR-0005).

## Edge cases

| Case | Behaviour |
|---|---|
| Той самий `seq`, інший `mac` | Обидва рядки зберігаються: ключ складений `(mac, seq)` (AC-04) |
| Той самий `(mac, seq)` вдруге | `INSERT … ON CONFLICT DO NOTHING` дає 0 рядків (деталі — T7) |
| Ролі `ingest`/`viewer` ще не існують | `GRANT` у міграції падає; це очікувано — ролі створюються до міграції (sad §7, крок 1) |
| Відкат | `DROP TABLE IF EXISTS sessions` разом із правами; після відкату `_yoyo_migration` має лише `0001_init` |

## Definition of Done

- [ ] інтеграційні тести з чеклиста проходять (`pytest -m integration`)
- [ ] міграція `0002_create_sessions` застосовується й відкочується чисто
- [ ] `sessions` має рівно одне обмеження унікальності
- [ ] staged migration is promoted to live `migrations/`, then applies and reverts cleanly
- [ ] every Hard Rule inlined above still holds
- [ ] lint + vet clean (`ruff check . && ruff format --check . && mypy src`)
