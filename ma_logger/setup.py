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
    מגדירה את ה-Root Logger וקובעת לאן יוזרמו הלוגים

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

    root_logger.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())

    # Use provided formatter/filter or create defaults
    if formatter is None:
        formatter = OTelJsonFormatter()
    if context_filter is None:
        context_filter = OTelContextFilter()

    # הגדרת הזרמים (Streams)
    # 1. תמיד כותב ל-STDOUT (עבור קונטיינרים/אורקסטרטורים)
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(formatter)
    stdout_handler.addFilter(context_filter)
    root_logger.addHandler(stdout_handler)

    # 2. כתיבה לקובץ - מופעל רק אם קיים משתנה סביבה LOG_FILE_PATH
    log_file = os.getenv("LOG_FILE_PATH")
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        file_handler.addFilter(context_filter)
        root_logger.addHandler(file_handler)

    # 3. הפניית warnings.warn() ללוגים
    # זה גורם לכל warnings.warn() להיכתב דרך מערכת הלוגים
    # ולהופיע באותו output (STDOUT/file) עם פורמט JSON
    logging.captureWarnings(True)
    warnings_logger = logging.getLogger('py.warnings')
    warnings_logger.addHandler(stdout_handler)
    if log_file:
        warnings_logger.addHandler(file_handler)

    root_logger._ma_logger_configured = True

