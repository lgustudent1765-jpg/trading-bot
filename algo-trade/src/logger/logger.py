# file: src/logger/logger.py
"""
Structured JSON logger with sensitive-field redaction.

Usage:
    from src.logger import get_logger
    log = get_logger(__name__)
    log.info("order placed", order_id="abc123", symbol="AAPL")
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Set

# Fields that must never appear in logs in plain text.
_REDACTED_FIELDS: Set[str] = {
    "api_key",
    "fmp_api_key",
    "access_token",
    "refresh_token",
    "trade_token",
    "password",
    "secret",
    "authorization",
    "device_id",
}

_SECRET_PATTERN = re.compile(
    r"(api[_-]?key|token|secret|password)[=:\"'\s]+\S+",
    re.IGNORECASE,
)


def _redact_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """Return a shallow copy of *data* with sensitive values replaced."""
    result = {}
    for k, v in data.items():
        if k.lower() in _REDACTED_FIELDS:
            result[k] = "***REDACTED***"
        elif isinstance(v, str):
            result[k] = _SECRET_PATTERN.sub(r"\1=***REDACTED***", v)
        elif isinstance(v, dict):
            result[k] = _redact_dict(v)
        else:
            result[k] = v
    return result


class _JsonFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Extra context fields added via log.info(..., key=val) or extra={}.
        for key, val in record.__dict__.items():
            if key.startswith("_") or key in (
                "msg", "args", "levelname", "levelno", "pathname", "filename",
                "module", "exc_info", "exc_text", "stack_info", "lineno",
                "funcName", "created", "msecs", "relativeCreated", "thread",
                "threadName", "processName", "process", "name", "message",
            ):
                continue
            payload[key] = val

        payload = _redact_dict(payload)

        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)

        return json.dumps(payload)


class _ContextAdapter(logging.LoggerAdapter):
    """Allows structured keyword arguments on every log call."""

    def process(self, msg: Any, kwargs: Dict) -> tuple:
        extra = kwargs.pop("extra", {})
        # Merge ad-hoc kwargs into extra so they appear in the JSON record.
        extra.update(kwargs.pop("_ctx", {}))
        kwargs["extra"] = extra
        return msg, kwargs

    def _log_with_ctx(self, level: int, msg: Any, **ctx: Any) -> None:
        self.log(level, msg, extra=ctx)

    def info(self, msg: Any, *args: Any, **kwargs: Any) -> None:  # type: ignore[override]
        self._log_with_ctx(logging.INFO, msg, **kwargs)

    def debug(self, msg: Any, *args: Any, **kwargs: Any) -> None:  # type: ignore[override]
        self._log_with_ctx(logging.DEBUG, msg, **kwargs)

    def warning(self, msg: Any, *args: Any, **kwargs: Any) -> None:  # type: ignore[override]
        self._log_with_ctx(logging.WARNING, msg, **kwargs)

    def error(self, msg: Any, *args: Any, **kwargs: Any) -> None:  # type: ignore[override]
        self._log_with_ctx(logging.ERROR, msg, **kwargs)

    def exception(self, msg: Any, *args: Any, **kwargs: Any) -> None:  # type: ignore[override]
        kwargs.setdefault("exc_info", True)
        self._log_with_ctx(logging.ERROR, msg, **kwargs)


_configured = False


def _configure_root(level: str = "INFO", log_file: Optional[str] = None, json_format: bool = True) -> None:
    global _configured
    if _configured:
        return
    _configured = True

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    formatter: logging.Formatter = _JsonFormatter() if json_format else logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s"
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)

    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)


def get_logger(name: str) -> _ContextAdapter:
    """
    Return a structured logger for *name*.

    Configuration is read from src.config on first call.
    Falls back to INFO / stdout if config is unavailable.
    """
    try:
        from src.config import get_config
        cfg = get_config().get("logging", {})
        _configure_root(
            level=cfg.get("level", "INFO"),
            log_file=cfg.get("log_file") or None,
            json_format=cfg.get("json_format", True),
        )
    except Exception:
        _configure_root()

    return _ContextAdapter(logging.getLogger(name), {})
