"""
Integration tests for setup_logging() with default configuration.
Tests the full pipeline: setup -> log -> verify output (stdout and file).
No custom configurations, no decorator.
"""

import json
import logging
import os
import tempfile
import warnings
import pytest

from ma_logger import setup_logging


def _close_and_clear_handlers(logger):
    """Close all handlers on a logger and clear the list."""
    for h in logger.handlers[:]:
        h.close()
    logger.handlers.clear()


@pytest.fixture(autouse=True)
def reset_logging():
    """Reset root logger before each test to allow fresh setup."""
    root = logging.getLogger()
    _close_and_clear_handlers(root)
    root.setLevel(logging.WARNING)  # Reset to default
    root._ma_logger_configured = False
    # Also reset warnings logger
    warnings_logger = logging.getLogger("py.warnings")
    _close_and_clear_handlers(warnings_logger)
    logging.captureWarnings(False)
    yield
    # Cleanup after test
    _close_and_clear_handlers(root)
    root.setLevel(logging.WARNING)
    root._ma_logger_configured = False
    warnings_logger = logging.getLogger("py.warnings")
    _close_and_clear_handlers(warnings_logger)
    logging.captureWarnings(False)


class TestSetupLoggingBasic:
    """Test basic setup behavior."""

    def test_setup_adds_handlers(self):
        setup_logging()
        root = logging.getLogger()
        assert len(root.handlers) > 0

    def test_setup_is_idempotent(self):
        setup_logging()
        handler_count = len(logging.getLogger().handlers)
        setup_logging()  # Second call should be no-op
        assert len(logging.getLogger().handlers) == handler_count

    def test_default_log_level_is_info(self, monkeypatch):
        monkeypatch.delenv("LOG_LEVEL", raising=False)
        setup_logging()
        assert logging.getLogger().level == logging.INFO

    def test_custom_log_level_from_env(self, monkeypatch):
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        setup_logging()
        assert logging.getLogger().level == logging.DEBUG

    def test_log_level_case_insensitive(self, monkeypatch):
        monkeypatch.setenv("LOG_LEVEL", "warning")
        setup_logging()
        assert logging.getLogger().level == logging.WARNING

    def test_invalid_log_level_falls_back_to_info(self, monkeypatch):
        monkeypatch.setenv("LOG_LEVEL", "INVALID_LEVEL")
        with pytest.warns(UserWarning, match="Invalid LOG_LEVEL"):
            setup_logging()
        assert logging.getLogger().level == logging.INFO


class TestSetupLoggingStdout:
    """Test logging to stdout (default behavior)."""

    def test_log_to_stdout_json(self, capsys, monkeypatch):
        monkeypatch.delenv("LOG_FILE_PATH", raising=False)
        setup_logging()
        logger = logging.getLogger("test.stdout")
        logger.info("hello stdout")
        captured = capsys.readouterr()
        parsed = json.loads(captured.out.strip())
        assert parsed["message"] == "hello stdout"
        assert parsed["level"] == "INFO"

    def test_stdout_contains_otel_context(self, capsys, monkeypatch):
        monkeypatch.delenv("LOG_FILE_PATH", raising=False)
        monkeypatch.setenv("TRACING_ID", "trace-123")
        setup_logging()
        logger = logging.getLogger("test.ctx")
        logger.info("with context")
        parsed = json.loads(capsys.readouterr().out.strip())
        assert parsed["message"] == "with context"
        assert parsed["level"] == "INFO"
        assert parsed["trace_id"] == "trace-123"

    def test_stdout_multiple_log_levels(self, capsys, monkeypatch):
        monkeypatch.delenv("LOG_FILE_PATH", raising=False)
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        setup_logging()
        logger = logging.getLogger("test.levels")
        logger.debug("debug msg")
        logger.info("info msg")
        logger.warning("warn msg")
        lines = capsys.readouterr().out.strip().split("\n")
        assert len(lines) == 3
        assert json.loads(lines[0])["level"] == "DEBUG"
        assert json.loads(lines[1])["level"] == "INFO"
        assert json.loads(lines[2])["level"] == "WARNING"

    def test_debug_not_shown_at_info_level(self, capsys, monkeypatch):
        monkeypatch.delenv("LOG_FILE_PATH", raising=False)
        monkeypatch.delenv("LOG_LEVEL", raising=False)
        setup_logging()
        logger = logging.getLogger("test.filter_level")
        logger.debug("should not appear")
        logger.info("should appear")
        captured = capsys.readouterr().out.strip()
        lines = [l for l in captured.split("\n") if l]
        assert len(lines) == 1
        assert json.loads(lines[0])["message"] == "should appear"


class TestSetupLoggingFile:
    """Test logging to file via LOG_FILE_PATH env var."""

    def test_log_to_file_when_env_set(self, monkeypatch):
        with tempfile.NamedTemporaryFile(mode="r", suffix=".log", delete=False) as f:
            log_path = f.name
        try:
            monkeypatch.setenv("LOG_FILE_PATH", log_path)
            setup_logging()
            logger = logging.getLogger("test.file")
            logger.info("file message")
            # Flush handlers
            for h in logging.getLogger().handlers:
                h.flush()
            with open(log_path, "r") as f:
                content = f.read().strip()
            parsed = json.loads(content)
            assert parsed["message"] == "file message"
        finally:
            _close_and_clear_handlers(logging.getLogger())
            _close_and_clear_handlers(logging.getLogger("py.warnings"))
            os.unlink(log_path)

    def test_log_to_file_when_env_set_multiple_lines(self, monkeypatch):
        with tempfile.NamedTemporaryFile(mode="r", suffix=".log", delete=False) as f:
            log_path = f.name
        try:
            monkeypatch.setenv("LOG_FILE_PATH", log_path)
            monkeypatch.setenv("LOG_LEVEL", "DEBUG")
            setup_logging()
            logger = logging.getLogger("test.multiline")
            logger.debug("debug message")
            logger.info("info message")
            logger.warning("warning message")
            logger.error("error message")
            # Flush handlers
            for h in logging.getLogger().handlers:
                h.flush()
            with open(log_path, "r") as f:
                lines = [json.loads(line) for line in f.read().strip().splitlines()]
            assert len(lines) == 4
            assert lines[0]["level"] == "DEBUG"
            assert lines[0]["message"] == "debug message"
            assert lines[1]["level"] == "INFO"
            assert lines[1]["message"] == "info message"
            assert lines[2]["level"] == "WARNING"
            assert lines[2]["message"] == "warning message"
            assert lines[3]["level"] == "ERROR"
            assert lines[3]["message"] == "error message"
        finally:
            _close_and_clear_handlers(logging.getLogger())
            _close_and_clear_handlers(logging.getLogger("py.warnings"))
            os.unlink(log_path)

    def test_no_file_when_env_not_set(self, monkeypatch):
        monkeypatch.delenv("LOG_FILE_PATH", raising=False)
        setup_logging()
        root = logging.getLogger()
        file_handlers = [h for h in root.handlers if isinstance(h, logging.FileHandler)]
        assert len(file_handlers) == 0

    def test_file_and_stdout_both_receive_logs(self, capsys, monkeypatch):
        with tempfile.NamedTemporaryFile(mode="r", suffix=".log", delete=False) as f:
            log_path = f.name
        try:
            monkeypatch.setenv("LOG_FILE_PATH", log_path)
            setup_logging()
            logger = logging.getLogger("test.both")
            logger.info("dual output")
            for h in logging.getLogger().handlers:
                h.flush()
            # Check stdout
            stdout_parsed = json.loads(capsys.readouterr().out.strip())
            assert stdout_parsed["message"] == "dual output"
            # Check file
            with open(log_path, "r") as f:
                file_parsed = json.loads(f.read().strip())
            assert file_parsed["message"] == "dual output"
        finally:
            _close_and_clear_handlers(logging.getLogger())
            _close_and_clear_handlers(logging.getLogger("py.warnings"))
            os.unlink(log_path)


class TestSetupLoggingWarnings:
    """Test that warnings.warn() is captured by the logging system."""

    def test_warning_captured_to_stdout(self, capsys, monkeypatch):
        monkeypatch.delenv("LOG_FILE_PATH", raising=False)
        setup_logging()
        warnings.warn("this is a warning")
        captured = capsys.readouterr().out.strip()
        # warnings.warn may produce output - find the warning line
        lines = [l for l in captured.split("\n") if l.strip()]
        warning_lines = [l for l in lines if "this is a warning" in l]
        assert len(warning_lines) >= 1
        parsed = json.loads(warning_lines[0])
        assert parsed["level"] == "WARNING"

    def test_warning_captured_to_file(self, monkeypatch):
        with tempfile.NamedTemporaryFile(mode="r", suffix=".log", delete=False) as f:
            log_path = f.name
        try:
            monkeypatch.setenv("LOG_FILE_PATH", log_path)
            setup_logging()
            warnings.warn("file warning")
            for h in logging.getLogger().handlers:
                h.flush()
            for h in logging.getLogger("py.warnings").handlers:
                h.flush()
            with open(log_path, "r") as f:
                content = f.read().strip()
            lines = [l for l in content.split("\n") if l.strip()]
            warning_lines = [l for l in lines if "file warning" in l]
            assert len(warning_lines) >= 1
            parsed = json.loads(warning_lines[0])
            assert parsed["level"] == "WARNING"
        finally:
            _close_and_clear_handlers(logging.getLogger())
            _close_and_clear_handlers(logging.getLogger("py.warnings"))
            os.unlink(log_path)


class TestSetupLoggingExceptionOutput:
    """Test that exceptions are properly formatted in output."""

    def test_exception_in_stdout(self, capsys, monkeypatch):
        monkeypatch.delenv("LOG_FILE_PATH", raising=False)
        setup_logging()
        logger = logging.getLogger("test.exc")
        try:
            raise RuntimeError("boom")
        except RuntimeError:
            logger.error("something failed", exc_info=True)
        parsed = json.loads(capsys.readouterr().out.strip())
        assert parsed["level"] == "ERROR"
        assert "exception.stacktrace" in parsed
        assert "RuntimeError" in parsed["exception.stacktrace"]
