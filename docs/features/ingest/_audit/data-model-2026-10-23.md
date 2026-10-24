---
updated_at: "2026-10-23"
---

# Audit — data-model — ingest (2026-10-23)

Міграції **staged** — ще не в живому дереві `migrations/`; `implement` промотує їх.

## Staged migrations

| Staged path | Що робить | Відкат |
|---|---|---|
| `docs/features/ingest/migrations/01_create_sessions.sql` | таблиця `sessions`, PK `(mac, seq)`, GRANT INSERT → `ingest`, SELECT → `viewer` | `01_create_sessions.rollback.sql` |
| `docs/features/ingest/migrations/02_create_rejected.sql` | таблиця `rejected`, identity PK, GRANT | `02_create_rejected.rollback.sql` |
| `docs/features/ingest/migrations/03_create_session_gaps.sql` | представлення `session_gaps`, GRANT SELECT → `viewer` | `03_create_session_gaps.rollback.sql` |

## Promote-time hint

Живе дерево: `migrations/0001_init.sql` + `0001_init.rollback.sql` (yoyo, послідовні 4-значні номери). Наступні ≈ `0002`, `0003`, `0004`; реальні номери присвоює `implement` при промоції, бо інша фіча може промотувати раніше. На промоції:
- замінити `-- depends: <PREV>` у `02` і `03` на фактичні імена попередніх міграцій; у `01` `depends: 0001_init` перевірити;
- прибрати рядки-коментарі «Промоція (implement)».

## Convention source and divergences

Джерела: `architecture-map.md` (yoyo, `NNNN_назва.sql` + `.rollback.sql`), SAD §5/§8, ADR-0002/0004/0005 (feature), ADR-0003 (foundation), конституція №4–6, 8, 10, 16. Greenfield, схемних прецедентів у `migrations/` немає (лише `SELECT 1`).

Розбіжності, які треба знати:
1. **Імена файлів: `.sql` / `.rollback.sql`, а не `.up.sql` / `.down.sql`** з Protocol скіла — за конвенцією репозиторію (`architecture-map.md`, `0001_init`). Пара зберігає сенс (повна оборотність).
2. **Три пари замість однієї `0002_sessions_rejected`** з SAD §5 (там імена — «пропозиція для tasks»): окремий відкат на сутність. Якщо власник хоче одну міграцію — об'єднати вручну, SQL не змінюється.
3. **Без `CHECK`** (end_reason, reason_code, формат `mac`): у репозиторії немає прецеденту, а запис не має падати на невідомому значенні (US-07, AC-05). Підтвердження власника — `<!-- TBD -->` у `data-model.md`.
4. **Ролі `ingest`, `viewer` мають існувати до міграції** (SAD §7 крок 1); у тестах їх створює фікстура. Інакше `GRANT` падає — це свідомо, а не мовчазне пропускання.

## Self-check (4 обов'язкові)

| Перевірка | Результат |
|---|---|
| Іменування збігається з конвенцією репозиторію | OK (див. розбіжність 1 — свідома, за конвенцією) |
| Оборотність: кожному CREATE — DROP | OK; виконано up → up (ідемпотентність) → rollback на ефемерному Postgres 16 |
| Індекси на FK | OK — FK немає; індекси поза PK відхилено з обґрунтуванням у `data-model.md` |
| Відповідність конвенціям | OK |

Додатково перевірено на ефемерному `pgvector/pgvector:pg16` (окремий контейнер, прод не чіпали):
- `ingest`: `INSERT … ON CONFLICT DO NOTHING` без цілі працює (дубль → 0 рядків); `SELECT`, `UPDATE`, `DELETE` — `permission denied` (AC-15/16, ADR-0005); `INSERT` в `rejected` з identity працює без права на послідовність.
- `viewer`: `SELECT` працює; `INSERT`/`DELETE` — `permission denied`.
- `session_gaps` для 28, 29, 31 повертає 30; після вставки 30 — порожньо (AC-08, AC-09); два `mac` з однаковим `seq` не конфліктують (AC-04).
- `sessions` має рівно одне обмеження (`sessions_pkey`) — інваріант ADR-0005.
- Відкат у зворотному порядку залишає порожню схему.

## Drift

Доменного коду ще немає (greenfield, `src/` не створено) — drift-перевірка N/A. Повторити після `implement`, коли з'явиться `domain/report.py`.

## Breaking-change decompositions

Немає: усі зміни — нові сутності.

## TBD

- `mac` без `CHECK` на формат; `end_reason` / `reason_code` без `CHECK` (рішення власника).
- `sessions(received_at)` — відкладено до читального запиту дашборду (крок 3).

## Next

Роут `quick` (розмір M — свідомий override власника). Умова N/A для `api` виконується: контракту не змінено (нових ендпоінтів/подій немає; контракт події канонічний, конституція №1) — `api` пропущено автоматично. Далі `/sdd:tasks ingest`; альтернатива — `/sdd:api ingest`.
