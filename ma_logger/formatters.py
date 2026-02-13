"""
JSON formatters for OpenTelemetry-compatible logging.
"""

import logging
import json
import os
import datetime


class OTelJsonFormatter(logging.Formatter):
    """
    JSON formatter compatible with OpenTelemetry semantic conventions.

    Default behavior (zero-config):
        Formats log records as JSON with OpenTelemetry field names:
        - timestamp: ISO 8601 format with 'Z' suffix
        - level: Log level (INFO, WARNING, ERROR, etc.)
        - message: The log message
        - service.name: Service name from SERVICE_NAME env var
        - log.logger: Logger name
        - log.origin.file.line: Line number where log was called
        - trace_id, execution_id, task_id: Context IDs (if available)
        - attributes: Additional data passed via extra={'data': {...}}
        - exception.stacktrace: Stack trace (if exception occurred)

    Customization options:
        Args:
            trace_id_field (str): Field name for trace ID (default: "trace_id")
            execution_id_field (str): Field name for execution ID (default: "execution_id")
            task_id_field (str): Field name for task ID (default: "task_id")
            timestamp_format (str): Timestamp format - "iso" or "unix" (default: "iso")
            include_service_name (bool): Include service.name field (default: True)
            include_logger_name (bool): Include log.logger field (default: True)
            include_line_number (bool): Include log.origin.file.line field (default: True)

    Examples:
        # Default usage (recommended)
        formatter = OTelJsonFormatter()

        # Custom field names (e.g., for camelCase)
        formatter = OTelJsonFormatter(
            trace_id_field="traceId",
            execution_id_field="executionId",
            task_id_field="taskId"
        )

        # Unix timestamp instead of ISO format
        formatter = OTelJsonFormatter(timestamp_format="unix")

        # Minimal output (exclude optional fields)
        formatter = OTelJsonFormatter(
            include_service_name=False,
            include_logger_name=False,
            include_line_number=False
        )
    """

    def __init__(
        self,
        trace_id_field="trace_id",
        execution_id_field="execution_id",
        task_id_field="task_id",
        timestamp_format="iso",
        include_service_name=True,
        include_logger_name=True,
        include_line_number=True,
    ):
        super().__init__()
        self.trace_id_field = trace_id_field
        self.execution_id_field = execution_id_field
        self.task_id_field = task_id_field
        self.timestamp_format = timestamp_format
        self.include_service_name = include_service_name
        self.include_logger_name = include_logger_name
        self.include_line_number = include_line_number

    def format(self, record):
        # Build timestamp
        if self.timestamp_format == "unix":
            timestamp = datetime.datetime.utcnow().timestamp()
        else:  # iso (default)
            timestamp = datetime.datetime.utcnow().isoformat() + "Z"

        # Build base log record
        log_record = {
            "timestamp": timestamp,
            "level": record.levelname,
            "message": record.getMessage(),
        }

        # Add optional fields
        if self.include_service_name:
            log_record["service.name"] = os.getenv("SERVICE_NAME", "unknown-service")

        if self.include_logger_name:
            log_record["log.logger"] = record.name

        if self.include_line_number:
            log_record["log.origin.file.line"] = record.lineno

        # Add context IDs (if available from filter)
        if hasattr(record, 'otel_ctx'):
            # Map the context fields to custom field names
            ctx = record.otel_ctx
            if 'trace_id' in ctx:
                log_record[self.trace_id_field] = ctx['trace_id']
            if 'execution_id' in ctx:
                log_record[self.execution_id_field] = ctx['execution_id']
            if 'task_id' in ctx:
                log_record[self.task_id_field] = ctx['task_id']

            # Add any additional context fields
            for key, value in ctx.items():
                if key not in ('trace_id', 'execution_id', 'task_id'):
                    log_record[key] = value

        # Add custom attributes
        if hasattr(record, 'data'):
            log_record["attributes"] = record.data

        # Add exception stack trace
        if record.exc_info:
            log_record["exception.stacktrace"] = self.formatException(record.exc_info)

        return json.dumps(log_record, ensure_ascii=False)

