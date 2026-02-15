"""
Internal utilities for module resolution and parameter handling.
"""

import inspect
import json
import os
import sys


def find_package_root(filepath):
    """Find the top-level package directory by walking up until no __init__.py exists."""
    current_dir = os.path.dirname(filepath)
    package_root = None

    while True:
        init_file = os.path.join(current_dir, "__init__.py")
        if os.path.isfile(init_file):
            package_root = current_dir
            parent_dir = os.path.dirname(current_dir)
            if parent_dir == current_dir:  # reached filesystem root
                break
            current_dir = parent_dir
        else:
            break

    return package_root


def resolve_module_name(func):
    """Return the real module name for *func*, even when running as __main__.

    When a script is executed directly (``python splitter/main.py``) or via
    ``python -m splitter.main``, ``func.__module__`` is ``"__main__"`` which
    is useless for tracing.  This helper resolves the actual dotted module
    path so trace logs always show e.g. ``package.splitter.main.process``.

    Resolution order:
        1. If ``__module__`` is not ``"__main__"`` — use it as-is.
        2. Try ``__spec__.name`` (set when using ``python -m``).
        3. Find package root via __init__.py hierarchy and derive full path.
        4. Fall back to ``"__main__"`` if nothing else works.
    """
    module = func.__module__
    if module != "__main__":
        return module

    # python -m sets __spec__
    main_mod = sys.modules.get("__main__")
    if main_mod and getattr(main_mod, "__spec__", None) and main_mod.__spec__.name:
        return main_mod.__spec__.name

    # Derive from file path using package hierarchy
    try:
        filepath = os.path.abspath(inspect.getfile(func))
    except (TypeError, OSError):
        return module

    # Find the top-level package by walking up __init__.py files
    package_root = find_package_root(filepath)

    if package_root:
        # Get package name (last component of package_root path)
        package_name = os.path.basename(package_root)

        # Get relative path from package root to file
        rel_path = os.path.relpath(filepath, package_root)
        rel_path = os.path.splitext(rel_path)[0]  # drop .py

        # Convert path to module notation
        parts = rel_path.split(os.sep)
        if parts[-1] == "__init__":
            parts = parts[:-1]

        if parts:
            module_path = ".".join(parts)
            return f"{package_name}.{module_path}"
        else:
            return package_name

    # Fallback to old sys.path matching (shortest first for outer packages)
    for path_entry in sorted(sys.path, key=len):
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


def safe_serialize_value(value):
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


def collect_params(func, args, kwargs, ignore_params=None, auto_skip_params=None):
    """Build a serializable dict of the function's bound arguments."""
    if auto_skip_params is None:
        auto_skip_params = set()
    ignore = auto_skip_params | set(ignore_params or [])
    try:
        sig = inspect.signature(func)
        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()
        return {
            name: safe_serialize_value(val)
            for name, val in bound.arguments.items()
            if name not in ignore
        }
    except (TypeError, ValueError):
        # Fallback – e.g. built-in functions without inspectable sig
        return {}
