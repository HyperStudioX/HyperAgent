"""Logging configuration using loguru."""

import logging
import sys
from typing import Literal

from loguru import logger


# Remove default handler
logger.remove()


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
                timestamp = record["time"].strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

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
                        f"{MAGENTA}{BOLD}🔧 TOOL{RESET}   {DIM}|{RESET} "
                        f"{CYAN}{record['name']}:{record['function']}{RESET} | "
                        f"{MAGENTA}{BOLD}{message}{RESET}"
                        f"{YELLOW}{extra_str}{RESET}\n"
                    )
                elif is_tool_completed:
                    return (
                        f"{GREEN}{timestamp}{RESET} | "
                        f"{GREEN}{BOLD}✓ DONE{RESET}   {DIM}|{RESET} "
                        f"{CYAN}{record['name']}:{record['function']}{RESET} | "
                        f"{GREEN}{message}{RESET}"
                        f"{YELLOW}{extra_str}{RESET}\n"
                    )
                elif is_tool_failed:
                    return (
                        f"{GREEN}{timestamp}{RESET} | "
                        f"{RED}{BOLD}✗ FAIL{RESET}   {DIM}|{RESET} "
                        f"{CYAN}{record['name']}:{record['function']}{RESET} | "
                        f"{RED}{message}{RESET}"
                        f"{YELLOW}{extra_str}{RESET}\n"
                    )
                else:
                    # Standard format with level-based colors
                    level_name = record["level"].name
                    level_color = {
                        "DEBUG": CYAN,
                        "INFO": RESET,
                        "WARNING": YELLOW,
                        "ERROR": RED,
                        "CRITICAL": f"{RED}{BOLD}",
                    }.get(level_name, RESET)

                    return (
                        f"{GREEN}{timestamp}{RESET} | "
                        f"{level_color}{level_name: <8}{RESET} {DIM}|{RESET} "
                        f"{CYAN}{record['name']}:{record['function']}:{record['line']}{RESET} | "
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
