---
id: T13
title: "Скрипти Оператора: ACL брокера, пробна публікація, перевірка запуску, відкат"
layer: "docs"
deps: ["T10", "T12"]
blocks: []
acs: ["AC-13", "AC-14", "AC-19", "AC-20"]
files_hint: ["ops/acl.narrow.template", "ops/probe_publish.sh", "ops/verify_launch.sh", "ops/rollback_acl.sh", "ops/README.md"]
owner: "12romis"
estimate: "M"
context_budget: "M"
status: "todo"
step: ""
---

## Why (user story)

> **As a** Оператор сервера
> **I want** щоб ровер, сервіс приймання й дашборд мали лише ті права, що потрібні для їхньої ролі
> **So that** витік одного пароля не дозволяє підробити звіт чи змінити збережені дані
>
> — `spec.md §4, US-08, verbatim` · full text: [spec.md](../spec.md)

> **As a** Оператор сервера
> **I want** підтвердити запуск у проді першим реальним звітом ровера
> **So that** я знаю, що звуження прав не заблокувало ровер і що збереження справді працює
>
> — `spec.md §4, US-10, verbatim` · full text: [spec.md](../spec.md)

Дає Операторові повторювані, оборотні кроки запуску: звуження ACL з пробною публікацією, перевірку наступного реального звіту (час «отримано», початок обліку, розрив до 27) і відкат після 30 хв.

## Inlined context

> **Chosen:** варіант 1. Порядок запуску: (1) БД, ролі, міграція; (2) у файл паролів і ACL додаються `rover-ingest` та `rover-viewer` (лише читання), `RomisRover` поки без змін, SIGHUP; (3) `ingest` запускається під `rover-ingest`, пробне повідомлення від `RomisRover` проходить наскрізь (потрапляє в `rejected`); (4) копія `acl` у `acl.bak` (уже з `rover-ingest`, тож відкат не забирає в `ingest` читання, AC-20), звужений ACL, `docker kill --signal=SIGHUP mosquitto`; (5) пробна публікація від `RomisRover` на `session` доходить, на інший топік не доходить, `rover-ingest` не може публікувати; (6) наступний реальний звіт підтверджує запуск (AC-19). Якщо після завершення відомого виїзду пройшло 30 хв (рішення власника, design 2026-10-23) і звіту серед збережених немає, Оператор сервера виконує `cp acl.bak acl` і SIGHUP (AC-20). Пробний запис виглядає як `rejected` із топіком `rover/000000000000/session`, і KPI «відхилені від справжнього ровера» його виключає.
>
> — `adr/0003, Decision outcome, verbatim` · full text: [adr/0003-narrow-broker-acl-in-staged-reversible-launch.md](../adr/0003-narrow-broker-acl-in-staged-reversible-launch.md)

> | Помилка в ACL: брокер на заборонений запис відповідає `PUBACK RC:0` і мовчки відкидає, ровер стирає звіт; помилка не видна без активної перевірки | High | Feature ADR-0003: пробна публікація до виїзду, відкат `acl.bak`; залишковий ризик — звіт у вікні між SIGHUP і виявленням не відновлюється | 12romis |
>
> — `sad.md §11, risk row 1, verbatim` · full text: [sad.md](../sad.md)

> | Authentication / AuthZ | Три облікові записи брокера (`RomisRover` лише `write rover/+/session`, `rover-ingest` лише `read`, `rover-viewer` лише `read`) і три ролі Postgres (`owner` — міграції, `ingest` — лише `INSERT` на `sessions`, `rejected`, `viewer` — лише `SELECT`); `ingest` не читає, не змінює, не видаляє | конституція №10, рішення власника №5, feature ADR-0003, ADR-0005 |
>
> — `sad.md §8, Authentication / AuthZ, verbatim` · full text: [sad.md](../sad.md)

> - ACL брокера: `/opt/mosquitto/config/acl`, паролі — `/opt/mosquitto/config/passwd`; перечитування — `docker kill --signal=SIGHUP mosquitto`.
>
> — `CLAUDE.md, Інфраструктура сервера, verbatim` · full text: [CLAUDE.md](../../../../CLAUDE.md)

> **Hard rule:** **Найменші права.** Окремі облікові записи брокера (ровер — лише запис у `rover/+/session`; ingest — лише читання) і окремі ролі Postgres (ingest — лише вставка; дашборд — лише читання).
>
> — `constitution.md, №10, verbatim` · full text: [constitution.md](../../../constitution.md)

> **Hard rule:** **Дашборд лише читає.** Жодного зворотного каналу до ровера; ровер нічого не отримує з сервера.
>
> — `constitution.md, №11, verbatim` · full text: [constitution.md](../../../constitution.md)

**Fallback:** insufficient or contradicted by the code → read the named file in full ([spec.md](../spec.md) · [sad.md](../sad.md) · [data-model.md](../data-model.md) · [adr/](../adr/)) and follow it. Do not guess.

## Data delta

No DB changes.

## API contract

Internal — no API surface.

## Acceptance criteria

### AC-13 (US-08) — authorization

> **Given** Ровер зі своїми обліковими даними брокера
> **When** він намагається прочитати повідомлення або надіслати щось, окрім звіту сесії
> **Then** брокер відмовляє, а Ровер лишається здатним лише надсилати звіти сесії; відмова діє на рівні каналів, а не окремих роверів, бо роверам поки що спільний обліковий запис
>
> — `spec.md §5, AC-13, verbatim` · full text: [spec.md](../spec.md)

### AC-14 (US-08) — authorization

> **Given** особа без облікових даних брокера
> **When** вона намагається надіслати звіт сесії
> **Then** брокер відмовляє, і нічого не зберігається
>
> — `spec.md §5, AC-14, verbatim` · full text: [spec.md](../spec.md)

### AC-19 (US-10) — happy path

> **Given** сервіс запущено в проді, а права брокера звужено
> **When** надходить наступний реальний звіт ровера
> **Then** Оператор сервера може підтвердити, що звіт є серед збережених із часом «отримано», що номер першої отриманої сесії записано як початок обліку втрат, і бачить розрив між цим номером і останнім відомим номером 27; цей розрив є довідкою для ручної перевірки, а не втратою в обліку
>
> — `spec.md §5, AC-19, verbatim` · full text: [spec.md](../spec.md)

### AC-20 (US-10) — error

> **Given** права брокера звужено, відомо, що ровер завершив виїзд, але його звіт серед збережених не з'явився
> **When** Оператор сервера, коли від завершення виїзду минуло 30 хв, виконує перевірку запуску і відкат вручну
> **Then** перевірка не вважається пройденою, і звуження прав відкочується: Ровер знову може надсилати звіти, а можливість читання звітів для сервісу приймання лишається; відсутність виїздів сама по собі відкату не викликає
>
> — `spec.md §5, AC-20, verbatim` · full text: [spec.md](../spec.md)

## Checklist

- [ ] `ops/acl.narrow.template`: `RomisRover` — лише `write rover/+/session`; `rover-ingest` — лише `read rover/+/session`; `rover-viewer` — лише `read` (за ADR-0003 і SAD §8); без паролів.
- [ ] `ops/probe_publish.sh <user> <topic>`: пробна публікація `mosquitto_pub` від імені користувача (пароль із `~/.config/claude-secrets/mqtt.env`); друкує, чи брокер прийняв (пам'ятати: заборонений запис дає `PUBACK RC:0` без помилки — тож успіх перевіряється доставкою підписнику `mosquitto_sub`, а не кодом виходу).
- [ ] `ops/verify_launch.sh <mac>`: запит під роллю `viewer`: остання сесія з `received_at`, найменший `seq` (початок обліку), розрив до 27 як довідка, а не втрата (AC-19); виключає синтетичний `mac` 000000000000 з відхилених.
- [ ] `ops/rollback_acl.sh`: `cp acl.bak acl`, `docker kill --signal=SIGHUP mosquitto`, пробна публікація від `RomisRover`; відмовляється працювати без `acl.bak` і до 30 хв з відомого завершення виїзду, якщо не передано `--now` (AC-20, вікно 30 хв — рішення власника, spec §8).
- [ ] `ops/README.md`: кроки 3–8 Launch checklist, порядок: розширити ACL читанням для `rover-ingest`/`rover-viewer` → запустити `ingest` → пробне повідомлення до `rejected` → `cp acl acl.bak` → звужений ACL → SIGHUP → пробні публікації → наступний реальний звіт → за невдачі відкат.
- [ ] Перевірити AC-13/AC-14 на живому брокері вручну: `RomisRover` не може підписатися чи писати поза `session`; без облікових даних відмова.

## Edge cases

| Case | Behaviour |
|---|---|
| Заборонена публікація | Брокер повертає `PUBACK RC:0` і відкидає мовчки; перевірка лише доставкою підписнику |
| Перший реальний `seq` > 27 | Розрив до 27 — довідка для ручної перевірки, не втрата (AC-19) |
| Менший номер надійде пізніше | Початок обліку зсунеться до нього (AC-08) |
| 30 хв минуло, звіту немає | Перевірка не пройдена; відкат `acl.bak`; читання для `rover-ingest` лишається (AC-20) |
| Виїздів не було | Відкату немає, перевірка лишається відкритою (AC-20) |
| `acl.bak` відсутній | `rollback_acl.sh` відмовляє, нічого не змінюючи |

## Definition of Done

- [ ] `shellcheck ops/*.sh` без зауважень (або `bash -n`)
- [ ] на тестовому Mosquitto пробна публікація дозволена на `session` і відхилена на інший топік
- [ ] відкат відновлює `RomisRover` і лишає читання для `rover-ingest`
- [ ] у репозиторії немає значень паролів
- [ ] запуск у проді (AC-19) і відкат (AC-20) виконує Оператор за README — окремий ручний крок, не код
- [ ] every Hard Rule inlined above still holds
- [ ] lint + vet clean (`ruff check . && ruff format --check . && mypy src`)
