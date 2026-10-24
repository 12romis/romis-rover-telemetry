---
id: T8
title: "Перевірити ролі Postgres і облік втрат session_gaps"
layer: "tests"
deps: ["T3", "T7"]
blocks: ["T11"]
acs: ["AC-08", "AC-09", "AC-15", "AC-16"]
files_hint: ["tests/integration/test_roles.py", "tests/integration/test_session_gaps.py", "tests/conftest.py"]
owner: "12romis"
estimate: "M"
context_budget: "M"
status: "done"
step: "COMMIT"
---

## Why (user story)

> **As a** Власник ровера
> **I want** бачити, які номери сесій ровера не дійшли
> **So that** пропуски не виглядають як «ровер просто не їздив»
>
> — `spec.md §4, US-04, verbatim` · full text: [spec.md](../spec.md)

> **As a** Оператор сервера
> **I want** щоб ровер, сервіс приймання й дашборд мали лише ті права, що потрібні для їхньої ролі
> **So that** витік одного пароля не дозволяє підробити звіт чи змінити збережені дані
>
> — `spec.md §4, US-08, verbatim` · full text: [spec.md](../spec.md)

Доводить, що представлення дає правильний облік за довільного порядку доставки, а права `ingest` (лише вставка) і `viewer` (лише читання) справді діють.

## Inlined context

> **Chosen:** варіант 1. Облік завжди відповідає збереженим даним: запізніла сесія сама зникає з пропусків, менший номер сам зсуває початок. Роль `viewer` читає представлення, роль `ingest` про нього не знає. Варіант 2 потребує оновлень і тригерів для ролі, що лише дописує; варіант 3 розмазує правило між шарами і не дає Власнику ровера готового обліку в сховищі (AC-08).
>
> — `adr/0004, Decision outcome, verbatim` · full text: [adr/0004-compute-lost-sessions-in-sql-view-from-lowest-stored-seq.md](../adr/0004-compute-lost-sessions-in-sql-view-from-lowest-stored-seq.md)

> | Authentication / AuthZ | Три облікові записи брокера (`RomisRover` лише `write rover/+/session`, `rover-ingest` лише `read`, `rover-viewer` лише `read`) і три ролі Postgres (`owner` — міграції, `ingest` — лише `INSERT` на `sessions`, `rejected`, `viewer` — лише `SELECT`); `ingest` не читає, не змінює, не видаляє | конституція №10, рішення власника №5, feature ADR-0003, ADR-0005 |
>
> — `sad.md §8, Authentication / AuthZ, verbatim` · full text: [sad.md](../sad.md)

> **Hard rule:** **Найменші права.** Окремі облікові записи брокера (ровер — лише запис у `rover/+/session`; ingest — лише читання) і окремі ролі Postgres (ingest — лише вставка; дашборд — лише читання).
>
> — `constitution.md, №10, verbatim` · full text: [constitution.md](../../../constitution.md)

> Синтетичні набори для `session_gaps` (28, 29, 31; зсув початку; запізніла 30; два `mac` з однаковим `seq`) будуються в тесті SQL-представлення; значення `mac` — довільні 12 hex (`aabbccddeeff`), без реальних даних.
>
> — `data-model.md §Test fixtures, abridged` · full text: [data-model.md](../data-model.md)

> **Інваріант безпеки (feature ADR-0005):** другого `UNIQUE` не додавати — `ON CONFLICT DO NOTHING` без цілі інакше мовчки трактуватиме його конфлікти як дублі; перевіряє тест на єдине обмеження.
>
> — `data-model.md §Entities, table sessions, Constraints, verbatim` · full text: [data-model.md](../data-model.md)

**Fallback:** insufficient or contradicted by the code → read the named file in full ([spec.md](../spec.md) · [sad.md](../sad.md) · [data-model.md](../data-model.md) · [adr/](../adr/)) and follow it. Do not guess.

## Data delta

| Column | Type | Notes |
|---|---|---|
| `mac` | text | Ровер |
| `seq` | bigint | Номер втраченої сесії |

— `data-model.md §Entities, view session_gaps, verbatim` · full text: [data-model.md](../data-model.md)

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

- [ ] `tests/integration/test_session_gaps.py` (сесії вставляються через `insert_session` під роллю `ingest`, читання `session_gaps` — під `viewer`): (а) 28, 29, 31 → `{30}`, сесії до 28 не втрачені (AC-08); (б) після вставки 30 після 31 і 32 → пусто (AC-09); (в) надходить 25 → початок зсувається, втрачено 26, 27 (AC-08, flow 5); (г) два `mac` з однаковим `seq` не змішуються.
- [ ] `tests/integration/test_roles.py`: `viewer` не може `INSERT`/`UPDATE`/`DELETE` на `sessions` і `rejected` (AC-15); `ingest` не може `UPDATE`/`DELETE`/`SELECT` на `sessions` і `rejected`, лише `INSERT` (AC-16, сервіс-частина); `viewer` читає `session_gaps`.
- [ ] Перевірка збережених даних без змін після відмов (рядок до і після відмови однаковий).
- [ ] У `tests/conftest.py` винести хелпери з'єднання під ролями `ingest`/`viewer`, якщо їх ще немає (без дублювання з T1).

## Edge cases

| Case | Behaviour |
|---|---|
| Порожня `sessions` | `session_gaps` порожнє |
| Менший номер надійшов пізніше | Початок обліку зсувається до нього (AC-08) |
| Запізніла сесія в межах діапазону | Зникає з пропусків (AC-09) |
| `viewer` намагається `DELETE` | `InsufficientPrivilege`, дані без змін (AC-15) |
| `ingest` намагається `UPDATE`/`DELETE` | `InsufficientPrivilege`, дані без змін (AC-16) |

## Definition of Done

- [ ] обидва файли тестів проходять (`pytest -m integration`)
- [ ] перевірка прав — мінімум по одному негативному тесту на кожну пару «роль, дія»: `viewer` INSERT/UPDATE/DELETE, `ingest` SELECT/UPDATE/DELETE
- [ ] `ruff`, `ruff format --check` без попереджень
- [ ] every Hard Rule inlined above still holds
- [ ] lint + vet clean (`ruff check . && ruff format --check . && mypy src`)
