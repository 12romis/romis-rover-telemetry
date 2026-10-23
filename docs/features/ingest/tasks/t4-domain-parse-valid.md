---
id: T4
title: "Розібрати валідний звіт у ParsedSession (domain.parse_report, щасливий шлях)"
layer: "domain"
deps: []
blocks: ["T5"]
acs: ["AC-02", "AC-10", "AC-11", "AC-12"]
files_hint: ["src/rover_telemetry/domain/report.py", "tests/unit/test_report_valid.py"]
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
> **I want** щоб відсутні у звіті значення лишалися відсутніми, а виміряний нуль нулем
> **So that** «немає даних» не плутається з «виміряно нуль»
>
> — `spec.md §4, US-05, verbatim` · full text: [spec.md](../spec.md)

Перетворює байти повідомлення на `ParsedSession` з колонками `sessions`: відсутнє → `None`, нуль → 0, невідомі поля ігноруються, але повний вміст лишається в `raw`/`payload`.

## Inlined context

> │   └── report.py        # parse_report(topic, payload, received_at) -> ParsedSession | Rejection; без I/O
>
> — `sad.md §5, Internal decomposition, abridged` · full text: [sad.md](../sad.md)

> **Hard rule:** **`null` ≠ 0.** Відсутнє значення зберігається як `NULL` і показується як «немає даних»; нуль — виміряне значення. Агрегації не перетворюють `NULL` на нуль.
>
> — `constitution.md, №4, verbatim` · full text: [constitution.md](../../../constitution.md)

> **Hard rule:** **Часу сесії немає.** `received_at` ставить сервер; це верхня межа часу сесії. В інтерфейсі й документах він називається «отримано», ніколи «час сесії». Час створення не вигадується, доки в контракті немає відповідних полів.
>
> — `constitution.md, №5, verbatim` · full text: [constitution.md](../../../constitution.md)

> **Hard rule:** **Еволюція схеми.** Невідомі поля ігноруються; повний сирий JSON зберігається поруч із розібраними колонками. Несумісна зміна — лише з новим `schema_version`.
>
> — `constitution.md, №8, verbatim` · full text: [constitution.md](../../../constitution.md)

> **Hard rule:** **Простежуваність.** Кожен критерій приймання (AC) простежується до коду й тесту. Тести на розбір звіту використовують реальні звіти з `tests/fixtures/`.
>
> — `constitution.md, №15, verbatim` · full text: [constitution.md](../../../constitution.md)

> - Невідомі поля ігнорувати (еволюція без зламу); `schema_version` змінюється лише при несумісній зміні.
> - `null` зберігати як відсутнє значення, не підставляти нуль.
>
> — `contracts/events.md, «Правила для споживача», verbatim` · full text: [events.md](../../../contracts/events.md)

> Відсутнє значення — явний `null`, а не нуль. Одиниці — в назві поля.
> | `fw.dirty` | bool | збірка з незафіксованими змінами; **поле відсутнє**, якщо збірка цього не повідомила |
>
> — `contracts/events.md, «Поля», verbatim` · full text: [events.md](../../../contracts/events.md)

> **Chosen:** варіант 1. Для валідного звіту `raw` — точні байти повідомлення (за AC-05 не більше 1024, тож без обрізання); `payload jsonb` лишається для запитів і представлень.
>
> — `adr/0002, Decision outcome, abridged` · full text: [adr/0002-store-raw-message-bytes-next-to-parsed-columns.md](../adr/0002-store-raw-message-bytes-next-to-parsed-columns.md)

**Fallback:** insufficient or contradicted by the code → read the named file in full ([spec.md](../spec.md) · [sad.md](../sad.md) · [data-model.md](../data-model.md) · [adr/](../adr/)) and follow it. Do not guess.

## Data delta

Ім'я колонки = шлях поля контракту, крапка → підкреслення (`holds.min_mm` → `holds_min_mm`, `speed.left_avg_rpm` → `speed_left_avg_rpm`, `encoders.left` → `encoders_left`, `fw.dirty` → `fw_dirty`). Поля `ParsedSession` — це колонки `sessions` 1:1:

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `mac` | text | PK (частина 1), NOT NULL | Ідентифікатор ровера, 12 hex нижнім регістром (контракт, «Доставка»); збігається з топіком, перевіряє `domain` (`id_mismatch`) |
| `seq` | integer | PK (частина 2), NOT NULL | Номер сесії (контракт, «Ідентифікатор для дедублікації») |
| `schema_version` | integer | NOT NULL | Завжди 1 для збереженого: інші версії відхиляються (`unsupported_schema`, AC-07). Колонка потрібна, щоб майбутня міграція версій не вгадувала її з `payload` |
| `received_at` | timestamptz | NOT NULL | Час сервісу UTC на вході в callback (SAD §8 «Time»). Єдина часова мітка (AC-11). `DEFAULT` немає: значення ставить `domain`, до розбору |
| `raw` | bytea | NOT NULL | Точні байти повідомлення, ≤ 1024 (feature ADR-0002, AC-12) |
| `payload` | jsonb | NOT NULL | Розбір `raw` для запитів; невідомі поля лишаються тут і в `raw` (конституція №8) |
| `duration_ms` | integer | NULL | Контракт «Сесія». Відсутнє поле = `NULL`, не відхилення (AC-05) |
| `end_reason` | text | NULL | `disarm` / `failsafe_link_lost` / `failsafe_voltage` за контрактом; значення не обмежуються `CHECK`, бо нове значення не має ламати запис (US-07) |
| `voltage_start_mv` | integer | NULL | Контракт: `int \| null` |
| `voltage_end_mv` | integer | NULL | |
| `voltage_min_mv` | integer | NULL | |
| `holds_count` | integer | NULL | `holds.count`; 0 = виміряно «утримань не було», `NULL` = немає даних (AC-10) |
| `holds_total_ms` | integer | NULL | `holds.total_ms` |
| `holds_min_mm` | integer | NULL | `holds.min_mm`; `NULL`, якщо утримань не було |
| `holds_min_sensor` | text | NULL | `holds.min_sensor` |
| `holds_left_front` | integer | NULL | `holds.by_sensor.left_front` |
| `holds_front` | integer | NULL | `holds.by_sensor.front` |
| `holds_right_front` | integer | NULL | `holds.by_sensor.right_front` |
| `holds_rear` | integer | NULL | `holds.by_sensor.rear`. Лічильники зберігаються як надіслано, без перерахунку (AC-02) |
| `tof_control_off_ms` | integer | NULL | |
| `moving_ms` | integer | NULL | |
| `distance_cm` | integer | NULL | Контракт: `null`, якщо не було енкодера; 0 — виміряний нуль (AC-10) |
| `speed_left_avg_rpm` | double precision | NULL | Контракт: `number \| null` (дробові, приклад 88.4) |
| `speed_left_peak_rpm` | double precision | NULL | |
| `speed_right_avg_rpm` | double precision | NULL | |
| `speed_right_peak_rpm` | double precision | NULL | |
| `speed_imbalance_pct` | double precision | NULL | |
| `encoders_left` | boolean | NULL | `encoders.left` |
| `encoders_right` | boolean | NULL | `encoders.right` |
| `fw_version` | text | NULL | `fw.version` |
| `fw_git` | text | NULL | `fw.git` |
| `fw_dirty` | boolean | NULL | Контракт: поле відсутнє, якщо збірка не повідомила → `NULL` |
| `fw_idf` | text | NULL | `fw.idf` |

— `data-model.md §Entities, table sessions, verbatim` · full text: [data-model.md](../data-model.md)

## API contract

Internal — no API surface.

## Acceptance criteria

### AC-02 (US-01) — happy path

> **Given** два реальні звіти ровера з номерами 26 і 27 (тестові фікстури)
> **When** вони проходять розбір
> **Then** кожне значення збереженої сесії збігається зі звітом, зокрема лічильники утримань за датчиками лишаються такими, як надіслав ровер, без перерахунку
>
> — `spec.md §5, AC-02, verbatim` · full text: [spec.md](../spec.md)

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

### AC-12 (US-07) — happy path

> **Given** коректний звіт містить додаткові поля, яких контракт не описує
> **When** він надходить до сервісу приймання
> **Then** сесія зберігається за відомими полями, а повний початковий вміст звіту, зокрема додаткові поля, зберігається дослівно, без перетворень
>
> — `spec.md §5, AC-12, verbatim` · full text: [spec.md](../spec.md)

## Checklist

- [ ] У `src/rover_telemetry/domain/report.py` оголосити `@dataclass(frozen=True) ParsedSession` (поля = колонки `sessions`, `Optional` для всіх `NULL`-able) і `Rejection` (`topic`, `reason_code`, `reason_text`, `raw`, `raw_size`, `raw_truncated`, `received_at`); `Rejection` заповнює T5.
- [ ] Реалізувати `parse_report(topic: str, payload: bytes, received_at: datetime) -> ParsedSession | Rejection` для валідного звіту: вкладені `holds.*`, `holds.by_sensor.*`, `speed.*`, `encoders.*`, `fw.*` розгортаються в плоскі поля; відсутнє поле й явний `null` → `None`; `raw = payload`, `payload` = розібраний JSON як `dict`; `received_at` береться з аргументу, `domain` годинника не читає.
- [ ] `tests/unit/test_report_valid.py`: параметризовано за `tests/fixtures/session_seq26.json` і `session_seq27.json` — кожне значення `ParsedSession` дорівнює відповідному значенню JSON, лічильники `holds_*` без перерахунку (AC-02).
- [ ] Тести AC-10: звіт з `distance_cm: null` і `speed.*: null` та `moving_ms: 0` → `distance_cm is None`, `moving_ms == 0`; `fw.dirty` відсутнє → `fw_dirty is None`.
- [ ] Тест AC-11/AC-12: у `ParsedSession` немає поля часу, крім `received_at`; звіт із зайвим полем `extra: 1` розбирається, `raw` дорівнює вхідним байтам, `payload['extra'] == 1`.
- [ ] Типи: `mypy src` strict без попереджень; жодного імпорту з `db`/`ingest`/`web` (фундаментальний ADR-0002).

## Edge cases

| Case | Behaviour |
|---|---|
| `distance_cm: 0` у фікстурі seq 26 | Зберігається 0, не `None` (AC-10) |
| `holds.min_mm: null` | `holds_min_mm is None` |
| `fw.dirty` відсутнє | `fw_dirty is None` |
| Невідоме поле у звіті | Ігнорується в колонках; лишається в `raw` і `payload` (AC-12) |
| `speed.left_avg_rpm: 88.4` | `float` без округлення |
| Невалідний вхід | Не обробляється тут — гілки відхилення додає T5 |

## Definition of Done

- [ ] `pytest tests/unit/test_report_valid.py` проходить для фікстур seq 26 і 27
- [ ] 100 % значень фікстур збігаються з JSON (NFR «Точність розбору»)
- [ ] `ruff check`, `ruff format --check`, `mypy src` без попереджень
- [ ] `domain` не імпортує нічого з проєкту поза собою
- [ ] every Hard Rule inlined above still holds
- [ ] lint + vet clean (`ruff check . && ruff format --check . && mypy src`)
