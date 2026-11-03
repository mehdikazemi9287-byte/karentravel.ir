"""Platform tenant management: platform admin only, create tenant with its own admin and brand, update domain, isolation."""
import uuid

def _h(client, email):
    r = client.post("/auth/dev-login", json={"email": email})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_platform_tenants(client):
    pa = _h(client, "platform-admin@aftab.test")
    assert client.get("/platform/tenants", headers=_h(client, "tenant-admin@aftab.test")).status_code == 403
    lst = client.get("/platform/tenants", headers=pa)
    assert lst.status_code == 200
    slugs = {t["slug"] for t in lst.json()["items"]}
    assert "aftab-bank" in slugs and "faraz-industries" in slugs
    aftab = next(t for t in lst.json()["items"] if t["slug"] == "aftab-bank")
    assert aftab["counts"]["users"] >= 3

    slug = "agency-" + uuid.uuid4().hex[:6]
    email = f"owner-{uuid.uuid4().hex[:6]}@{slug}.test"
    body = {"slug": slug, "name": "آژانس آزمون", "primary_color": "#3a1b3d", "custom_domain": f"{slug}.example.ir",
            "enabled_services": ["flight", "hotel"], "admin_email": email, "admin_name": "مدیر آژانس"}
    assert client.post("/platform/tenants", json={**body, "enabled_services": ["rocket"]}, headers=pa).status_code == 422
    assert client.post("/platform/tenants", json={**body, "custom_domain": "bad domain"}, headers=pa).status_code == 422
    assert client.post("/platform/tenants", json={**body, "slug": "admin"}, headers=pa).status_code == 422
    c = client.post("/platform/tenants", json=body, headers=pa)
    assert c.status_code == 201, c.text
    t = c.json()
    assert t["counts"] == {"users": 1, "reservations": 0, "suppliers": 0} and t["admins"] == [email] and t["domain_status"] == "unverified"
    assert client.post("/platform/tenants", json=body, headers=pa).status_code == 409
    assert client.post("/platform/tenants", json={**body, "slug": slug + "x", "admin_email": "platform-admin@aftab.test"}, headers=pa).status_code == 409

    # the new admin lands in the new tenant only
    owner = _h(client, email)
    wl = client.get("/tenant/white-label", headers=owner).json()
    assert wl["display_name"] == "آژانس آزمون" and wl["primary_color"] == "#3A1B3D"
    assert client.get("/platform/tenants", headers=owner).status_code == 403

    u = client.put(f"/platform/tenants/{t['id']}", json={"name": "آژانس آزمون تازه", "primary_color": "#EF5B3D", "secondary_color": "#B98319",
                                                          "custom_domain": f"www.{slug}.example.ir", "enabled_services": ["tour"]}, headers=pa).json()
    assert u["name"] == "آژانس آزمون تازه" and u["enabled_services"] == ["tour"] and u["domain_status"] == "unverified"
    # caller context is restored: the platform admin still sees its own tenant data
    assert client.get("/admin/users", headers=pa).status_code == 200
    assert client.put("/platform/tenants/999999", json={"name": "x" * 3, "primary_color": "#000000", "secondary_color": "#000000"}, headers=pa).status_code == 404
