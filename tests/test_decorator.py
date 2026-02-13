"""
Tests for trace decorator with default setup_logging().
Tests success/failure scenarios, duration tracking, param capture, stdout and file output.
"""

import json
import logging
import os
import tempfile
import time
import pytest

from ma_logger import setup_logging, trace, monitor_task


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


class TestTraceSuccess:
    """Test decorator on successful function execution."""

    def test_success_log_message(self, capsys, monkeypatch):
        monkeypatch.delenv("LOG_FILE_PATH", raising=False)
        setup_logging()

        @trace
        def my_task():
            return "done"

        result = my_task()
        assert result == "done"
        parsed = json.loads(capsys.readouterr().out.strip())
        assert parsed["level"] == "INFO"
        assert "my_task" in parsed["message"]
        assert "success" in parsed["message"]

    def test_success_includes_duration(self, capsys, monkeypatch):
        monkeypatch.delenv("LOG_FILE_PATH", raising=False)
        setup_logging()

        @trace
        def slow_task():
            time.sleep(0.05)
            return 42

        slow_task()
        parsed = json.loads(capsys.readouterr().out.strip())
        assert "attributes" in parsed
        assert "duration" in parsed["attributes"]
        assert parsed["attributes"]["duration"] >= 0.04

    def test_return_value_preserved(self, capsys, monkeypatch):
        monkeypatch.delenv("LOG_FILE_PATH", raising=False)
        setup_logging()

        @trace
        def returns_dict():
            return {"key": "value"}

        result = returns_dict()
        assert result == {"key": "value"}

    def test_function_name_preserved(self):
        @trace
        def original_name():
            pass

        assert original_name.__name__ == "original_name"

    def test_function_with_args(self, capsys, monkeypatch):
        monkeypatch.delenv("LOG_FILE_PATH", raising=False)
        setup_logging()

        @trace
        def add(a, b):
            return a + b

        result = add(3, 4)
        assert result == 7
        parsed = json.loads(capsys.readouterr().out.strip())
        assert "add" in parsed["message"]
        assert "success" in parsed["message"]

    def test_function_with_kwargs(self, capsys, monkeypatch):
        monkeypatch.delenv("LOG_FILE_PATH", raising=False)
        setup_logging()

        @trace
        def greet(name="world"):
            return f"hello {name}"

        result = greet(name="python")
        assert result == "hello python"


class TestTraceFailure:
    """Test decorator on function failure."""

    def test_failure_log_message(self, capsys, monkeypatch):
        monkeypatch.delenv("LOG_FILE_PATH", raising=False)
        setup_logging()

        @trace
        def failing_task():
            raise ValueError("something broke")

        with pytest.raises(ValueError, match="something broke"):
            failing_task()
        parsed = json.loads(capsys.readouterr().out.strip())
        assert parsed["level"] == "ERROR"
        assert "failing_task" in parsed["message"]
        assert "failed" in parsed["message"]

    def test_failure_includes_stacktrace(self, capsys, monkeypatch):
        monkeypatch.delenv("LOG_FILE_PATH", raising=False)
        setup_logging()

        @trace
        def error_task():
            raise RuntimeError("runtime error")

        with pytest.raises(RuntimeError):
            error_task()
        parsed = json.loads(capsys.readouterr().out.strip())
        assert "exception.stacktrace" in parsed
        assert "RuntimeError" in parsed["exception.stacktrace"]
        assert "runtime error" in parsed["exception.stacktrace"]

    def test_exception_is_reraised(self, capsys, monkeypatch):
        monkeypatch.delenv("LOG_FILE_PATH", raising=False)
        setup_logging()

        @trace
        def raises():
            raise TypeError("type error")

        with pytest.raises(TypeError, match="type error"):
            raises()

    def test_failure_includes_duration_and_params(self, capsys, monkeypatch):
        monkeypatch.delenv("LOG_FILE_PATH", raising=False)
        setup_logging()

        @trace
        def fail_with_args(x, y):
            raise ValueError("boom")

        with pytest.raises(ValueError):
            fail_with_args(1, 2)
        parsed = json.loads(capsys.readouterr().out.strip())
        assert "duration" in parsed["attributes"]
        assert parsed["attributes"]["params"] == {"x": 1, "y": 2}


class TestTraceWithFile:
    """Test decorator output to file (with and without LOG_FILE_PATH)."""

    def test_no_file_output_without_env(self, capsys, monkeypatch):
        monkeypatch.delenv("LOG_FILE_PATH", raising=False)
        setup_logging()

        @trace
        def simple():
            return 1

        simple()
        root = logging.getLogger()
        file_handlers = [h for h in root.handlers if isinstance(h, logging.FileHandler)]
        assert len(file_handlers) == 0
        # But stdout should still have the log
        parsed = json.loads(capsys.readouterr().out.strip())
        assert "simple" in parsed["message"]

    def test_success_logged_to_file(self, monkeypatch):
        with tempfile.NamedTemporaryFile(mode="r", suffix=".log", delete=False) as f:
            log_path = f.name
        try:
            monkeypatch.setenv("LOG_FILE_PATH", log_path)
            setup_logging()

            @trace
            def file_task():
                return "result"

            file_task()
            for h in logging.getLogger().handlers:
                h.flush()
            with open(log_path, "r") as f:
                parsed = json.loads(f.read().strip())
            assert parsed["level"] == "INFO"
            assert "file_task" in parsed["message"]
            assert "success" in parsed["message"]
            assert "attributes" in parsed
            assert "duration" in parsed["attributes"]
        finally:
            _close_and_clear_handlers(logging.getLogger())
            _close_and_clear_handlers(logging.getLogger("py.warnings"))
            os.unlink(log_path)

    def test_failure_logged_to_file(self, monkeypatch):
        with tempfile.NamedTemporaryFile(mode="r", suffix=".log", delete=False) as f:
            log_path = f.name
        try:
            monkeypatch.setenv("LOG_FILE_PATH", log_path)
            setup_logging()

            @trace
            def file_fail():
                raise ValueError("file error")

            with pytest.raises(ValueError):
                file_fail()
            for h in logging.getLogger().handlers:
                h.flush()
            with open(log_path, "r") as f:
                parsed = json.loads(f.read().strip())
            assert parsed["level"] == "ERROR"
            assert "file_fail" in parsed["message"]
            assert "exception.stacktrace" in parsed
            assert "ValueError" in parsed["exception.stacktrace"]
        finally:
            _close_and_clear_handlers(logging.getLogger())
            _close_and_clear_handlers(logging.getLogger("py.warnings"))
            os.unlink(log_path)

    def test_success_to_both_stdout_and_file(self, capsys, monkeypatch):
        with tempfile.NamedTemporaryFile(mode="r", suffix=".log", delete=False) as f:
            log_path = f.name
        try:
            monkeypatch.setenv("LOG_FILE_PATH", log_path)
            setup_logging()

            @trace
            def dual_task():
                return "dual"

            dual_task()
            for h in logging.getLogger().handlers:
                h.flush()
            # Check stdout
            stdout_parsed = json.loads(capsys.readouterr().out.strip())
            assert stdout_parsed["message"] == "Task dual_task success"
            # Check file
            with open(log_path, "r") as f:
                file_parsed = json.loads(f.read().strip())
            assert file_parsed["message"] == "Task dual_task success"
            # Both should have same content
            assert stdout_parsed["level"] == file_parsed["level"]
            assert stdout_parsed["message"] == file_parsed["message"]
        finally:
            _close_and_clear_handlers(logging.getLogger())
            _close_and_clear_handlers(logging.getLogger("py.warnings"))
            os.unlink(log_path)


class TestTraceParamCapture:
    """Test that @trace captures function parameters."""

    def test_captures_positional_args(self, capsys, monkeypatch):
        monkeypatch.delenv("LOG_FILE_PATH", raising=False)
        setup_logging()

        @trace
        def add(a, b):
            return a + b

        add(3, 4)
        parsed = json.loads(capsys.readouterr().out.strip())
        assert parsed["attributes"]["params"] == {"a": 3, "b": 4}

    def test_captures_kwargs(self, capsys, monkeypatch):
        monkeypatch.delenv("LOG_FILE_PATH", raising=False)
        setup_logging()

        @trace
        def greet(name="world"):
            return f"hello {name}"

        greet(name="python")
        parsed = json.loads(capsys.readouterr().out.strip())
        assert parsed["attributes"]["params"] == {"name": "python"}

    def test_captures_default_values(self, capsys, monkeypatch):
        monkeypatch.delenv("LOG_FILE_PATH", raising=False)
        setup_logging()

        @trace
        def greet(name="world"):
            return f"hello {name}"

        greet()
        parsed = json.loads(capsys.readouterr().out.strip())
        assert parsed["attributes"]["params"] == {"name": "world"}

    def test_no_params_function(self, capsys, monkeypatch):
        monkeypatch.delenv("LOG_FILE_PATH", raising=False)
        setup_logging()

        @trace
        def noop():
            return 1

        noop()
        parsed = json.loads(capsys.readouterr().out.strip())
        assert parsed["attributes"]["params"] == {}

    def test_mixed_args_and_kwargs(self, capsys, monkeypatch):
        monkeypatch.delenv("LOG_FILE_PATH", raising=False)
        setup_logging()

        @trace
        def func(a, b, c="default"):
            return a + b

        func(1, 2, c="custom")
        parsed = json.loads(capsys.readouterr().out.strip())
        assert parsed["attributes"]["params"] == {"a": 1, "b": 2, "c": "custom"}

    def test_skips_self_on_method(self, capsys, monkeypatch):
        monkeypatch.delenv("LOG_FILE_PATH", raising=False)
        setup_logging()

        class MyClass:
            @trace
            def method(self, x):
                return x * 2

        obj = MyClass()
        obj.method(5)
        parsed = json.loads(capsys.readouterr().out.strip())
        # 'self' should NOT appear in params
        assert "self" not in parsed["attributes"]["params"]
        assert parsed["attributes"]["params"] == {"x": 5}

    def test_skips_cls_on_classmethod(self, capsys, monkeypatch):
        monkeypatch.delenv("LOG_FILE_PATH", raising=False)
        setup_logging()

        class MyClass:
            @classmethod
            @trace
            def class_method(cls, x):
                return x

        MyClass.class_method(10)
        parsed = json.loads(capsys.readouterr().out.strip())
        assert "cls" not in parsed["attributes"]["params"]
        assert parsed["attributes"]["params"] == {"x": 10}


class TestTraceIgnoreParams:
    """Test ignore_params to exclude specific parameters from logging."""

    def test_ignore_single_param(self, capsys, monkeypatch):
        monkeypatch.delenv("LOG_FILE_PATH", raising=False)
        setup_logging()

        @trace(ignore_params=["password"])
        def login(user, password):
            return True

        login("admin", "secret123")
        parsed = json.loads(capsys.readouterr().out.strip())
        assert parsed["attributes"]["params"] == {"user": "admin"}
        assert "password" not in parsed["attributes"]["params"]

    def test_ignore_multiple_params(self, capsys, monkeypatch):
        monkeypatch.delenv("LOG_FILE_PATH", raising=False)
        setup_logging()

        @trace(ignore_params=["password", "token"])
        def auth(user, password, token):
            return True

        auth("admin", "secret", "tok123")
        parsed = json.loads(capsys.readouterr().out.strip())
        assert parsed["attributes"]["params"] == {"user": "admin"}

    def test_ignore_nonexistent_param_is_harmless(self, capsys, monkeypatch):
        monkeypatch.delenv("LOG_FILE_PATH", raising=False)
        setup_logging()

        @trace(ignore_params=["nonexistent"])
        def func(a):
            return a

        func(42)
        parsed = json.loads(capsys.readouterr().out.strip())
        assert parsed["attributes"]["params"] == {"a": 42}


class TestTraceNonSerializable:
    """Test that non-JSON-serializable values are handled gracefully."""

    def test_non_serializable_replaced_with_classname(self, capsys, monkeypatch):
        monkeypatch.delenv("LOG_FILE_PATH", raising=False)
        setup_logging()

        class HeavyObject:
            pass

        @trace
        def process(data, label):
            return label

        process(HeavyObject(), "test")
        parsed = json.loads(capsys.readouterr().out.strip())
        assert parsed["attributes"]["params"]["data"] == "<HeavyObject>"
        assert parsed["attributes"]["params"]["label"] == "test"

    def test_bytes_replaced(self, capsys, monkeypatch):
        monkeypatch.delenv("LOG_FILE_PATH", raising=False)
        setup_logging()

        @trace
        def upload(payload, name):
            return name

        upload(b"\x00\x01\x02", "file.bin")
        parsed = json.loads(capsys.readouterr().out.strip())
        assert parsed["attributes"]["params"]["payload"] == "<bytes>"
        assert parsed["attributes"]["params"]["name"] == "file.bin"

    def test_serializable_types_pass_through(self, capsys, monkeypatch):
        monkeypatch.delenv("LOG_FILE_PATH", raising=False)
        setup_logging()

        @trace
        def func(a, b, c, d, e):
            pass

        func(42, 3.14, "hello", [1, 2], {"k": "v"})
        parsed = json.loads(capsys.readouterr().out.strip())
        params = parsed["attributes"]["params"]
        assert params == {"a": 42, "b": 3.14, "c": "hello", "d": [1, 2], "e": {"k": "v"}}


class TestBackwardCompatAlias:
    """Test that monitor_task still works as a deprecated alias."""

    def test_monitor_task_is_same_as_trace(self):
        assert monitor_task is trace

    def test_monitor_task_still_works(self, capsys, monkeypatch):
        monkeypatch.delenv("LOG_FILE_PATH", raising=False)
        setup_logging()

        @monitor_task
        def old_style():
            return "ok"

        result = old_style()
        assert result == "ok"
        parsed = json.loads(capsys.readouterr().out.strip())
        assert "old_style" in parsed["message"]
        assert "success" in parsed["message"]
