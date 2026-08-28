import logging
import sys


class SafeFormatter(logging.Formatter):
    """
    Log formatter that avoids exposing sensitive API key patterns in logs.
    """
    def format(self, record: logging.LogRecord) -> str:
        formatted = super().format(record)
        # Redact any accidental groq or bearer token leakage
        if "gsk_" in formatted:
            import re
            formatted = re.sub(r"gsk_[a-zA-Z0-9_\-]+", "gsk_[REDACTED]", formatted)
        return formatted


def setup_logging(level: str = "INFO") -> None:
    """Configure application-wide structured logging."""
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers to avoid duplicate log records
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    formatter = SafeFormatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)


setup_logging()
