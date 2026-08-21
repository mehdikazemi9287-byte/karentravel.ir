from __future__ import annotations

import logging
import json
import time
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from . import main as _main_models  # noqa: F401 - register FK target metadata in worker process
from .database import SessionLocal
from .observability import configure_logging, prometheus_metrics, set_gauge
from .operations import NotificationDeliveryAttempt, NotificationRecord, OutboxEvent
from .providers import ADAPTERS, ProviderContext

logger = logging.getLogger("karenseir.outbox")


def process_batch(limit: int = 50, *, adapter=None) -> int:
    processed = 0
    delivery_adapter = adapter or ADAPTERS["push"]
    with SessionLocal() as db:
        set_gauge("karenseir_outbox_queue_depth", db.scalar(select(func.count()).select_from(OutboxEvent).where(OutboxEvent.status.in_(["pending", "retry"]))) or 0)
        set_gauge("karenseir_outbox_dead_letter_depth", db.scalar(select(func.count()).select_from(OutboxEvent).where(OutboxEvent.status == "dead_letter")) or 0)
        # Due retries (especially near dead-letter) must not starve behind a large
        # notification burst. The ordering remains deterministic within priority.
        events = db.scalars(select(OutboxEvent).where(OutboxEvent.status.in_(["pending", "retry"]), OutboxEvent.available_at <= datetime.now(timezone.utc)).order_by(OutboxEvent.attempts.desc(), OutboxEvent.available_at, OutboxEvent.created_at).limit(limit).with_for_update(skip_locked=True)).all()
        for event in events:
            event.attempts += 1
            result = delivery_adapter.execute("publish_outbox", {"event_id": event.id}, ProviderContext(event.tenant_id, event.correlation_id or event.id, event.idempotency_key or event.id))
            if result["ok"]:
                event.status = "delivered"
            elif event.attempts >= 5:
                event.status = "dead_letter"
                event.last_error = result["reason"]
                event.dead_lettered_at = datetime.now(timezone.utc)
            else:
                event.status = "retry"
                event.last_error = result["reason"]
                event.available_at = datetime.now(timezone.utc) + timedelta(minutes=2 ** event.attempts)
            try:
                payload = json.loads(event.payload_json)
            except (TypeError, ValueError):
                payload = {}
            notification_id = payload.get("notification_id")
            if notification_id:
                notification = db.scalar(select(NotificationRecord).where(NotificationRecord.id == notification_id, NotificationRecord.tenant_id == event.tenant_id))
                attempt = db.scalar(select(NotificationDeliveryAttempt).where(NotificationDeliveryAttempt.notification_id == notification_id, NotificationDeliveryAttempt.tenant_id == event.tenant_id, NotificationDeliveryAttempt.channel == "push"))
                if notification:
                    notification.status = event.status
                if attempt:
                    attempt.attempt = event.attempts
                    attempt.status = event.status
                    attempt.error_code = None if result["ok"] else result["reason"]
            processed += 1
        db.commit()
        set_gauge("karenseir_outbox_queue_depth", db.scalar(select(func.count()).select_from(OutboxEvent).where(OutboxEvent.status.in_(["pending", "retry"]))) or 0)
        set_gauge("karenseir_outbox_dead_letter_depth", db.scalar(select(func.count()).select_from(OutboxEvent).where(OutboxEvent.status == "dead_letter")) or 0)
    return processed


class WorkerStatusHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            body = b'{"status":"ok","service":"karenseir-outbox-worker"}\n'; content_type = "application/json"
        elif self.path == "/metrics":
            body = prometheus_metrics().encode("utf-8"); content_type = "text/plain; version=0.0.4"
        else:
            self.send_error(404); return
        self.send_response(200); self.send_header("Content-Type", content_type); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

    def log_message(self, format, *args):
        return


def start_status_server() -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("0.0.0.0", 9101), WorkerStatusHandler)
    threading.Thread(target=server.serve_forever, daemon=True, name="worker-status").start()
    return server


def run() -> None:
    configure_logging()
    start_status_server()
    while True:
        count = process_batch()
        logger.info("outbox_batch", extra={"processed": count})
        time.sleep(5 if count else 15)


if __name__ == "__main__":
    run()
