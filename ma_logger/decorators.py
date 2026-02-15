"""
Decorators for tracing and instrumentation (OTel-ready).
"""

import logging
import functools
import time

from .utils import resolve_module_name, collect_params

# Parameters automatically excluded from trace logging
_AUTO_SKIP_PARAMS = {"self", "cls"}


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
            real_module = resolve_module_name(func)
            logger = logging.getLogger(real_module)
            qualified_name = f"{real_module}.{func.__qualname__}"
            params = collect_params(func, args, kwargs, ignore_params, _AUTO_SKIP_PARAMS)
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
