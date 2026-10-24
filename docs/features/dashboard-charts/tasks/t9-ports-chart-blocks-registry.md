---
id: T9
title: "Додати web/chart_blocks.py: реєстр блоків з ізоляцією збою кожного блоку, лог chart_block_failed і вивід блоків між підсумками та виїздами"
layer: "ports"
deps: ["T8"]
blocks: ["T10", "T11", "T12", "T13", "T17"]
acs: ["AC-19", "AC-17", "AC-22"]
files_hint: ["src/rover_telemetry/web/chart_blocks.py", "src/rover_telemetry/web/app.py", "src/rover_telemetry/web/templates/dashboard.html", "tests/unit/test_chart_blocks.py", "tests/unit/test_dashboard_route.py"]
owner: "12romis"
estimate: "M"
context_budget: "M"
status: "done"
step: "COMMIT"
---

<!-- Принцип файлу: вбудований зріз, що потрібен задачі, з підписом джерела; посилання — запасний шлях. Кожен шматок має підпис `<file> §<section>, <id>, verbatim|abridged`. Джерело завжди важливіше за вбудовану копію. -->

# T9 — Додати web/chart_blocks.py: реєстр блоків з ізоляцією збою кожного блоку, лог chart_block_failed і вивід блоків між підсумками та виїздами

## Place in the sequence

- **Blocked by:** T8 — Додати токени --chart-* з тестом контрасту та макроси «Блок графіка», «Список приміток», «Схему-заповнювач» зі станами блока · **Blocks:** T10 — Побудувати блок «Акумулятор»: шаблон _charts_battery.html, опис, примітки і дані блока (напруга, на банку, просадка, причина завершення), T11 — Побудувати блок «Перешкоди»: шаблон _charts_obstacles.html зі схемою датчиків (SVG), карткою «Утримань усього», описом, примітками і даними блока, T12 — Побудувати блок «Рух і борти»: шаблон _charts_motion.html, опис, примітки «немає даних»/«без енкодера» і дані блока, T13 — Додати static/charts.js: ініціалізація ECharts по блоках з ізоляцією збою, вісь із порожніми слотами, підказка через textContent і графіки блока «Акумулятор», T17 — Додати інтеграційні тести сторінки на реальному Postgres: свіжість, дубль і відхилене, порожнє сховище, лише читання, затримка на 1000 виїздів · **Wave:** 2 (після найпізнішої залежності).
- **Lane:** спільний `src/rover_telemetry/web/app.py` з T7 — серіалізація; спільний `tests/unit/test_dashboard_route.py` з T7 — серіалізація; спільний `src/rover_telemetry/web/chart_blocks.py` з T10, T11, T12 — серіалізація; спільний `src/rover_telemetry/web/templates/dashboard.html` з T13 — серіалізація.

## Why (user story)

> **As a** Оператор сервера
> **I want** щоб блоки з графіками лише читали збережені дані, не залежали від сторонніх вузлів і щоб збій одного блоку не ламав сторінку чи збереження звітів
> **So that** дашборд можна безпечно показувати публічно, а ровер не втрачав звіти
>
> — `spec.md §4, US-10, verbatim` · full text: [spec.md](../spec.md)

> **As a** Власник ровера
> **I want** щоб новий збережений виїзд з'являвся на всіх графіках після оновлення сторінки, а дублі й відхилені повідомлення на них не потрапляли
> **So that** бачити результат останнього виїзду одразу й не бачити зайвого
>
> — `spec.md §4, US-11, verbatim` · full text: [spec.md](../spec.md)

Цей крок будує на сервері блоки з одного знімка так, що збій одного блоку дає повідомлення на його місці й не ламає сторінку.

## Inlined context

> **Chosen:** варіант 1. Підсумки, таблиця і графіки будуються з одного набору рядків; блок, що не збудувався, ловиться `try/except` на межі `web` окремо для кожного блоку й замінюється повідомленням (AC-19). Новий код не додає маршрутів, заголовків безпеки чи `fetch`; стану «завантаження» немає. Дані кожного блоку — `<script type="application/json">` через `|tojson`.
>
> — `adr/0001, Decision outcome, abridged` · full text: [adr/0001-embed-chart-data-in-the-page-from-one-read-only-snapshot.md](../adr/0001-embed-chart-data-in-the-page-from-one-read-only-snapshot.md)

> Збій побудови блоку — `try/except` на межі `web` для кожного блоку окремо, повідомлення «графік недоступний» на його місці. Збій у браузері — окремо для кожного блоку в `charts.js`; без скрипта — те саме повідомлення
>
> — `sad.md §8, Error handling, abridged` · full text: [sad.md](../sad.md)

> Web→Domain: побудувати ряди блоку Акумулятор → Domain-->>Web: ряди блоку; Web→Domain: побудувати ряди блоку Перешкоди; alt блок не вдалося побудувати: Domain--xWeb: помилка побудови; Web: записати назву блоку й клас помилки в лог, без подробиць для сторінки; Web-->>Caddy: сторінка, де на місці блоку повідомлення, що графік недоступний; else: сторінка з даними блоку. Далі в браузері: Charts: намалювати наявні блоки, при збої ініціалізації замінити блок повідомленням.
>
> — `sad.md §6, Critical flow 2 (AC-19), abridged` · full text: [sad.md](../sad.md)

> Єдина сторінка (`GET /`), що вже існує в `dashboard-summary`. Тут додаються лише три блоки між «Підсумками» й «Виїздами». Порядок зверху вниз: **h1 → Опис → Підсумки → Акумулятор → Перешкоди → Рух і борти → Виїзди**. Підсумки й таблиця виїздів не змінюються (AC-22: підсумки враховують новий виїзд так само).
>
> — `screens.md, SCR-01, intro, verbatim` · full text: [screens.md](../screens.md)

> | State | Trigger / condition | Components (from the inventory) | Source-ref |
> |---|---|---|---|
> | default | Є ≥ 1 виїзд, усі три блоки збудовано (AC-01, AC-05, AC-10, AC-18, AC-20, AC-22, AC-23). Дій, що змінюють дані, немає (AC-20) | `base.html` (базовий макет); Картка показника (макрос) ×8 (підсумки); Рядок виїзду (макрос); NEW: Блок графіка ×3 | wireframe SCR-01 / default |
> | empty | Жодного виїзду не збережено (AC-17, Flow US-08) | `base.html` (базовий макет); Картка показника (макрос); Порожній стан «немає даних» (макрос); Повідомлення стану (макрос); NEW: Блок графіка ×3 (стан `empty`) | wireframe SCR-01 / empty |
> | block-unavailable | Один (чи кілька) блоків не збудовано; решта сторінки ціла (AC-19, `sad.md` §6 потік 2) | `base.html` (базовий макет); Картка показника (макрос); Рядок виїзду (макрос); Повідомлення стану (макрос); NEW: Блок графіка (стан `error` для блока, що збіг; інші — з даними) | wireframe SCR-01 / block-unavailable |
> | error | Сховище недоступне: HTTP 503, блоків немає взагалі (`sad.md` §6, summary SAD §6 потік 2; змін немає) | `base.html` (базовий макет); Повідомлення стану (макрос) | wireframe SCR-01 / error (без змін відносно `docs/features/dashboard-summary/screens.md`) |
> | loading | N/A: сторінка формується на сервері одним запитом, загального стану завантаження немає; завантаження графіків — стан кожного блока (див. SCR-02…SCR-04 `loading`) | — | — |
> | success | N/A: екран нічого не змінює й не надсилає (AC-20), підтверджувати нічого | — | — |
> | validation | N/A: форм і полів вводу немає (`docs/constitution.md` №11) | — | — |
>
> — `screens.md, SCR-01, states table, verbatim` · full text: [screens.md](../screens.md)

> **Логування:** `chart_block_failed block=battery error_class=ValueError` (значення `block`: `battery`, `obstacles`, `motion`) — без вмісту звітів і без паролів; на сторінку — лише загальне повідомлення.
>
> — `sad.md §7 Monitoring + §8 Logging, abridged` · full text: [sad.md](../sad.md)

**To the executing agent:** працюй із вбудованого; якщо зріз недостатній, суперечить коду чи застарів — відкрий названий файл і дій за ним ([spec.md](../spec.md) · [sad.md](../sad.md) · [screens.md](../screens.md) · [adr/](../adr/)). Не вигадуй відсутнього.

## Data delta

No DB changes.

## API contract

- `GET /` → `200` HTML (стани `ok`/`empty` із блоками графіків) · `503` HTML без блоків (збій сховища, без змін). Нових маршрутів, методів і полів запиту немає: сторінка лишається `GET`-only.

— `sad.md §4/§8 + dashboard-summary/screens.md, SCR-01, abridged` · full text: [sad.md](../sad.md)

## Acceptance criteria

### AC-19 — error

> **Given** один із блоків не вдалося побудувати
> **When** Глядач відкриває дашборд
> **Then** на місці цього блоку є повідомлення простою мовою, що графік недоступний, без технічних подробиць, а опис, підсумки, таблиця та інші блоки працюють
>
> — `spec.md §5, AC-19, verbatim` · full text: [spec.md](../spec.md)

### AC-17 — domain invariant violation

> **Given** жодного виїзду ще не збережено
> **When** Глядач відкриває дашборд
> **Then** кожен із трьох блоків показує «немає даних» замість порожніх осей чи нульових ліній, сторінка лишається цілою, а підсумки показують нуль виїздів як виміряне число
>
> — `spec.md §5, AC-17, verbatim` · full text: [spec.md](../spec.md)

### AC-22 — cross-context

> **Given** сервіс приймання щойно зберіг новий виїзд
> **When** Власник ровера оновлює сторінку
> **Then** новий виїзд стоїть на своєму номері в кожному з трьох блоків, а підсумки його враховують
>
> — `spec.md §5, AC-22, verbatim` · full text: [spec.md](../spec.md)

## Checklist

- [ ] Створити `web/chart_blocks.py`: `BlockView(template: str, context: dict, data: dict)`; `RenderedBlock(key, title, state, view)`; реєстр `BLOCKS: list[BlockSpec]` (`key`, `title`, `build: Callable[[Snapshot], BlockView]`) — **порожній за замовчуванням**; кожна задача блока (T10–T12) додає свій запис; `render_blocks(snapshot) -> list[RenderedBlock]` — `src/rover_telemetry/web/chart_blocks.py`.
- [ ] Правило станів: немає жодного виїзду → усі зареєстровані блоки в стані `empty` **без виклику `build`** (AC-17); інакше кожен `build` виконується в окремому `try/except Exception`; збій → `state="error"`, `logger.error("chart_block_failed block=%s error_class=%s", key, type(exc).__name__)` без тексту винятку на сторінці — `chart_blocks.py`.
- [ ] Спільна оболонка даних блока для `charts.js` (документувати в докстрингу): `{"block": key, "slots": [{"seq": N, "gap": bool, "received": "ДД.ММ.РРРР ГГ:ХВ"|null}], "constants": {…}}` + ключі, специфічні для блока (їх визначають T10–T12) — `chart_blocks.py`.
- [ ] У `_render` (`web/app.py`) передати `blocks=render_blocks(snapshot)` лише для станів `ok`/`empty` (не для 503); у `dashboard.html` вивести блоки між `_summary.html` і `_sessions.html` у порядку реєстру (Акумулятор → Перешкоди → Рух і борти); заміна `<script>`-тегів для `charts.js`/`echarts.min.js` — у T13 — `src/rover_telemetry/web/app.py`, `src/rover_telemetry/web/templates/dashboard.html`.
- [ ] Тести: підставний блок, що кидає `ValueError("секрет")`, → сторінка `200`, на місці блока дослівне повідомлення про недоступність, у HTML немає тексту винятку, в логу — `chart_block_failed block=… error_class=ValueError`; інші блоки цілі; порожній знімок → `empty` без викликів `build`; підсумки й таблиця працюють — `tests/unit/test_chart_blocks.py`, `tests/unit/test_dashboard_route.py`.

## Edge cases

| Case | Behaviour |
|---|---|
| Збій одного блока | повідомлення на його місці, решта сторінки цілі; `chart_block_failed` у логу (AC-19) |
| Збір усіх трьох блоків збоїв | сторінка `200`: підсумки й таблиця працюють, три повідомлення |
| Сховище недоступне | наявний `503` без блоків; змін немає |
| Жодного виїзду | три блоки в `empty`, підсумки показують `0` як виміряне число (AC-17) |
| Блок не зареєстровано (наприклад, «Рух і борти» відкинуто) | сторінка будується без нього; жодної помилки |

## Definition of Done

- [ ] тести ізоляції блоків проходять без Docker: 3 з 3 незалежні (підставні збої по одному)
- [ ] у відповіді немає тексту винятку, шляхів чи назв класів помилок
- [ ] `GET /` лишається єдиним маршрутом сторінки; інших методів немає
- [ ] `ruff`, `mypy --strict` чисті
- [ ] кожне правило з розділу «Inlined context» (Hard Rules, конституція №4) досі виконується
- [ ] lint + vet чисті
