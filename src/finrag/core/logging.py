import logging
import sys
from contextvars import ContextVar
import structlog

# Define dynamic correlation ID context variable
correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")

def add_correlation_id(logger: logging.Logger, method_name: str, event_dict: dict) -> dict:
    """Inject active request correlation_id into structured logs."""
    cid = correlation_id_var.get()
    if cid:
        event_dict["correlation_id"] = cid
    return event_dict

def configure_logging(log_level: str = "INFO", env: str = "development") -> None:
    """Initialize structured logger configs."""
    # Convert string log level to logging integer constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        add_correlation_id,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if env == "production":
        # Production output renders structured JSON lines
        processors = shared_processors + [
            structlog.processors.JSONRenderer()
        ]
    else:
        # Development output renders user-friendly colored lines
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True)
        ]

    structlog.configure(
        processors=processors,
        logger_factory=structlog.PrintLoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        cache_logger_on_first_use=True,
    )

    # Re-route standard python logs through structlog formatters
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=numeric_level,
    )
