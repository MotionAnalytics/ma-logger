"""
End-to-end tests with custom configurations.
Tests setup_logging() with custom formatter and filter instances.
No decorator tests here.
"""

import json
import logging
import os
import tempfile
import pytest

from ma_logger import setup_logging, OTelJsonFormatter, OTelContextFilter


def _close_and_clear_handlers(logger):
    """Close all handlers on a logger and clear the list."""
    for h in logger.handlers[:]:
        h.close()
    logger.handlers.clear()


@pytest.fixture(autouse=True)
def reset_logging():
    """Reset root logger before each test."""
    root = logging.getLogger()
    _close_and_clear_handlers(root)
    root.setLevel(logging.WARNING)
    root._ma_logger_configured = False
    warnings_logger = logging.getLogger("py.warnings")
    _close_and_clear_handlers(warnings_logger)
    logging.captureWarnings(False)
    yield
    _close_and_clear_handlers(root)
    root.setLevel(logging.WARNING)
    root._ma_logger_configured = False
    warnings_logger = logging.getLogger("py.warnings")
    _close_and_clear_handlers(warnings_logger)
    logging.captureWarnings(False)


class TestCustomFormatter:
    """Test setup_logging with custom OTelJsonFormatter."""

    def test_camel_case_field_names(self, capsys, monkeypatch):
        monkeypatch.delenv("LOG_FILE_PATH", raising=False)
        monkeypatch.setenv("TRACING_ID", "trace-abc")
        monkeypatch.setenv("KESTRA_EXECUTION_ID", "exec-def")
        monkeypatch.setenv("KESTRA_TASK_ID", "task-ghi")
        formatter = OTelJsonFormatter(
            trace_id_field="traceId",
            execution_id_field="executionId",
            task_id_field="taskId",
        )
        setup_logging(formatter=formatter)
        logging.getLogger("test").info("camel case test")
        parsed = json.loads(capsys.readouterr().out.strip())
        assert parsed["traceId"] == "trace-abc"
        assert parsed["executionId"] == "exec-def"
        assert parsed["taskId"] == "task-ghi"
        assert "trace_id" not in parsed
        assert "execution_id" not in parsed
        assert "task_id" not in parsed

    def test_unix_timestamp_format(self, capsys, monkeypatch):
        monkeypatch.delenv("LOG_FILE_PATH", raising=False)
        formatter = OTelJsonFormatter(timestamp_format="unix")
        setup_logging(formatter=formatter)
        logging.getLogger("test").info("unix ts")
        parsed = json.loads(capsys.readouterr().out.strip())
        assert isinstance(parsed["timestamp"], float)

    def test_minimal_formatter(self, capsys, monkeypatch):
        monkeypatch.delenv("LOG_FILE_PATH", raising=False)
        formatter = OTelJsonFormatter(
            include_service_name=False,
            include_logger_name=False,
            include_line_number=False,
        )
        setup_logging(formatter=formatter)
        logging.getLogger("test").info("minimal")
        parsed = json.loads(capsys.readouterr().out.strip())
        assert "service.name" not in parsed
        assert "log.logger" not in parsed
        assert "log.origin.file.line" not in parsed
        assert parsed["message"] == "minimal"


class TestCustomFilter:
    """Test setup_logging with custom OTelContextFilter."""

    def test_custom_env_vars(self, capsys, monkeypatch):
        monkeypatch.delenv("LOG_FILE_PATH", raising=False)
        monkeypatch.setenv("MY_TRACE_ID", "custom-trace")
        context_filter = OTelContextFilter(
            trace_id_env_vars=["MY_TRACE_ID"],
        )
        setup_logging(context_filter=context_filter)
        logging.getLogger("test").info("custom env")
        parsed = json.loads(capsys.readouterr().out.strip())
        assert parsed["trace_id"] == "custom-trace"

    def test_additional_static_context(self, capsys, monkeypatch):
        monkeypatch.delenv("LOG_FILE_PATH", raising=False)
        context_filter = OTelContextFilter(
            additional_context={"environment": "staging", "version": "2.0"}
        )
        setup_logging(context_filter=context_filter)
        logging.getLogger("test").info("with static ctx")
        parsed = json.loads(capsys.readouterr().out.strip())
        assert parsed["environment"] == "staging"
        assert parsed["version"] == "2.0"

    def test_additional_env_context(self, capsys, monkeypatch):
        monkeypatch.delenv("LOG_FILE_PATH", raising=False)
        monkeypatch.setenv("K8S_POD", "pod-xyz")
        monkeypatch.setenv("K8S_NS", "production")
        context_filter = OTelContextFilter(
            additional_env_context={
                "pod_name": "K8S_POD",
                "namespace": "K8S_NS",
            }
        )
        setup_logging(context_filter=context_filter)
        logging.getLogger("test").info("k8s context")
        parsed = json.loads(capsys.readouterr().out.strip())
        assert parsed["pod_name"] == "pod-xyz"
        assert parsed["namespace"] == "production"

    def test_custom_fallback_value(self, capsys, monkeypatch):
        monkeypatch.delenv("LOG_FILE_PATH", raising=False)
        for var in ["TRACING_ID", "CORRELATION_ID"]:
            monkeypatch.delenv(var, raising=False)
        context_filter = OTelContextFilter(fallback_value="unknown")
        setup_logging(context_filter=context_filter)
        logging.getLogger("test").info("fallback test")
        parsed = json.loads(capsys.readouterr().out.strip())
        assert parsed["trace_id"] == "unknown"




class TestCustomFormatterAndFilter:
    """Test setup_logging with both custom formatter and filter."""

    def test_combined_custom_config(self, capsys, monkeypatch):
        monkeypatch.delenv("LOG_FILE_PATH", raising=False)
        monkeypatch.setenv("MY_TRACE", "combined-trace")
        monkeypatch.setenv("K8S_POD", "my-pod")
        formatter = OTelJsonFormatter(
            trace_id_field="traceId",
            include_line_number=False,
        )
        context_filter = OTelContextFilter(
            trace_id_env_vars=["MY_TRACE"],
            additional_env_context={"pod": "K8S_POD"},
        )
        setup_logging(formatter=formatter, context_filter=context_filter)
        logging.getLogger("test").info("combined")
        parsed = json.loads(capsys.readouterr().out.strip())
        assert parsed["traceId"] == "combined-trace"
        assert parsed["pod"] == "my-pod"
        assert "log.origin.file.line" not in parsed


class TestCustomConfigWithFile:
    """Test custom configurations with file output."""

    def test_custom_formatter_writes_to_file(self, monkeypatch):
        with tempfile.NamedTemporaryFile(mode="r", suffix=".log", delete=False) as f:
            log_path = f.name
        try:
            monkeypatch.setenv("LOG_FILE_PATH", log_path)
            monkeypatch.setenv("TRACING_ID", "file-trace")
            formatter = OTelJsonFormatter(trace_id_field="traceId")
            setup_logging(formatter=formatter)
            logging.getLogger("test").info("custom to file")
            for h in logging.getLogger().handlers:
                h.flush()
            with open(log_path, "r") as f:
                parsed = json.loads(f.read().strip())
            assert parsed["traceId"] == "file-trace"
            assert parsed["message"] == "custom to file"
        finally:
            _close_and_clear_handlers(logging.getLogger())
            _close_and_clear_handlers(logging.getLogger("py.warnings"))
            os.unlink(log_path)

    def test_custom_filter_writes_to_file(self, monkeypatch):
        with tempfile.NamedTemporaryFile(mode="r", suffix=".log", delete=False) as f:
            log_path = f.name
        try:
            monkeypatch.setenv("LOG_FILE_PATH", log_path)
            context_filter = OTelContextFilter(
                additional_context={"env": "test"}
            )
            setup_logging(context_filter=context_filter)
            logging.getLogger("test").info("filter to file")
            for h in logging.getLogger().handlers:
                h.flush()
            with open(log_path, "r") as f:
                parsed = json.loads(f.read().strip())
            assert parsed["env"] == "test"
            assert parsed["message"] == "filter to file"
        finally:
            _close_and_clear_handlers(logging.getLogger())
            _close_and_clear_handlers(logging.getLogger("py.warnings"))
            os.unlink(log_path)