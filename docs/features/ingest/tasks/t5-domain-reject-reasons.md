---
id: T5
title: "Відхиляти невалідні повідомлення з кодом причини (domain.parse_report, гілки Rejection)"
layer: "domain"
deps: ["T4"]
blocks: ["T7"]
acs: ["AC-05", "AC-06", "AC-07"]
files_hint: ["src/rover_telemetry/domain/report.py", "tests/unit/test_report_rejected.py"]
owner: "12romis"
estimate: "M"
context_budget: "M"
status: "done"
step: "COMMIT"
---

## Why (user story)

> **As a** Власник ровера
> **I want** щоб повідомлення, яке не є коректним звітом, зберігалося окремо з причиною
> **So that** я бачу, що надійшло щось неправильне, і не втрачаю його вміст
>
> — `spec.md §4, US-03, verbatim` · full text: [spec.md](../spec.md)

Робить відхилення нормальним результатом, а не помилкою: сім причин у фіксованому порядку, вміст дослівно й обрізаний по байтах до 1024 із позначкою.

## Inlined context

> | Reason codes | Фіксований перелік, перший спрацьований у порядку: `too_large`, `not_json`, `unknown_event`, `unsupported_schema`, `missing_id`, `id_mismatch`, `bad_type`; відсутність інших полів і явні `null` — не причина; перевірок діапазонів немає; точні значення колонки уточнює `data-model` | spec AC-05…AC-07 |
>
> — `sad.md §8, Reason codes, verbatim` · full text: [sad.md](../sad.md)

> Причини перелічено в порядку перевірки (§8, «Reason codes»): перша, що спрацювала, і є причиною.
>
> — `sad.md §6, flow 4, verbatim` · full text: [sad.md](../sad.md)

> Svc->>Store: Зберігає як відхилене, причина too_large, вміст обрізано по байтах
>
> — `sad.md §6, flow 4, verbatim` · full text: [sad.md](../sad.md)

> **Hard rule:** **Надійність запису.** Підписник: QoS 1, фіксований client id, постійна сесія (`clean_session=false`). Підтвердження брокеру — лише після `COMMIT`. Невалідне повідомлення зберігається в таблицю відхилених і лише тоді підтверджується.
>
> — `constitution.md, №7, verbatim` · full text: [constitution.md](../../../constitution.md)

> **Hard rule:** **Еволюція схеми.** Невідомі поля ігноруються; повний сирий JSON зберігається поруч із розібраними колонками. Несумісна зміна — лише з новим `schema_version`.
>
> — `constitution.md, №8, verbatim` · full text: [constitution.md](../../../constitution.md)

> **Chosen:** варіант 1. Для валідного звіту `raw` — точні байти повідомлення (за AC-05 не більше 1024, тож без обрізання); `payload jsonb` лишається для запитів і представлень.
>
> — `adr/0002, Decision outcome, abridged` · full text: [adr/0002-store-raw-message-bytes-next-to-parsed-columns.md](../adr/0002-store-raw-message-bytes-next-to-parsed-columns.md)

> | Топік | `rover/<mac>/session`; `<mac>` — 12 hex-символів нижнім регістром |
> | Формат | один JSON, компактний, ≤ 1024 байти, UTF-8 |
>
> — `contracts/events.md, «Доставка», verbatim` · full text: [events.md](../../../contracts/events.md)

**Fallback:** insufficient or contradicted by the code → read the named file in full ([spec.md](../spec.md) · [sad.md](../sad.md) · [data-model.md](../data-model.md) · [adr/](../adr/)) and follow it. Do not guess.

## Data delta

No DB changes.

## API contract

Internal — no API surface.

## Acceptance criteria

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

### AC-07 (US-03) — error

> **Given** надійшов звіт з версією схеми, відмінною від поточної (1)
> **When** сервіс приймання його отримує
> **Then** звіт зберігається серед відхилених з причиною «непідтримана версія схеми», а його вміст зберігається дослівно в межах 1024 байт (понад ліміт обрізається по байтах, позначка про обрізання зберігається окремо й до ліміту не входить), щоб обробити його, коли версію буде підтримано
>
> — `spec.md §5, AC-07, verbatim` · full text: [spec.md](../spec.md)

## Checklist

- [ ] У `domain/report.py` додати перевірки в порядку SAD §8: `too_large` (len > 1024) → `not_json` (не UTF-8 / не JSON-об'єкт) → `unknown_event` (`event` ≠ `rover.session.v1`) → `unsupported_schema` (`schema_version` не `int` 1; `bool` не рахується за `int`) → `missing_id` (немає або `null` `mac`/`seq`) → `id_mismatch` (`mac` ≠ сегмент топіка) → `bad_type` (відоме поле з неправильним типом).
- [ ] `Rejection.raw` — перші 1024 байти; `raw_size` — початковий розмір; `raw_truncated` — `True` лише для `too_large` (позначка до ліміту не входить, AC-07). Решта причин: `raw` — усі байти, `raw_truncated=False`.
- [ ] `reason_text` — проста мова: для `id_mismatch` — «ідентифікатори не збігаються», для `unsupported_schema` — «непідтримана версія схеми» (дослівно зі spec AC-06/AC-07); для решти — власні короткі формулювання українською.
- [ ] Явний `null` і відсутність необов'язкових полів — не причина; перевірок діапазонів немає.
- [ ] `tests/unit/test_report_rejected.py`: по тесту на кожну з 7 причин, на порядок (повідомлення з двома вадами дає першу за порядком), на дослівність `raw` для `unsupported_schema` і на обрізання по байтах (багатобайтовий символ на межі 1024 не ламає `raw`, бо це `bytes`).

## Edge cases

| Case | Behaviour |
|---|---|
| Рівно 1024 байти валідного звіту | Приймається (межа включно), `too_large` лише для > 1024 |
| Понад 1024 байти | `too_large`; `raw` — перші 1024 байти, `raw_size` — початковий розмір, `raw_truncated=True` |
| Порожнє тіло, JSON-масив чи число | `not_json` |
| `schema_version: 2` (або відсутнє, або не-`int`) | `unsupported_schema`, `raw` дослівно в межах 1024 (AC-07). Spec мовчить про відсутнє поле; прийнято порядок SAD: усе, що не `int` 1, — `unsupported_schema` |
| `mac` у звіті ≠ `mac` у топіку | `id_mismatch` (AC-06) |
| `mac`/`seq` присутні, але неправильного типу | `bad_type` (перевірка типу ідентифікаторів передує звірці з топіком) |
| `distance_cm: null`, відсутній `fw.dirty` | Не відхилення (AC-05) |
| `seq: true` | `bad_type`: `bool` не є `int` |

## Definition of Done

- [ ] `pytest tests/unit/test_report_rejected.py` проходить: усі 7 причин, порядок, обрізання
- [ ] тести T4 лишаються зеленими
- [ ] `ruff`, `mypy src` без попереджень
- [ ] every Hard Rule inlined above still holds
- [ ] lint + vet clean (`ruff check . && ruff format --check . && mypy src`)
