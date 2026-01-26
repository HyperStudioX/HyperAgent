"""Logging configuration using loguru."""

import logging
import sys
import time
from contextlib import contextmanager
from typing import Literal

from loguru import logger


# Remove default handler
logger.remove()


def _abbreviate_module_name(name: str) -> str:
    """Abbreviate module name for cleaner console output.

    Example: app.agents.subagents.chat -> a.a.s.chat
    """
    parts = name.split(".")
    if len(parts) <= 1:
        return name
    # Keep last part full, abbreviate the rest
    abbreviated = [p[0] for p in parts[:-1]]
    abbreviated.append(parts[-1])
    return ".".join(abbreviated)


def setup_logging(
    log_level: str = "INFO",
    log_format: Literal["json", "console"] = "console",
) -> None:
    """Configure logging for the application using loguru.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Output format - "json" for production, "console" for development
    """
    # Configure format based on environment
    if log_format == "json":
        # Production: JSON output with custom serialization
        logger.add(
            sys.stdout,
            format="{message}",
            level=log_level.upper(),
            serialize=True,
            backtrace=True,
            diagnose=True,
        )
    else:
        # Development: Colored console output with tool invocation highlighting
        from loguru._colorizer import Colorizer

        class ToolHighlightSink:
            """Custom sink that highlights tool invocations."""

            def __init__(self, sink=sys.stdout):
                self.sink = sink
                self.colorizer = Colorizer()

            def write(self, message):
                """Write formatted message with colors applied."""
                self.sink.write(message)

            def format_record(self, record):
                """Format a log record with tool highlighting."""
                message = record["message"]
                extra = record["extra"]
                # Compact timestamp: time only, no date
                timestamp = record["time"].strftime("%H:%M:%S.%f")[:-3]

                # Abbreviate module name for cleaner output
                module_name = _abbreviate_module_name(record["name"])

                # Check if this is a tool invocation
                is_tool_invoked = message.endswith("_tool_invoked")
                is_tool_completed = message.endswith("_completed")
                is_tool_failed = message.endswith("_failed")

                # Build extra fields string (without 'name')
                extra_str = ""
                if extra:
                    relevant_extra = {k: v for k, v in extra.items() if k != "name"}
                    if relevant_extra:
                        parts = [f"{k}={v!r}" for k, v in relevant_extra.items()]
                        extra_str = " | " + ", ".join(parts)

                # ANSI color codes
                GREEN = "\033[32m"
                CYAN = "\033[36m"
                YELLOW = "\033[33m"
                MAGENTA = "\033[35m"
                RED = "\033[31m"
                BOLD = "\033[1m"
                RESET = "\033[0m"
                DIM = "\033[2m"

                # Format based on log type
                if is_tool_invoked:
                    return (
                        f"{GREEN}{timestamp}{RESET} | "
                        f"{MAGENTA}{BOLD}🔧 TOOL{RESET}  {DIM}|{RESET} "
                        f"{CYAN}{module_name}{RESET} | "
                        f"{MAGENTA}{BOLD}{message}{RESET}"
                        f"{YELLOW}{extra_str}{RESET}\n"
                    )
                elif is_tool_completed:
                    return (
                        f"{GREEN}{timestamp}{RESET} | "
                        f"{GREEN}{BOLD}✓ DONE{RESET}  {DIM}|{RESET} "
                        f"{CYAN}{module_name}{RESET} | "
                        f"{GREEN}{message}{RESET}"
                        f"{YELLOW}{extra_str}{RESET}\n"
                    )
                elif is_tool_failed:
                    return (
                        f"{GREEN}{timestamp}{RESET} | "
                        f"{RED}{BOLD}✗ FAIL{RESET}  {DIM}|{RESET} "
                        f"{CYAN}{module_name}{RESET} | "
                        f"{RED}{message}{RESET}"
                        f"{YELLOW}{extra_str}{RESET}\n"
                    )
                else:
                    # Standard format with level-based colors
                    level_name = record["level"].name
                    # Shorten level names to 5 chars for consistency
                    level_display = {
                        "DEBUG": "DEBUG",
                        "INFO": "INFO ",
                        "WARNING": "WARN ",
                        "ERROR": "ERROR",
                        "CRITICAL": "CRIT ",
                    }.get(level_name, level_name[:5].ljust(5))

                    level_color = {
                        "DEBUG": CYAN,
                        "INFO": RESET,
                        "WARNING": YELLOW,
                        "ERROR": RED,
                        "CRITICAL": f"{RED}{BOLD}",
                    }.get(level_name, RESET)

                    return (
                        f"{GREEN}{timestamp}{RESET} | "
                        f"{level_color}{level_display}{RESET} | "
                        f"{CYAN}{module_name}{RESET} | "
                        f"{level_color}{message}{RESET}"
                        f"{YELLOW}{extra_str}{RESET}\n"
                    )

        # Create custom sink
        tool_sink = ToolHighlightSink()

        logger.add(
            lambda msg: tool_sink.write(tool_sink.format_record(msg.record)),
            level=log_level.upper(),
            backtrace=True,
            diagnose=True,
        )

    # Intercept standard library logging and route to loguru
    class InterceptHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            # Get corresponding Loguru level if it exists
            try:
                level = logger.level(record.levelname).name
            except ValueError:
                level = record.levelno

            # Find caller from where originated the logged message
            frame, depth = sys._getframe(6), 6
            while frame and frame.f_code.co_filename == logging.__file__:
                frame = frame.f_back
                depth += 1

            logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())

    # Configure standard library logging to use loguru
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").propagate = True

    # LLM frameworks
    logging.getLogger("langchain").setLevel(logging.WARNING)
    logging.getLogger("langchain_core").setLevel(logging.WARNING)
    logging.getLogger("langgraph").setLevel(logging.WARNING)

    # LLM providers
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("anthropic").setLevel(logging.WARNING)
    logging.getLogger("google.generativeai").setLevel(logging.WARNING)

    # Database
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("asyncpg").setLevel(logging.WARNING)

    # Misc
    logging.getLogger("PIL").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("charset_normalizer").setLevel(logging.WARNING)


def get_logger(name: str | None = None):
    """Get a logger instance.

    Args:
        name: Logger name, typically __name__ of the module

    Returns:
        A loguru logger instance bound with the module name
    """
    if name:
        return logger.bind(name=name)
    return logger


@contextmanager
def log_timing(logger_instance, event_name: str, **context):
    """Context manager that logs start/complete/fail with duration_ms.

    Usage:
        with log_timing(logger, "web_search", query=query):
            results = perform_search(query)

    Args:
        logger_instance: A loguru logger instance
        event_name: Base name for the event (will append _started/_completed/_failed)
        **context: Additional context to include in all log messages

    Yields:
        None

    Example:
        >>> logger = get_logger(__name__)
        >>> with log_timing(logger, "api_call", endpoint="/users"):
        ...     response = api.get("/users")
        # Logs:
        # DEBUG: api_call_started | endpoint='/users'
        # INFO: api_call_completed | duration_ms=234, endpoint='/users'
    """
    start = time.perf_counter()
    logger_instance.debug(f"{event_name}_started", **context)
    try:
        yield
        duration_ms = int((time.perf_counter() - start) * 1000)
        logger_instance.info(f"{event_name}_completed", duration_ms=duration_ms, **context)
    except Exception as e:
        duration_ms = int((time.perf_counter() - start) * 1000)
        logger_instance.error(f"{event_name}_failed", duration_ms=duration_ms, error=str(e), **context)
        raise
