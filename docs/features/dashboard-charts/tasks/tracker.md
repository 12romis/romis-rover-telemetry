# Tracker — dashboard-charts

> Status of every task in the epic. `implement` updates **Status** and **Step** after every
> subagent it runs (and commits them with the task), so this table shows where the run is right now.
> Status: `todo` · `in_progress` · `blocked` · `review` · `done`.
> Step: `SELECT` · `RED` · `GREEN` · `REFACTOR` · `GATE` · `REVIEW` · `COMMIT` (`—` before the task starts).
> A `blocked` row carries its reason in Step, e.g. `GATE — lint red after 3 retries`.

| # | Task | Layer | Owner | Estimate | Blocked by | Status | Step |
|---|---|---|---|---|---|---|---|
| T1 | Розширити StoredSession полями графіків і додати domain/charts.py: константи з джерелами, Value/Absent/AbsentReason, вісь за номером сесії з порожніми місцями | domain | 12romis | M | — | done | COMMIT |
| T2 | Читати в read_snapshot нові колонки sessions для графіків тим самим знімком | infra | 12romis | S | T1 | done | COMMIT |
| T3 | Побудувати в domain ряди блоку «Акумулятор»: три напруги, напруга на банку, просадка, причина завершення, відсутні значення | domain | 12romis | M | T1 | done | COMMIT |
| T4 | Побудувати в domain ряди блоку «Перешкоди»: найменша відстань і датчик, «утримань не було», лічильники датчиків, секунди вимкненого захисту | domain | 12romis | M | T1 | done | COMMIT |
| T5 | Побудувати в domain ряди блоку «Рух і борти»: швидкості в об/хв і м/с, різниця бортів, причини відсутності, «без енкодера» | domain | 12romis | M | T1 | done | COMMIT |
| T6 | Додати в web/formatting.py підписи причин відсутності, датчиків і бортів, м/с, об/хв і напругу на банку | ui | 12romis | S | T1 | done | COMMIT |
| T7 | Закріпити ECharts у web/static з VENDOR.md, віддавати /static з no-cache і перевірити в браузері, що canvas працює під незміненим CSP | infra | 12romis | M | — | done | COMMIT |
| T8 | Додати токени --chart-* з тестом контрасту та макроси «Блок графіка», «Список приміток», «Схему-заповнювач» зі станами блока | ui | 12romis | M | — | done | COMMIT |
| T9 | Додати web/chart_blocks.py: реєстр блоків з ізоляцією збою кожного блоку, лог chart_block_failed і вивід блоків між підсумками та виїздами | ports | 12romis | M | T8 | done | COMMIT |
| T10 | Побудувати блок «Акумулятор»: шаблон _charts_battery.html, опис, примітки і дані блока (напруга, на банку, просадка, причина завершення) | ui | 12romis | M | T3, T6, T9 | done | COMMIT |
| T11 | Побудувати блок «Перешкоди»: шаблон _charts_obstacles.html зі схемою датчиків (SVG), карткою «Утримань усього», описом, примітками і даними блока | ui | 12romis | L | T4, T6, T9 | done | COMMIT |
| T12 | Побудувати блок «Рух і борти»: шаблон _charts_motion.html, опис, примітки «немає даних»/«без енкодера» і дані блока | ui | 12romis | M | T5, T6, T9 | done | COMMIT |
| T13 | Додати static/charts.js: ініціалізація ECharts по блоках з ізоляцією збою, вісь із порожніми слотами, підказка через textContent і графіки блока «Акумулятор» | ui | 12romis | L | T7, T9, T10 | done | COMMIT |
| T14 | Додати в charts.js графіки блока «Перешкоди»: найменша відстань на тлі порога 190 мм і секунди вимкненого захисту | ui | 12romis | M | T11, T13 | done | COMMIT |
| T15 | Додати в charts.js графіки блока «Рух і борти»: швидкість бортів у м/с із піками та різниця бортів із причинами відсутності | ui | 12romis | M | T12, T13 | done | COMMIT |
| T16 | Додати наскрізні браузерні тести сторінки: 360 px, дотик, 0 сторонніх запитів, CSP, збій кожного блока, XSS-фікстура | tests | 12romis | M | T13, T14 | done | COMMIT |
| T17 | Додати інтеграційні тести сторінки на реальному Postgres: свіжість, дубль і відхилене, порожнє сховище, лише читання, затримка на 1000 виїздів | tests | 12romis | M | T2, T9, T10, T11 | blocked | GATE — latency p95 1.11 s > 1 s limit on loaded 1-CPU host (baseline page test 2.4 s) |
| T18 | Review F8: у domain/charts.py `NO_STRAIGHT` лише коли moving_ms>0 і обидва encoders True, інакше `NOT_REPORTED` (ADR-0003) | domain | 12romis | S | — | done | COMMIT |
| T19 | Review F7+F4: рендер вмісту блока й JSON під try у render_blocks; holds_count і тривалість виїзду в даних блока «Перешкоди» (формат format_duration_ms) | ports | 12romis | S | T18 | todo | — |
| T20 | Review F10+F14: видалити мертві форматери з дубльованими константами; прибрати тавтологічний статичний тест JS, прихований імпорт і type: ignore/noqa без обґрунтування | ui | 12romis | S | — | todo | — |
| T21 | Review F11: видимий стан loading — прибрати hidden із заповнювача .chart, та сама висота, тест на видимість | ui | 12romis | S | — | todo | — |
| T22 | Review F2+F3+F4+F13: динамічні межі осі напруги; slotStates для акумулятора та причина вздовж слотів; підказка «Перешкоди» за SCR-05; dispose() при частковому збої блока | ui | 12romis | S | T19, T21 | todo | — |
| T23 | Review F6: тест AC-22 перевіряє картку «Виїздів» == 2 (підсумки), а не рядки таблиці | tests | 12romis | S | — | todo | — |
| T24 | Review F9+F5: примітка в SAD §6 про покриття решти AC ux-flows/screens; ручна ship-перевірка AC-21 (HTTPS через Caddy, збереження при зупиненому web) | docs | 12romis | S | — | todo | — |

**Total:** 24 tasks (T18–T24 — follow-up за рев'ю 2026-10-24), ~16 person-days. Блок «Рух і борти» (T5, T12, T15) відкидається першим, якщо до 2026-10-26 не вистачить часу (spec §1): решта задач від нього не залежить.
