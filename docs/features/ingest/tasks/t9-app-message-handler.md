---
id: T9
title: "Обробити одне повідомлення: розбір → запис → COMMIT → результат (ingest.handler)"
layer: "app"
deps: ["T7"]
blocks: ["T10"]
acs: ["AC-01", "AC-03", "AC-05", "AC-06"]
files_hint: ["src/rover_telemetry/ingest/handler.py", "tests/integration/test_handler.py"]
owner: "12romis"
estimate: "M"
context_budget: "M"
status: "done"
step: "COMMIT"
---

## Why (user story)

> **As a** Ровер
> **I want** щоб кожен звіт сесії, який я надсилаю, потрапляв у сховище сесій
> **So that** виїзд не втрачається, а мій буфер із двох недоставлених звітів не витісняє старі звіти
>
> — `spec.md §4, US-01, verbatim` · full text: [spec.md](../spec.md)

> **As a** Власник ровера
> **I want** щоб повідомлення, яке не є коректним звітом, зберігалося окремо з причиною
> **So that** я бачу, що надійшло щось неправильне, і не втрачаю його вміст
>
> — `spec.md §4, US-03, verbatim` · full text: [spec.md](../spec.md)

Склеює domain і db в одну функцію без MQTT: повертає `stored`/`duplicate`/`rejected` лише після COMMIT і пише один рядок логу `key=value`.

## Inlined context

> **Chosen:** варіант 1. Повідомлення обробляються по одному в callback: розбір → INSERT → COMMIT → `ack`; з кожного повідомлення COMMIT робиться окремо (без пакетного запису).
>
> — `adr/0001, Decision outcome, abridged` · full text: [adr/0001-commit-before-ack-and-exit-on-storage-failure.md](../adr/0001-commit-before-ack-and-exit-on-storage-failure.md)

> **Hard rule:** **Надійність запису.** Підписник: QoS 1, фіксований client id, постійна сесія (`clean_session=false`). Підтвердження брокеру — лише після `COMMIT`. Невалідне повідомлення зберігається в таблицю відхилених і лише тоді підтверджується.
>
> — `constitution.md, №7, verbatim` · full text: [constitution.md](../../../constitution.md)

> | Logging | Один рядок `key=value` на подію в stdout: `event` (`stored`/`duplicate`/`rejected`/`error`), `mac`, `seq`, `reason_code`, `received_at`, `latency_ms`; без вмісту звіту й без паролів | тут |
>
> — `sad.md §8, Logging, verbatim` · full text: [sad.md](../sad.md)

> | Error handling | Невалідне повідомлення не падає процес: збережене в `rejected` з кодом причини і текстом, потім `ack`; збій сховища — вихід без `ack`; виняток `ReportError` у `domain` | конституція №7, feature ADR-0001, `docs/architecture-map.md` |
>
> — `sad.md §8, Error handling, verbatim` · full text: [sad.md](../sad.md)

> Ingest->>Ingest: Ставить received_at і розбирає звіт за контрактом
> Ingest->>Db: INSERT у sessions ON CONFLICT DO NOTHING і COMMIT
> Db-->>Ingest: 1 рядок (нова сесія) або 0 рядків (дубль)
> Ingest->>Db: INSERT у rejected з кодом причини і COMMIT
> Ingest->>Broker: ack після COMMIT
>
> — `sad.md §6, flow 1, abridged` · full text: [sad.md](../sad.md)

> Тактичні рішення цього етапу (без ADR, бо відкат — години, а не дні): `received_at` — час сервісу в UTC на вході в callback, до розбору; розбір — власна чиста функція в `domain` без pydantic/jsonschema; логування — рядки `key=value` у stdout; БД і ролі створює одноразовий скрипт Оператора від суперкористувача Postgres (паролі не в git), а таблиці, представлення і GRANT — міграція `0002` від `owner`, `ingest` міграцій не запускає.
>
> — `sad.md §4, Solution strategy, verbatim` · full text: [sad.md](../sad.md)

**Fallback:** insufficient or contradicted by the code → read the named file in full ([spec.md](../spec.md) · [sad.md](../sad.md) · [data-model.md](../data-model.md) · [adr/](../adr/)) and follow it. Do not guess.

## Data delta

No DB changes.

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

### AC-05 (US-03) — error

> **Given** надійшло повідомлення, яке не є коректним звітом: його не можна прочитати як звіт, воно перевищує 1024 байти (межа з контракту), має невідомий тип події, відоме поле має неправильний тип, немає ідентифікатора ровера чи номера сесії. Відсутність інших полів і явне порожнє значення не є підставою для відхилення, а перевірок діапазонів значень немає
> **When** сервіс приймання його отримує
> **Then** повідомлення зберігається дослівно серед відхилених із причиною простою мовою й часом «отримано», сесія не створюється, і лише після цього отримання підтверджується брокеру; кожна повторна доставка такого повідомлення дає окремий запис
>
> — `spec.md §5, AC-05, verbatim` · full text: [spec.md](../spec.md)

### AC-06 (US-03) — error

> **Given** надійшов звіт, у якому ідентифікатор ровера не збігається з ідентифікатором ровера в каналі, яким його надіслано
> **When** сервіс приймання його отримує
> **Then** звіт зберігається серед відхилених з причиною «ідентифікатори не збігаються», сесія не створюється
>
> — `spec.md §5, AC-06, verbatim` · full text: [spec.md](../spec.md)

## Checklist

- [ ] `ingest/handler.py`: `handle_message(conn, topic: str, payload: bytes, received_at: datetime) -> Outcome` (`Outcome` — `StrEnum`: `stored`, `duplicate`, `rejected`).
- [ ] Тіло: `parse_report` → для `ParsedSession` `insert_session`, для `Rejection` `insert_rejected` → `conn.commit()` → лог → повернути результат. Помилку запису не ловити (піднімається до T10).
- [ ] Лог: один рядок `key=value` у stdout через `logging`: `event`, `mac`, `seq`, `reason_code`, `received_at`, `latency_ms` (від `received_at` до COMMIT); вміст звіту й паролі в лог не потрапляють.
- [ ] `tests/integration/test_handler.py` на ефемерному Postgres під роллю `ingest`: фікстура seq 26 → `stored` + рядок із `received_at` (AC-01); повтор → `duplicate`, `received_at` не змінений, у `rejected` нічого (AC-03); сміття → `rejected` + запис; повтор сміття → два записи (AC-05); mac ≠ топік → `rejected` з `id_mismatch` (AC-06).
- [ ] Тест логу: `caplog` містить `event=stored`, не містить сирого тіла звіту.

## Edge cases

| Case | Behaviour |
|---|---|
| Дубль | `duplicate`, `ack` дозволено (T10), у `rejected` нічого (AC-03) |
| Невалідне повідомлення | Запис у `rejected`, COMMIT, `rejected` (AC-05) |
| Збій запису чи COMMIT | Виняток піднімається; результат не повертається, отже `ack` не буде (ADR-0001) |
| Повторна доставка сміття | Окремий запис кожного разу (AC-05) |

## Definition of Done

- [ ] `pytest tests/integration/test_handler.py` проходить
- [ ] функція повертає результат лише після `commit()`
- [ ] у лозі немає вмісту звіту й паролів
- [ ] `ruff`, `mypy src` без попереджень
- [ ] every Hard Rule inlined above still holds
- [ ] lint + vet clean (`ruff check . && ruff format --check . && mypy src`)
