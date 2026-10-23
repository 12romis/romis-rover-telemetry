---
id: T2
title: "Промотувати міграцію таблиці rejected як 0003"
layer: "migration"
deps: ["T1"]
blocks: ["T3", "T7"]
acs: ["AC-05", "AC-07"]
files_hint: ["docs/features/ingest/migrations/02_create_rejected.sql", "docs/features/ingest/migrations/02_create_rejected.rollback.sql", "migrations/", "tests/integration/test_migrations.py"]
owner: "12romis"
estimate: "S"
context_budget: "M"
status: "todo"
step: ""
---

## Why (user story)

> **As a** Власник ровера
> **I want** щоб повідомлення, яке не є коректним звітом, зберігалося окремо з причиною
> **So that** я бачу, що надійшло щось неправильне, і не втрачаю його вміст
>
> — `spec.md §4, US-03, verbatim` · full text: [spec.md](../spec.md)

Створює таблицю відхилених: кожна доставка — окремий запис, вміст дослівно в межах 1024 байт, позначка обрізання окремо.

## Inlined context

> **Hard rule:** **Надійність запису.** Підписник: QoS 1, фіксований client id, постійна сесія (`clean_session=false`). Підтвердження брокеру — лише після `COMMIT`. Невалідне повідомлення зберігається в таблицю відхилених і лише тоді підтверджується.
>
> — `constitution.md, №7, verbatim` · full text: [constitution.md](../../../constitution.md)

> **Hard rule:** **Канонічні файли.** `docs/constitution.md`, `docs/contracts/events.md` і вже застосовані міграції БД не змінюються без явної згоди власника; зміна схеми — нова міграція.
>
> — `constitution.md, №16, verbatim` · full text: [constitution.md](../../../constitution.md)

> **Chosen:** варіант 1. Для валідного звіту `raw` — точні байти повідомлення (за AC-05 не більше 1024, тож без обрізання); `payload jsonb` лишається для запитів і представлень. Для відхиленого `raw` — перші 1024 байти, `raw_size` — початковий розмір, `raw_truncated` — позначка обрізання (до ліміту не входить). Варіант 2 дає лише семантичну еквівалентність, варіант 3 губить повідомлення, що не є валідним UTF-8.
>
> — `adr/0002, Decision outcome, verbatim` · full text: [adr/0002-store-raw-message-bytes-next-to-parsed-columns.md](../adr/0002-store-raw-message-bytes-next-to-parsed-columns.md)

> | Reason codes | Фіксований перелік, перший спрацьований у порядку: `too_large`, `not_json`, `unknown_event`, `unsupported_schema`, `missing_id`, `id_mismatch`, `bad_type`; відсутність інших полів і явні `null` — не причина; перевірок діапазонів немає; точні значення колонки уточнює `data-model` | spec AC-05…AC-07 |
>
> — `sad.md §8, Reason codes, verbatim` · full text: [sad.md](../sad.md)

**Fallback:** insufficient or contradicted by the code → read the named file in full ([spec.md](../spec.md) · [sad.md](../sad.md) · [data-model.md](../data-model.md) · [adr/](../adr/)) and follow it. Do not guess.

## Data delta

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | bigint | PK, `GENERATED ALWAYS AS IDENTITY` | Сурогат: у відхилених немає природного ключа, кожна доставка дає окремий запис (AC-05, SAD §8 «ID strategy») |
| `topic` | text | NOT NULL | Топік доставки `rover/<mac>/session`; потрібен, бо `mac` з невалідного вмісту недовіряний (AC-06) |
| `reason_code` | text | NOT NULL | Один із: `too_large`, `not_json`, `unknown_event`, `unsupported_schema`, `missing_id`, `id_mismatch`, `bad_type` (SAD §8 «Reason codes»). Без `CHECK`: перелік може рости, а запис відхиленого не має падати |
| `reason_text` | text | NOT NULL | Причина простою мовою (AC-05) |
| `raw` | bytea | NOT NULL | Перші ≤ 1024 байти повідомлення, дослівно (ADR-0002). `bytea`, бо сміття може бути не UTF-8 і містити нуль-байти |
| `raw_size` | integer | NOT NULL | Початковий розмір повідомлення в байтах |
| `raw_truncated` | boolean | NOT NULL | Позначка обрізання; до ліміту 1024 не входить (AC-07). Явного `DEFAULT` немає: значення ставить `domain` |
| `received_at` | timestamptz | NOT NULL | Час «отримано» (AC-05) |

**Staged пара:** `docs/features/ingest/migrations/02_create_rejected.sql` / `.rollback.sql` → `migrations/0003_create_rejected.sql` / `.rollback.sql`; `-- depends: 0002_create_sessions`.

— `data-model.md §Entities, table rejected, verbatim` · full text: [data-model.md](../data-model.md)

## API contract

Internal — no API surface.

## Acceptance criteria

### AC-05 (US-03) — error

> **Given** надійшло повідомлення, яке не є коректним звітом: його не можна прочитати як звіт, воно перевищує 1024 байти (межа з контракту), має невідомий тип події, відоме поле має неправильний тип, немає ідентифікатора ровера чи номера сесії. Відсутність інших полів і явне порожнє значення не є підставою для відхилення, а перевірок діапазонів значень немає
> **When** сервіс приймання його отримує
> **Then** повідомлення зберігається дослівно серед відхилених із причиною простою мовою й часом «отримано», сесія не створюється, і лише після цього отримання підтверджується брокеру; кожна повторна доставка такого повідомлення дає окремий запис
>
> — `spec.md §5, AC-05, verbatim` · full text: [spec.md](../spec.md)

### AC-07 (US-03) — error

> **Given** надійшов звіт з версією схеми, відмінною від поточної (1)
> **When** сервіс приймання його отримує
> **Then** звіт зберігається серед відхилених з причиною «непідтримана версія схеми», а його вміст зберігається дослівно в межах 1024 байт (понад ліміт обрізається по байтах, позначка про обрізання зберігається окремо й до ліміту не входить), щоб обробити його, коли версію буде підтримано
>
> — `spec.md §5, AC-07, verbatim` · full text: [spec.md](../spec.md)

## Checklist

- [ ] Скопіювати staged `02_create_rejected*.sql` у `migrations/0003_create_rejected.sql` і `.rollback.sql`; у `-- depends:` поставити `0002_create_sessions`, службові рядки «Промоція» прибрати.
- [ ] Розширити `tests/integration/test_migrations.py`: застосовано три міграції; відкат `0003` лишає `sessions`.
- [ ] Тест: два однакові рядки `rejected` вставляються як два запис (немає ключа дедублікації, AC-05); `raw_truncated` і `raw_size` зберігаються окремо від `raw`; `raw` приймає нуль-байти й не-UTF-8 (`bytea`).

## Edge cases

| Case | Behaviour |
|---|---|
| Повторна доставка того самого сміття | Окремий запис з новим `id` (AC-05) |
| Вміст не UTF-8 або з нуль-байтами | Зберігається в `bytea` без втрат |
| `id` ставить БД | `GENERATED ALWAYS`: явна вставка `id` заборонена — `INSERT` не називає колонку `id` |

## Definition of Done

- [ ] тести з чеклиста проходять
- [ ] `0003_create_rejected` застосовується й відкочується чисто, `sessions` не зачеплено
- [ ] staged migration is promoted to live `migrations/`, then applies and reverts cleanly
- [ ] every Hard Rule inlined above still holds
- [ ] lint + vet clean (`ruff check . && ruff format --check . && mypy src`)
