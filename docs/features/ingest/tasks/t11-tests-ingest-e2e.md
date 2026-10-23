---
id: T11
title: "Наскрізні тести ingest: збій сховища, наздоганяння 1000 звітів, перезапуск"
layer: "tests"
deps: ["T8", "T10"]
blocks: []
acs: ["AC-17", "AC-18"]
files_hint: ["tests/conftest.py", "tests/integration/test_ingest_e2e.py"]
owner: "12romis"
estimate: "M"
context_budget: "M"
status: "todo"
step: ""
---

## Why (user story)

> **As a** Оператор сервера
> **I want** щоб простій сервісу чи недоступність сховища не призводили до втрати звітів
> **So that** не доводиться стежити за кожним перезапуском вручну
>
> — `spec.md §4, US-09, verbatim` · full text: [spec.md](../spec.md)

Доводить NFR збереженості й наздоганяння на реальному брокері й Postgres: збій посеред запису, черга після простою, самовідновлення.

## Inlined context

> **Hard rule:** **Надійність запису.** Підписник: QoS 1, фіксований client id, постійна сесія (`clean_session=false`). Підтвердження брокеру — лише після `COMMIT`. Невалідне повідомлення зберігається в таблицю відхилених і лише тоді підтверджується.
>
> — `constitution.md, №7, verbatim` · full text: [constitution.md](../../../constitution.md)

> **Hard rule:** **Без нових попереджень.** Лінтер, перевірка типів і тести проходять без нових попереджень; вимкнення правила — лише з коментарем-обґрунтуванням.
>
> — `constitution.md, №14, verbatim` · full text: [constitution.md](../../../constitution.md)

> **Chosen:** варіант 1. Повідомлення обробляються по одному в callback: розбір → INSERT → COMMIT → `ack`; з кожного повідомлення COMMIT робиться окремо (без пакетного запису). Помилка запису чи COMMIT — вихід із кодом 1 без `ack`. Щоб відновлення вкладалося в ≤ 60 с і не росла пауза між перезапусками Docker, на старті процес спершу чекає доступності БД (опитування в процесі, інтервал — параметр конфігурації, значення обирає `tasks`) і лише потім підключається до брокера та підписується. Таймаути підключення й запиту до БД — кілька секунд, менше за keepalive. Варіант 2 відхилено через блокування мережевого потоку, варіант 3 — через зайвий код і стан «напівживий» у дедлайн-фічі.
>
> — `adr/0001, Decision outcome, verbatim` · full text: [adr/0001-commit-before-ack-and-exit-on-storage-failure.md](../adr/0001-commit-before-ack-and-exit-on-storage-failure.md)

> | Збереженість | 0 звітів, підтверджених брокеру без збереження як сесії чи відхиленого (конституція №7) | інтеграційний тест зі збоєм сховища посеред запису; порівняння підтверджень і записів |
> | Наздоганяння черги | до 1000 накопичених повідомлень (межа черги брокера, `docs/idea-brief.md` §6) оброблено ≤ 60 с після старту (пропозиція, див. §8) | тест із 1000 синтетичних звітів |
> | Самовідновлення | після збою сервіс сам перепідключається і продовжує ≤ 60 с (пропозиція, див. §8) | приймальний тест із перезапуском сервісу |
>
> — `spec.md §6, NFR rows, verbatim` · full text: [spec.md](../spec.md)

> - Брокер Mosquitto 2: `persistence true`, `max_queued_messages 1000`, `message_size_limit 262144`, внутрішній listener `mosquitto:1883` (`/opt/mosquitto/config/mosquitto.conf`).
> | Другий екземпляр `ingest` (або локальний запуск проти прод-брокера) із тим самим client id витісне перший з'єднання і зіб'є чергу | Medium | Одна репліка; окремий client id для тестів; ніколи не запускати локальний `ingest` проти прод-брокера | 12romis |
>
> — `sad.md §2 + §11, verbatim` · full text: [sad.md](../sad.md)

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

- [ ] `tests/conftest.py`: сесійна фікстура ефемерного `eclipse-mosquitto:2` (випадковий порт на 127.0.0.1, `persistence true`, `max_queued_messages 1000`, анонімний доступ лише в тесті), окремий тестовий `MQTT_CLIENT_ID`; ніколи не підключатися до прод-брокера.
- [ ] `tests/integration/test_ingest_e2e.py`: (а) AC-18 — зупинити Postgres (`docker pause`) під час публікації, `ingest` виходить з кодом 1 без `ack`; після `unpause` і перезапуску звіт збережено рівно один раз; (б) AC-17 — зупинити `ingest`, опублікувати 1000 синтетичних звітів у довільному порядку з пропуском, запустити: усі збережено ≤ 60 с, `session_gaps` показує лише справжній пропуск; (в) перезапуск: ≤ 60 с до продовження.
- [ ] Порівняти кількість `ack` (через відсутність повторної доставки) і записів: 0 підтверджених без збереження.
- [ ] Позначити тести `@pytest.mark.integration`; `pytest -m 'not integration'` їх не чіпає.

## Edge cases

| Case | Behaviour |
|---|---|
| Збій БД посеред запису | Без `ack`, після відновлення рівно один запис (AC-18) |
| 1000 звітів у зворотному порядку | Усі збережено, облік втрат — лише справжні пропуски (AC-17) |
| Повторна доставка уже збереженого | `duplicate`, без другого запису |
| Docker недоступний | Інтеграційні тести пропускаються маркером; CI має Docker |

## Definition of Done

- [ ] `pytest -m integration tests/integration/test_ingest_e2e.py` проходить
- [ ] 1000 звітів наздоганяються ≤ 60 с на ефемерному брокері
- [ ] тести не звертаються до прод-брокера й прод-БД
- [ ] `ruff`, `ruff format --check` без попереджень
- [ ] every Hard Rule inlined above still holds
- [ ] lint + vet clean (`ruff check . && ruff format --check . && mypy src`)
