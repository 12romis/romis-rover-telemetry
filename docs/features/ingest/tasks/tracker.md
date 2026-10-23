# Tracker — ingest

> Status of every task in the epic. `implement` updates **Status** and **Step** after every
> subagent it runs (and commits them with the task), so this table shows where the run is right now.
> Status: `todo` · `in_progress` · `blocked` · `review` · `done`.
> Step: `SELECT` · `RED` · `GREEN` · `REFACTOR` · `GATE` · `REVIEW` · `COMMIT` (`—` before the task starts).
> A `blocked` row carries its reason in Step, e.g. `GATE — lint red after 3 retries`.

| # | Task | Layer | Owner | Estimate | Blocked by | Status | Step |
|---|---|---|---|---|---|---|---|
| T1 | Промотувати міграцію таблиці sessions у live migrations/ як 0002 | migration | 12romis | S | — | done | COMMIT |
| T2 | Промотувати міграцію таблиці rejected як 0003 | migration | 12romis | S | T1 | done | COMMIT |
| T3 | Промотувати міграцію представлення session_gaps як 0004 | migration | 12romis | S | T2 | done | COMMIT |
| T4 | Розібрати валідний звіт у ParsedSession (domain.parse_report, щасливий шлях) | domain | 12romis | M | — | done | COMMIT |
| T5 | Відхиляти невалідні повідомлення з кодом причини (domain.parse_report, гілки Rejection) | domain | 12romis | M | T4 | done | COMMIT |
| T6 | Розділити налаштування й паролі: INGEST_DATABASE_URL, MQTT_*, compose environment | wiring | 12romis | S | — | todo | — |
| T7 | Записувати сесії й відхилені: db.sessions.insert_session / insert_rejected | infra | 12romis | M | T2, T5 | todo | — |
| T8 | Перевірити ролі Postgres і облік втрат session_gaps | tests | 12romis | M | T3, T7 | todo | — |
| T9 | Обробити одне повідомлення: розбір → запис → COMMIT → результат (ingest.handler) | app | 12romis | M | T7 | todo | — |
| T10 | Запустити підписника: очікування БД, MQTT QoS 1 з manual ack, вихід при збої | app | 12romis | M | T6, T9 | todo | — |
| T11 | Наскрізні тести ingest: збій сховища, наздоганяння 1000 звітів, перезапуск | tests | 12romis | M | T8, T10 | todo | — |
| T12 | Скрипт Оператора: створити БД rover і ролі owner, ingest, viewer | infra | 12romis | S | — | todo | — |
| T13 | Скрипти Оператора: ACL брокера, пробна публікація, перевірка запуску, відкат | docs | 12romis | M | T10, T12 | todo | — |

**Total:** 13 tasks, ~10.5 person-days.
