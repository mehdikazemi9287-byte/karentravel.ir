# CheckLine bundle — full inventory and implementation map (candidate, migration 44)

Bundle: `artifacts/CheckLine-KarenTravel-Technical-Bundle.zip`, sha256 `8c2f292a…`, 1,891 files, 173 MB extracted (`~/ks-checkline-work/zip`).

## Inventory
| Part | Files | What it is | Used as |
|---|---|---|---|
| `evidence-round3/deep-data-audit-round3.json` | 1 | 1,080 catalogue items with public body text (800 hotels, 109 cities, 52 countries, 31 provinces, 83 tours, 5 visa articles), 82 pages, 69 menu items, 331 taxonomy terms, 11,495 media records | main content source |
| `evidence-round3/catalog-controls-round3.json` | 1 | full meta of 1,040 published items, 3,517 item↔term links, roles, option names | fields, categories |
| `round3-technical/media-workbench.json` | 1 | attachment id → file path (10,698 existing files) | image URLs on `checkline.travel` |
| `round3-technical/*-workbench.json`, `tour-dates.json` | 5 | reduced hotel/geo/tour tables | first import (kept), tour dates |
| `technical/api-official-fields.json` | 1 | Citysoft gateway documentation extract: 32 documented operations | `app/citysoft_contract.py` |
| `technical/*`, `deep-technical/*`, `ecosystem-technical/*` | 68 | schema, hooks, plugin/theme lists, risk register, acceptance tests, proposed roles/API/state models, economics model | reference only (see below) |
| `source-sanitized/` | 1,758 | theme/plugin PHP, JS, CSS of the old site (sanitized, not deployable) | read for field semantics |
| `evidence*/` images, `*.php` read-only probes | 20 | audit evidence | reference only |
| 3 `.xlsx`, 1 `.html`, handoff/readme | 6 | the same data and findings as the JSON files, for people | reference only |

## What was imported (candidate DB `ks_cand37`)
- Hotels: 800 source items → 777 rows `cl-<id>` (23 stay staged: 13 without a resolvable country, 9 country/city conflicts, 1 without a title). 605 with description, 340 address, 158 rules, 88 phone, 3,826 images on 579 hotels (296 broken gallery references skipped), 429 room types on 82 hotels, facts (district, room count, build year, floors, distances, restaurants, board plans). 501 published, 276 draft (source draft/pending, no city, or an unreviewed duplicate pair).
- Places: 30 more countries (50 total), 1 province, 20 cities added; 184 places enriched with description, English name, coordinates (only where empty), currency, capital, language, time zone, visa note. Existing OSM values are never replaced.
- Reference tours: 76 (58 published, 18 draft) with description, destination, duration, services, inclusions, transport legs, cancellation text, 189 tour↔hotel links, 165 past dates.
- 12 attractions (name, city, coordinates), 4 visa articles, 72 old-site pages mapped to KarenSeir routes (58 have an equivalent).
- Duplicates: 70 pairs by exact name within a city; 3 also share address evidence and are linked; 67 wait for a reviewer and are not public.

## Where it shows in the site
`/hotels` (search, filters, cards) → `/hotels/[slug]` (gallery, description, facts, distances, room types, rules) · `/destinations/[id]` (description, facts, visa note, hotels, past tours) · `/tours` section and `/tours/reference` → `/tours/reference/[id]` (programme, services, transport, hotels, past dates, inquiry) · autocomplete `/catalog/suggest` (hotels, places, tours) · admin `/admin/catalog`, `/admin/tours`.
API: `/catalog/hotels*`, `/catalog/places*`, `/catalog/tours*`, `/catalog/content*`, `/catalog/legacy-route(s)`.

## Deliberately not imported
- Prices and commercial values: tour price tables and start prices, hotel `discount-amount`, tour capacities — historical, not provable today. Price stays null; nothing is bookable from this content.
- Hotel facility groups 1–3 (numeric codes on 586 hotels): the labels live in site options whose values are not in the bundle. Room-level facility codes are named and were imported.
- Hotel coordinates: the source has none (75 hotels only have a map embed with a text query).
- Page and blog bodies: the bundle carries titles/slugs/length only. Orders, wallet and user records: audit aggregates, no traveller export — not catalogue content.
- Image bytes: not in the bundle; images are referenced on the source site with the note “rights unverified”.
- Proposal/spec documents (`deep-technical`, `ecosystem-technical`): proposals of the audit, not CheckLine data.
