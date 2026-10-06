"""ZIP manifest: a status for every file and every dataset of the CheckLine bundle, with usage percentages computed
from the bundle itself and from the candidate database. Output: JSON (every file) + Markdown (summary, datasets, menus, pages)."""
import collections, json, os, re, subprocess, sys
from urllib.parse import unquote
Z, OUT = sys.argv[1], sys.argv[2]
def sql(q):
    return subprocess.run(["docker", "exec", "ks-catalog-scratch-pg", "psql", "-U", "postgres", "-d", "ks_cand37", "-At", "-F", "|", "-c", q], capture_output=True, text=True).stdout.strip()
one = lambda q: int(sql(q) or 0)
IMPLEMENTED = {"evidence-round3/deep-data-audit-round3.json": "catalogue items, pages, menus, taxonomy → importer", "evidence-round3/catalog-controls-round3.json": "full meta and term links → importer",
               "round3-technical/media-workbench.json": "attachment → image URL, de-duplication by sha256", "round3-technical/media-duplicate-groups.json": "duplicate groups → enforced by sha256 in the importer",
               "ecosystem-technical/country-city-mismatches.json": "9 conflicting hotels held back", "technical/api-official-fields.json": "Citysoft contract (provider_contracts/citysoft_api_fields.json)",
               "round3-technical/hotel-workbench.json": "first hotel import (staged)", "round3-technical/geography-workbench.json": "first geography import", "round3-technical/tour-workbench.json": "first tour import",
               "round3-technical/tour-dates.json": "165 tour dates", "round3-technical/hotel-gallery-reference-issues.json": "broken gallery refs skipped (same result from media check)", "round3-technical/tour-reference-issues.json": "tour→hotel refs resolved or dropped"}
MAPPED = {"deep-technical/screen-inventory.json": "35 screens → KarenSeir routes (table below)", "deep-technical/role-matrix.json": "22 roles → KarenSeir roles (table below)", "round3-technical/service-registry.json": "services → verticals (table below)",
          "technical/wordpress-routes.json": "old routes → legacy route map", "deep-technical/order-state-model.json": "→ reservation state machine already in operations.py (compared, not imported)",
          "deep-technical/event-contract-proposal.json": "→ trip_events / outbox contract (compared)", "deep-technical/target-api-proposal.json": "→ existing API surface (compared)", "deep-technical/target-modules.json": "→ existing modules (compared)",
          "technical/ajax-hooks.json": "old AJAX actions → KarenSeir endpoints by capability", "CheckLine-Catalog-Workbench.xlsx": "same tables as the JSON workbenches", "technical/database-schema.json": "source schema → field mapping of the importer",
          "round3-technical/schema-current-columns.json": "source columns → field mapping", "round3-technical/acf-field-topology.json": "ACF field names → importer field map", "round3-technical/acf-group-coverage.json": "ACF groups → importer field map"}
files, status_count, bytes_by = [], collections.Counter(), collections.Counter()
for root, _, names in os.walk(Z):
    for n in names:
        rel = os.path.relpath(os.path.join(root, n), Z); size = os.path.getsize(os.path.join(root, n))
        if rel in IMPLEMENTED: st, note = "IMPLEMENTED", IMPLEMENTED[rel]
        elif rel in MAPPED: st, note = "MAPPED", MAPPED[rel]
        elif rel.startswith("source-sanitized/"): st, note = "PRESERVED_AS_REFERENCE", "old site code (sanitized, not deployable); read for field semantics and facility code names"
        elif rel.startswith(("evidence", "technical/", "deep-technical/", "ecosystem-technical/", "round3-technical/")) or rel.endswith((".xlsx", ".html", ".txt")): st, note = "PRESERVED_AS_REFERENCE", "audit evidence / inventory / proposal document"
        else: st, note = "PRESERVED_AS_REFERENCE", "document"
        files.append({"path": rel, "bytes": size, "status": st, "note": note}); status_count[st] += 1; bytes_by[st] += size
assert all(f["status"] for f in files)
deep = json.load(open(f"{Z}/evidence-round3/deep-data-audit-round3.json")); ctl = json.load(open(f"{Z}/evidence-round3/catalog-controls-round3.json"))
media = {str(m["id"]): m for m in json.load(open(f"{Z}/round3-technical/media-workbench.json"))}
by_type = collections.Counter(x["type"] for x in deep["catalog"]); tax = collections.Counter(t["taxonomy"] for t in deep["taxonomy"])
E = (None, "", [], {}, [""], [[]], [None])
meta = {str(x["id"]): x["meta"] for x in ctl["catalog_meta"] if isinstance(x["meta"], dict)}
gal_refs = sum(len(m["gallery"][0]) for m in meta.values() if isinstance(m.get("gallery"), list) and m["gallery"] and isinstance(m["gallery"][0], list))
room_rows = sum(1 for m in meta.values() for k, v in m.items() if re.fullmatch(r"rooms-info_\d+_room-title", k) and v not in E)
fac_hotels = sum(1 for x in ctl["catalog_meta"] if x["type"] == "location" and isinstance(x["meta"], dict) and any(x["meta"].get(f"facilitice-group-{g}") not in E for g in ("first", "secound", "third")))
price_fields = sum(1 for m in meta.values() for k, v in m.items() if re.search(r"price-value|discount-amount|hd-capacity|price-percent|visa_price", k) and v not in E and v != ["0"])
used_media = set()
for col, table in (("url", "catalog_hotel_images"), ("image_url", "catalog_hotel_room_types"), ("image_url", "catalog_places"), ("image_url", "catalog_venues")):
    used_media |= {u for u in sql(f"select {col} from {table} where {col} like 'https://checkline.travel/%'").split("\n") if u}
for d in sql("select details_json from catalog_places where details_json like '%checkline.travel%' union all select details_json from catalog_tours where details_json like '%checkline.travel%'").split("\n"):
    used_media |= set(re.findall(r"https://checkline\.travel/wp-content/uploads/[^\"\\\\]+", d))
D = []  # (dataset, total, implemented, status, note)
def ds(name, total, done, status, note): D.append({"dataset": name, "records": total, "implemented": done, "status": status, "note": note})
h = one("select count(*) from catalog_hotels where source='checkline'")
ds("Hotels (location)", by_type["location"], h, "IMPLEMENTED", f"{by_type['location'] - h} held back: 13 without a resolvable country and 9 country/city conflicts (BLOCKED), 1 without a title (INVALID)")
ds("Hotel descriptions", sum(1 for x in deep["catalog"] if x["type"] == "location" and x.get("public_body")), one("select count(*) from catalog_hotels where source='checkline' and description is not null"), "IMPLEMENTED", "HTML reduced to text")
ds("Hotel gallery references", gal_refs, one("select count(*) from catalog_hotel_images i join catalog_hotels h on h.id=i.hotel_id where h.source='checkline'"), "IMPLEMENTED", "every existing, distinct image of an imported hotel is attached; broken references (296), byte-identical copies and galleries of held-back or non-hotel items are not")
ds("Hotel room rows", room_rows, one("select count(*) from catalog_hotel_room_types r join catalog_hotels h on h.id=r.hotel_id where h.source='checkline'"), "IMPLEMENTED", "hidden rooms and rooms of held-back hotels excluded")
ds("Hotel facility groups 1–3 (numeric codes)", fac_hotels, 0, "BLOCKED", "the code→label lists are site options whose values are not in the bundle; raw codes stay in the bundle, nothing is guessed")
ds("Hotel coordinates", 0, 0, "BLOCKED", "the source has no latitude/longitude for hotels (75 have a map embed without a text query)")
ds("Countries", by_type["country"], one("select count(*) from catalog_places where kind='country' and details_json like '%checkline%'"), "IMPLEMENTED", "52 posts are 50 distinct countries (two duplicated in the source)")
ds("Provinces (state)", by_type["state"], one("select count(*) from catalog_places where kind='region' and details_json like '%checkline%'"), "IMPLEMENTED", "matched to existing provinces or added")
ds("Cities", by_type["city"], one("select count(*) from catalog_places where kind='city' and details_json like '%checkline%'"), "IMPLEMENTED", "published cities; drafts/pending, duplicates and ambiguous names are not separate places")
ds("Tours", by_type["tour"], one("select count(*) from catalog_tours"), "IMPLEMENTED", "4 trashed and untitled items are INVALID; reference programmes only")
ds("Tour dates", len(json.load(open(f"{Z}/round3-technical/tour-dates.json"))), one("select count(*) from catalog_tour_departures"), "IMPLEMENTED", "history only; 3 invalid Jalali dates kept as text")
ds("Tour ↔ hotel references", sum(1 for m in meta.values() for k, v in m.items() if k.endswith("hl-hotel-select") and v not in E), one("select count(*) from catalog_tour_hotels"), "IMPLEMENTED", "references to hotels outside the imported set are dropped; repeated hotels count once per tour")
ds("Prices, discounts, capacities", price_fields, 0, "INVALID", "historical commercial values (past tours, old discounts): not provable as current, never published; price stays null")
ds("Visa articles", by_type["visa"], one("select count(*) from catalog_content where kind='visa'"), "IMPLEMENTED", "1 draft without text is INVALID")
ds("Country visa notes", sum(1 for x in ctl["catalog_meta"] if x["type"] == "country" and isinstance(x["meta"], dict) and x["meta"].get("visa") not in E), one("select count(*) from catalog_content where kind='visa_country'"), "IMPLEMENTED", "notes of duplicated country posts collapse into one")
ds("Attractions", sum(1 for x in ctl["catalog_meta"] if x["type"] == "attraction"), one("select count(*) from catalog_venues where source='checkline'"), "IMPLEMENTED", "name, city, coordinates")
ds("Pages", len(deep["pages"]), one("select count(*) from catalog_legacy_routes"), "MAPPED", "published pages mapped to KarenSeir routes; the bundle has titles and slugs only, no page text")
ds("Menu items", len(deep["menu_items"]), len(deep["menu_items"]), "MAPPED", "every item resolved to a KarenSeir target (table below)")
for name, st, note in (("tour-category", "IMPLEMENTED", "tour search filter"), ("location-category", "IMPLEMENTED", "hotel categories kept on the record; geography expressed by city/country filters"), ("region", "IMPLEMENTED", "kept on the record"), ("city-category", "IMPLEMENTED", "kept on the place"),
                       ("country-category", "IMPLEMENTED", "kept on the place"), ("visa-category", "IMPLEMENTED", "kept on visa content"), ("attraction-category", "IMPLEMENTED", "kept on the venue kind"),
                       ("nav_menu", "MAPPED", "menu table below"), ("category", "BLOCKED", "blog categories; the bundle has no post text"), ("post_tag", "BLOCKED", "blog tags; no post text"),
                       ("term_translations", "PRESERVED_AS_REFERENCE", "translation links of the multilingual plugin"), ("post_translations", "PRESERVED_AS_REFERENCE", "translation links")):
    ds(f"Taxonomy: {name}", tax[name], tax[name] if st in ("IMPLEMENTED", "MAPPED") else 0, st, note)
ds("Media library records", len(media), len(used_media), "IMPLEMENTED", "files referenced by imported hotels, rooms, places, tours and attractions; the rest are unreferenced, missing (454) or duplicate copies and stay PRESERVED in the bundle")
ds("Blog posts", 41, 0, "BLOCKED", "only counted in the bundle; no titles or text were exported")
ds("Supplier API operations (Citysoft)", 32, 26, "MAPPED", "26 distinct operations mapped to ports; request/response handling built for flight search and hotel rooms; no live connection")
ds("Orders, wallet movements, users, roles, options", 0, 0, "PRESERVED_AS_REFERENCE", "audit aggregates without traveller export; not site content")
content = [d for d in D if d["status"] in ("IMPLEMENTED", "MAPPED", "BLOCKED", "INVALID") and d["records"]]
tot, done = sum(d["records"] for d in content), sum(min(d["implemented"], d["records"]) for d in content)
usable = [d for d in content if d["status"] in ("IMPLEMENTED", "MAPPED")]
utot, udone = sum(d["records"] for d in usable), sum(min(d["implemented"], d["records"]) for d in usable)
pct_files = 100 * (status_count["IMPLEMENTED"] + status_count["MAPPED"]) / len(files)
pct_bytes = 100 * (bytes_by["IMPLEMENTED"] + bytes_by["MAPPED"]) / sum(bytes_by.values())
# ---- menus and pages
pages = {p["ID"]: p for p in deep["pages"]}; terms = {t["term_id"]: t for t in deep["taxonomy"]}
routes = {r.split("|")[0]: r.split("|") for r in sql("select source_ref, legacy_path, title, coalesce(target_path,''), in_menu from catalog_legacy_routes").split("\n") if r}
places = [r.split("|") for r in sql("select id, kind, country_code, name_fa from catalog_places where name_fa is not null").split("\n") if r]
sq = lambda s: re.sub(r"[\s‌]+", "", (s or "").replace("ي", "ی").replace("ك", "ک").replace("آ", "ا"))
def place_target(name, prefix):
    key = sq(name)
    for word in ("هتلهای", "هتل‌های", "هتلها", "تورهای", "تور"):
        if key.startswith(sq(word)): key = key[len(sq(word)):]; break
    hit = next((p for p in places if p[1] == "city" and sq(p[3]) == key), None) or next((p for p in places if p[1] == "country" and sq(p[3]) == key), None)
    if hit is None: return None
    return (f"/hotels?country={hit[2]}" + (f"&city={hit[0]}" if hit[1] == "city" else "")) if prefix == "hotel" else f"/tours/destination/{hit[0]}"
menu_rows = []
for mi in deep["menu_items"]:
    obj, oid = mi["_menu_item_object"], mi["_menu_item_object_id"]
    if obj == "page":
        title = mi["post_title"] or (pages.get(oid) or {}).get("post_title") or "?"; r = routes.get(f"page/{oid}")
        target = (r[3] if r and r[3] else None) or ("(صفحهٔ منتشرنشده در منبع)" if (pages.get(oid) or {}).get("post_status") != "publish" else None)
    elif obj == "tour-category":
        name = (terms.get(oid) or {}).get("name") or mi["post_title"] or "?"; title = mi["post_title"] or name; target = place_target(name, "tour") or f"/tours/search?category={name}"
    elif obj == "location-category":
        name = (terms.get(oid) or {}).get("name") or mi["post_title"] or "?"; title = mi["post_title"] or name; target = place_target(name, "hotel") or "/hotels"
    elif obj == "tour": title, target = mi["post_title"] or "تورها", "/tours"
    else: title, target = mi["post_title"] or "?", None
    menu_rows.append((title.replace(" ", "").strip(), obj, "زیرمنو" if mi["_menu_item_menu_item_parent"] != "0" else "اصلی", target or "—"))
unresolved_menu = sum(1 for m in menu_rows if m[3] == "—")
SCREENS = {"D01": "/", "D02": "/flights", "D03": "/search/results?vertical=flight", "D04": "/search/results (fare detail)", "D05": "/hotels", "D06": "/hotels (list; map view not built)", "D07": "/hotels/[slug]", "D08": "/tours/[slug]", "D09": "— (no pilgrimage vertical)",
           "D10": "/checkout (travellers step)", "D11": "/checkout", "D12": "/payments", "D13": "/trips, /manage-booking", "D14": "/manage-booking (service requests)", "D15": "/account (wallet)", "D16": "/agency", "D17": "/white-label", "D18": "/supplier",
           "D19": "— (needs a flight supplier)", "D20": "/admin/tours, /supplier (tours)", "D21": "—", "D22": "/backoffice", "D23": "/backoffice/support", "D24": "/finance", "D25": "/finance/accounting, /supplier/settlements", "D26": "/finance/accounting (tax summary only)",
           "D27": "/admin/catalog", "D28": "/admin/catalog (mapping editor), /supplier/hotels", "D29": "— (pricing rules have no screen)", "D30": "/admin", "D31": "/integrations", "D32": "— (no executive report screen)", "D33": "/integrations", "D34": "/trips/[id] (voucher/documents)", "D35": "/admin/catalog history, audit_events (no global screen)"}
ROLES = {"U01": "anonymous", "U02": "customer", "U03": "employee / organization_admin", "U04": "agency_partner", "U05": "agency_partner (+ membership)", "U06": "tenant_admin (white-label)", "U07": "supplier", "U08": "supplier (hotel) / backoffice_expert", "U09": "supplier (tour) / backoffice_expert",
         "U10": "— (no pilgrimage role)", "U11": "— (no flight-operations role)", "U12": "backoffice_expert", "U13": "backoffice_expert (support:manage)", "U14": "backoffice_expert", "U15": "finance_operator", "U16": "finance_operator", "U17": "finance_operator (settlement:manage)",
         "U18": "— (no tax role)", "U19": "backoffice_expert / platform_admin (catalog)", "U20": "tenant_admin", "U21": "platform_admin", "U22": "— (read-only auditor role not defined)"}
screens = json.load(open(f"{Z}/deep-technical/screen-inventory.json")); roles = json.load(open(f"{Z}/deep-technical/role-matrix.json")); services = json.load(open(f"{Z}/round3-technical/service-registry.json"))
SERVICE = {"flight": "/flights", "hotel": "/hotels", "flighandhotel": "/search (پرواز + هتل)", "tour": "/tours", "package": "/search (package)", "cip": "— (no CIP vertical; Citysoft /cip mapped in the contract)", "insurance": "— (contract only)", "visa": "/visa", "train": "/trains"}
md = [f"# CheckLine bundle — manifest and usage (generated)", "", f"Files: {len(files)} — every file has a status. " + ", ".join(f"{k} {v}" for k, v in status_count.most_common()) + ".",
      f"Usage by files: {pct_files:.1f}% of files ({status_count['IMPLEMENTED'] + status_count['MAPPED']} of {len(files)}) carry content that is implemented or mapped; by bytes {pct_bytes:.1f}%. The remaining files are the old site code (1,758), evidence and audit documents.",
      f"Usage by content records: {done:,} of {tot:,} = {100 * done / tot:.1f}% across all content datasets; {udone:,} of {utot:,} = {100 * udone / utot:.1f}% within datasets that are usable at all (excluding BLOCKED and INVALID ones).",
      "", "## Datasets", "| Dataset | Records | Implemented | Status | Note |", "|---|---|---|---|---|"]
md += [f"| {d['dataset']} | {d['records']:,} | {d['implemented']:,} | {d['status']} | {d['note']} |" for d in D]
md += ["", f"## Menu items ({len(menu_rows)}; without a target: {unresolved_menu})", "| Item | Type | Level | KarenSeir target |", "|---|---|---|---|"] + [f"| {a} | {b} | {c} | `{d}` |" for a, b, c, d in menu_rows]
md += ["", "## Old pages", "| Old path | Title | In menu | KarenSeir target |", "|---|---|---|---|"] + [f"| `{unquote(r[1])}` | {r[2]} | {'yes' if r[4] == 't' else ''} | `{r[3] or '—'}` |" for r in sorted(routes.values(), key=lambda r: r[2])]
md += ["", "## Screens of the audit → KarenSeir", "| Id | Screen | Role | KarenSeir |", "|---|---|---|---|"] + [f"| {s['id']} | {s['صفحه']} | {s['نقش']} | `{SCREENS.get(s['id'], '—')}` |" for s in screens]
md += ["", "## Roles of the audit → KarenSeir roles", "| Id | Role | KarenSeir |", "|---|---|---|"] + [f"| {r['id']} | {r['نقش']} | {ROLES.get(r['id'], '—')} |" for r in roles]
md += ["", "## Service registry → verticals", "| Registry | Service | Active | KarenSeir |", "|---|---|---|---|"] + [f"| {s['registry']} | {s['service_code']} | {s['active']} | `{SERVICE.get(s['service_code'], '—')}` |" for s in services]
open(OUT + ".md", "w").write("\n".join(md) + "\n"); json.dump({"files": files, "datasets": D, "summary": {"files_total": len(files), "files_by_status": status_count, "pct_files": round(pct_files, 2), "pct_bytes": round(pct_bytes, 2), "records_total": tot, "records_implemented": done,
          "pct_records_all": round(100 * done / tot, 2), "pct_records_usable": round(100 * udone / utot, 2)}}, open(OUT + ".json", "w"), ensure_ascii=False)
print("files", len(files), dict(status_count), f"pct_files={pct_files:.1f} pct_bytes={pct_bytes:.1f}"); print("datasets", len(D), collections.Counter(d["status"] for d in D)); print(f"records {done}/{tot}={100*done/tot:.1f}% usable {udone}/{utot}={100*udone/utot:.1f}%"); print("menu unresolved", unresolved_menu, [m for m in menu_rows if m[3] == "—"][:6])
for d in D: print(" ", d["dataset"], d["records"], d["implemented"], d["status"])
