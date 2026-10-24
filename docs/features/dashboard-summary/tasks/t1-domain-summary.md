---
id: T1
title: "Додати в domain типи виїзду, підсумки з Total(sum, missing) і класифікацію причини завершення"
layer: "domain"
deps: []
blocks: ["T2", "T3", "T4", "T6"]
acs: ["AC-01", "AC-04", "AC-07", "AC-11"]
files_hint: ["src/rover_telemetry/domain/dashboard.py", "tests/unit/test_dashboard_summary.py", "tests/conftest.py"]
owner: "12romis"
estimate: "M"
context_budget: "M"
status: "done"
step: ""
---

# T1 — Додати в domain типи виїзду, підсумки з Total(sum, missing) і класифікацію причини завершення

## Place in the sequence

- **Blocked by:** — · **Blocks:** T2 — Додати в domain хронологію виїздів із позначками номерів без виїзду, T3 — Додати читання одного знімка лише для читання (db/reading.py) і налаштування таймаутів web, T4 — Додати web/formatting.py: «отримано» за Києвом, одиниці, підписи причин, назва ровера, текст звіту, T6 — Побудувати сторінку dashboard.html: опис, вісім карток підсумків, стани empty і error · **Wave:** 1 (немає залежностей, стартує з першою хвилею).
- **Lane:** спільні файли з T10 (`tests/conftest.py`) — серіалізуються (порядок задає DAG).

## Why (user story)

> **As a** Глядач
> **I want** одразу побачити підсумки за всіма збереженими виїздами з коротким поясненням простою мовою
> **So that** без жодного контексту зрозуміти, що це за ровер і як він працює
>
> — `spec.md §4, US-01, verbatim` · full text: [spec.md](../spec.md)

> **As a** Власник ровера
> **I want** щоб значення, яких ровер не передав, показувалися як «немає даних», а виміряний нуль нулем
> **So that** не прийняти відсутність вимірювання за нульовий результат
>
> — `spec.md §4, US-04, verbatim` · full text: [spec.md](../spec.md)

Дає чисті функції, що з рядків одного знімка будують підсумки «сума лише за відомими + скільки без даних» і розпізнають причину завершення, — єдине місце, де живе правило «NULL ≠ 0».

## Inlined context

> Обраний підхід (рішення власника в інтерв'ю, `docs/idea-brief.md` §5, §7; розкладка підсумків — припущення цієї специфікації, §8): одна публічна сторінка лише для читання, зручна на телефоні. Угорі — короткий опис простою мовою й підсумки за всіма збереженими виїздами; нижче — таблиця виїздів від найновіших до найстаріших за номером сесії, де кожен рядок можна розгорнути до повного звіту. Усе, чого ровер не передав, показується як «немає даних», а не нулем; час подається як «отримано»; втрачені сесії видно.
>
> — `spec.md §1, committed approach, verbatim` · full text: [spec.md](../spec.md)

> **Hard rule:** **`null` ≠ 0.** Відсутнє значення зберігається як `NULL` і показується як «немає даних»; нуль — виміряне значення. Агрегації не перетворюють `NULL` на нуль.
>
> — `constitution.md, №4, verbatim` · full text: [constitution.md](../../../constitution.md)

> | NULL vs 0 | `NULL` → `None` у `domain` → «немає даних» (макрос, окремий вигляд); виміряний нуль показується як 0; підсумок = сума лише за відомими значеннями + кількість виїздів без даних, а якщо відомих немає, «немає даних»; уніфікована структура `Total(sum, missing)` для пробігу, часу руху й утримань | конституція №4, feature ADR-0001 |
>
> — `sad.md §8, NULL vs 0, verbatim` · full text: [sad.md](../sad.md)

> 1. **Один знімок читання, підсумки рахує `domain`** — запит сторінки відкриває одну транзакцію лише для читання, читає виїзди й облік пропусків, і чисті функції `domain` будують із цих самих рядків підсумки та список. Таблиця й підсумки узгоджені за побудовою, правило «`NULL` ≠ 0» живе в одному тестованому місці, нової міграції немає (QG-1, QG-3) — feature ADR-0001.
>
> — `sad.md §4, стратегічний вибір 1, verbatim` · full text: [sad.md](../sad.md)

> **Chosen:** варіант 1. Підсумки й таблиця будуються з одного набору рядків, тому узгоджені за побудовою; правило «сума лише за відомими значеннями + кількість без даних» живе в `domain` як `Total(sum, missing)` і тестується швидкими юніт-тестами на реальних фікстурах. Нова міграція не потрібна: `viewer` уже має `SELECT` на `sessions` і `session_gaps`. Це уточнення, а не скасування фундаментального ADR-0003: представлення лишаються способом агрегації для даних, яких сторінка не завантажує (графіки по днях у кроках 4–8). Свідомий відступ від його букви — `web` читає саму таблицю `sessions` (виїзди з `payload`, без `raw`), а не представлення; він записаний як Decision override у SAD §1 ¶4.
>
> — `adr/0001, Decision outcome, verbatim` · full text: [adr/0001](../adr/0001-compute-dashboard-summary-in-domain-from-one-read-only-snapshot.md)

> Прості шари за фундаментальним ADR-0002: чистий `domain` (підсумки, хронологія, класифікація причини завершення), `db` (читання сирим SQL), `web` (маршрут, шаблони, підписи, київський час). Новий модуль не створюється, змінюються наявні `domain`, `db`, `web`; міграцій і змін `ingest` немає. Правило залежностей: `domain` нічого не імпортує з проєкту, `db` залежить від `domain`, `web` від обох.
>
> — `sad.md §5, building block view, verbatim` · full text: [sad.md](../sad.md)

> | # | Підпис картки | Значення | Підпис під значенням |
> |---|---|---|---|
> | 1 | Виїздів | кількість збережених виїздів | — |
> | 2 | Пробіг | сума, м | «без даних у N з M виїздів» за правилом вище |
> | 3 | Час руху | сума, с/хв | те саме |
> | 4 | Утримань перед перешкодою | сума `holds.count` | те саме |
> | 5 | Кінцева напруга останнього виїзду | `voltage_end_mv` виїзду з найбільшим номером, В; без підміни попереднім, якщо її немає | «виїзд № N» |
> | 6 | Отримано востаннє (за київським часом) | найпізніше `received_at` | — |
> | 7 | Прошивка останнього виїзду | `fw.version` виїзду з найбільшим номером | — |
> | 8 | Втрачені сесії | кількість номерів без виїзду | — |
>
> — `screens.md SCR-01, таблиця підсумків, verbatim` · full text: [screens.md](../screens.md)

> - **Підсумок-сума (AC-07).** Сума лише за виїздами з даними; якщо ≥ 1 виїзд без даних — під значенням підпис «без даних у N з M виїздів»; якщо даних немає в жодному — значення «немає даних» (не 0), підпису немає. Правило однакове для пробігу, часу руху й утримань (`Total(sum, missing)`, `sad.md` §8).
>
> — `screens.md «Правила показу», підсумок-сума, verbatim` · full text: [screens.md](../screens.md)

> - **Причина завершення (AC-04).** `disarm` → «Роззброєння»; `failsafe_link_lost` → «Зникнення зв'язку з пультом»; `failsafe_voltage` → «Занизька напруга акумулятора»; інше значення → «Інша причина» (справжнє значення видно в SCR-02); `NULL` → «немає даних» (це не «інша причина»).
>
> — `screens.md «Правила показу», причина завершення, verbatim` · full text: [screens.md](../screens.md)

> «Виїздів 0» — виміряне число; решта карток — «немає даних» (AC-11). Таблиці виїздів немає, замість неї одне повідомлення.
>
> — `screens.md SCR-01 / empty, примітка, verbatim` · full text: [screens.md](../screens.md)

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

## API contract

Internal — no API surface.

## Acceptance criteria

### AC-01 — happy path

> **Given** серед збережених є кілька виїздів ровера
> **When** Глядач відкриває дашборд
> **Then** він бачить кількість виїздів, сумарний пробіг, сумарний час руху, кількість утримань перед перешкодами, кінцеву напругу останнього виїзду, час «отримано» останнього звіту, версію прошивки останнього виїзду та кількість втрачених сесій, кожне з підписом простою мовою та одиницею виміру
>
> — `spec.md §5, AC-01, verbatim` · full text: [spec.md](../spec.md)

### AC-04 — happy path

> **Given** причина завершення виїзду — роззброєння, зникнення зв'язку з пультом або занизька напруга акумулятора
> **When** Власник ровера дивиться рядок цього виїзду
> **Then** причина написана зрозумілою мовою, а причина, якої дашборд не знає, показана як «інша причина» без втрати самого значення в повному звіті
>
> — `spec.md §5, AC-04, verbatim` · full text: [spec.md](../spec.md)

### AC-07 — domain invariant violation

> **Given** частина виїздів не має пробігу
> **When** Глядач дивиться підсумки
> **Then** сума пробігу враховує лише виїзди з даними (час руху в контракті завжди заданий), поруч указано, у скількох виїздах даних немає, а якщо даних немає в жодному, підсумок показаний як «немає даних», а не нуль
>
> — `spec.md §5, AC-07, verbatim` · full text: [spec.md](../spec.md)

### AC-11 — happy path

> **Given** жодного виїзду ще не збережено
> **When** Глядач відкриває дашборд
> **Then** він бачить, що виїздів ще немає, кількість виїздів показана як нуль (це виміряне число), а решта підсумків як «немає даних», і сторінка лишається цілою
>
> — `spec.md §5, AC-11, verbatim` · full text: [spec.md](../spec.md)

## Checklist

- [ ] Тести спочатку — `tests/unit/test_dashboard_summary.py` на реальних фікстурах seq 26 і 27 (через `parse_report` → `StoredSession`), без Docker; фабрика `stored_session(...)` — у `tests/conftest.py`
- [ ] `src/rover_telemetry/domain/dashboard.py`: `StoredSession` (поля з Data delta; `None` для `NULL`), `GapNumber(mac, seq)`, `Total(sum: int | None, missing: int, total: int)`, `EndReason` (`DISARM`, `LINK_LOST`, `VOLTAGE`, `OTHER`) і `classify_end_reason(raw: str | None) -> EndReason | None`
- [ ] `build_summary(sessions, gaps) -> Summary`: кількість виїздів (0 — число), `Total` для пробігу (`distance_cm`), часу руху (`moving_ms`), утримань (`holds_count`); `last_voltage_end_mv` і `last_seq` — виїзду з найбільшим `seq` (потім за `mac`) без підміни попереднім; `last_received_at` — максимум `received_at`; `last_fw_version`; `lost` = `len(gaps)`, а для порожнього набору `None`
- [ ] Модуль без I/O й без імпортів з `db`/`web`/`ingest` (фундаментальний ADR-0002); `mypy --strict`, `ruff` без нових попереджень

## Edge cases

| Case | Behaviour |
|---|---|
| Виїздів немає | `sessions == 0`; усі `Total.sum` і `last_*`, `lost` — `None`; жодного нуля замість відсутнього (AC-11) |
| У жодного виїзду немає пробігу | `Total(sum=None, missing=N, total=N)` — «немає даних», не 0 (AC-07) |
| Частина виїздів без пробігу | `sum` — лише за відомими; `missing` = кількість без даних, `total` = усі виїзди (AC-07) |
| Виміряний нуль пробігу | `distance_cm == 0` входить у суму як 0 і не рахується в `missing` |
| Кінцева напруга останнього виїзду `NULL` | `last_voltage_end_mv is None`; попереднє значення не підставляється |
| Однаковий `seq` у різних `mac` | «останній» — за `(seq ↓, mac)`; порядок детермінований |
| Невідома причина завершення | `EndReason.OTHER`; сам рядок лишається в `StoredSession.end_reason` (AC-04) |
| `end_reason is None` | `classify_end_reason` повертає `None`, а не `OTHER` |
| Останнє «отримано» ≠ виїзд з найбільшим `seq` | `last_received_at` — максимум за всіма виїздами, а не за останнім номером |

## Definition of Done

- [ ] `pytest tests/unit/test_dashboard_summary.py` проходить: підсумки seq 26 + 27 (пробіг 0,17 м → `sum == 17`, утримань 1), випадок «без жодного пробігу», порожній набір, невідома причина
- [ ] для AC-01, AC-04, AC-07, AC-11 є принаймні по одному тесту, що називає AC у docstring
- [ ] модуль `domain/dashboard.py` не імпортує нічого з `db`, `web`, `ingest`
- [ ] кожне Hard Rule, процитоване вище, лишається дотриманим
- [ ] lint + type-check чисті (`ruff check . && ruff format --check . && mypy src`)
