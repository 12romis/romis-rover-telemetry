---
id: T5
title: "Створити базовий макет, токени CSS, макроси «немає даних»/картка/повідомлення та блок «Опис»"
layer: "ui"
deps: []
blocks: ["T6"]
acs: ["AC-02", "AC-10"]
files_hint: ["src/rover_telemetry/web/templates/base.html", "src/rover_telemetry/web/templates/_macros.html", "src/rover_telemetry/web/templates/_description.html", "src/rover_telemetry/web/static/app.css", "src/rover_telemetry/web/templating.py", "tests/unit/test_templates_base.py", "docs/design-system.md"]
owner: "12romis"
estimate: "M"
context_budget: "M"
status: "todo"
step: ""
---

# T5 — Створити базовий макет, токени CSS, макроси «немає даних»/картка/повідомлення та блок «Опис»

## Place in the sequence

- **Blocked by:** — · **Blocks:** T6 — Побудувати сторінку dashboard.html: опис, вісім карток підсумків, стани empty і error · **Wave:** 1 (немає залежностей, стартує з першою хвилею).
- **Lane:** спільні файли з T6 (`src/rover_telemetry/web/templating.py`), T7 (`docs/design-system.md, src/rover_telemetry/web/static/app.css, src/rover_telemetry/web/templates/_macros.html`) — серіалізуються (порядок задає DAG).

## Why (user story)

> **As a** Глядач
> **I want** переглядати сторінку на телефоні без прокручування вбік
> **So that** презентацію можна показати з будь-якого пристрою
>
> — `spec.md §4, US-06, verbatim` · full text: [spec.md](../spec.md)

Закладає мобільний одноколонковий макет, токени й примітиви (`немає даних`, картка показника, повідомлення), на яких стоять усі решта екранні задачі.

## Inlined context

> - Власний CSS у `web/static/app.css` без Tailwind і збірки; без CDN і без шрифтів з мережі; бібліотеку графіків ця фіча не додає (`docs/design-system.md`, spec §3).
>
> — `sad.md §2, Technical, CSS, verbatim` · full text: [sad.md](../sad.md)

> - Мобільна розкладка обов'язкова: одна колонка, без прокручування вбік (рішення власника №13, `docs/design-system.md` §Platform posture).
>
> — `sad.md §2, Technical, мобільна розкладка, verbatim` · full text: [sad.md](../sad.md)

> - **Три вигляди значення (AC-06, конституція №4).** Виміряний нуль → `0 м`, `0 с`, `0` — звичайним числом. Число → число з одиницею. Не передано (`NULL`) → слова «немає даних» макросом «Порожній стан «немає даних»»: курсив, приглушений колір з окремої ролі токенів і сам текст, тож вигляд відрізняється від числа не лише кольором. Жодних прочерків, порожніх клітинок, `—` чи `0` замість відсутнього.
>
> — `screens.md «Правила показу», три вигляди значення, verbatim` · full text: [screens.md](../screens.md)

> - **Телефон (від 360 px, базовий макет):** одна колонка; картки підсумків у 2 колонки, картки 4 і 5 на всю ширину (довгі підписи); рядок виїзду — картка на всю ширину; поля рядка — пари «підпис — значення» в 2 колонки, довгі значення переносяться всередині картки (`overflow-wrap`), сторінка вбік не прокручується (AC-10).
>
> — `screens.md SCR-01, розкладка, телефон, verbatim` · full text: [screens.md](../screens.md)

> - **Широкий екран (від 640 px — припущення OP-1):** той самий макет, лише більше колонок: підсумки у 4 колонки, поля рядка в 4 колонки; контент обмежено по ширині й центровано. Окремих флоу немає.
>
> — `screens.md SCR-01, розкладка, широкий екран, verbatim` · full text: [screens.md](../screens.md)

> - **Ціль дотику:** шапка рядка виїзду має висоту ≥ 44 px на всю ширину рядка (припущення OP-2).
>
> — `screens.md SCR-01, розкладка, ціль дотику, verbatim` · full text: [screens.md](../screens.md)

> **Копія блоку «Опис» (AC-02), вона ж зразок для `implement`:**
> >
> > **Телеметрія ровера.** Це дашборд ровера — невеликої машини на колесах, яку керують з пульта. Виїзд — один запуск ровера: від увімкнення моторів до зупинки. Утримання — коли ровер зупиняється перед перешкодою, доки вона не зникне. Ровер не знає часу, тому ми показуємо, коли звіт отримано.
>
> — `screens.md SCR-01, копія блоку «Опис», verbatim` · full text: [screens.md](../screens.md)

> | Security headers | `Content-Security-Policy: default-src 'self'` (без inline-скриптів і стилів), `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`; жодних запитів до сторонніх вузлів | тут, spec §6 |
>
> — `sad.md §8, Security headers, verbatim` · full text: [sad.md](../sad.md)

> | Придатність на телефоні | немає горизонтального прокручування сторінки при ширині екрана від 360 px | візуальна перевірка власником на телефоні й емулятор у тесті |
>
> — `spec.md §6, Придатність на телефоні, verbatim` · full text: [spec.md](../spec.md)

> | Зовнішні залежності | 0 запитів до сторонніх вузлів | перегляд мережевих запитів сторінки в тесті |
>
> — `spec.md §6, Зовнішні залежності, verbatim` · full text: [spec.md](../spec.md)

**Fallback:** insufficient or contradicted by the code → read the named file in full ([spec.md](../spec.md) · [sad.md](../sad.md) · [screens.md](../screens.md) · [adr/](../adr/)) and follow it. Do not guess.

## Data delta

No DB changes.

## API contract

Internal — no API surface.

## Acceptance criteria

### AC-02 — happy path

> **Given** Глядач відкриває дашборд уперше
> **When** сторінка завантажилась
> **Then** над підсумками є короткий опис того, що це ровер, що таке виїзд і що означає утримання перед перешкодою, без внутрішніх термінів і скорочень
>
> — `spec.md §5, AC-02, verbatim` · full text: [spec.md](../spec.md)

### AC-10 — happy path

> **Given** Глядач відкриває дашборд на екрані телефона
> **When** сторінка завантажилась
> **Then** підсумки й таблиця читаються в одну колонку без прокручування сторінки вбік, а натискні елементи достатньо великі для пальця
>
> — `spec.md §5, AC-10, verbatim` · full text: [spec.md](../spec.md)

## Checklist

- [ ] Тести спочатку — `tests/unit/test_templates_base.py` (без FastAPI): рендер через `make_environment()`; опис містить 3 визначення (ровер, виїзд, утримання); `no_data` дає окремий клас і текст «немає даних»; `0` рендериться як `0`
- [ ] `web/templating.py`: `make_environment()` — `jinja2.Environment(PackageLoader('rover_telemetry.web', 'templates'), autoescape=True)`; фільтр `safe` не використовується ніде
- [ ] `templates/base.html`: `<html lang="uk">`, `<meta name="viewport" content="width=device-width, initial-scale=1">`, лише `<link rel="stylesheet" href="/static/app.css">`; без інлайн-стилів, інлайн-скриптів і зовнішніх адрес (CSP `default-src 'self'`)
- [ ] `templates/_macros.html`: `no_data()` (`<em class="no-data">немає даних</em>`), `metric_card(label, value, note=None, wide=False)` — **перевірка `value is none`, не truthiness** (нуль — число), `state_message(text)`
- [ ] `templates/_description.html`: текст блоку «Опис» дослівно з `screens.md` (OP-4)
- [ ] `static/app.css`: токени-змінні `:root` (фон, поверхня, текст, приглушений, акцент, межа, окрема роль «немає даних»; відступи; системні шрифти), одна колонка, картки в 2 колонки (4-та й 5-та — на всю ширину), `@media (min-width: 640px)` — 4 колонки й обмежена ширина, `overflow-wrap`, ціль дотику ≥ 44 px; без `@import`, без `url(http…)`
- [ ] У `docs/design-system.md` зареєструвати токени, брейкпоінт 640 px (OP-1), ціль дотику 44 px (OP-2) і нові компоненти «Повідомлення стану» (решту — у T7); замінити «заплановані» прив'язки на `file:line`

## Edge cases

| Case | Behaviour |
|---|---|
| `value = 0` у `metric_card` | показується `0` (число), не «немає даних» — перевірка `is none` |
| `value = None` | макрос `no_data`: курсив, окремий колір і текст — відрізняється від числа не лише кольором |
| Вузький екран 360 px | одна колонка, довгий підпис/значення переноситься (`overflow-wrap`), горизонтального прокручування немає |
| Текст із `<script>` у значенні картки | виводиться екранованим текстом (автоекранування) |
| Нова зовнішня адреса в CSS/шаблоні | тест падає: у `app.css`, `base.html` немає `http://`, `https://`, `@import`, `<script`, `style=` |

## Definition of Done

- [ ] `pytest tests/unit/test_templates_base.py` проходить (опис, `no_data` проти `0`, відсутність зовнішніх адрес/скриптів/інлайн-стилів, `viewport`)
- [ ] `app.css` містить правило `@media (min-width: 640px)` і мінімальну висоту натискного елемента 44 px
- [ ] `docs/design-system.md` оновлено: токени, брейкпоінт, компоненти з `file:line`
- [ ] всі Hard Rule вище дотримані; `ruff`/`mypy --strict` без нових попереджень
- [ ] кожне Hard Rule, процитоване вище, лишається дотриманим
- [ ] lint + type-check чисті (`ruff check . && ruff format --check . && mypy src`)
