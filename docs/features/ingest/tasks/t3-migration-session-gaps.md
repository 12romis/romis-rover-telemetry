---
id: T3
title: "Промотувати міграцію представлення session_gaps як 0004"
layer: "migration"
deps: ["T2"]
blocks: ["T8"]
acs: ["AC-08", "AC-09"]
files_hint: ["docs/features/ingest/migrations/03_create_session_gaps.sql", "docs/features/ingest/migrations/03_create_session_gaps.rollback.sql", "migrations/", "tests/integration/test_migrations.py"]
owner: "12romis"
estimate: "S"
context_budget: "M"
status: "todo"
step: ""
---

## Why (user story)

> **As a** Власник ровера
> **I want** бачити, які номери сесій ровера не дійшли
> **So that** пропуски не виглядають як «ровер просто не їздив»
>
> — `spec.md §4, US-04, verbatim` · full text: [spec.md](../spec.md)

Дає готовий облік втрат у сховищі. Поведінку на синтетичних даних перевіряє T8; тут — що представлення створюється й відкочується.

## Inlined context

> **Hard rule:** **Дедублікація за `(mac, seq)`.** Запис — `ON CONFLICT DO NOTHING`. Пропуск у `seq` для одного `mac` — втрачена сесія, її показують, а не приховують.
>
> — `constitution.md, №6, verbatim` · full text: [constitution.md](../../../constitution.md)

> **Hard rule:** **Канонічні файли.** `docs/constitution.md`, `docs/contracts/events.md` і вже застосовані міграції БД не змінюються без явної згоди власника; зміна схеми — нова міграція.
>
> — `constitution.md, №16, verbatim` · full text: [constitution.md](../../../constitution.md)

> **Chosen:** варіант 1. Облік завжди відповідає збереженим даним: запізніла сесія сама зникає з пропусків, менший номер сам зсуває початок. Роль `viewer` читає представлення, роль `ingest` про нього не знає. Варіант 2 потребує оновлень і тригерів для ролі, що лише дописує; варіант 3 розмазує правило між шарами і не дає Власнику ровера готового обліку в сховищі (AC-08).
>
> — `adr/0004, Decision outcome, verbatim` · full text: [adr/0004-compute-lost-sessions-in-sql-view-from-lowest-stored-seq.md](../adr/0004-compute-lost-sessions-in-sql-view-from-lowest-stored-seq.md)

> Логіка (ADR-0004): для кожного `mac` діапазон `generate_series(min(seq), max(seq))` мінус збережені `seq`. Початок обліку — найменший збережений `seq` (AC-08); запізніла сесія сама зникає з пропусків (AC-09); менший номер сам зсуває початок. Нічого не зберігається, роль `ingest` про представлення не знає.
>
> — `data-model.md §Entities, view session_gaps, verbatim` · full text: [data-model.md](../data-model.md)

**Fallback:** insufficient or contradicted by the code → read the named file in full ([spec.md](../spec.md) · [sad.md](../sad.md) · [data-model.md](../data-model.md) · [adr/](../adr/)) and follow it. Do not guess.

## Data delta

| Column | Type | Notes |
|---|---|---|
| `mac` | text | Ровер |
| `seq` | bigint | Номер втраченої сесії |

**Права:** `viewer` — `SELECT`. **Staged пара:** `docs/features/ingest/migrations/03_create_session_gaps.sql` / `.rollback.sql` → `migrations/0004_create_session_gaps.sql` / `.rollback.sql`; `-- depends: 0003_create_rejected`.

— `data-model.md §Entities, view session_gaps, abridged` · full text: [data-model.md](../data-model.md)

## API contract

Internal — no API surface.

## Acceptance criteria

### AC-08 (US-04) — happy path

> **Given** для ровера збережено сесії з номерами 28, 29 і 31
> **When** Власник ровера запитує готовий облік втрат у сховищі (показ на дашборді не входить у цю фічу)
> **Then** облік повертає сесію 30 як втрачену; початком обліку є найменший збережений номер ровера, тож сесії до нього (наприклад, 1–27) втраченими не вважаються, а якщо пізніше надійде менший номер, початок обліку зсувається до нього
>
> — `spec.md §5, AC-08, verbatim` · full text: [spec.md](../spec.md)

### AC-09 (US-04) — domain invariant

> **Given** сесія 30 показана як втрачена
> **When** звіт 30 надходить пізніше за звіти 31 і 32 (порядок отримання довільний)
> **Then** сесія 30 зберігається і більше не вважається втраченою
>
> — `spec.md §5, AC-09, verbatim` · full text: [spec.md](../spec.md)

## Checklist

- [ ] Скопіювати staged `03_create_session_gaps*.sql` у `migrations/0004_create_session_gaps.sql` і `.rollback.sql`; `-- depends: 0003_create_rejected`, службові рядки прибрати.
- [ ] Розширити `tests/integration/test_migrations.py`: застосовано чотири міграції; відкат `0004` прибирає лише представлення; повний відкат лишає `_yoyo_migration` порожньою.

## Edge cases

| Case | Behaviour |
|---|---|
| `sessions` порожня | Представлення повертає 0 рядків |
| Один збережений номер | Діапазон з одного елемента, пропусків немає |
| `seq` як `integer` у таблиці, `bigint` у представленні | `generate_series` працює над `bigint`; приведення вже в staged SQL |

## Definition of Done

- [ ] `0004_create_session_gaps` застосовується й відкочується чисто
- [ ] поведінка представлення — AC-08/AC-09 — перевіряється в T8
- [ ] staged migration is promoted to live `migrations/`, then applies and reverts cleanly
- [ ] every Hard Rule inlined above still holds
- [ ] lint + vet clean (`ruff check . && ruff format --check . && mypy src`)
