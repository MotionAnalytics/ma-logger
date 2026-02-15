# ma-logger

**OpenTelemetry-like** structured JSON logging and tracing for distributed environments.

> **Note:** This library follows OpenTelemetry semantic conventions but does **not** depend on the OTel SDK. It is an "OTel-like" approach that will be adapted as needed when a full OpenTelemetry integration is required.

## Features

- 📝 **Structured JSON logging** — all logs output as JSON for easy parsing and aggregation
- 🔍 **Function tracing decorator** — `@trace` logs function calls with parameters, duration, and errors
- 🔄 **Automatic context propagation** — injects `trace_id`, `execution_id`, `task_id` from environment variables
- 🎨 **Transparent integration** — third-party libraries and internal utils get JSON-formatted logs automatically via the root logger
- 📦 **Zero external dependencies** — uses only the Python standard library
- ⚙️ **Fully configurable** — customize field names, env var sources, and output targets

## Installation

```bash
pip install git+https://github.com/MotionAnalytics/ma-logger.git
```

---

## Development Setup

If you're contributing to this project, follow these steps to set up your local environment:

### 1. Install development dependencies

```bash
pip install -e ".[dev]"
```

This installs the package in editable mode along with development tools: `pytest`, `black`, `ruff`, and `pre-commit`.

### 2. Install pre-commit hooks

```bash
pre-commit install
```

This sets up automatic code quality checks that run **before every commit**:
- **Black** — automatic code formatting (fixes issues automatically)
- **Ruff** — linting and code quality checks (reports issues, does not auto-fix)

Once installed, these checks run automatically on `git commit`. If any issues are found, the commit will be blocked until you fix them.

**To skip checks in an emergency** (not recommended):
```bash
git commit -m "message" --no-verify
```

### 3. Run tests

```bash
pytest
```

---

## 1. Logger — `setup_logging()`

Call `setup_logging()` **once** at the entry point of your application. It configures the Python root logger so that **every** log message (including from third-party libraries) is formatted as JSON with tracing context.

### Basic usage

```python
from ma_logger import setup_logging
import logging
import os

# Initialize once at application startup
# Read file path from environment variable if needed
log_file_path = os.getenv("LOG_FILE_PATH")
setup_logging(log_to_file=log_file_path)

# Use standard logging everywhere
logger = logging.getLogger(__name__)
logger.info("Application started")
logger.warning("Something looks off", extra={"data": {"detail": "value"}})
```

### What it does

1. Sets the root logger level from the `LOG_LEVEL` env var (default: `INFO`).
2. Attaches a JSON formatter (`OTelJsonFormatter`) and a context filter (`OTelContextFilter`) to STDOUT.
3. Optionally writes to a file if the `log_to_file` parameter is provided.
4. Captures `warnings.warn()` messages and routes them through the logging system.
5. Is idempotent — safe to call multiple times (only configures once).

### Environment variables

| Variable | Purpose | Default |
|---|---|---|
| `LOG_LEVEL` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) | `INFO` |
| `SERVICE_NAME` | Identifies the service in log output | `unknown-service` |
| `TRACING_ID` / `CORRELATION_ID` | Populates `trace_id` | `N/A` |
| `KESTRA_EXECUTION_ID` / `EXECUTION_ID` | Populates `execution_id` | `N/A` |
| `KESTRA_TASK_ID` / `TASK_ID` | Populates `task_id` | `N/A` |

**Note:** The library no longer reads `LOG_FILE_PATH` directly. If you want to log to a file, read the environment variable in your application code and pass it to `setup_logging(log_to_file=...)` as shown in the example above.

### Custom configuration

You can pass custom formatter and filter instances for advanced use cases:

```python
import os
from ma_logger import setup_logging, OTelJsonFormatter, OTelContextFilter

formatter = OTelJsonFormatter(
    trace_id_field="traceId",          # rename JSON fields
    timestamp_format="unix",           # "iso" (default) or "unix"
    include_line_number=False,         # exclude optional fields
)

context_filter = OTelContextFilter(
    additional_context={"environment": "production"},
    additional_env_context={"pod_name": "POD_NAME"},
    fallback_value="unknown",
)

log_file_path = os.getenv("LOG_FILE_PATH")
setup_logging(log_to_file=log_file_path, formatter=formatter, context_filter=context_filter)
```

### Usage in internal libraries / utils

Internal packages should **not** import `ma-logger`. They just use standard logging:

```python
import logging

logger = logging.getLogger(__name__)

def my_utility_function():
    logger.info("Doing work")  # automatically formatted as JSON if setup_logging(...) was called
```

The root logger configuration propagates to all child loggers automatically.

---

## 2. Tracer — `@trace` decorator

The `@trace` decorator logs the success or failure of a function call, including its fully-qualified name, parameters, and execution duration. Each trace log line includes a `"type": "trace"` field for easy filtering.

### Basic usage

```python
from ma_logger import trace

@trace
def process_data(file_path, batch_size=100):
    # ... your logic ...
    return result
```

On success, this logs:
```json
{
  "message": "trace complete: mypackage.pipeline.process_data [success]",
  "type": "trace",
  "trace.function": "mypackage.pipeline.process_data",
  "trace.result": "success",
  "trace.duration": 1.234,
  "attributes": {
    "params": {"file_path": "/data/input.csv", "batch_size": 100}
  }
}
```

On failure:
```json
{
  "message": "trace complete: mypackage.pipeline.process_data [error]",
  "type": "trace",
  "trace.function": "mypackage.pipeline.process_data",
  "trace.result": "error",
  "trace.duration": 0.003,
  "attributes": {
    "params": {"file_path": "/data/input.csv", "batch_size": 100}
  },
  "exception.stacktrace": "Traceback ..."
}
```

The exception is always **re-raised** (never suppressed).

### Filtering trace logs

```bash
# All traces
jq 'select(.type == "trace")'

# Only failures
jq 'select(.type == "trace" and .["trace.result"] == "error")'

# Specific function
jq 'select(.["trace.function"] | contains("process_data"))'
```

### Ignoring sensitive parameters

```python
from ma_logger import trace

@trace(ignore_params=["password", "api_key"])
def authenticate(user, password, api_key):
    ...
```

Parameters listed in `ignore_params` are excluded from the log output. `self` and `cls` are always excluded automatically.

### Notes

- `trace.function` contains the fully-qualified function name (`package.module.function`), resolved automatically even when running as `__main__`.
- Non-JSON-serializable parameter values are replaced with `<ClassName>` (e.g. `<DataFrame>`).
- The decorator works with or without parentheses: `@trace` and `@trace()` are both valid.
- `monitor_task` is available as a deprecated alias for `trace`.

---

## Example JSON output

```json
{
  "timestamp": "2025-01-15T10:30:00.123456Z",
  "level": "INFO",
  "message": "Application started",
  "service.name": "my-service",
  "log.logger": "__main__",
  "log.origin.file.line": 12,
  "trace_id": "abc-123",
  "execution_id": "exec-456",
  "task_id": "task-789"
}
```

---

## Future direction

This library is **OpenTelemetry-like** — it uses OTel naming conventions and field structures so that a future migration to the full OTel SDK will be straightforward. When that happens, only the internals of `ma-logger` will change; consuming code will remain the same.

## License

MIT License — Motion Analytics