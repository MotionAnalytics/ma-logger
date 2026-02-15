"""
Logging setup and configuration.
"""

import logging
import sys
import os
import warnings

from .formatters import OTelJsonFormatter
from .filters import OTelContextFilter


def setup_logging(log_to_file, formatter=None, context_filter=None):
    """
    Configures the root logger with JSON formatting and context injection.

    Basic usage:
        # STDOUT only (for containers/orchestrators)
        setup_logging(log_to_file=None)

        # STDOUT + file logging (for local development)
        log_file_path = os.getenv("LOG_FILE_PATH")
        setup_logging(log_to_file=log_file_path)

    Custom behavior:
        # Custom formatter
        formatter = OTelJsonFormatter(trace_id_field="traceId")
        setup_logging(log_to_file=None, formatter=formatter)

        # Custom filter
        filter = OTelContextFilter(additional_context={"env": "prod"})
        setup_logging(log_to_file=None, context_filter=filter)

        # Both custom
        setup_logging(log_to_file=None, formatter=my_formatter, context_filter=my_filter)

    Args:
        log_to_file (str | None): File path for logging. If None, logs only to STDOUT.
            If a string path is provided, logs to both STDOUT and the specified file.
            The calling code should read this from environment variables if needed.
        formatter (OTelJsonFormatter, optional): Custom formatter instance.
            If None, uses default OTelJsonFormatter().
        context_filter (OTelContextFilter, optional): Custom context filter instance.
            If None, uses default OTelContextFilter().

    Configuration via environment variables:
        - LOG_LEVEL: Logging level (default: INFO)
        - SERVICE_NAME: Service name for identification (default: unknown-service)

    Behavior:
        - Always logs to STDOUT (for containers/orchestrators)
        - Optionally logs to file if log_to_file parameter is provided
        - Captures warnings.warn() messages and routes them through logging
        - Idempotent: safe to call multiple times (only configures once)
    """
    root_logger = logging.getLogger()
    if getattr(root_logger, "_ma_logger_configured", False):
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

    # 2. Write to file - only if log_to_file parameter is provided
    file_handler = None
    if log_to_file:
        file_handler = logging.FileHandler(log_to_file)
        file_handler.setFormatter(formatter)
        file_handler.addFilter(context_filter)
        root_logger.addHandler(file_handler)

    # 3. Redirect warnings.warn() to the logging system
    # This causes all warnings.warn() calls to go through the logging pipeline
    # and appear in the same output (STDOUT/file) in JSON format.
    # propagate=False prevents duplicate output (once from py.warnings handlers,
    # once from propagation to root logger which has the same handlers).
    logging.captureWarnings(True)
    warnings_logger = logging.getLogger("py.warnings")
    warnings_logger.propagate = False
    warnings_logger.addHandler(stdout_handler)
    if file_handler:
        warnings_logger.addHandler(file_handler)

    root_logger._ma_logger_configured = True
