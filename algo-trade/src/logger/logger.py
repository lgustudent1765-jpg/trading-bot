# file: src/logger/logger.py
"""
Structured JSON logger with:
  - Sensitive-field redaction
  - Rotating file handler (10 MB per file, 5 backups)
  - Console + file output
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import os
import re
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Set

_REDACTED_FIELDS: Set[str] = {
    "api_key", "fmp_api_key", "access_token", "refresh_token",
    "trade_token", "password", "secret", "authorization",
    "device_id", "notify_email_pass", "notify_email_user",
    "webhook_url",
}

_SECRET_PATTERN = re.compile(
    r"(api[_-]?key|token|secret|password|webhook)[=:\"'\s]+\S+",
    re.IGNORECASE,
)


def _redact_dict(data: Dict[str, Any]) -> Dict[str, Any]:
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
    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
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
    def _log_with_ctx(self, level: int, msg: Any, **ctx: Any) -> None:
        self.log(level, msg, extra=ctx)

    def info(self, msg: Any, *args: Any, **kwargs: Any) -> None:       # type: ignore[override]
        self._log_with_ctx(logging.INFO, msg, **kwargs)

    def debug(self, msg: Any, *args: Any, **kwargs: Any) -> None:      # type: ignore[override]
        self._log_with_ctx(logging.DEBUG, msg, **kwargs)

    def warning(self, msg: Any, *args: Any, **kwargs: Any) -> None:    # type: ignore[override]
        self._log_with_ctx(logging.WARNING, msg, **kwargs)

    def error(self, msg: Any, *args: Any, **kwargs: Any) -> None:      # type: ignore[override]
        self._log_with_ctx(logging.ERROR, msg, **kwargs)

    def exception(self, msg: Any, *args: Any, **kwargs: Any) -> None:  # type: ignore[override]
        kwargs.setdefault("exc_info", True)
        self._log_with_ctx(logging.ERROR, msg, **kwargs)


_configured = False


def _configure_root(
    level: str = "INFO",
    log_file: Optional[str] = None,
    json_format: bool = True,
    max_bytes: int = 10 * 1024 * 1024,  # 10 MB
    backup_count: int = 5,
) -> None:
    global _configured
    if _configured:
        return
    _configured = True

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    json_fmt  = _JsonFormatter()
    plain_fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    formatter = json_fmt if json_format else plain_fmt

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    root.addHandler(console)

    if log_file:
        log_path = os.path.abspath(log_file)
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        fh = logging.handlers.RotatingFileHandler(
            log_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        fh.setFormatter(json_fmt)  # always JSON in file
        root.addHandler(fh)


def get_logger(name: str) -> _ContextAdapter:
    """Return a structured logger for *name*."""
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
