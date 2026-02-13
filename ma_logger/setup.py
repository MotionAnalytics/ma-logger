"""
Logging setup and configuration.
"""

import logging
import sys
import os
import warnings

from .formatters import OTelJsonFormatter
from .filters import OTelContextFilter


def setup_logging(formatter=None, context_filter=None):
    """
    Configures the root logger with JSON formatting and context injection.

    Default behavior (zero-config):
        setup_logging()  # Uses default formatter and filter

    Custom behavior:
        # Custom formatter
        formatter = OTelJsonFormatter(trace_id_field="traceId")
        setup_logging(formatter=formatter)

        # Custom filter
        filter = OTelContextFilter(additional_context={"env": "prod"})
        setup_logging(context_filter=filter)

        # Both custom
        setup_logging(formatter=my_formatter, context_filter=my_filter)

    Args:
        formatter (OTelJsonFormatter, optional): Custom formatter instance.
            If None, uses default OTelJsonFormatter().
        context_filter (OTelContextFilter, optional): Custom context filter instance.
            If None, uses default OTelContextFilter().

    Configuration via environment variables:
        - LOG_LEVEL: Logging level (default: INFO)
        - LOG_FILE_PATH: Optional file path for logging (in addition to STDOUT)
        - SERVICE_NAME: Service name for identification (default: unknown-service)

    Behavior:
        - Always logs to STDOUT (for containers/orchestrators)
        - Optionally logs to file if LOG_FILE_PATH is set
        - Captures warnings.warn() messages and routes them through logging
        - Idempotent: safe to call multiple times (only configures once)
    """
    root_logger = logging.getLogger()
    if getattr(root_logger, '_ma_logger_configured', False):
        return

    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    try:
        root_logger.setLevel(log_level)
    except ValueError:
        root_logger.setLevel(logging.INFO)
        warnings.warn(
            f"Invalid LOG_LEVEL '{log_level}', falling back to INFO",
            stacklevel=2,
        )

    # Use provided formatter/filter or create defaults
    if formatter is None:
        formatter = OTelJsonFormatter()
    if context_filter is None:
        context_filter = OTelContextFilter()

    # Configure output streams
    # 1. Always write to STDOUT (for containers/orchestrators)
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(formatter)
    stdout_handler.addFilter(context_filter)
    root_logger.addHandler(stdout_handler)

    # 2. Write to file - only if LOG_FILE_PATH env var is set
    log_file = os.getenv("LOG_FILE_PATH")
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        file_handler.addFilter(context_filter)
        root_logger.addHandler(file_handler)

    # 3. Redirect warnings.warn() to the logging system
    # This causes all warnings.warn() calls to go through the logging pipeline
    # and appear in the same output (STDOUT/file) in JSON format.
    # propagate=False prevents duplicate output (once from py.warnings handlers,
    # once from propagation to root logger which has the same handlers).
    logging.captureWarnings(True)
    warnings_logger = logging.getLogger('py.warnings')
    warnings_logger.propagate = False
    warnings_logger.addHandler(stdout_handler)
    if log_file:
        warnings_logger.addHandler(file_handler)

    root_logger._ma_logger_configured = True

