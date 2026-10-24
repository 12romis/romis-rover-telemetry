---
status: Living
tool: code
figma_file: ""
pen_file: ""
updated_at: "2026-10-24"
---

# Design system — romis-rover-telemetry

> Дизайн-канон дашборду, створений `/sdd:design-system` (раз на репозиторій); читають
> `ux-flows`, `screens`, `implement`, `review`. `docs/architecture-map.md` §Frontend / UI foundation
> лишається переліком **коду**; тут — дизайн-канон (інструмент, позиція, токени, інвентар,
> наскрізні правила). Оновлюється через `/sdd:design-system`.

## Platform posture

- **Posture:** mobile-first — бриф вимагає «зручно на телефоні», глядачі презентації відкривають дашборд з телефона (`docs/idea-brief.md` §5, §7); десктоп — розширення, не окремий макет.
- **Breakpoints / device classes:** не зафіксовані; значення визначає перший екран («Підсумки + таблиця виїздів») і записує сюди. Одна колонка на вузькому екрані, горизонтального скролу сторінки немає.

## Design tool

- **Tool:** code — екрани малюються markdown-вайрфреймами в `docs/features/<slug>/screens.md`; Pencil MCP у сесії немає, Figma не авторизовано (і має ліміт 6 read-викликів на місяць).
- **Library location:** бібліотекою є сам код (`web/templates/`, `web/static/app.css`), окремого файлу дизайн-інструмента немає. Перехід на figma/pencil — повторний запуск `/sdd:design-system`.

## Token source

Токени ще не існують: `src/rover_telemetry/web/static/` порожній (`.gitkeep`). Джерело токенів — **один файл CSS-змінних** `web/static/app.css` (`docs/architecture-map.md:106`, ADR-0001: власний CSS, без Tailwind і без збірки). Конкретні значення вирішує перший екран і реєструє `implement`; екран не оголошує токен інлайн.

- **Colors:** CSS-змінні в `app.css`; ролі — фон, поверхня, текст, приглушений текст, акцент, межа, а також окремий колір статусу «немає даних» (відмінний від усіх кольорів вимірюваних значень). Кольори графіків перевіряються на контраст і не покладаються лише на колір (є мітка/підпис).
- **Spacing / sizing:** CSS-змінні в `app.css`; шкала відступів і мінімальна ціль дотику для телефона — фіксуються першим екраном.
- **Typography:** CSS-змінні в `app.css`; системні шрифти, без завантаження з CDN (презентація не залежить від зовнішньої мережі — `docs/architecture-map.md:109`).

## Component inventory

Готових компонентів немає (greenfield). Рядки — **заплановані** примітиви з `architecture-map.md`; після `implement` прив'язка замінюється на `file:line` коду. `screens.md` використовує лише ці імена або оголошує `NEW: <name>` з поясненням, чому не підходить жоден примітив.

| Component | Source (`file:line` / node / URL) | States it supports | Notes |
|---|---|---|---|
| `base.html` (базовий макет) | `docs/architecture-map.md:105` (планується `web/templates/base.html`) | default | Спільна шапка, одна колонка на телефоні, підключення `app.css` |
| Картка показника (макрос) | `docs/architecture-map.md:108` | default / немає даних | Значення + підпис + одиниця; `NULL` → «немає даних» |
| Порожній стан «немає даних» (макрос) | `docs/architecture-map.md:108` | default | Єдиний вигляд відсутнього значення; не нуль |
| Графік ECharts | `docs/architecture-map.md:109` (`web/static/echarts.min.js`) | default / loading / empty / error | Дані з JSON-ендпоінтів FastAPI (`docs/architecture-map.md:110`); без CDN |

## Interaction & writing conventions

- **Errors:** вбудоване повідомлення в межах блоку, що не завантажився; решта сторінки працює. Тости не використовуються (клієнтського стану немає — `docs/architecture-map.md:110`).
- **Empty states:** простий текст «немає даних» у межах блоку; відсутнє значення (`NULL`) ніколи не показується як 0 — `docs/constitution.md` №4.
- **Loading:** стан завантаження графіка — простий текстовий заповнювач у тому ж місці; без анімацій, що зсувають макет.
- **Validation:** не застосовується — дашборд лише читає, форм немає (`docs/constitution.md` №11).
- **Microcopy tone:** українською, нейтрально й коротко, зрозуміло глядачеві без контексту; час — «отримано» (не «час сесії», `docs/constitution.md` №5), у зоні Europe/Kyiv; пропуск у `seq` показується як втрачена сесія, а не приховується (№6).
