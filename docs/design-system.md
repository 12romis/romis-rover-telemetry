---
status: Living
tool: code
figma_file: ""
pen_file: ""
updated_at: "2026-10-25"
---

# Design system — romis-rover-telemetry

> Дизайн-канон дашборду, створений `/sdd:design-system` (раз на репозиторій); читають
> `ux-flows`, `screens`, `implement`, `review`. `docs/architecture-map.md` §Frontend / UI foundation
> лишається переліком **коду**; тут — дизайн-канон (інструмент, позиція, токени, інвентар,
> наскрізні правила). Оновлюється через `/sdd:design-system`.

## Platform posture

- **Posture:** mobile-first — бриф вимагає «зручно на телефоні», глядачі презентації відкривають дашборд з телефона (`docs/idea-brief.md` §5, §7); десктоп — розширення, не окремий макет.
- **Breakpoints / device classes:** базовий макет — від 360 px, одна колонка; широкий екран — від 640 px (`src/rover_telemetry/web/static/app.css:58`, припущення OP-1 фічі dashboard-summary). Горизонтального скролу сторінки немає.

## Design tool

- **Tool:** code — екрани малюються markdown-вайрфреймами в `docs/features/<slug>/screens.md`; Pencil MCP у сесії немає, Figma не авторизовано (і має ліміт 6 read-викликів на місяць).
- **Library location:** бібліотекою є сам код (`web/templates/`, `web/static/app.css`), окремого файлу дизайн-інструмента немає. Перехід на figma/pencil — повторний запуск `/sdd:design-system`.

## Token source

Джерело токенів — **один файл CSS-змінних** `src/rover_telemetry/web/static/app.css:2` (блок `:root`) (`docs/architecture-map.md:106`, ADR-0001: власний CSS, без Tailwind і без збірки). Екран не оголошує токен інлайн.

- **Colors:** CSS-змінні в `app.css`; ролі — фон, поверхня, текст, приглушений текст, акцент, межа, а також окремий колір статусу «немає даних» (відмінний від усіх кольорів вимірюваних значень). Кольори графіків перевіряються на контраст і не покладаються лише на колір (є мітка/підпис).
- **Spacing / sizing:** CSS-змінні в `app.css`; `--space-1…5` (4–24 px), `--touch-min: 44px` — мінімальна висота натискного елемента (`app.css:15`, припущення OP-2).
- **Typography:** CSS-змінні в `app.css`; системні шрифти, без завантаження з CDN (презентація не залежить від зовнішньої мережі — `docs/architecture-map.md:109`).

## Component inventory

Компоненти прив'язані до `file:line` коду. `screens.md` використовує лише ці імена або оголошує `NEW: <name>` з поясненням, чому не підходить жоден примітив.

| Component | Source (`file:line` / node / URL) | States it supports | Notes |
|---|---|---|---|
| `base.html` (базовий макет) | `src/rover_telemetry/web/templates/base.html:1` | default | Спільна шапка, одна колонка на телефоні, підключення `app.css` |
| Картка показника (макрос) | `src/rover_telemetry/web/templates/_macros.html:7` | default / немає даних | Значення + підпис + одиниця; `NULL` → «немає даних» |
| Порожній стан «немає даних» (макрос) | `src/rover_telemetry/web/templates/_macros.html:2` | default | Єдиний вигляд відсутнього значення; не нуль |
| Повідомлення стану (макрос) | `src/rover_telemetry/web/templates/_macros.html:15` | default | Текст на місці підсумків і списку для станів empty / error |
| Рядок виїзду (макрос) | `src/rover_telemetry/web/templates/_macros.html:27` | collapsed / expanded | Нативний `<details>`/`<summary>`, шапка ≥ 44 px, 10 полів AC-03, без скриптів (feature ADR-0002) |
| Позначка пропуску (макрос) | `src/rover_telemetry/web/templates/_macros.html:47` | default | Нерозгортуваний рядок зі штриховою рамкою; однакова для втраченого й відхиленого номера |
| Блок звіту (макрос) | `src/rover_telemetry/web/templates/_macros.html:22` | default | `<pre>` з форматованим JSON із `payload`; екранує лише autoescape |
| Графік ECharts | `src/rover_telemetry/web/templates/_macros.html:76` (макрос `chart`), `src/rover_telemetry/web/static/charts.js:255` (`mount`); бібліотека — `web/static/echarts.min.js` (`VENDOR.md`) | default / loading / empty / error | Дані вбудовані в сторінку як `<script type="application/json">` із одного зрізу (feature ADR-0001), без JSON-ендпоінтів і CDN; заповнювач — текст, роль `img` ставить скрипт після малювання |
| Блок графіка | `src/rover_telemetry/web/templates/_macros.html:57` (макрос `chart_block`) | ok / empty / error | Оболонка `<h2>`, опис, вміст блока й дані JSON; збій одного блока не торкається решти (feature `dashboard-charts`, AC-19) |
| Схема датчиків | `src/rover_telemetry/web/templates/_macros.html:90` (макрос `sensor_diagram`) | default / немає даних | Вбудований SVG ровера з чотирма числами біля датчиків; працює без скрипта |
| Список приміток блоку | `src/rover_telemetry/web/templates/_macros.html:82` (макроси `chart_notes`, `chart_warning`) | default / порожній | Рядки «Немає даних — виїзд № N: …» поза полотном графіка; порожній список нічого не виводить |
| Підказка виїзду | `src/rover_telemetry/web/static/charts.js:98` (`tooltipFor`), `:84` (`row`) | default / shown | Збирається лише через `createElement`/`textContent` (CSP, spec §6.1); пара «підпис — значення», відсутнє — «немає даних — причина» |

## Interaction & writing conventions

- **Errors:** вбудоване повідомлення в межах блоку, що не завантажився; решта сторінки працює. Тости не використовуються (клієнтського стану немає — `docs/architecture-map.md:110`).
- **Empty states:** простий текст «немає даних» у межах блоку; відсутнє значення (`NULL`) ніколи не показується як 0 — `docs/constitution.md` №4.
- **Loading:** стан завантаження графіка — простий текстовий заповнювач у тому ж місці; без анімацій, що зсувають макет.
- **Validation:** не застосовується — дашборд лише читає, форм немає (`docs/constitution.md` №11).
- **Microcopy tone:** українською, нейтрально й коротко, зрозуміло глядачеві без контексту; час — «отримано» (не «час сесії», `docs/constitution.md` №5), у зоні Europe/Kyiv; пропуск у `seq` показується як втрачена сесія, а не приховується (№6).
