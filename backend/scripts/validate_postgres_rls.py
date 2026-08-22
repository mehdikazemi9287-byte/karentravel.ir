#!/usr/bin/env python3
"""Isolated PostgreSQL 16 RLS/FORCE-RLS validation for the twelve travel-commerce
tenant tables introduced in migration 20260821_14 (plus the visa_applications
column added in 20260821_15). Runs entirely against a disposable database/role
supplied via RLS_TEST_DSN. Never touches any pre-existing application database.

Exits non-zero on any assertion failure; prints a PASS/FAIL line per check.
"""
import datetime
import os
import sys
import threading
import uuid

import psycopg

DSN = os.environ["RLS_TEST_DSN"]

TABLES = [
    "vacation_properties", "vacation_units", "vacation_reservations",
    "tour_products", "tour_departures", "tour_reservations",
    "cruise_sailings", "visa_products", "visa_applications",
    "visa_applicants", "visa_documents", "visa_timeline_events",
]

RESULTS = []


def report(name, ok, detail=""):
    RESULTS.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'} | {name}" + (f" | {detail}" if detail else ""))


def conn():
    return psycopg.connect(DSN, autocommit=False)


def set_tenant(cur, tenant_id):
    cur.execute("SELECT set_config('app.tenant_id', %s, true)", (str(tenant_id),))


def clear_tenant(cur):
    cur.execute("SELECT set_config('app.tenant_id', '', true)")


NOW = datetime.datetime.now(datetime.timezone.utc)


def new_id():
    return str(uuid.uuid4())


def new_tenant(slug):
    c = conn()
    try:
        with c.cursor() as cur:
            cur.execute(
                "INSERT INTO tenants (slug, name, primary_color) VALUES (%s,%s,'#123456') RETURNING id",
                (f"{slug}-{new_id()[:8]}", "RLS Validator Tenant"),
            )
            tid = cur.fetchone()[0]
        c.commit()
        return tid
    finally:
        c.close()


def make_fixture(tenant_id):
    """Create one full parent->child chain for every one of the 12 tables,
    all owned by tenant_id, committed with the tenant context set (own-tenant
    writes, exercising WITH CHECK positively). Returns table -> created row id."""
    ids = {}
    c = conn()
    try:
        with c.cursor() as cur:
            set_tenant(cur, tenant_id)

            cur.execute(
                "INSERT INTO users (tenant_id, email, name, role) VALUES (%s,%s,%s,%s) RETURNING id",
                (tenant_id, f"rls-{tenant_id}-{new_id()[:8]}@test.local", "RLS Test User", "employee"),
            )
            user_id = cur.fetchone()[0]

            reservation_id = new_id()
            cur.execute(
                "INSERT INTO reservations (id, tenant_id, user_id, service_type, status, price_snapshot_json, "
                "policy_at_booking_json, current_policy_json, version, created_at, updated_at) "
                "VALUES (%s,%s,%s,'vacation_rental','draft','{}','{}','{}',1,%s,%s)",
                (reservation_id, tenant_id, user_id, NOW, NOW),
            )
            ids["_user"] = user_id
            ids["_reservation"] = reservation_id

            supplier_id = new_id()
            cur.execute(
                "INSERT INTO suppliers (id, tenant_id, supplier_type, display_name, status, created_at, updated_at) "
                "VALUES (%s,%s,'vacation_rental','RLS Test Supplier','sample',%s,%s)",
                (supplier_id, tenant_id, NOW, NOW),
            )
            ids["_supplier"] = supplier_id

            prop_id = new_id()
            cur.execute(
                "INSERT INTO vacation_properties (id, tenant_id, supplier_id, title, slug, city, property_type, "
                "capacity, bedrooms, status, details_json, created_at, updated_at) "
                "VALUES (%s,%s,%s,'RLS Villa',%s,'Tehran','villa',4,2,'draft','{}',%s,%s)",
                (prop_id, tenant_id, supplier_id, f"rls-villa-{prop_id[:8]}", NOW, NOW),
            )
            ids["vacation_properties"] = prop_id

            unit_id = new_id()
            cur.execute(
                "INSERT INTO vacation_units (id, tenant_id, property_id, title, capacity, available_units, "
                "nightly_price, currency, status, pricing_json, created_at, updated_at) "
                "VALUES (%s,%s,%s,'Unit A',4,1,5000000,'IRR','active','{}',%s,%s)",
                (unit_id, tenant_id, prop_id, NOW, NOW),
            )
            ids["vacation_units"] = unit_id

            vres_id = new_id()
            cur.execute(
                "INSERT INTO vacation_reservations (id, tenant_id, unit_id, user_id, reservation_id, check_in, "
                "check_out, guests, total_amount, status, command_id, created_at, updated_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,2,10000000,'held',%s,%s,%s)",
                (vres_id, tenant_id, unit_id, user_id, reservation_id, NOW, NOW + datetime.timedelta(days=2), f"cmd-{vres_id[:8]}", NOW, NOW),
            )
            ids["vacation_reservations"] = vres_id

            tour_id = new_id()
            cur.execute(
                "INSERT INTO tour_products (id, tenant_id, supplier_id, title, slug, origin, destination, "
                "tour_type, status, details_json, created_at, updated_at) "
                "VALUES (%s,%s,%s,'RLS Tour',%s,'Tehran','Kish','domestic','draft','{}',%s,%s)",
                (tour_id, tenant_id, supplier_id, f"rls-tour-{tour_id[:8]}", NOW, NOW),
            )
            ids["tour_products"] = tour_id

            dep_id = new_id()
            cur.execute(
                "INSERT INTO tour_departures (id, tenant_id, tour_id, starts_at, ends_at, booking_deadline, "
                "capacity, remaining, base_price, currency, status, pricing_json, created_at, updated_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,20,20,8000000,'IRR','active','{}',%s,%s)",
                (dep_id, tenant_id, tour_id, NOW, NOW + datetime.timedelta(days=5), NOW - datetime.timedelta(days=1), NOW, NOW),
            )
            ids["tour_departures"] = dep_id

            treservation_id = new_id()
            cur.execute(
                "INSERT INTO reservations (id, tenant_id, user_id, service_type, status, price_snapshot_json, "
                "policy_at_booking_json, current_policy_json, version, created_at, updated_at) "
                "VALUES (%s,%s,%s,'tour','draft','{}','{}','{}',1,%s,%s)",
                (treservation_id, tenant_id, user_id, NOW, NOW),
            )
            tres_id = new_id()
            cur.execute(
                "INSERT INTO tour_reservations (id, tenant_id, departure_id, user_id, reservation_id, travellers, "
                "room_type, total_amount, status, command_id, created_at, updated_at) "
                "VALUES (%s,%s,%s,%s,%s,2,'double',16000000,'held',%s,%s,%s)",
                (tres_id, tenant_id, dep_id, user_id, treservation_id, f"cmd-{tres_id[:8]}", NOW, NOW),
            )
            ids["tour_reservations"] = tres_id

            cruise_id = new_id()
            cur.execute(
                "INSERT INTO cruise_sailings (id, tenant_id, title, cruise_line, ship, departure_port, "
                "arrival_port, starts_at, nights, status, details_json, created_at, updated_at) "
                "VALUES (%s,%s,'RLS Cruise','TestLine','TestShip','Bandar Abbas','Dubai',%s,5,'catalog_only','{}',%s,%s)",
                (cruise_id, tenant_id, NOW, NOW, NOW),
            )
            ids["cruise_sailings"] = cruise_id

            visap_id = new_id()
            cur.execute(
                "INSERT INTO visa_products (id, tenant_id, destination_country, visa_type, title, status, "
                "source_url, source_verified_at, details_json, created_at, updated_at) "
                "VALUES (%s,%s,'Turkey','tourist','RLS Visa','published','https://example.test',%s,'{}',%s,%s)",
                (visap_id, tenant_id, NOW, NOW, NOW),
            )
            ids["visa_products"] = visap_id

            visaapp_id = new_id()
            cur.execute(
                "INSERT INTO visa_applications (id, tenant_id, product_id, user_id, purpose, travel_at, status, "
                "command_id, created_at, updated_at) "
                "VALUES (%s,%s,%s,%s,'tourism',%s,'started',%s,%s,%s)",
                (visaapp_id, tenant_id, visap_id, user_id, NOW + datetime.timedelta(days=30), f"cmd-{visaapp_id[:8]}", NOW, NOW),
            )
            ids["visa_applications"] = visaapp_id

            applicant_id = new_id()
            cur.execute(
                "INSERT INTO visa_applicants (id, tenant_id, application_id, full_name, passport_country, "
                "passport_reference, created_at, updated_at) "
                "VALUES (%s,%s,%s,'RLS Applicant','Iran','HASHEDREF',%s,%s)",
                (applicant_id, tenant_id, visaapp_id, NOW, NOW),
            )
            ids["visa_applicants"] = applicant_id

            doc_id = new_id()
            cur.execute(
                "INSERT INTO visa_documents (id, tenant_id, application_id, document_type, status, created_at, updated_at) "
                "VALUES (%s,%s,%s,'passport','missing',%s,%s)",
                (doc_id, tenant_id, visaapp_id, NOW, NOW),
            )
            ids["visa_documents"] = doc_id

            evt_id = new_id()
            cur.execute(
                "INSERT INTO visa_timeline_events (id, tenant_id, application_id, event_type, source_type, "
                "message, event_key, created_at, updated_at) "
                "VALUES (%s,%s,%s,'created','system','RLS test event',%s,%s,%s)",
                (evt_id, tenant_id, visaapp_id, f"evt-{evt_id[:8]}", NOW, NOW),
            )
            ids["visa_timeline_events"] = evt_id

        c.commit()
    finally:
        c.close()
    return ids


def with_conn(fn):
    """Open a connection, run fn(cur), always close, roll back on exception."""
    c = conn()
    try:
        with c.cursor() as cur:
            result = fn(cur)
        c.rollback()
        return result
    except psycopg.errors.Error as e:
        c.rollback()
        raise e
    finally:
        c.close()


def run_matrix(tenant_a, tenant_b, rows_a, rows_b):
    # 1. Missing-context: no SET at all -> SELECT sees nothing, INSERT rejected.
    for table in TABLES:
        def _sel(cur, table=table):
            clear_tenant(cur)
            cur.execute(f"SELECT count(*) FROM {table}")
            return cur.fetchone()[0]
        n = with_conn(_sel)
        report(f"missing-context select fail-closed [{table}]", n == 0, f"rows visible={n}")

    for table in TABLES:
        c = conn()
        try:
            with c.cursor() as cur:
                clear_tenant(cur)
                cur.execute(f"INSERT INTO {table} (id, tenant_id, created_at, updated_at) VALUES (%s,%s,%s,%s)",
                            (new_id(), tenant_a, NOW, NOW))
            ok, detail = False, "insert unexpectedly succeeded"
        except psycopg.errors.Error:
            ok, detail = True, "insert correctly rejected (RLS WITH CHECK)"
        finally:
            c.rollback()
            c.close()
        report(f"missing-context insert rejected [{table}]", ok, detail)

    # 2. Own-tenant read: tenant A sees exactly its own row.
    for table in TABLES:
        def _own(cur, table=table):
            set_tenant(cur, tenant_a)
            cur.execute(f"SELECT id FROM {table}")
            return {r[0] for r in cur.fetchall()}
        seen = with_conn(_own)
        expected = rows_a[table]
        report(f"own-tenant read [{table}]", seen == {expected}, f"seen={seen} expected={{{expected}}}")

    # 3. Cross-tenant read: tenant A must not see tenant B's row.
    for table in TABLES:
        def _cross(cur, table=table):
            set_tenant(cur, tenant_a)
            cur.execute(f"SELECT count(*) FROM {table} WHERE id = %s", (rows_b[table],))
            return cur.fetchone()[0]
        n = with_conn(_cross)
        report(f"cross-tenant read denied [{table}]", n == 0, f"tenant A saw {n} of tenant B's row")

    # 4. Cross-tenant write: tenant A UPDATE/DELETE against tenant B's row id affects 0 rows.
    for table in TABLES:
        def _write(cur, table=table):
            set_tenant(cur, tenant_a)
            cur.execute(f"UPDATE {table} SET updated_at = updated_at WHERE id = %s", (rows_b[table],))
            upd = cur.rowcount
            cur.execute(f"DELETE FROM {table} WHERE id = %s", (rows_b[table],))
            return upd, cur.rowcount
        upd, dele = with_conn(_write)
        report(f"cross-tenant write denied [{table}]", upd == 0 and dele == 0, f"update={upd} delete={dele}")

    # 5. Cross-tenant insert (WITH CHECK): tenant A context, tenant_id = B -> rejected.
    for table in TABLES:
        c = conn()
        try:
            with c.cursor() as cur:
                set_tenant(cur, tenant_a)
                cur.execute(f"INSERT INTO {table} (id, tenant_id, created_at, updated_at) VALUES (%s,%s,%s,%s)",
                            (new_id(), tenant_b, NOW, NOW))
            ok, detail = False, "cross-tenant insert unexpectedly succeeded"
        except psycopg.errors.Error:
            ok, detail = True, "cross-tenant insert correctly rejected (WITH CHECK)"
        finally:
            c.rollback()
            c.close()
        report(f"cross-tenant insert (WITH CHECK) rejected [{table}]", ok, detail)


def run_force_rls_owner_proof(table, tenant_a):
    """The validator role OWNS every table (it ran the migration) and is NOT
    superuser/BYPASSRLS. Seeing zero rows with no tenant context set proves
    FORCE ROW LEVEL SECURITY is engaged -- without FORCE, a table owner is
    exempt from RLS regardless of policies."""
    def _probe(cur):
        cur.execute("SELECT current_user")
        owner = cur.fetchone()[0]
        clear_tenant(cur)
        cur.execute(f"SELECT count(*) FROM {table}")
        return owner, cur.fetchone()[0]
    owner, n = with_conn(_probe)
    report(f"FORCE RLS applies to owner role [{table}]", n == 0, f"owner={owner} rows_visible_without_context={n}")


def run_concurrency_test(tenant_a, tenant_b, rows_a, rows_b, table="vacation_reservations", iterations=25):
    errors = []
    counts = {"a_leak": 0, "b_leak": 0}
    lock = threading.Lock()

    def worker(tenant_id, own_row, other_row, tag):
        try:
            for _ in range(iterations):
                c = conn()
                try:
                    with c.cursor() as cur:
                        set_tenant(cur, tenant_id)
                        cur.execute(f"SELECT id FROM {table} WHERE id = %s", (own_row,))
                        own_visible = cur.fetchone() is not None
                        cur.execute(f"SELECT id FROM {table} WHERE id = %s", (other_row,))
                        other_visible = cur.fetchone() is not None
                    c.rollback()
                finally:
                    c.close()
                if not own_visible:
                    with lock:
                        errors.append(f"{tag}: own row not visible")
                if other_visible:
                    with lock:
                        counts["a_leak" if tag == "A" else "b_leak"] += 1
        except Exception as e:
            with lock:
                errors.append(f"{tag}: {e}")

    threads = [
        threading.Thread(target=worker, args=(tenant_a, rows_a[table], rows_b[table], "A")),
        threading.Thread(target=worker, args=(tenant_b, rows_b[table], rows_a[table], "B")),
        threading.Thread(target=worker, args=(tenant_a, rows_a[table], rows_b[table], "A")),
        threading.Thread(target=worker, args=(tenant_b, rows_b[table], rows_a[table], "B")),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    ok = not errors and counts["a_leak"] == 0 and counts["b_leak"] == 0
    report(
        f"concurrency isolation [{table}] {len(threads)} threads x{iterations} iters",
        ok,
        f"errors={errors[:3]} leaks={counts}",
    )


def main():
    tenant_a = new_tenant("rls-validator-a")
    tenant_b = new_tenant("rls-validator-b")
    print(f"Fixture tenants: A={tenant_a} B={tenant_b}")

    rows_a = make_fixture(tenant_a)
    rows_b = make_fixture(tenant_b)

    run_matrix(tenant_a, tenant_b, rows_a, rows_b)

    for table in TABLES:
        run_force_rls_owner_proof(table, tenant_a)

    run_concurrency_test(tenant_a, tenant_b, rows_a, rows_b)

    failed = [r for r in RESULTS if not r[1]]
    print(f"\n=== RLS VALIDATION SUMMARY: {len(RESULTS) - len(failed)}/{len(RESULTS)} passed ===")
    if failed:
        print("FAILED CHECKS:")
        for name, _, detail in failed:
            print(f"  - {name}: {detail}")
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
