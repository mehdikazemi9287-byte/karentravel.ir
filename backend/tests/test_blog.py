"""Blog: editor-only writes, draft → publish, no HTML, no prices, slug uniqueness, public read and tenant isolation."""
import uuid

BODY = "شیراز شهر باغ‌ها و شعر است.\n\n## بهترین زمان سفر\n- اردیبهشت برای دیدن باغ‌ها\n- پاییز برای هوای معتدل"


def _h(client, email):
    r = client.post("/auth/dev-login", json={"email": email})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _post(**kw):
    return {"slug": "shiraz-" + uuid.uuid4().hex[:8], "title": "راهنمای سفر به شیراز", "excerpt": "هر آنچه برای سفر به شیراز لازم است",
            "body": BODY, "category": "guide", "tags": ["شیراز", "شیراز", "بهار"], "cover": "/images/approved-figma/refTripShiraz.jpg", **kw}


def test_blog_flow(client):
    admin = _h(client, "tenant-admin@aftab.test")
    employee = _h(client, "employee@aftab.test")
    assert client.post("/blog/posts", json=_post(), headers=employee).status_code == 403

    assert client.post("/blog/posts", json=_post(body="<script>alert(1)</script> متن کافی برای آزمون است"), headers=admin).status_code == 422
    assert client.post("/blog/posts", json=_post(slug="Bad Slug"), headers=admin).status_code == 422
    assert client.post("/blog/posts", json=_post(category="ads"), headers=admin).status_code == 422
    assert client.post("/blog/posts", json=_post(cover="https://evil.example/x.jpg"), headers=admin).status_code == 422
    assert client.post("/blog/posts", json=_post(body=BODY + "\nتور شیراز از ۵ میلیون تومان"), headers=admin).status_code == 422

    r = client.post("/blog/posts", json=_post(), headers=admin)
    assert r.status_code == 201, r.text
    post = r.json()
    assert post["status"] == "draft" and post["tags"] == ["شیراز", "بهار"]
    assert client.post("/blog/posts", json=_post(slug=post["slug"]), headers=admin).status_code == 409

    # drafts are not public
    assert client.get(f"/public/tenants/aftab-bank/blog/{post['slug']}").status_code == 404
    assert post["slug"] not in str(client.get("/public/tenants/aftab-bank/blog").json())

    assert client.post(f"/blog/posts/{post['id']}/publish", headers=admin).json()["status"] == "published"
    pub = client.get(f"/public/tenants/aftab-bank/blog/{post['slug']}").json()
    assert pub["title"] == "راهنمای سفر به شیراز" and pub["body"] == BODY and pub["category_label"] == "راهنمای مقصد"
    listing = client.get("/public/tenants/aftab-bank/blog", params={"category": "guide"}).json()
    assert post["slug"] in [i["slug"] for i in listing["items"]] and "body" not in listing["items"][0]
    assert post["slug"] in [i["slug"] for i in client.get("/public/tenants/aftab-bank/blog", params={"tag": "بهار"}).json()["items"]]
    assert client.get("/public/tenants/aftab-bank/blog", params={"category": "ads"}).status_code == 404
    assert f"/blog/{post['slug']}" in [i["path"] for i in client.get("/public/tenants/aftab-bank/blog-sitemap").json()["items"]]

    # another tenant neither sees nor edits it
    other = _h(client, "employee@faraz.test")
    assert client.get(f"/public/tenants/faraz-industries/blog/{post['slug']}").status_code == 404
    assert client.get(f"/blog/posts/{post['id']}", headers=other).status_code in (403, 404)

    upd = client.put(f"/blog/posts/{post['id']}", json=_post(slug=post["slug"], title="راهنمای کامل سفر به شیراز"), headers=admin)
    assert upd.status_code == 200 and upd.json()["published_at"] == pub["published_at"]
    assert client.post(f"/blog/posts/{post['id']}/unpublish", headers=admin).json()["status"] == "draft"
    assert client.get(f"/public/tenants/aftab-bank/blog/{post['slug']}").status_code == 404
