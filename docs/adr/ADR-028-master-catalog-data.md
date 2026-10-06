# ADR028 — Master catalog data, separate from commercial data

## Decision
Real, relatively static reference records (places, hotels, airlines, airports, rail operators and stations, venues) live in
global `catalog_*` tables (`backend/app/catalog.py`, migration `20261003_36`). They have no `tenant_id` and no price, offer,
availability, inventory, room, seat, rating or review column. The API role gets `SELECT` only; rows are written by
`backend/scripts/catalog/import_catalog.py` under the owner role. Supplier offers, rates and bookings stay in the existing
tenant-scoped tables and will reference catalog ids when a real provider is mapped — the catalog is never rebuilt for pricing.

## Sources and provenance
OpenStreetMap via Overpass (ODbL, attribution shown in the UI), Wikidata (CC0), OurAirports (public domain), Wikimedia
Commons images (per-file author and licence stored in `image_credit`), operators' own websites for rail companies. Every row
stores `source`, `source_ref`, `source_license`, `retrieved_on`. `backend/catalog_data/MANIFEST.json` records counts.

## Pipeline
`fetch_osm.py` / `fetch_reference.py` (raw cache, not committed) → `build_catalog.py` (normalize, validate, deduplicate,
attach images only when the source ties the file to that exact record) → `catalog_data/*.json.gz` → `import_catalog.py`
(idempotent upsert, stale rows removed).

## Rules
- No fabricated commercial data. Every catalog response carries `price: null`, `price_status: "inquiry"`.
- An image shared by more than one record is dropped; records without a verified image render a neutral non-photo header.
- Turkey is limited to the tourism provinces relevant to the Iranian market; other countries are covered country-wide.

## Rollback
Frontend: redeploy the previous image. Backend: `alembic downgrade 20260929_35` drops only the `catalog_*` tables; no
existing table is altered.
