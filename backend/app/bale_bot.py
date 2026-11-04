"""Karen Travel bot on Bale (بازوی بله) — long polling, so it works without a public HTTPS webhook.

Flow: any message → welcome + a «ارسال شماره» button (Bale's request_contact) → the customer shares their OWN number
→ a sales-desk case is opened (channel "bale", the customer's last text as the trip) → confirmation; the keyboard is
removed. Later messages from a known chat are appended to the open case. A contact that is not the sender's own number
is refused. Nothing is sent to anyone except the chat that wrote to the bot.

Enabled only when BALE_BOT_TOKEN is set. Runs inside the API process (one uvicorn process) via start_in_background().
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Callable, Optional

import httpx

from .sales_desk import normalize_mobile

API = "https://tapi.bale.ai/bot{token}/{method}"
LOG = logging.getLogger("karenseir.bale")

WELCOME = ("سلام{name}! به کارن تراول خوش آمدی.\n"
           "مقصد، تاریخ و تعداد مسافرها را بنویس و بعد با دکمه‌ی «ارسال شماره» شماره‌ات را بفرست تا کارشناس ما تماس بگیرد.")
ASK_CONTACT = "برای ثبت درخواست، روی دکمه‌ی «ارسال شماره» بزن."
NOT_OWN = "فقط شماره‌ی خودت را با دکمه‌ی «ارسال شماره» بفرست."
BAD_NUMBER = "این شماره موبایل ایران نیست؛ لطفاً با شماره‌ی موبایل ایرانی دوباره تلاش کن."
DONE = "ممنون{name}! درخواستت در کارن تراول ثبت شد و کارشناس ما به‌زودی با شماره‌ی {mobile} تماس می‌گیرد.\nهر پیام دیگری بفرستی به همین درخواست اضافه می‌شود."
APPENDED = "پیامت به درخواستت اضافه شد. کارشناس کارن تراول به‌زودی تماس می‌گیرد."
CLOSED = "ثبت درخواست از بله فعلاً ممکن نیست؛ لطفاً با پشتیبانی کارن تراول تماس بگیر."
CONTACT_KEYBOARD = {"keyboard": [[{"text": "ارسال شماره", "request_contact": True}]], "resize_keyboard": True, "one_time_keyboard": True}
REMOVE_KEYBOARD = {"remove_keyboard": True}


class BaleBot:
    """Pure update handling; I/O goes through `send` and `open_case` so it is testable without network or DB."""

    def __init__(self, send: Callable[[int, str, Optional[dict]], Any], open_case: Callable[[str, Optional[str], str, str], str]):
        self.send, self.open_case = send, open_case
        self.pending_text: dict[int, str] = {}   # chat id → what the customer asked before sharing a number
        self.known: dict[int, tuple[str, Optional[str]]] = {}  # chat id → (mobile, name) after a shared contact

    def handle(self, update: dict) -> Optional[str]:
        msg = update.get("message") or {}
        chat = (msg.get("chat") or {}).get("id")
        sender = msg.get("from") or {}
        if chat is None or update.get("update_id") is None or sender.get("is_bot"):
            return None
        first = (sender.get("first_name") or "").strip()
        hello = f" {first}" if first else ""
        text = (msg.get("text") or msg.get("caption") or "").strip()
        ext = f"bale:{update['update_id']}"
        contact = msg.get("contact")
        if contact:
            if contact.get("user_id") not in (None, sender.get("id")):
                self.send(chat, NOT_OWN, CONTACT_KEYBOARD)
                return "not_own"
            try:
                mobile = normalize_mobile(str(contact.get("phone_number") or ""))
            except ValueError:
                self.send(chat, BAD_NUMBER, CONTACT_KEYBOARD)
                return "bad_number"
            name = " ".join(x for x in (contact.get("first_name") or first, contact.get("last_name") or sender.get("last_name")) if x) or None
            try:
                result = self.open_case(mobile, name, self.pending_text.pop(chat, ""), ext)
            except Exception:  # intake closed or DB error: tell the customer, never pretend it worked
                LOG.exception("bale_case_failed")
                self.send(chat, CLOSED, REMOVE_KEYBOARD)
                return "failed"
            self.known[chat] = (mobile, name)
            if result != "duplicate":
                self.send(chat, DONE.format(name=hello, mobile=mobile), REMOVE_KEYBOARD)
            return result
        if chat in self.known and text:
            mobile, name = self.known[chat]
            try:
                result = self.open_case(mobile, name, text, ext)
            except Exception:
                LOG.exception("bale_case_failed")
                self.send(chat, CLOSED, None)
                return "failed"
            if result != "duplicate":
                self.send(chat, APPENDED, None)
            return result
        if text and not text.startswith("/"):
            self.pending_text[chat] = (self.pending_text.get(chat, "") + "\n" + text).strip()[:1000]
            self.send(chat, ASK_CONTACT, CONTACT_KEYBOARD)
            return "asked_contact"
        self.send(chat, WELCOME.format(name=hello), CONTACT_KEYBOARD)
        return "welcome"


async def run_forever(token: str, session_factory, bale_case) -> None:
    async with httpx.AsyncClient(timeout=40.0) as client:
        async def call(method: str, **payload) -> dict:
            r = await client.post(API.format(token=token, method=method), json=payload)
            data = r.json()
            if not data.get("ok"):
                raise RuntimeError(f"bale {method}: {str(data.get('description'))[:120]}")
            return data

        pending: list = []

        def send(chat: int, text: str, markup: Optional[dict]) -> None:
            pending.append({"chat_id": chat, "text": text, **({"reply_markup": markup} if markup else {})})

        def open_case(mobile: str, name: Optional[str], text: str, ext: str) -> str:
            with session_factory() as db:
                return bale_case(db, mobile, name, text, ext)

        bot = BaleBot(send, open_case)
        offset: Optional[int] = None
        delay = 2
        LOG.info("bale_bot_started")
        while True:
            try:
                data = await call("getUpdates", timeout=25, **({"offset": offset} if offset is not None else {}))
                for update in data.get("result") or []:
                    offset = int(update["update_id"]) + 1
                    await asyncio.to_thread(bot.handle, update)
                    while pending:
                        await call("sendMessage", **pending.pop(0))
                delay = 2
            except asyncio.CancelledError:
                raise
            except Exception:
                LOG.exception("bale_poll_error")
                await asyncio.sleep(delay)
                delay = min(delay * 2, 60)


def start_in_background(session_factory) -> Optional[asyncio.Task]:
    token = (os.getenv("BALE_BOT_TOKEN") or "").strip()
    if not token:
        return None
    from . import sales_desk
    if sales_desk.BALE_CASE is None:
        LOG.warning("bale_bot_not_started: sales desk router not mounted")
        return None
    return asyncio.create_task(run_forever(token, session_factory, sales_desk.BALE_CASE))
