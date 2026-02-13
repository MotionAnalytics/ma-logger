"""
Unit tests for OTelContextFilter.
Tests the filter in isolation - no setup_logging, no formatter, no decorator.
"""

import logging
import pytest

from ma_logger.filters import OTelContextFilter


@pytest.fixture
def make_record():
    """Helper to create a bare log record."""

    def _make():
        logger = logging.getLogger("test.filter")
        return logger.makeRecord(
            name="test.filter",
            level=logging.INFO,
            fn="test.py",
            lno=1,
            msg="test",
            args=(),
            exc_info=None,
        )

    return _make


class TestOTelContextFilterDefaults:
    """Test default (zero-config) behavior."""

    def test_filter_returns_true(self, make_record):
        f = OTelContextFilter()
        assert f.filter(make_record()) is True

    def test_otel_ctx_injected(self, make_record):
        f = OTelContextFilter()
        record = make_record()
        f.filter(record)
        assert hasattr(record, "otel_ctx")
        assert "trace_id" in record.otel_ctx
        assert "execution_id" in record.otel_ctx
        assert "task_id" in record.otel_ctx

    def test_fallback_values_when_no_env(self, make_record, monkeypatch):
        for var in [
            "TRACING_ID",
            "CORRELATION_ID",
            "KESTRA_EXECUTION_ID",
            "EXECUTION_ID",
            "KESTRA_TASK_ID",
            "TASK_ID",
        ]:
            monkeypatch.delenv(var, raising=False)
        f = OTelContextFilter()
        record = make_record()
        f.filter(record)
        assert record.otel_ctx["trace_id"] == "N/A"
        assert record.otel_ctx["execution_id"] == "N/A"
        assert record.otel_ctx["task_id"] == "N/A"


class TestOTelContextFilterEnvVars:
    """Test environment variable extraction with default env var names."""

    def test_trace_id_from_tracing_id(self, make_record, monkeypatch):
        monkeypatch.setenv("TRACING_ID", "trace-abc")
        monkeypatch.delenv("CORRELATION_ID", raising=False)
        f = OTelContextFilter()
        record = make_record()
        f.filter(record)
        assert record.otel_ctx["trace_id"] == "trace-abc"

    def test_trace_id_from_correlation_id_fallback(self, make_record, monkeypatch):
        monkeypatch.delenv("TRACING_ID", raising=False)
        monkeypatch.setenv("CORRELATION_ID", "corr-xyz")
        f = OTelContextFilter()
        record = make_record()
        f.filter(record)
        assert record.otel_ctx["trace_id"] == "corr-xyz"

    def test_tracing_id_takes_priority_over_correlation_id(self, make_record, monkeypatch):
        monkeypatch.setenv("TRACING_ID", "trace-first")
        monkeypatch.setenv("CORRELATION_ID", "corr-second")
        f = OTelContextFilter()
        record = make_record()
        f.filter(record)
        assert record.otel_ctx["trace_id"] == "trace-first"

    def test_execution_id_from_kestra(self, make_record, monkeypatch):
        monkeypatch.setenv("KESTRA_EXECUTION_ID", "kestra-exec-1")
        monkeypatch.delenv("EXECUTION_ID", raising=False)
        f = OTelContextFilter()
        record = make_record()
        f.filter(record)
        assert record.otel_ctx["execution_id"] == "kestra-exec-1"

    def test_execution_id_fallback(self, make_record, monkeypatch):
        monkeypatch.delenv("KESTRA_EXECUTION_ID", raising=False)
        monkeypatch.setenv("EXECUTION_ID", "exec-fallback")
        f = OTelContextFilter()
        record = make_record()
        f.filter(record)
        assert record.otel_ctx["execution_id"] == "exec-fallback"

    def test_task_id_from_kestra(self, make_record, monkeypatch):
        monkeypatch.setenv("KESTRA_TASK_ID", "kestra-task-1")
        monkeypatch.delenv("TASK_ID", raising=False)
        f = OTelContextFilter()
        record = make_record()
        f.filter(record)
        assert record.otel_ctx["task_id"] == "kestra-task-1"

    def test_task_id_fallback(self, make_record, monkeypatch):
        monkeypatch.delenv("KESTRA_TASK_ID", raising=False)
        monkeypatch.setenv("TASK_ID", "task-fallback")
        f = OTelContextFilter()
        record = make_record()
        f.filter(record)
        assert record.otel_ctx["task_id"] == "task-fallback"


class TestOTelContextFilterCustomConfig:
    """Test custom configuration options."""

    def test_custom_env_vars(self, make_record, monkeypatch):
        monkeypatch.setenv("MY_TRACE", "custom-trace")
        f = OTelContextFilter(trace_id_env_vars=["MY_TRACE"])
        record = make_record()
        f.filter(record)
        assert record.otel_ctx["trace_id"] == "custom-trace"

    def test_custom_fallback_value(self, make_record, monkeypatch):
        for var in ["TRACING_ID", "CORRELATION_ID"]:
            monkeypatch.delenv(var, raising=False)
        f = OTelContextFilter(fallback_value="unknown")
        record = make_record()
        f.filter(record)
        assert record.otel_ctx["trace_id"] == "unknown"

    def test_additional_static_context(self, make_record):
        f = OTelContextFilter(additional_context={"environment": "prod", "region": "us-east-1"})
        record = make_record()
        f.filter(record)
        assert record.otel_ctx["environment"] == "prod"
        assert record.otel_ctx["region"] == "us-east-1"

    def test_additional_env_context(self, make_record, monkeypatch):
        monkeypatch.setenv("POD_NAME", "my-pod-abc")
        f = OTelContextFilter(additional_env_context={"pod_name": "POD_NAME"})
        record = make_record()
        f.filter(record)
        assert record.otel_ctx["pod_name"] == "my-pod-abc"

    def test_additional_env_context_missing_var_not_added(self, make_record, monkeypatch):
        monkeypatch.delenv("POD_NAME", raising=False)
        f = OTelContextFilter(additional_env_context={"pod_name": "POD_NAME"})
        record = make_record()
        f.filter(record)
        assert "pod_name" not in record.otel_ctx
