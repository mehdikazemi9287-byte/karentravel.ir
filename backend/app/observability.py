from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from typing import Any


REDACT_KEYS = {"authorization", "password", "token", "refresh_token", "otp", "secret"}
_metrics_lock = threading.Lock()
_request_counts: dict[tuple[str, str], int] = {}
_request_duration_seconds = 0.0
_business_counts: dict[tuple[str, str], int] = {}
_gauges: dict[str, float] = {}


def record_request(method: str, status_code: int, duration_seconds: float) -> None:
    global _request_duration_seconds
    with _metrics_lock:
        key = (method, str(status_code))
        _request_counts[key] = _request_counts.get(key, 0) + 1
        _request_duration_seconds += duration_seconds


def record_business_event(event: str, status: str) -> None:
    allowed_events = {"booking", "payment", "refund", "otp", "provider"}
    if event not in allowed_events or not status.replace("_", "").isalnum():
        return
    with _metrics_lock:
        key = (event, status)
        _business_counts[key] = _business_counts.get(key, 0) + 1


def set_gauge(name: str, value: float) -> None:
    if name not in {"karenseir_outbox_queue_depth", "karenseir_outbox_dead_letter_depth"}:
        return
    with _metrics_lock:
        _gauges[name] = max(float(value), 0.0)


def prometheus_metrics() -> str:
    with _metrics_lock:
        lines = [
            "# HELP karenseir_http_requests_total Total HTTP requests by method and status class.",
            "# TYPE karenseir_http_requests_total counter",
        ]
        for (method, response_status), count in sorted(_request_counts.items()):
            lines.append(f'karenseir_http_requests_total{{method="{method}",status="{response_status}",status_class="{int(response_status) // 100}xx"}} {count}')
        lines.extend([
            "# HELP karenseir_http_request_duration_seconds_total Cumulative HTTP request duration.",
            "# TYPE karenseir_http_request_duration_seconds_total counter",
            f"karenseir_http_request_duration_seconds_total {_request_duration_seconds:.6f}",
        ])
        lines.extend([
            "# HELP karenseir_business_events_total Bounded operational events by domain and status.",
            "# TYPE karenseir_business_events_total counter",
        ])
        for (event, event_status), count in sorted(_business_counts.items()):
            lines.append(f'karenseir_business_events_total{{event="{event}",status="{event_status}"}} {count}')
        for name, value in sorted(_gauges.items()):
            lines.extend([f"# TYPE {name} gauge", f"{name} {value:.0f}"])
        return "\n".join(lines) + "\n"


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: "[REDACTED]" if key.lower() in REDACT_KEYS else redact(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    return value


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in ("request_id", "correlation_id", "method", "path", "status", "processed"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        return json.dumps(redact(payload), ensure_ascii=False)


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    if not any(isinstance(item.formatter, JsonFormatter) for item in root.handlers):
        root.handlers = [handler]
    root.setLevel(logging.INFO)
