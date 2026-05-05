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
            "event",
            "session_id",
            "user",
            "turn",
            "course_id",
            "model",
            "tokens_in",
            "tokens_out",
            "cost",
            "duration_ms",
            "ttfb_ms",
            "tool",
            "agent",
            "round",
            "rounds",
            "msg_count",
            "token_count",
            "text_length",
            "topic_count",
            "section_count",
            "score",
            "mastery",
            "provider",
            "stop_reason",
            "caller",
            "intent",
            "preview",
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
    """Configure the root logger for structured JSON output to stdout.

    BYO pipeline logs go to a separate file (logs/byo.log) so they don't
    clutter the main service output. In Cloud Run, both go to stdout
    (Cloud Logging separates by service name).
    """
    import os

    formatter = JSONFormatter()

    # Main handler — stdout for all non-BYO logs
    main_handler = logging.StreamHandler(sys.stdout)
    main_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(main_handler)
    root.setLevel(logging.INFO)

    # BYO handler — separate file in local dev, stdout in Cloud Run
    is_cloud_run = os.environ.get("K_SERVICE") or os.environ.get("CLOUD_RUN")
    if not is_cloud_run:
        try:
            log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
            os.makedirs(log_dir, exist_ok=True)
            byo_file = logging.FileHandler(os.path.join(log_dir, "byo.log"), encoding="utf-8")
            byo_file.setFormatter(formatter)

            # Route all byo.* loggers to the file
            byo_logger = logging.getLogger("byo")
            byo_logger.addHandler(byo_file)
            byo_logger.propagate = False  # Don't send to root (stdout)
            byo_logger.setLevel(logging.INFO)

            # Also add stdout so you can still see BYO in terminal if needed,
            # but at WARNING level only (errors + warnings show, INFO goes to file)
            byo_stdout = logging.StreamHandler(sys.stdout)
            byo_stdout.setFormatter(formatter)
            byo_stdout.setLevel(logging.WARNING)
            byo_logger.addHandler(byo_stdout)
        except Exception:
            pass  # Fall back to default (all to stdout)

    # Silence noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("anthropic").setLevel(logging.WARNING)


class SessionLogger:
    """Convenience wrapper that injects session context into every log call.

    Usage:
        slog = SessionLogger(logger, session_id="abc123", user="alice@example.com")
        slog.info("Chat started", extra={"msg_count": 5})
    """

    def __init__(self, logger: logging.Logger, session_id: str = "", user: str = "",
                 course_id: int | str | None = None):
        self._logger = logger
        self._extra: dict = {
            "session_id": session_id[:8] if session_id else "",
            "user": user or "",
        }
        if course_id is not None:
            self._extra["course_id"] = course_id

    def set_turn(self, turn_number: int) -> None:
        """Set the current turn number for all subsequent log calls."""
        self._extra["turn"] = turn_number

    def set_course(self, course_id: int | str) -> None:
        """Set the course_id for all subsequent log calls."""
        self._extra["course_id"] = course_id

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
