# ma-logger

OTel-ready JSON logging library for distributed environments (Kubernetes, Kestra, Microservices).

## Features

- 🎯 **OpenTelemetry-ready**: Uses OTel semantic conventions for trace_id, execution_id, task_id
- 📦 **Zero dependencies**: Uses only Python standard library
- 🔄 **Automatic context propagation**: Captures context from environment variables
- 📝 **Structured JSON logging**: All logs in JSON format for easy parsing
- 🎨 **Transparent integration**: Works with third-party libraries without modification

## Installation

```bash
pip install ma-logger
```

## Quick Start

```python
from ma_logger import setup_logging
import logging

# Initialize once at application startup
setup_logging()

# Use standard logging everywhere
logger = logging.getLogger(__name__)
logger.info("Application started")
```

## Documentation

See [Logging Best Practices.md](Logging%20Best%20Practices.md) for detailed documentation.

## License

MIT License - Motion Analytics

