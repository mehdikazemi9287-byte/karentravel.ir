"""SMS campaigns: audience from the tenant's own data, opt-outs removed, nothing reported delivered without a provider."""
import uuid

from sqlalchemy import select

from app.main import SessionLocal, User
from app.sms_campaigns import SmsCampaignRecipient, full_text, sms_parts


def _h(client, email):
    r = client.post("/auth/dev-login", json={"email": email})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_text_helpers():
    t = full_text(" سلام ")
    assert t.endswith("لغو۱۱") and t.startswith("سلام") and sms_parts("x" * 68) == 2


def test_campaign_flow_without_provider(client):
    admin = _h(client, "tenant-admin@aftab.test")
    desk = _h(client, "backoffice@aftab.test")
    assert client.get("/sms-campaigns", headers=desk).status_code == 403
    tag = uuid.uuid4().hex[:6]
    mobiles = ["0912" + str(uuid.uuid4().int)[:7], "0912" + str(uuid.uuid4().int)[:7]]
    for i, mob in enumerate(mobiles):
        r = client.post("/sales-desk/cases", json={"customer_name": f"مخاطب {i}", "mobile": mob, "channel": "instagram", "trip": f"کمپین {tag}"}, headers=desk)
        assert r.status_code == 201, r.text
    assert client.post("/sms-campaigns/opt-outs", json={"mobile": mobiles[1]}, headers=admin).status_code == 201
    pv = client.post("/sms-campaigns/preview", json={"source": "sales_desk", "channels": ["instagram"]}, headers=admin).json()
    assert pv["count"] >= 1 and all("***" in s["mobile"] for s in pv["sample"])
    assert client.post("/sms-campaigns/preview", json={"source": "sales_desk", "stages": ["nope"]}, headers=admin).status_code == 422
    c = client.post("/sms-campaigns", json={"title": f"پاییز {tag}", "body": "تورهای پاییزی کیش با پرواز رفت و برگشت", "audience": {"source": "sales_desk", "channels": ["instagram"]}}, headers=admin)
    assert c.status_code == 201 and c.json()["status"] == "draft" and c.json()["text"].endswith("لغو۱۱")
    cid = c.json()["id"]
    connected = client.get("/sms-campaigns/provider", headers=admin).json()["connected"]
    sent = client.post(f"/sms-campaigns/{cid}/send", headers=admin).json()
    assert sent["recipients"] >= 1 and sent["delivered"] == 0  # no real SMS provider in tests: nothing may be reported as delivered
    if connected:  # a sandbox adapter that cannot send campaign SMS -> failed, never "sent"
        assert sent["status"] == "failed" and sent["failed"] == sent["recipients"]
    else:
        assert sent["status"] == "waiting_for_provider" and sent["blocked"] == sent["recipients"]
    with SessionLocal() as db:
        got = set(db.scalars(select(SmsCampaignRecipient.mobile).where(SmsCampaignRecipient.campaign_id == cid)).all())
    assert mobiles[0] in got and mobiles[1] not in got  # opted-out number never queued
    again = client.post(f"/sms-campaigns/{cid}/send", headers=admin).json()  # retry while waiting does not duplicate recipients
    assert again["recipients"] == sent["recipients"]
    assert client.post(f"/sms-campaigns/{cid}/cancel", headers=admin).json()["status"] == "cancelled"
    assert client.post(f"/sms-campaigns/{cid}/send", headers=admin).status_code == 409
    # another tenant never sees it
    with SessionLocal() as db:
        otid = db.scalar(select(User.tenant_id).where(User.email == "employee@faraz.test"))
        oemail = f"sms-admin-{uuid.uuid4().hex[:6]}@faraz.test"
        db.add(User(tenant_id=otid, email=oemail, name="مدیر فراز", role="tenant_admin"))
        db.commit()
    other = _h(client, oemail)
    assert client.post(f"/sms-campaigns/{cid}/send", headers=other).status_code == 404
    assert all(i["id"] != cid for i in client.get("/sms-campaigns", headers=other).json()["items"])
