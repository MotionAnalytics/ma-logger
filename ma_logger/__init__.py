"""
ma-logger: OTel-ready JSON logging for distributed environments

This package provides structured JSON logging with OpenTelemetry semantic conventions
for distributed environments (Kubernetes, Kestra, Microservices).

Key Features:
- Zero external dependencies (uses only Python standard library)
- Automatic context propagation (trace_id, execution_id, task_id)
- JSON formatted logs compatible with OpenTelemetry
- Transparent integration with third-party libraries
- Support for both STDOUT and file logging
- Automatic capture of warnings.warn() messages

Usage:
    from ma_logger import setup_logging
    import logging

    # Initialize once at application startup
    setup_logging()

    # Use standard logging everywhere
    logger = logging.getLogger(__name__)
    logger.info("Application started")
"""

from .setup import setup_logging
from .decorators import trace, monitor_task  # monitor_task is a deprecated alias
from .formatters import OTelJsonFormatter
from .filters import OTelContextFilter

__all__ = [
    "setup_logging",
    "trace",
    "monitor_task",  # deprecated alias – use trace
    "OTelJsonFormatter",
    "OTelContextFilter",
]
