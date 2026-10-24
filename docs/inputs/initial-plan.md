# Початковий план (вхід для `/sdd:interview` і `/sdd:survey`)

Узгоджено з власником 2026-10-22/23. Це вхід, а не специфікація: деталі уточнює конвеєр SDD.

## Прийняті рішення

- **Ingest:** окремий Python-сервіс (не n8n) у Docker-мережі `infra`; `paho-mqtt` 2.x з `manual_ack`, `psycopg` 3; підключення до `mosquitto:1883`; топік `rover/+/session`, QoS 1, фіксований client id, `clean_session=false`; підтвердження після `COMMIT`; `ON CONFLICT (mac, seq) DO NOTHING`; невалідні повідомлення — у таблицю відхилених.
- **Дедублікація:** лише `(mac, seq)`; додаткових ідентифікаторів не потрібно (контракт гарантує, що `seq` не повторюється після перезапуску).
- **Зберігання:** окрема БД `rover` у наявному Postgres 16; розібрані колонки + сирий `payload jsonb`; ролі власник / ingest (insert) / дашборд (select).
- **Агрегації:** SQL-представлення (обсяг даних малий, TimescaleDB не потрібен): сесія з похідними метриками, по днях, пропуски `seq`, версії прошивки, цикли заряду.
- **Дашборд:** FastAPI + ECharts, лише читання; публічний домен `rover.romis.cloud` за Caddy, без автентифікації (рішення власника №4, конституція №12).
- **Брокер:** облікові записи з найменшими правами (ровер — запис у `rover/+/session`; ingest і перегляд — читання).
- **Час:** лише `received_at`; поля `boot_id`, `end_uptime_ms`, `sent_uptime_ms`, `sent_at_utc` заплановані в прошивці — схема має прийняти їх адитивно.

## Ідеї для дашборду (з контракту)

- Підсумки: пробіг, час руху, кількість виїздів, утримання, остання напруга, останній контакт і прошивка, втрачені сесії.
- Активність у часі (за `received_at`).
- Акумулятор: старт / мінімум / кінець по виїздах, просадка (старт − мінімум) проти швидкості, тренд.
- Склад часу виїзду: рух / утримання / решта; частка часу з вимкненим захистом (`tof_control_off_ms`).
- Перешкоди: схема ровера з 4 датчиками за `holds.by_sensor`, розподіл `holds.min_mm` відносно порога 190 мм.
- Борти: лівий проти правого, `imbalance_pct` у часі, пікові швидкості, лінійна швидкість (об/хв × 0.1382 м / 60), сесії без енкодера.
- Причини завершення (`disarm`, `failsafe_link_lost`, `failsafe_voltage`).
- Якість даних: шкала `seq` з пропусками, відхилені повідомлення.
- Таблиця виїздів із сирим JSON.

## Реальні звіти

Отримано 2026-10-22, MAC `288485922c94`, прошивка `4727195`: seq 26 і seq 27 — у `tests/fixtures/` після scaffold (тексти — нижче).

```json
{"event":"rover.session.v1","schema_version":1,"seq":26,"duration_ms":4300,"end_reason":"disarm","voltage_start_mv":7687,"voltage_end_mv":7679,"voltage_min_mv":7675,"holds":{"count":0,"total_ms":0,"min_mm":null,"min_sensor":null,"by_sensor":{"left_front":0,"front":0,"right_front":0,"rear":0}},"tof_control_off_ms":4300,"distance_cm":0,"moving_ms":0,"speed":{"left_avg_rpm":null,"left_peak_rpm":null,"right_avg_rpm":null,"right_peak_rpm":null,"imbalance_pct":null},"encoders":{"left":true,"right":true},"fw":{"version":"4727195","git":"4727195","dirty":false,"idf":"v6.1"},"mac":"288485922c94"}
{"event":"rover.session.v1","schema_version":1,"seq":27,"duration_ms":27660,"end_reason":"disarm","voltage_start_mv":7691,"voltage_end_mv":7675,"voltage_min_mv":7628,"holds":{"count":1,"total_ms":12400,"min_mm":103,"min_sensor":"front","by_sensor":{"left_front":0,"front":1,"right_front":1,"rear":1}},"tof_control_off_ms":6660,"distance_cm":17,"moving_ms":2360,"speed":{"left_avg_rpm":30.6,"left_peak_rpm":100.1,"right_avg_rpm":30.3,"right_peak_rpm":105.0,"imbalance_pct":1.1},"encoders":{"left":true,"right":true},"fw":{"version":"4727195","git":"4727195","dirty":false,"idf":"v6.1"},"mac":"288485922c94"}
```
