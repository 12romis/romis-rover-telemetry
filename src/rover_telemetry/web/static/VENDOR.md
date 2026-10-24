# Закріплені сторонні файли

Сторонній файл у репозиторії — лише закріплена версія з SHA-256 і ліцензією. Оновлення —
окрема зміна, що перераховує SHA-256 (його звіряє юніт-тест `test_vendored_echarts_matches_sha256_in_vendor_md`).

## Apache ECharts

| Поле | Значення |
|---|---|
| Файл | `echarts.min.js` |
| Версія | 5.6.0 |
| Джерело | `npm pack echarts@5.6.0`, файл `package/dist/echarts.min.js` (цілісність tarball звірено з `npm view echarts@5.6.0 dist.integrity`) |
| SHA-256 | `bf4a223524e40b77c304bec67e1222cf551f14880cf42c69dc046558e11c07b1` |
| Розмір | 1034102 байт |
| Ліцензія | Apache-2.0 (`LICENSE-echarts`, `NOTICE-echarts` поруч) |
| Рішення | ADR-0002 (`docs/features/dashboard-charts/adr/`): закріплена копія, `default-src 'self'` без змін |

Результат перевірки під CSP (`tests/e2e/test_echarts_csp.py`): canvas і підказка працюють без
послаблення політики; підказка — DOM-елемент із `textContent`, а не рядок HTML зі `style=`.
