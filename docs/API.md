# Public API (gateway)

Base URL: `https://<host>/v1` · Auth: `X-API-Key: <key>` (or `Authorization: Bearer <key>`) · OpenAPI UI: `/docs`

| Method | Path | Role | Purpose |
|---|---|---|---|
| GET | `/v1/health` | public | Status, rule count, provider health |
| POST | `/v1/ask` | partner | `{question, language?, use_llm?}` → answer, citations, calculations, amendments, trace |
| GET | `/v1/search?q=&k=` | partner | BM25 full-text search |
| GET | `/v1/rules` · `/v1/rules/{id}` | partner | Rule list / full text + amendments + PDF link |
| GET | `/v1/parts` · `/v1/amendments` | partner | Structure of the rulebook / version tracker |
| GET | `/v1/calc/front-open-space?street_width_m=&height_m=` | partner | Rule 56(1)(a) |
| GET | `/v1/calc/rear-open-space?plot_area_sqm=&height_m=` | partner | Rule 56(2)(a) |
| GET | `/v1/calc/permission-fee?built_up_sqm=&use=&height_m=` | partner | Rule 21 |
| GET | `/v1/summaries/rule/{id}?language=en\|hi` | partner | AI (or extractive) rule summary |
| POST | `/v1/feedback` | partner | `{query_id, helpful}` |
| GET | `/v1/stats` · `/v1/queries` · `/v1/queries.csv` · `/v1/reports/summary` · `/v1/eval` | admin/ui | Dashboards & reports |
| POST | `/v1/eval/run?use_llm=` | admin/ui | Re-run the 17-question accuracy harness |
| GET | `/gateway/usage` | admin/ui | Per-consumer request counts and latency |

Response headers: `X-Request-ID`, `X-RateLimit-Remaining`, `X-Upstream-Latency-ms`. Errors: 401, 403, 429 (`Retry-After`), 502.

Keys are configured with `GATEWAY_API_KEYS="name:key:role,..."`. Each `/v1/ask` is tagged with the caller's name,
so the dashboard splits traffic by portal.

### Embed widget
```html
<script src="https://<host>/widget.js" data-api-base="https://<host>"></script>
```
