"""Structured JSON logging for Cloud Run / Cloud Logging compatibility.

All log output goes to stdout as single-line JSON objects. Cloud Run's
logging agent automatically ingests these and makes them searchable in
Cloud Logging with proper severity mapping.

Usage:
    from app.core.logging_config import setup_logging
    setup_logging()  # call once at startup, before any other imports log
"""

import json
import logging
import sys


class JSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON for Cloud Logging ingestion."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict = {
            "timestamp": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S.%03d"),
            "severity": record.levelname,  # Cloud Logging uses "severity"
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Structured context fields — only included when set
        for key in (
            "session_id",
            "user",
            "model",
            "tokens_in",
            "tokens_out",
            "cost",
            "duration_ms",
            "tool",
            "agent",
            "round",
            "msg_count",
            "token_count",
            "provider",
            "stop_reason",
            "caller",
        ):
            val = getattr(record, key, None)
            if val is not None:
                log_entry[key] = val

        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str)

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:  # noqa: N802
        """ISO-8601 timestamp with milliseconds."""
        from datetime import datetime, timezone

        dt = datetime.fromtimestamp(record.created, tz=timezone.utc)
        return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{int(record.msecs):03d}Z"


def setup_logging() -> None:
    """Configure the root logger for structured JSON output to stdout."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)

    # Silence noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("anthropic").setLevel(logging.WARNING)


class SessionLogger:
    """Convenience wrapper that injects session context into every log call.

    Usage:
        slog = SessionLogger(logger, session_id="abc123", user="alice@example.com")
        slog.info("Chat started", extra={"msg_count": 5})
    """

    def __init__(self, logger: logging.Logger, session_id: str = "", user: str = ""):
        self._logger = logger
        self._extra: dict = {
            "session_id": session_id[:8] if session_id else "",
            "user": user or "",
        }

    def _log(self, level: int, msg: str, *args, **kwargs) -> None:
        extra = {**self._extra, **kwargs.pop("extra", {})}
        kwargs["extra"] = extra
        self._logger.log(level, msg, *args, **kwargs)

    def debug(self, msg: str, *args, **kwargs) -> None:
        self._log(logging.DEBUG, msg, *args, **kwargs)

    def info(self, msg: str, *args, **kwargs) -> None:
        self._log(logging.INFO, msg, *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs) -> None:
        self._log(logging.WARNING, msg, *args, **kwargs)

    def error(self, msg: str, *args, **kwargs) -> None:
        self._log(logging.ERROR, msg, *args, **kwargs)
