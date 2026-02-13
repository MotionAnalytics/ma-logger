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

## 1. Logger — `setup_logging()`

Call `setup_logging()` **once** at the entry point of your application. It configures the Python root logger so that **every** log message (including from third-party libraries) is formatted as JSON with tracing context.

### Basic usage

```python
from ma_logger import setup_logging
import logging

# Initialize once at application startup
setup_logging()

# Use standard logging everywhere
logger = logging.getLogger(__name__)
logger.info("Application started")
logger.warning("Something looks off", extra={"data": {"detail": "value"}})
```

### What it does

1. Sets the root logger level from the `LOG_LEVEL` env var (default: `INFO`).
2. Attaches a JSON formatter (`OTelJsonFormatter`) and a context filter (`OTelContextFilter`) to STDOUT.
3. Optionally writes to a file if `LOG_FILE_PATH` is set.
4. Captures `warnings.warn()` messages and routes them through the logging system.
5. Is idempotent — safe to call multiple times (only configures once).

### Environment variables

| Variable | Purpose | Default |
|---|---|---|
| `LOG_LEVEL` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) | `INFO` |
| `LOG_FILE_PATH` | If set, logs are also written to this file path | *(none — STDOUT only)* |
| `SERVICE_NAME` | Identifies the service in log output | `unknown-service` |
| `TRACING_ID` / `CORRELATION_ID` | Populates `trace_id` | `N/A` |
| `KESTRA_EXECUTION_ID` / `EXECUTION_ID` | Populates `execution_id` | `N/A` |
| `KESTRA_TASK_ID` / `TASK_ID` | Populates `task_id` | `N/A` |

### Custom configuration

You can pass custom formatter and filter instances for advanced use cases:

```python
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

setup_logging(formatter=formatter, context_filter=context_filter)
```

### Usage in internal libraries / utils

Internal packages should **not** import `ma-logger`. They just use standard logging:

```python
import logging

logger = logging.getLogger(__name__)

def my_utility_function():
    logger.info("Doing work")  # automatically formatted as JSON if setup_logging() was called
```

The root logger configuration propagates to all child loggers automatically.

---

## 2. Tracer — `@trace` decorator

The `@trace` decorator logs the start, success, or failure of a function call, including its parameters and execution duration.

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
  "message": "Task process_data success",
  "attributes": {
    "duration": 1.234,
    "params": {"file_path": "/data/input.csv", "batch_size": 100}
  }
}
```

On failure, it logs the error with a full stack trace and **re-raises the exception** (never suppresses it).

### Ignoring sensitive parameters

```python
from ma_logger import trace

@trace(ignore_params=["password", "api_key"])
def authenticate(user, password, api_key):
    ...
```

Parameters listed in `ignore_params` are excluded from the log output. `self` and `cls` are always excluded automatically.

### Notes

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
