"""
Unit tests for OTelJsonFormatter.
Tests the formatter in isolation - no setup_logging, no filter, no decorator.
"""

import json
import logging
import os
import pytest

from ma_logger.formatters import OTelJsonFormatter


@pytest.fixture
def make_record():
    """Helper to create a log record with optional extras."""

    def _make(
        msg="test message",
        level=logging.INFO,
        logger_name="test.logger",
        exc_info=None,
        extra=None,
    ):
        logger = logging.getLogger(logger_name)
        record = logger.makeRecord(
            name=logger_name,
            level=level,
            fn="test_file.py",
            lno=42,
            msg=msg,
            args=(),
            exc_info=exc_info,
            extra=extra,
        )
        return record

    return _make


class TestOTelJsonFormatterDefaults:
    """Test default (zero-config) behavior."""

    def test_output_is_valid_json(self, make_record):
        formatter = OTelJsonFormatter()
        output = formatter.format(make_record())
        parsed = json.loads(output)
        assert isinstance(parsed, dict)

    def test_default_fields_present(self, make_record):
        formatter = OTelJsonFormatter()
        parsed = json.loads(formatter.format(make_record()))
        assert "timestamp" in parsed
        assert "level" in parsed
        assert "message" in parsed
        assert "service.name" in parsed
        assert "log.logger" in parsed
        assert "log.origin.file.line" in parsed

    def test_message_content(self, make_record):
        formatter = OTelJsonFormatter()
        parsed = json.loads(formatter.format(make_record(msg="hello world")))
        assert parsed["message"] == "hello world"

    def test_level_names(self, make_record):
        formatter = OTelJsonFormatter()
        for level, name in [
            (logging.DEBUG, "DEBUG"),
            (logging.INFO, "INFO"),
            (logging.WARNING, "WARNING"),
            (logging.ERROR, "ERROR"),
            (logging.CRITICAL, "CRITICAL"),
        ]:
            parsed = json.loads(formatter.format(make_record(level=level)))
            assert parsed["level"] == name

    def test_logger_name(self, make_record):
        formatter = OTelJsonFormatter()
        parsed = json.loads(formatter.format(make_record(logger_name="my.module")))
        assert parsed["log.logger"] == "my.module"

    def test_line_number(self, make_record):
        formatter = OTelJsonFormatter()
        parsed = json.loads(formatter.format(make_record()))
        assert parsed["log.origin.file.line"] == 42

    def test_default_timestamp_is_iso_format(self, make_record):
        formatter = OTelJsonFormatter()
        parsed = json.loads(formatter.format(make_record()))
        ts = parsed["timestamp"]
        assert ts.endswith("Z")
        assert "T" in ts  # ISO 8601 contains 'T' separator

    def test_default_service_name_without_env(self, make_record, monkeypatch):
        monkeypatch.delenv("SERVICE_NAME", raising=False)
        formatter = OTelJsonFormatter()
        parsed = json.loads(formatter.format(make_record()))
        assert parsed["service.name"] == "unknown-service"

    def test_service_name_from_env(self, make_record, monkeypatch):
        monkeypatch.setenv("SERVICE_NAME", "my-service")
        formatter = OTelJsonFormatter()
        parsed = json.loads(formatter.format(make_record()))
        assert parsed["service.name"] == "my-service"

    def test_unicode_message(self, make_record):
        formatter = OTelJsonFormatter()
        parsed = json.loads(formatter.format(make_record(msg="שלום עולם 🌍")))
        assert parsed["message"] == "שלום עולם 🌍"


class TestOTelJsonFormatterOTelContext:
    """Test handling of otel_ctx injected by filter."""

    def test_no_otel_ctx_no_trace_fields(self, make_record):
        formatter = OTelJsonFormatter()
        parsed = json.loads(formatter.format(make_record()))
        assert "trace_id" not in parsed
        assert "execution_id" not in parsed
        assert "task_id" not in parsed

    def test_otel_ctx_fields_added(self, make_record):
        formatter = OTelJsonFormatter()
        record = make_record()
        record.otel_ctx = {
            "trace_id": "abc-123",
            "execution_id": "exec-456",
            "task_id": "task-789",
        }
        parsed = json.loads(formatter.format(record))
        assert parsed["trace_id"] == "abc-123"
        assert parsed["execution_id"] == "exec-456"
        assert parsed["task_id"] == "task-789"

    def test_additional_context_fields_passed_through(self, make_record):
        formatter = OTelJsonFormatter()
        record = make_record()
        record.otel_ctx = {
            "trace_id": "abc",
            "execution_id": "def",
            "task_id": "ghi",
            "pod_name": "my-pod",
        }
        parsed = json.loads(formatter.format(record))
        assert parsed["pod_name"] == "my-pod"


class TestOTelJsonFormatterDataAttributes:
    """Test handling of extra data attributes."""

    def test_data_attribute_added(self, make_record):
        formatter = OTelJsonFormatter()
        record = make_record()
        record.data = {"duration": 1.23, "count": 5}
        parsed = json.loads(formatter.format(record))
        assert parsed["attributes"] == {"duration": 1.23, "count": 5}

    def test_no_data_no_attributes_field(self, make_record):
        formatter = OTelJsonFormatter()
        parsed = json.loads(formatter.format(make_record()))
        assert "attributes" not in parsed


class TestOTelJsonFormatterExceptions:
    """Test exception/stack trace handling."""

    def test_exception_stacktrace_included(self, make_record):
        formatter = OTelJsonFormatter()
        try:
            raise ValueError("something broke")
        except ValueError:
            import sys

            record = make_record(exc_info=sys.exc_info())
        parsed = json.loads(formatter.format(record))
        assert "exception.stacktrace" in parsed
        assert "ValueError" in parsed["exception.stacktrace"]
        assert "something broke" in parsed["exception.stacktrace"]

    def test_no_exception_no_stacktrace_field(self, make_record):
        formatter = OTelJsonFormatter()
        parsed = json.loads(formatter.format(make_record()))
        assert "exception.stacktrace" not in parsed


class TestOTelJsonFormatterCustomConfig:
    """Test custom configuration options."""

    def test_custom_field_names(self, make_record):
        formatter = OTelJsonFormatter(
            trace_id_field="traceId",
            execution_id_field="executionId",
            task_id_field="taskId",
        )
        record = make_record()
        record.otel_ctx = {
            "trace_id": "abc",
            "execution_id": "def",
            "task_id": "ghi",
        }
        parsed = json.loads(formatter.format(record))
        assert parsed["traceId"] == "abc"
        assert parsed["executionId"] == "def"
        assert parsed["taskId"] == "ghi"
        # Original names should NOT be present
        assert "trace_id" not in parsed
        assert "execution_id" not in parsed
        assert "task_id" not in parsed

    def test_unix_timestamp(self, make_record):
        formatter = OTelJsonFormatter(timestamp_format="unix")
        parsed = json.loads(formatter.format(make_record()))
        assert isinstance(parsed["timestamp"], float)

    def test_exclude_service_name(self, make_record):
        formatter = OTelJsonFormatter(include_service_name=False)
        parsed = json.loads(formatter.format(make_record()))
        assert "service.name" not in parsed

    def test_exclude_logger_name(self, make_record):
        formatter = OTelJsonFormatter(include_logger_name=False)
        parsed = json.loads(formatter.format(make_record()))
        assert "log.logger" not in parsed

    def test_exclude_line_number(self, make_record):
        formatter = OTelJsonFormatter(include_line_number=False)
        parsed = json.loads(formatter.format(make_record()))
        assert "log.origin.file.line" not in parsed

    def test_minimal_output(self, make_record):
        """Exclude all optional fields - only timestamp, level, message remain."""
        formatter = OTelJsonFormatter(
            include_service_name=False,
            include_logger_name=False,
            include_line_number=False,
        )
        parsed = json.loads(formatter.format(make_record()))
        assert set(parsed.keys()) == {"timestamp", "level", "message"}

    def test_no_data_no_attributes_field(self, make_record):
        formatter = OTelJsonFormatter()
        parsed = json.loads(formatter.format(make_record()))
        assert "attributes" not in parsed
