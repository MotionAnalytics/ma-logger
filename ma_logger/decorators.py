"""
Decorators for tracing and instrumentation (OTel-ready).
"""

import logging
import functools
import inspect
import json
import os
import sys
import time

# Parameters automatically excluded from trace logging
_AUTO_SKIP_PARAMS = {"self", "cls"}


def _resolve_module_name(func):
    """Return the real module name for *func*, even when running as __main__.

    When a script is executed directly (``python splitter/main.py``) or via
    ``python -m splitter.main``, ``func.__module__`` is ``"__main__"`` which
    is useless for tracing.  This helper resolves the actual dotted module
    path so trace logs always show e.g. ``splitter.main.process``.

    Resolution order:
        1. If ``__module__`` is not ``"__main__"`` — use it as-is.
        2. Try ``__spec__.name`` (set when using ``python -m``).
        3. Derive from the file path by matching against ``sys.path``.
        4. Fall back to ``"__main__"`` if nothing else works.
    """
    module = func.__module__
    if module != "__main__":
        return module

    # python -m sets __spec__
    main_mod = sys.modules.get("__main__")
    if main_mod and getattr(main_mod, "__spec__", None) and main_mod.__spec__.name:
        return main_mod.__spec__.name

    # Derive from file path
    try:
        filepath = os.path.abspath(inspect.getfile(func))
    except (TypeError, OSError):
        return module

    # Match against sys.path entries (longest first → most specific)
    for path_entry in sorted(sys.path, key=len, reverse=True):
        path_entry = os.path.abspath(path_entry)
        if not path_entry:
            continue
        if filepath.startswith(path_entry + os.sep):
            rel = os.path.relpath(filepath, path_entry)
            rel = os.path.splitext(rel)[0]  # drop .py
            parts = rel.split(os.sep)
            if parts[-1] == "__init__":
                parts = parts[:-1]
            if parts:
                return ".".join(parts)

    return module


def _safe_serialize_value(value):
    """Return a JSON-serializable representation of *value*.

    Primitives and simple containers (list, dict) that survive
    ``json.dumps`` are returned as-is.  Anything else is replaced
    with a short placeholder so the log line never explodes.
    """
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError, OverflowError):
        return f"<{type(value).__name__}>"


def _collect_params(func, args, kwargs, ignore_params=None):
    """Build a serializable dict of the function's bound arguments."""
    ignore = _AUTO_SKIP_PARAMS | set(ignore_params or [])
    try:
        sig = inspect.signature(func)
        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()
        return {
            name: _safe_serialize_value(val)
            for name, val in bound.arguments.items()
            if name not in ignore
        }
    except (TypeError, ValueError):
        # Fallback – e.g. built-in functions without inspectable sig
        return {}


def trace(_func=None, *, ignore_params=None):
    """Decorator for tracing function execution (OTel-ready).

    Can be used with or without arguments::

        @trace
        def simple():
            ...

        @trace(ignore_params=["password", "token"])
        def login(user, password):
            ...

    Behavior:
        - Captures function parameters (auto-skips ``self`` / ``cls``)
        - Logs success with execution duration and captured params
        - Logs failure with full stack trace
        - Non-JSON-serializable values are replaced with ``<ClassName>``
        - Re-raises exceptions (never suppresses them)

    Args:
        ignore_params: Optional list of parameter names to exclude from
            trace logging (e.g. secrets, large payloads).
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            real_module = _resolve_module_name(func)
            logger = logging.getLogger(real_module)
            qualified_name = f"{real_module}.{func.__qualname__}"
            params = _collect_params(func, args, kwargs, ignore_params)
            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                duration = time.perf_counter() - start
                logger.info(
                    f"trace complete: {qualified_name} [success]",
                    extra={
                        "trace_data": {
                            "function": qualified_name,
                            "result": "success",
                            "duration": duration,
                            "params": params,
                        }
                    },
                )
                return result
            except Exception:
                duration = time.perf_counter() - start
                logger.error(
                    f"trace complete: {qualified_name} [error]",
                    extra={
                        "trace_data": {
                            "function": qualified_name,
                            "result": "error",
                            "duration": duration,
                            "params": params,
                        }
                    },
                    exc_info=True,
                )
                raise

        return wrapper

    if _func is not None:
        # Called as @trace without parentheses
        return decorator(_func)
    # Called as @trace(...) with parentheses
    return decorator


# Backward-compatible alias (deprecated – use ``trace`` instead)
monitor_task = trace
