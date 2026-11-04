from app.bale_bot import ASK_CONTACT, BaleBot, NOT_OWN


def make():
    sent, cases = [], []
    def open_case(mobile, name, text, ext):
        cases.append((mobile, name, text, ext))
        return "created" if len(cases) == 1 else "appended"
    return BaleBot(lambda chat, text, markup: sent.append((chat, text, markup)), open_case), sent, cases


def upd(uid, **msg):
    return {"update_id": uid, "message": {"chat": {"id": 7}, "from": {"id": 70, "first_name": "سارا"}, **msg}}


def test_text_then_own_contact_opens_case_and_appends_later():
    bot, sent, cases = make()
    assert bot.handle(upd(1, text="/start")) == "welcome"
    assert bot.handle(upd(2, text="کیش ۴ روز ۳ نفر")) == "asked_contact" and sent[-1][1] == ASK_CONTACT
    assert sent[-1][2]["keyboard"][0][0]["request_contact"] is True
    assert bot.handle(upd(3, contact={"phone_number": "+989121234567", "user_id": 70, "first_name": "سارا"})) == "created"
    assert cases[0] == ("09121234567", "سارا", "کیش ۴ روز ۳ نفر", "bale:3")
    assert "09121234567" in sent[-1][1] and sent[-1][2] == {"remove_keyboard": True}
    assert bot.handle(upd(4, text="ترجیحاً هتل ساحلی")) == "appended" and cases[1][2] == "ترجیحاً هتل ساحلی"


def test_someone_elses_contact_and_bad_number_are_refused():
    bot, sent, cases = make()
    assert bot.handle(upd(1, contact={"phone_number": "09121234567", "user_id": 99})) == "not_own" and sent[-1][1] == NOT_OWN
    assert bot.handle(upd(2, contact={"phone_number": "12345", "user_id": 70})) == "bad_number"
    assert cases == []


def test_closed_intake_is_reported_not_faked():
    sent = []
    def boom(*a):
        raise RuntimeError("closed")
    bot = BaleBot(lambda c, t, m: sent.append(t), boom)
    assert bot.handle(upd(1, contact={"phone_number": "09121234567", "user_id": 70})) == "failed"
    assert "ممکن نیست" in sent[-1]
