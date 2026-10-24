# Changelog — ingest

## ingest — звіти ровера зберігаються в Postgres

**What:** окремий фоновий сервіс `ingest` підписується на `rover/+/session` (QoS 1, постійна сесія), розбирає кожен звіт за контрактом і зберігає його як сесію (`sessions`) або, якщо звіт невалідний, як відхилений із причиною (`rejected`). Облік втрачених сесій — представлення `session_gaps`. Поруч — скрипти Оператора (`ops/`) для бази й ролей, поетапного звуження ACL брокера, пробної публікації, перевірки запуску та відкату.

**Why:** звіти, підтверджені брокеру, але ніким не прийняті, зникають назавжди; без збережених даних нічого показати на дашборді (кроки 3–6 роудмапу) — див. [spec](spec.md) §1/§2. Ключові рішення: підтвердження брокеру лише після `COMMIT` і вихід при збої сховища ([ADR-0001](adr/0001-commit-before-ack-and-exit-on-storage-failure.md)), сирі байти поруч із розібраними колонками ([ADR-0002](adr/0002-store-raw-message-bytes-next-to-parsed-columns.md)), поетапне звуження ACL з відкатом ([ADR-0003](adr/0003-narrow-broker-acl-in-staged-reversible-launch.md)), облік втрат у SQL від найменшого збереженого `seq` ([ADR-0004](adr/0004-compute-lost-sessions-in-sql-view-from-lowest-stored-seq.md)), `ON CONFLICT DO NOTHING` без цілі ([ADR-0005](adr/0005-insert-sessions-with-on-conflict-do-nothing-without-target.md)).

**How to use:** запуск сервісу — `docker compose up -d ingest` (потрібні `.env` за зразком `.env.example` і мережа `infra`). Перевірка запуску — `ops/verify_launch.sh`; повний порядок кроків — `ops/README.md` і `sad.md` §7.

**Operational notes:**
- Migration: `0002_create_sessions`, `0003_create_rejected`, `0004_create_session_gaps` (поверх `0001_init`); застосовує `owner` образом сервісу (`ops/README.md`, крок 2). Кожна має `.rollback.sql`.
- Feature flag / config: змінні `INGEST_DATABASE_URL`, `MQTT_*` у `.env`; паролі ролей Postgres і користувачів брокера — лише в `~/.config/claude-secrets/rover.env` і `mqtt.env`. Прод-крок: перед запуском створити БД `rover` і ролі (`ops/bootstrap_db.sh`).
- Rollback: `ops/rollback_acl.sh` повертає попередній ACL брокера; міграції — `rollback_migrations` (`ops/README.md`); сервіс — `docker compose stop ingest`.

**Acceptance criteria delivered:** AC-01…AC-18 (прийняття, дедублікація, відхилені, облік втрат, `null` ≠ 0, лише «отримано», сирий JSON, найменші права, ретрай і відновлення). AC-19 і AC-20 (перевірка реального звіту в проді та відкат звуження за відсутності звіту) виконує Оператор під час запуску — у цьому шипі не перевірені.
