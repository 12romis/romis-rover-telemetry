---
id: T10
title: "Запустити підписника: очікування БД, MQTT QoS 1 з manual ack, вихід при збої"
layer: "app"
deps: ["T6", "T9"]
blocks: ["T11", "T13"]
acs: ["AC-17", "AC-18"]
files_hint: ["src/rover_telemetry/ingest/__main__.py", "tests/unit/test_runner.py"]
owner: "12romis"
estimate: "M"
context_budget: "M"
status: "done"
step: "COMMIT"
---

## Why (user story)

> **As a** Оператор сервера
> **I want** щоб простій сервісу чи недоступність сховища не призводили до втрати звітів
> **So that** не доводиться стежити за кожним перезапуском вручну
>
> — `spec.md §4, US-09, verbatim` · full text: [spec.md](../spec.md)

Дає процес: чекає БД, підключається з фіксованим client id і постійною сесією, підтверджує брокеру лише після COMMIT, а при збої сховища виходить без `ack`.

## Inlined context

> **Chosen:** варіант 1. Повідомлення обробляються по одному в callback: розбір → INSERT → COMMIT → `ack`; з кожного повідомлення COMMIT робиться окремо (без пакетного запису). Помилка запису чи COMMIT — вихід із кодом 1 без `ack`. Щоб відновлення вкладалося в ≤ 60 с і не росла пауза між перезапусками Docker, на старті процес спершу чекає доступності БД (опитування в процесі, інтервал — параметр конфігурації, значення обирає `tasks`) і лише потім підключається до брокера та підписується. Таймаути підключення й запиту до БД — кілька секунд, менше за keepalive. Варіант 2 відхилено через блокування мережевого потоку, варіант 3 — через зайвий код і стан «напівживий» у дедлайн-фічі.
>
> — `adr/0001, Decision outcome, verbatim` · full text: [adr/0001-commit-before-ack-and-exit-on-storage-failure.md](../adr/0001-commit-before-ack-and-exit-on-storage-failure.md)

> **Hard rule:** **Надійність запису.** Підписник: QoS 1, фіксований client id, постійна сесія (`clean_session=false`). Підтвердження брокеру — лише після `COMMIT`. Невалідне повідомлення зберігається в таблицю відхилених і лише тоді підтверджується.
>
> — `constitution.md, №7, verbatim` · full text: [constitution.md](../../../constitution.md)

> Db--xIngest: Збій, БД недоступна
> Ingest->>Ingest: Пише помилку в лог, не підтверджує
> Ingest->>Broker: Відключається, процес завершується з кодом 1
> Note over Ingest: Docker перезапускає процес
> Ingest->>Db: Очікує доступності БД
> Ingest->>Broker: Підключається з тим самим client id, clean_session=false
> Broker->>Ingest: Повторно віддає непідтверджені звіти
>
> — `sad.md §6, flow 2, abridged` · full text: [sad.md](../sad.md)

> | Events / ack | QoS 1, фіксований client id, `clean_session=false`, `manual_ack`; `ack` лише після COMMIT, лише в тому самому з'єднанні | конституція №7, feature ADR-0001 |
>
> — `sad.md §8, Events / ack, verbatim` · full text: [sad.md](../sad.md)

> | Самовідновлення | після збою сервіс сам перепідключається і продовжує ≤ 60 с (пропозиція, див. §8) | приймальний тест із перезапуском сервісу |
> | Наздоганяння черги | до 1000 накопичених повідомлень (межа черги брокера, `docs/idea-brief.md` §6) оброблено ≤ 60 с після старту (пропозиція, див. §8) | тест із 1000 синтетичних звітів |
>
> — `spec.md §6, NFR rows, verbatim` · full text: [spec.md](../spec.md)

**Fallback:** insufficient or contradicted by the code → read the named file in full ([spec.md](../spec.md) · [sad.md](../sad.md) · [data-model.md](../data-model.md) · [adr/](../adr/)) and follow it. Do not guess.

## Data delta

No DB changes.

## API contract

Internal — no API surface.

## Acceptance criteria

### AC-17 (US-09) — cross-context

> **Given** сервіс уже підключався до брокера раніше, потім був вимкнений, а Ровер за цей час надіслав звіти, які брокер зберіг у черзі
> **When** сервіс запускається знову
> **Then** усі накопичені звіти збережено (порядок отримання довільний), а облік втрат показує лише справжні пропуски в нумерації
>
> — `spec.md §5, AC-17, verbatim` · full text: [spec.md](../spec.md)

### AC-18 (US-09) — cross-context

> **Given** сховище сесій недоступне в момент надходження звіту
> **When** звіт не вдалося зберегти
> **Then** отримання не підтверджується брокеру, звіт не втрачається, а після відновлення сховища його збережено рівно один раз
>
> — `spec.md §5, AC-18, verbatim` · full text: [spec.md](../spec.md)

## Checklist

- [ ] `ingest/__main__.py`: `main()` читає `IngestSettings` (T6); цикл очікування БД — спроба `connect` з `DB_CONNECT_TIMEOUT_S`, пауза `DB_WAIT_INTERVAL_S`, лише потім MQTT (ADR-0001).
- [ ] paho-mqtt 2.x: `Client(CallbackAPIVersion.VERSION2, client_id=MQTT_CLIENT_ID, clean_session=False)` (MQTT 3.1.1), `manual_ack_set(True)`, `username_pw_set` з налаштувань, `subscribe('rover/+/session', qos=1)` після `on_connect`; підписка відновлюється на перепідключенні.
- [ ] `on_message`: `received_at = datetime.now(UTC)` першим рядком → `handle_message` → `client.ack(msg.mid, msg.qos)` лише після повернення; під час обробки мережевий потік блокується на запис (ADR-0001, варіант 1).
- [ ] Будь-який виняток із `handle_message`/`connect`: лог `event=error`, `client.disconnect()`, `raise SystemExit(1)` без `ack`.
- [ ] Обробка `SIGTERM` — чисте відключення без втрати непідтверджених (вони лишаються в черзі брокера).
- [ ] `tests/unit/test_runner.py` з фейковим клієнтом і фейковим `handle_message`: `ack` викликається після успішної обробки, не викликається при винятку; виняток дає `SystemExit(1)`; `received_at` ставиться до виклику обробника.

## Edge cases

| Case | Behaviour |
|---|---|
| БД недоступна на старті | Очікування в циклі, до брокера не підключається, поки БД не відповість |
| Збій запису посеред обробки | Лог `event=error`, вихід з кодом 1, `ack` не надсилається; брокер віддасть звіт знову (AC-18) |
| Черга накопичених звітів після простою | Усі оброблено, порядок довільний; дублі → `duplicate` (AC-17) |
| Брокер розірвав з'єднання | Бібліотека перепідключається з тим самим client id; процес не плодить другий клієнт |
| Повідомлення з довільним топіком | Підписка лише на `rover/+/session`; інший топік до обробника не доходить |

## Definition of Done

- [ ] `pytest tests/unit/test_runner.py` проходить
- [ ] `ack` лише після `commit`, при винятку — `SystemExit(1)` без `ack`
- [ ] client id фіксований, `clean_session=False`, `manual_ack` увімкнено
- [ ] `docker compose build` збирається; `ruff`, `mypy src` без попереджень
- [ ] every Hard Rule inlined above still holds
- [ ] lint + vet clean (`ruff check . && ruff format --check . && mypy src`)
