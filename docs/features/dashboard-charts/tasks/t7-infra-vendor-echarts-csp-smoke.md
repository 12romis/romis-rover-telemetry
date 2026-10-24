---
id: T7
title: "Закріпити ECharts у web/static з VENDOR.md, віддавати /static з no-cache і перевірити в браузері, що canvas працює під незміненим CSP"
layer: "infra"
deps: []
blocks: ["T13"]
acs: ["AC-21"]
files_hint: ["src/rover_telemetry/web/static/echarts.min.js", "src/rover_telemetry/web/static/VENDOR.md", "src/rover_telemetry/web/app.py", "pyproject.toml", "tests/e2e/test_echarts_csp.py", "tests/unit/test_dashboard_route.py"]
owner: "12romis"
estimate: "M"
context_budget: "S"
status: "todo"
step: ""
---

<!-- Принцип файлу: вбудований зріз, що потрібен задачі, з підписом джерела; посилання — запасний шлях. Кожен шматок має підпис `<file> §<section>, <id>, verbatim|abridged`. Джерело завжди важливіше за вбудовану копію. -->

# T7 — Закріпити ECharts у web/static з VENDOR.md, віддавати /static з no-cache і перевірити в браузері, що canvas працює під незміненим CSP

## Place in the sequence

- **Blocked by:** — · **Blocks:** T13 — Додати static/charts.js: ініціалізація ECharts по блоках з ізоляцією збою, вісь із порожніми слотами, підказка через textContent і графіки блока «Акумулятор» · **Wave:** 1 (немає залежностей: старт паралельно з іншими задачами хвилі).
- **Lane:** спільний `src/rover_telemetry/web/app.py` з T9 — серіалізація; спільний `tests/unit/test_dashboard_route.py` з T9 — серіалізація.

## Why (user story)

> **As a** Оператор сервера
> **I want** щоб блоки з графіками лише читали збережені дані, не залежали від сторонніх вузлів і щоб збій одного блоку не ламав сторінку чи збереження звітів
> **So that** дашборд можна безпечно показувати публічно, а ровер не втрачав звіти
>
> — `spec.md §4, US-10, verbatim` · full text: [spec.md](../spec.md)

Цей крок гарантує, що бібліотека графіків віддається зі свого вузла й працює під CSP `default-src 'self'`, перш ніж на неї спиратимуться три блоки.

## Inlined context

> **Chosen:** варіант 1. Закріплена копія `echarts.min.js` у `web/static/` + власний `charts.js`, малювання на `<canvas>`; файл віддається зі свого вузла, `default-src 'self'` лишається; дані до скрипта йдуть вбудованими блоками (ADR-0001), кольори він читає з CSS-змінних. Схема датчиків — окремий вбудований SVG у шаблоні (працює без скрипта). Якщо canvas/підказки потребують послаблення політики — не послаблювати: `renderer: 'svg'` або нова ADR.
>
> — `adr/0002, Decision outcome + Consequences, abridged` · full text: [adr/0002-draw-charts-with-vendored-echarts-under-unchanged-csp.md](../adr/0002-draw-charts-with-vendored-echarts-under-unchanged-csp.md)

> Заголовок `Content-Security-Policy: default-src 'self'` лишається без змін: ні inline-скриптів, ні стилів, ні сторонніх вузлів (`web/app.py`, spec §6.1 «політика захисту не послаблена», AC-21).
>
> — `sad.md §2, Technical constraints, abridged` · full text: [sad.md](../sad.md)

> Закріплену копію ECharts `implement` один раз завантажує через npm на машині розробки й коммітить у репозиторій із SHA-256 у `VENDOR.md`; у проді мережа для цього не потрібна. Сторонній файл у репо — лише закріплена версія з SHA-256 і ліцензією у `static/VENDOR.md`; оновлення — окрема зміна, що перераховує SHA-256. Кеш: HTML лишається `no-store`, а `/static` отримує `Cache-Control: no-cache` (перевірка ETag).
>
> — `sad.md §7 + §8 (Vendored assets, Caching) + §4, abridged` · full text: [sad.md](../sad.md)

> ECharts на `<canvas>` та його підказки не перевірені під CSP `default-src 'self'` у реальному браузері — Mitigation: перевірити в браузерному тесті першою задачею `implement`; якщо потрібне послаблення політики — не послаблювати: перейти на `renderer: 'svg'` або повернутися до рішення в ADR-0002 (нова ADR, що замінює).
>
> — `sad.md §11, Risks (рядок 2), verbatim` · full text: [sad.md](../sad.md)

> Запасний шлях, якщо canvas чи підказки ECharts не працюють під CSP: `renderer: 'svg'`; політику не послаблювати.
>
> — `sad.md §11 + adr/0002, Consequences, abridged` · full text: [sad.md](../sad.md)

**To the executing agent:** працюй із вбудованого; якщо зріз недостатній, суперечить коду чи застарів — відкрий названий файл і дій за ним ([spec.md](../spec.md) · [sad.md](../sad.md) · [screens.md](../screens.md) · [adr/](../adr/)). Не вигадуй відсутнього.

## Data delta

No DB changes.

## API contract

Internal — no API surface.

## Acceptance criteria

### AC-21 — happy path

> **Given** Оператор сервера опублікував дашборд із графіками
> **When** Глядач відкриває публічну адресу
> **Then** сторінка з графіками відкривається через захищене з'єднання, працює без звернень до сторонніх вузлів, а збереження нових звітів триває, навіть якщо дашборд зупинено
>
> — `spec.md §5, AC-21, verbatim` · full text: [spec.md](../spec.md)

## Checklist

- [ ] На машині розробки (поза репо, у тимчасовому каталозі) завантажити ECharts 5.x через `npm pack echarts@<5.x.y>`; скопіювати `dist/echarts.min.js` у `src/rover_telemetry/web/static/echarts.min.js`, ліцензію Apache-2.0 (LICENSE/NOTICE) покласти поруч — `web/static/`.
- [ ] Створити `web/static/VENDOR.md`: версія, джерело (`npm pack`), SHA-256 файлу, розмір, ліцензія Apache-2.0, правило «оновлення — окрема зміна, що перераховує SHA-256» — `src/rover_telemetry/web/static/VENDOR.md`.
- [ ] У `web/app.py` змінити заголовок для відповідей `/static/*` на `Cache-Control: no-cache` (ETag лишається); HTML і решта — `no-store`; `Content-Security-Policy` не змінювати — `src/rover_telemetry/web/app.py`. Юніт-тест у `tests/unit/test_dashboard_route.py`: заголовки `/` (`no-store`, CSP дослівно `default-src 'self'`) і `/static/echarts.min.js` (`no-cache`).
- [ ] Додати в `[project.optional-dependencies].dev` пакет `playwright` і маркер `e2e` у `[tool.pytest.ini_options].markers`; e2e-тести пропускаються (`pytest.importorskip("playwright")` + skip без встановленого браузера), щоб `pytest -m 'not integration'` не вимагав браузера — `pyproject.toml`.
- [ ] `tests/e2e/test_echarts_csp.py`: підняти `app` у потоці, змонтувати в тесті **лише тестовий** маршрут зі сторінкою-пробою й файл ініціалізації (inline-скриптів CSP не дозволяє); у Chromium намалювати найпростіший стовпчастий графік на canvas; перевірити: подій `securitypolicyviolation` немає, помилок консолі немає, canvas не порожній, усі запити — лише до хоста тесту (0 сторонніх) — `tests/e2e/test_echarts_csp.py`.

## Edge cases

| Case | Behaviour |
|---|---|
| Canvas або підказка ECharts порушує CSP | політику не послаблювати: перейти на `renderer: 'svg'` (перевірити тим самим тестом) або відкрити нову ADR; рішення записати в `VENDOR.md` |
| Браузер для e2e не встановлено | e2e-тести пропускаються з поясненням; решта набору зелена |
| Повторне відкриття сторінки | `/static/echarts.min.js` перевіряється за ETag (`no-cache`), HTML — `no-store` |
| SHA-256 у `VENDOR.md` не збігається з файлом | юніт-тест перераховує хеш і падає |

## Definition of Done

- [ ] `pytest -m 'not integration'` зелений без браузера (e2e пропущено)
- [ ] e2e-проба ECharts проходить у Chromium: 0 порушень CSP, 0 сторонніх запитів
- [ ] `VENDOR.md` містить версію, SHA-256, ліцензію; тест хеша зелений
- [ ] CSP у `web/app.py` дослівно `default-src 'self'` (тест)
- [ ] кожне правило з розділу «Inlined context» (Hard Rules, конституція №4) досі виконується
- [ ] lint + vet чисті
