# Changelog — dashboard-summary

## dashboard-summary — публічний дашборд «Підсумки + таблиця виїздів»

**What:** сторінка `https://rover.romis.cloud/` лише для читання: короткий опис простою мовою, вісім підсумків за всіма збереженими виїздами (кількість, пробіг, час руху, утримання перед перешкодою, кінцева напруга останнього виїзду, «отримано востаннє» за київським часом, прошивка останнього виїзду, втрачені сесії) і список виїздів від найбільшого номера сесії. Кожен виїзд розгортається (`<details>`, без скриптів) до повного звіту. Відсутнє значення показується як «немає даних», а виміряний нуль — нулем; номери без виїзду мають позначку «виїзду з цим номером немає». Читається на телефоні в одну колонку.

**Why:** власник не бачив роботи ровера, а глядачам презентації нічого було показати — див. [spec](spec.md) §1/§2. Ключові рішення: підсумки й список рахуються в `domain` з одного знімка лише для читання ([ADR-0001](adr/0001-compute-dashboard-summary-in-domain-from-one-read-only-snapshot.md)), звіт розгортається нативним `<details>` без скриптів ([ADR-0002](adr/0002-render-reports-inline-in-native-details-without-scripts.md)).

**How to use:** відкрити `https://rover.romis.cloud/`; після нового виїзду оновити сторінку (кешу даних немає). Якщо сховище недоступне — сторінка з описом і повідомленням (HTTP 503).

**Operational notes:**
- Migration: <!-- none -->; читається наявна таблиця `sessions` і представлення `session_gaps` ролі `viewer`.
- Feature flag / config: `WEB_DATABASE_URL` (роль `viewer`), необов'язкові `WEB_DB_CONNECT_TIMEOUT_S` (3), `WEB_DB_STATEMENT_TIMEOUT_S` (5); залежність `tzdata`.
- Публікація: alias `rover-web` у `docker-compose.yml`, блок `rover.romis.cloud` у `/opt/n8n/Caddyfile`, запис DNS A у Cloudflare, `viewer CONNECTION LIMIT 3` — [ops/README.md](../../../ops/README.md), «Публікація дашборду».
- Rollback: прибрати блок із `/opt/n8n/Caddyfile` (копія до змін — `Caddyfile.bak-rover`), перезавантажити Caddy, `docker compose stop web`; `ingest` це не зачіпає.

**Acceptance criteria delivered:** AC-01…AC-18 (підсумки, опис, список, причини завершення, розгорнутий звіт, нуль проти «немає даних», втрачені сесії, «отримано», телефон, empty/error, лише читання, публікація, актуальність, дубль).
