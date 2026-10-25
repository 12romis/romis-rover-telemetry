---
id: T2
title: "Читати в read_snapshot нові колонки sessions для графіків тим самим знімком"
layer: "infra"
deps: ["T1"]
blocks: ["T17"]
acs: ["AC-22", "AC-23"]
files_hint: ["src/rover_telemetry/db/reading.py", "tests/integration/test_reading.py"]
owner: "12romis"
estimate: "S"
context_budget: "M"
status: "done"
step: "COMMIT"
---

<!-- Принцип файлу: вбудований зріз, що потрібен задачі, з підписом джерела; посилання — запасний шлях. Кожен шматок має підпис `<file> §<section>, <id>, verbatim|abridged`. Джерело завжди важливіше за вбудовану копію. -->

# T2 — Читати в read_snapshot нові колонки sessions для графіків тим самим знімком

## Place in the sequence

- **Blocked by:** T1 — Розширити StoredSession полями графіків і додати domain/charts.py: константи з джерелами, Value/Absent/AbsentReason, вісь за номером сесії з порожніми місцями · **Blocks:** T17 — Додати інтеграційні тести сторінки на реальному Postgres: свіжість, дубль і відхилене, порожнє сховище, лише читання, затримка на 1000 виїздів · **Wave:** 2 (після найпізнішої залежності).
- **Lane:** own lane.

## Why (user story)

> **As a** Власник ровера
> **I want** щоб новий збережений виїзд з'являвся на всіх графіках після оновлення сторінки, а дублі й відхилені повідомлення на них не потрапляли
> **So that** бачити результат останнього виїзду одразу й не бачити зайвого
>
> — `spec.md §4, US-11, verbatim` · full text: [spec.md](../spec.md)

Цей крок доставляє в `domain` значення, потрібні графікам, з того самого знімка, що й підсумки, тож новий виїзд видно скрізь одночасно.

## Inlined context

> **Chosen:** варіант 1. Підсумки, таблиця і графіки будуються з одного набору рядків; блок, що не збудувався, ловиться `try/except` на межі `web` окремо для кожного блоку й замінюється повідомленням (AC-19). Новий код не додає маршрутів, заголовків безпеки чи `fetch`; стану «завантаження» немає. Дані кожного блоку — `<script type="application/json">` через `|tojson`.
>
> — `adr/0001, Decision outcome, abridged` · full text: [adr/0001-embed-chart-data-in-the-page-from-one-read-only-snapshot.md](../adr/0001-embed-chart-data-in-the-page-from-one-read-only-snapshot.md)

> Додавання колонок до `StoredSession` і `_SESSION_COLUMNS` зсуває позиційне створення `StoredSession(*row)` — Mitigation: нові поля в кінці зі значенням за замовчуванням; інтеграційний тест `test_reading.py` на всіх колонках.
>
> — `sad.md §11, Risks (останній рядок), abridged` · full text: [sad.md](../sad.md)

> Web→Db: прочитати виїзди й номери без виїзду (знімок лише для читання; вибрати виїзди з полями графіків і номери з session_gaps) → Web→Domain: порахувати підсумки, хронологію і ряди трьох блоків → сторінка з даними блоків усередині → браузер запитує `charts.js` і `echarts.min.js` зі свого вузла → Charts: прочитати дані кожного блоку й намалювати графік. Нових запитів за даними немає, дотик показує значення з уже наявних даних.
>
> — `sad.md §6, Critical flow 1 (AC-01, AC-05, AC-10, AC-15, AC-22), abridged` · full text: [sad.md](../sad.md)

**To the executing agent:** працюй із вбудованого; якщо зріз недостатній, суперечить коду чи застарів — відкрий названий файл і дій за ним ([spec.md](../spec.md) · [sad.md](../sad.md) · [screens.md](../screens.md) · [adr/](../adr/)). Не вигадуй відсутнього.

## Data delta

| Column | Type | Constraints | Change |
|---|---|---|---|
| `holds_min_mm` | `integer` | nullable | read-only (додається до `SELECT`) |
| `holds_min_sensor` | `text` | nullable | read-only (додається до `SELECT`) |
| `holds_left_front` | `integer` | nullable | read-only (додається до `SELECT`) |
| `holds_front` | `integer` | nullable | read-only (додається до `SELECT`) |
| `holds_right_front` | `integer` | nullable | read-only (додається до `SELECT`) |
| `holds_rear` | `integer` | nullable | read-only (додається до `SELECT`) |
| `tof_control_off_ms` | `integer` | nullable | read-only (додається до `SELECT`) |
| `speed_left_avg_rpm` | `double precision` | nullable | read-only (додається до `SELECT`) |
| `speed_left_peak_rpm` | `double precision` | nullable | read-only (додається до `SELECT`) |
| `speed_right_avg_rpm` | `double precision` | nullable | read-only (додається до `SELECT`) |
| `speed_right_peak_rpm` | `double precision` | nullable | read-only (додається до `SELECT`) |
| `speed_imbalance_pct` | `double precision` | nullable | read-only (додається до `SELECT`) |
| `encoders_left` | `boolean` | nullable | read-only (додається до `SELECT`) |
| `encoders_right` | `boolean` | nullable | read-only (додається до `SELECT`) |

— `migrations/0002_create_sessions.sql, table sessions, abridged` (окремого data-model.md у фічі немає: міграції, ролі й права не змінюються; `viewer` має `SELECT` на `sessions`)

## API contract

Internal — no API surface.

## Acceptance criteria

### AC-22 — cross-context

> **Given** сервіс приймання щойно зберіг новий виїзд
> **When** Власник ровера оновлює сторінку
> **Then** новий виїзд стоїть на своєму номері в кожному з трьох блоків, а підсумки його враховують
>
> — `spec.md §5, AC-22, verbatim` · full text: [spec.md](../spec.md)

### AC-23 — cross-context

> **Given** ровер повторно надіслав уже збережений звіт, а також є відхилене повідомлення
> **When** Глядач дивиться графіки
> **Then** повтор не додає другої точки чи стовпця на жодному графіку, а відхилене повідомлення виїздом не вважається і на графіках не з'являється, окрім того, що його номер сесії (якщо він був) лишається порожнім місцем на осі, як будь-який номер без виїзду
>
> — `spec.md §5, AC-23, verbatim` · full text: [spec.md](../spec.md)

## Checklist

- [ ] Дописати нові колонки в **кінець** `_SESSION_COLUMNS` (після `payload`) у тому самому порядку, що й нові поля `StoredSession` (T1) — `src/rover_telemetry/db/reading.py`. `_SELECT_GAPS`, ізоляція `REPEATABLE READ` + `READ ONLY` і `statement_timeout` не змінюються.
- [ ] Інтеграційний тест на реальному Postgres: вставити виїзд із усіма колонками та виїзд із `NULL` у всіх нових колонках; перевірити, що значення збігаються, а `NULL` лишається `None` (не `0`, не `False`) — `tests/integration/test_reading.py`.
- [ ] У тому ж файлі: дубль `(mac, seq)` не дає другого виїзду; запис у таблицю `rejected` не потрапляє в `Snapshot.sessions` (AC-23).

## Edge cases

| Case | Behaviour |
|---|---|
| `encoders_left = false` | читається як `False`, не `None`; `NULL` читається як `None` (різні випадки) |
| `speed_*` = `0.0` | читається як `0.0` (виміряний нуль), а не `None` |
| Повторна вставка того самого `(mac, seq)` | `ON CONFLICT DO NOTHING` — у знімку один рядок (AC-23) |
| Відхилене повідомлення | живе в `rejected`; `read_snapshot` його не читає — номер лишається порожнім слотом осі |

## Definition of Done

- [ ] інтеграційний тест `test_reading.py` на всіх колонках проходить (потрібен Docker)
- [ ] роль `viewer` лишається єдиною, транзакція `READ ONLY`: нових прав у міграціях немає
- [ ] `StoredSession(*row)` збігається з порядком колонок (тест падає при розсинхроні)
- [ ] кожне правило з розділу «Inlined context» (Hard Rules, конституція №4) досі виконується
- [ ] lint + vet чисті
