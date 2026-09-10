# karenseir-search

Independently deployable Search microservice (strangler extraction from the
KarenSeir monolith). Owns query interpretation, provider fan-out, normalization,
aggregation, dedup, filter, sort, ranking, search metadata, cache, telemetry,
autocomplete. Does NOT own reservation / payment / trip / identity / supplier
admin. ShadShahr (leisure) stays out of scope — future consumer relationship.

- Runtime: `uvicorn app.main:app` on :8080, own Docker image `karenseir-search:*`.
- Data source: the monolith `POST /internal/search/offer-pool` (single DB owner).
- Contract: `POST /v1/search`, `GET /v1/autocomplete`, `GET /v1/providers`,
  `/health` `/ready` `/version` `/metrics`.
- Cache: Redis (`SEARCH_REDIS_URL`) with bounded in-memory fallback.
- External carriers/bedbanks: declared ports, fail-closed (`not_connected`).
- Index/search-cluster (ES/OpenSearch): NOT adopted this phase. Trigger later
  when autocomplete corpus > a few thousand rows or geo/fuzzy hotel text search
  is required by real load.
