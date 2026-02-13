"""
Decorators for tracing and instrumentation (OTel-ready).
"""

import logging
import functools
import inspect
import json
import time

# Parameters automatically excluded from trace logging
_AUTO_SKIP_PARAMS = {"self", "cls"}


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
            logger = logging.getLogger(func.__module__)
            params = _collect_params(func, args, kwargs, ignore_params)
            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                duration = time.perf_counter() - start
                logger.info(
                    f"Task {func.__name__} success",
                    extra={"data": {"duration": duration, "params": params}},
                )
                return result
            except Exception:
                duration = time.perf_counter() - start
                logger.error(
                    f"Task {func.__name__} failed",
                    extra={"data": {"duration": duration, "params": params}},
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

