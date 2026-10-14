# Hotel catalog requirement — verified gate

Environment: read-only Source / existing scratch DB. Source HEAD791d007; Production frontend d2ba674. Application/DB writes blocked by MASTER_RULES Source/Production gate. No code, migration, catalog import, Production or UI change performed.

## Existing data
Five target countries:16079 accommodation records,10353 with source hotel type. TR6609 / AE1574 / AM1082 / GE3277 / IQ3537. Hotel-only: TR5382 / AE1039 / AM540 / GE1807 / IQ1585. Scratch city association matches631 Dubai accommodation records (association uses a nearest-city heuristic). Supporting target-country references:1035 places,97 airports,42 airlines. Audit checks IDs/slugs, source refs, provenance and coordinate bounds; this does not prove exhaustive coverage or independently validate hotel facts.

## Exact required correction
- Existing importer must be additive: never delete rows absent from input. Skip identical rows; protect verified fields from lower-confidence/null input. Equal-priority conflicts are quarantined. Completeness score must not stand in for source authority.
- Stable source-ID identity and explicit, deterministic merge ordering; preserve aliases and all source references. Fuzzy name/proximity matches require review before merge.
- API must expose catalogued=true, rate_available=false, bookable=false, price=null. Catalog queries must never depend on offer/rate existence. No zero/default price.
- Inquiry CTA must read «استعلام قیمت» and carry stable catalog hotel ID plus dates/occupancy into an existing supported inquiry flow. Do not claim request delivery without server evidence.
- Record source URL, retrieval time separately from actual last_verified_at, per-field provenance/confidence and explicit source-reported star status. Keep unknown verification time null; never use today's build date as verification evidence.
- Preserve licensed metadata/images per record; add structured author/license/license URL/asset source and permission validation. Missing image rights means no image ingestion, not a stock photo substitute.
- Provider mappings only from verifiable provider IDs/contracts; missing mappings remain unmapped. No guessed airline/airport/provider codes. Do not infer international designation from an airport's name.
- Turkey-wide collection is needed beyond the current13-province restriction; record missing/incomplete regions without a false coverage claim.

## Acceptance and rollback
Targeted tests: two imports yield no second-run updates; partial imports delete nothing; lower-confidence/null inputs preserve verified fields; ambiguous duplicates quarantine; all no-rate hotels remain searchable/filterable with null prices and honest inquiry; provenance survives enrichment and merging. Use Source/Preview only once the drift gate is explicitly lifted. Any migration execution or Production import needs operation-specific authorization, verified backup and a scoped rollback. Preserve existing dirty work.

## Sources
OpenStreetMap ODbL1.0: https://www.openstreetmap.org/copyright — attribution and share-alike obligations apply to derived database distribution.
OurAirports public-domain dataset: https://ourairports.com/data/ — no accuracy guarantee.
Wikidata CC0 structured data: https://www.wikidata.org/wiki/Wikidata:Licensing
Commons image permissions must be validated per file; a Wikidata image link alone is not a licence grant.
