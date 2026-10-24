# Tracker — dashboard-summary

> Status of every task in the epic. `implement` updates **Status** and **Step** after every
> subagent it runs (and commits them with the task), so this table shows where the run is right now.
> Status: `todo` · `in_progress` · `blocked` · `review` · `done`.
> Step: `SELECT` · `RED` · `GREEN` · `REFACTOR` · `GATE` · `REVIEW` · `COMMIT` (`—` before the task starts).
> A `blocked` row carries its reason in Step, e.g. `GATE — lint red after 3 retries`.

| # | Task | Layer | Owner | Estimate | Blocked by | Status | Step |
|---|---|---|---|---|---|---|---|
| T1 | [Додати в domain типи виїзду, підсумки з Total(sum, missing) і класифікацію причини завершення](./t1-domain-summary.md) | domain | 12romis | M | — | done | — |
| T2 | [Додати в domain хронологію виїздів із позначками номерів без виїзду](./t2-domain-timeline.md) | domain | 12romis | S | T1 | done | — |
| T3 | [Додати читання одного знімка лише для читання (db/reading.py) і налаштування таймаутів web](./t3-infra-read-snapshot.md) | infra | 12romis | M | T1 | todo | — |
| T4 | [Додати web/formatting.py: «отримано» за Києвом, одиниці, підписи причин, назва ровера, текст звіту](./t4-ui-formatting.md) | ui | 12romis | M | T1 | todo | — |
| T5 | [Створити базовий макет, токени CSS, макроси «немає даних»/картка/повідомлення та блок «Опис»](./t5-ui-base-layout.md) | ui | 12romis | M | — | todo | — |
| T6 | [Побудувати сторінку dashboard.html: опис, вісім карток підсумків, стани empty і error](./t6-ui-summary-block.md) | ui | 12romis | M | T1, T4, T5 | todo | — |
| T7 | [Побудувати список виїздів: розгортуваний рядок (details), позначка пропуску, блок повного звіту](./t7-ui-sessions-list.md) | ui | 12romis | M | T2, T4, T6 | todo | — |
| T8 | [Додати маршрут GET / з читанням знімка, 503 при недоступному сховищі, заголовками безпеки і /static](./t8-ports-dashboard-route.md) | ports | 12romis | M | T3, T6, T7 | todo | — |
| T9 | [Підготувати публікацію: alias rover-web у compose, фрагмент Caddyfile, runbook і скрипт перевірки](./t9-wiring-publish-ops.md) | wiring | 12romis | S | T8 | todo | — |
| T10 | [Додати інтеграційні тести сторінки на реальному Postgres: свіжість, дубль, запис, затримка, зовнішні запити](./t10-tests-dashboard-e2e.md) | tests | 12romis | M | T8 | todo | — |

**Total:** 10 tasks, ~9 person-days (S ≈ 0,5 дня, M ≈ 1 день).
