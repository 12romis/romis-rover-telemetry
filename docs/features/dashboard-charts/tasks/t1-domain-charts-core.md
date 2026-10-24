---
id: T1
title: "Розширити StoredSession полями графіків і додати domain/charts.py: константи з джерелами, Value/Absent/AbsentReason, вісь за номером сесії з порожніми місцями"
layer: "domain"
deps: []
blocks: ["T2", "T3", "T4", "T5", "T6"]
acs: ["AC-15", "AC-16", "AC-23", "AC-17"]
files_hint: ["src/rover_telemetry/domain/dashboard.py", "src/rover_telemetry/domain/charts.py", "tests/unit/test_charts_axis.py", "tests/conftest.py"]
owner: "12romis"
estimate: "M"
context_budget: "M"
status: "todo"
step: ""
---

<!-- Принцип файлу: вбудований зріз, що потрібен задачі, з підписом джерела; посилання — запасний шлях. Кожен шматок має підпис `<file> §<section>, <id>, verbatim|abridged`. Джерело завжди важливіше за вбудовану копію. -->

# T1 — Розширити StoredSession полями графіків і додати domain/charts.py: константи з джерелами, Value/Absent/AbsentReason, вісь за номером сесії з порожніми місцями

## Place in the sequence

- **Blocked by:** — · **Blocks:** T2 — Читати в read_snapshot нові колонки sessions для графіків тим самим знімком, T3 — Побудувати в domain ряди блоку «Акумулятор»: три напруги, напруга на банку, просадка, причина завершення, відсутні значення, T4 — Побудувати в domain ряди блоку «Перешкоди»: найменша відстань і датчик, «утримань не було», лічильники датчиків, секунди вимкненого захисту, T5 — Побудувати в domain ряди блоку «Рух і борти»: швидкості в об/хв і м/с, різниця бортів, причини відсутності, «без енкодера», T6 — Додати в web/formatting.py підписи причин відсутності, датчиків і бортів, м/с, об/хв і напругу на банку · **Wave:** 1 (немає залежностей: старт паралельно з іншими задачами хвилі).
- **Lane:** спільний `src/rover_telemetry/domain/charts.py` з T3, T4, T5 — серіалізація.

## Why (user story)

> **As a** Власник ровера
> **I want** щоб втрачені номери сесій були видимі на осі, виїзди стояли за номером сесії, а відсутні значення не перетворювалися на нуль чи лінію
> **So that** вибірка не вводила в оману ні мене, ні глядачів
>
> — `spec.md §4, US-08, verbatim` · full text: [spec.md](../spec.md)

Цей крок дає спільну основу всіх графіків: вісь за номером сесії, де втрачені номери — порожні місця, і типи, що не дозволяють відсутньому значенню стати нулем.

## Inlined context

> Прості шари за фундаментальним ADR-0002: чистий `domain` (ряди графіків, причини відсутності, константи), `db` (читання сирим SQL), `web` (маршрут, шаблони, підписи, статичні файли). Додається файл `domain/charts.py`, змінюються наявні `domain/dashboard.py`, `db/reading.py`, `web/*`. Правило залежностей не змінюється: `domain` не імпортує нічого з проєкту, підписи (рядки інтерфейсу) додає `web`.
>
> — `sad.md §5, Building block view, abridged` · full text: [sad.md](../sad.md)

> **Вісь** — категорії за номером сесії від найменшого до найбільшого збереженого; кожен номер із `session_gaps` — порожня категорія «сесія не дійшла»; лінії між виїздами не будуються (напруга наприкінці одного виїзду не продовжується початком наступного), кожен виїзд — окремі позначки, відрізняються формою й підписом, не лише кольором.
>
> — `sad.md §4, Тактичні рішення «Вісь», abridged` · full text: [sad.md](../sad.md)

> Номери з `session_gaps` — порожні категорії осі з підписом «сесія не дійшла»; лінія не з'єднує сусідні виїзди; відхилений номер на осі не відрізняється від втраченого
>
> — `sad.md §8, Lost sessions, verbatim` · full text: [sad.md](../sad.md)

> Відсічка 6.0 В, повний заряд 8.4 В, поріг 190 мм, 2 банки, коефіцієнт 0.1382 м, 60 с — іменовані константи в `domain/charts.py` із посиланням на джерело; передаються в JS у даних
>
> — `sad.md §8, Constants & sources, verbatim` · full text: [sad.md](../sad.md)

> **Chosen:** варіант 1. Усі правила `null` ≠ 0 і причин тестуються швидкими юніт-тестами `domain`, а `charts.js` лишається «німим» шаром малювання. Пріоритет причин для відсутньої швидкості (початкове рішення design, у контракті порядку немає): не їхав → без енкодера (із зазначенням борту) → прямої ділянки не було (лише для різниці бортів) → не передано; позначка «без енкодера» (AC-13) не залежить від цього порядку.
> Варіант 1: кожне значення точки — `Value(число)` або `Absent(reason)`, де `reason` — елемент `AbsentReason` (`NOT_MOVING`, `NO_ENCODER` із зазначенням борту, `NO_STRAIGHT`, `NO_HOLDS`, `NOT_REPORTED`); `web/formatting.py` додає підпис простою мовою; у JSON точка має `null` у значенні плюс код і підпис причини.
>
> — `adr/0003, Decision outcome + option 1, abridged` · full text: [adr/0003-decide-absent-value-reasons-in-domain-and-ship-them-with-each-point.md](../adr/0003-decide-absent-value-reasons-in-domain-and-ship-them-with-each-point.md)

> **`null` ≠ 0.** Відсутнє значення зберігається як `NULL` і показується як «немає даних»; нуль — виміряне значення. Агрегації не перетворюють `NULL` на нуль.
>
> — `docs/constitution.md, №4, verbatim` · full text: [../../constitution.md](../../../constitution.md)

> Додавання колонок до `StoredSession` і `_SESSION_COLUMNS` зсуває позиційне створення `StoredSession(*row)` — Mitigation: нові поля в кінці зі значенням за замовчуванням; інтеграційний тест `test_reading.py` на всіх колонках.
>
> — `sad.md §11, Risks (останній рядок), abridged` · full text: [sad.md](../sad.md)

**To the executing agent:** працюй із вбудованого; якщо зріз недостатній, суперечить коду чи застарів — відкрий названий файл і дій за ним ([spec.md](../spec.md) · [sad.md](../sad.md) · [screens.md](../screens.md) · [adr/](../adr/)). Не вигадуй відсутнього.

## Data delta

No DB changes.

## API contract

Internal — no API surface.

## Acceptance criteria

### AC-15 — domain invariant violation

> **Given** серед збережених виїздів пропущено номери сесій
> **When** Власник ровера дивиться будь-який із трьох блоків
> **Then** кожен втрачений номер лишається на осі на своєму місці порожнім і підписаним як сесія, що не дійшла, а лінія не з'єднує сусідні виїзди через пропуск
>
> — `spec.md §5, AC-15, verbatim` · full text: [spec.md](../spec.md)

### AC-16 — domain invariant violation

> **Given** звіти двох виїздів надійшли майже одночасно, а третій через години
> **When** Власник ровера дивиться графіки
> **Then** виїзди розташовані за номером сесії, а не за часом отримання, вісь названа номером сесії, ніде не названа часом виїзду, а час «отримано» з'являється лише як підпис значення за київським часом
>
> — `spec.md §5, AC-16, verbatim` · full text: [spec.md](../spec.md)

### AC-23 — cross-context

> **Given** ровер повторно надіслав уже збережений звіт, а також є відхилене повідомлення
> **When** Глядач дивиться графіки
> **Then** повтор не додає другої точки чи стовпця на жодному графіку, а відхилене повідомлення виїздом не вважається і на графіках не з'являється, окрім того, що його номер сесії (якщо він був) лишається порожнім місцем на осі, як будь-який номер без виїзду
>
> — `spec.md §5, AC-23, verbatim` · full text: [spec.md](../spec.md)

### AC-17 — domain invariant violation

> **Given** жодного виїзду ще не збережено
> **When** Глядач відкриває дашборд
> **Then** кожен із трьох блоків показує «немає даних» замість порожніх осей чи нульових ліній, сторінка лишається цілою, а підсумки показують нуль виїздів як виміряне число
>
> — `spec.md §5, AC-17, verbatim` · full text: [spec.md](../spec.md)

## Checklist

- [ ] Додати в `StoredSession` (`domain/dashboard.py`) необов'язкові поля **після `payload`**, усі зі значенням `None`: `holds_min_mm`, `holds_min_sensor`, `holds_left_front`, `holds_front`, `holds_right_front`, `holds_rear`, `tof_control_off_ms`, `speed_left_avg_rpm`, `speed_left_peak_rpm`, `speed_right_avg_rpm`, `speed_right_peak_rpm`, `speed_imbalance_pct`, `encoders_left`, `encoders_right` — `src/rover_telemetry/domain/dashboard.py`. Порядок наявних полів не змінювати (позиційне `StoredSession(*row)` у `db/reading.py`).
- [ ] Створити `domain/charts.py` без I/O; імпортувати з проєкту лише `domain.dashboard`. Іменовані константи з коментарем-джерелом: `CUTOFF_V = 6.0` (контракт), `FULL_CHARGE_V = 8.4` (рішення власника №9), `OBSTACLE_THRESHOLD_MM = 190` (контракт, конституція №3), `BATTERY_CELLS = 2` (рішення №8), `WHEEL_CIRCUMFERENCE_M = 0.1382` (контракт), `SECONDS_PER_MINUTE = 60` — `src/rover_telemetry/domain/charts.py`.
- [ ] Додати `AbsentReason(Enum)`: `NOT_MOVING`, `NO_ENCODER`, `NO_STRAIGHT`, `NO_HOLDS`, `NOT_REPORTED`; `Value` (frozen dataclass з числом) і `Absent` (frozen dataclass: `reason`, `subject: str | None` — назва значення чи борт) — `domain/charts.py`.
- [ ] Додати `Slot(seq, session | None)` і `build_axis(sessions, gaps) -> list[Slot]`: впорядкована за `seq` (не за `received_at`) множина збережених номерів ∪ номерів із `gaps`; номер без виїзду — `Slot` із `session=None`; жодного збереженого виїзду → порожній список — `domain/charts.py`.
- [ ] Юніт-тести на фікстурах `tests/fixtures/session_seq26.json`, `session_seq27.json` та синтетичних рядках: порядок за `seq` при зворотному `received_at`, номер-пропуск, відхилений номер (виглядає як пропуск), порожній набір, сталість `mypy --strict` — `tests/unit/test_charts_axis.py`.

## Edge cases

| Case | Behaviour |
|---|---|
| Жодного збереженого виїзду | `build_axis` повертає `[]`; номери з `gaps` без виїздів осі не створюють (AC-17: блоки покажуть «немає даних») |
| Звіти з майже однаковим «отримано» і різними `seq` | порядок слотів лише за `seq` (AC-16); `received_at` в осі не бере участі |
| Номер у `gaps` і відхилене повідомлення з тим самим номером | один порожній слот; відхилений від втраченого не відрізняється (AC-23) |
| Повторно надісланий звіт | у сховищі один рядок за `(mac, seq)`, тож другого слота немає (дедублікація в `ingest`) |
| `StoredSession(...)` без нових полів | усі нові поля `None` — наявні виклики й тести підсумків не ламаються |

## Definition of Done

- [ ] юніт-тести осі й типів проходять без Docker (`pytest -m 'not integration'`)
- [ ] наявні тести `test_dashboard_summary.py`, `test_dashboard_timeline.py` лишаються зеленими
- [ ] `domain/charts.py` не імпортує `web`, `db`, `psycopg`, `fastapi`
- [ ] кожна константа має коментар із джерелом; чисел без джерела немає (конституція №3)
- [ ] кожне правило з розділу «Inlined context» (Hard Rules, конституція №4) досі виконується
- [ ] lint + vet чисті
