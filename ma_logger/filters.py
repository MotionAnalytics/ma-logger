"""
Logging filters for automatic context injection.
"""

import logging
import os


class OTelContextFilter(logging.Filter):
    """
    Automatically injects OpenTelemetry context into log records.

    Default behavior (zero-config):
        Extracts context from standard environment variables:
        - trace_id: TRACING_ID or CORRELATION_ID
        - execution_id: KESTRA_EXECUTION_ID or EXECUTION_ID
        - task_id: KESTRA_TASK_ID or TASK_ID

        Falls back to "N/A" if environment variables are not set.

    Customization options:
        Args:
            trace_id_env_vars (list): Environment variable names for trace_id
                (default: ["TRACING_ID", "CORRELATION_ID"])
            execution_id_env_vars (list): Environment variable names for execution_id
                (default: ["KESTRA_EXECUTION_ID", "EXECUTION_ID"])
            task_id_env_vars (list): Environment variable names for task_id
                (default: ["KESTRA_TASK_ID", "TASK_ID"])
            additional_context (dict): Additional static context to inject
                (default: None)
            additional_env_context (dict): Additional context from env vars
                Format: {"context_key": "ENV_VAR_NAME"}
                (default: None)
            fallback_value (str): Value to use when env var not found
                (default: "N/A")

    Examples:
        # Default usage (recommended)
        filter = OTelContextFilter()

        # Custom environment variable names
        filter = OTelContextFilter(
            trace_id_env_vars=["X_TRACE_ID", "TRACE_ID"],
            execution_id_env_vars=["RUN_ID", "EXECUTION_ID"]
        )

        # Add static context
        filter = OTelContextFilter(
            additional_context={"environment": "production", "region": "us-east-1"}
        )

        # Add dynamic context from environment variables
        filter = OTelContextFilter(
            additional_env_context={
                "pod_name": "POD_NAME",
                "namespace": "K8S_NAMESPACE"
            }
        )

        # Combine multiple customizations
        filter = OTelContextFilter(
            trace_id_env_vars=["X_TRACE_ID"],
            additional_context={"service_version": "1.0.0"},
            additional_env_context={"pod_name": "POD_NAME"},
            fallback_value="unknown"
        )
    """

    def __init__(
        self,
        trace_id_env_vars=None,
        execution_id_env_vars=None,
        task_id_env_vars=None,
        additional_context=None,
        additional_env_context=None,
        fallback_value="N/A",
    ):
        super().__init__()

        # Set default environment variable names
        self.trace_id_env_vars = trace_id_env_vars or ["TRACING_ID", "CORRELATION_ID"]
        self.execution_id_env_vars = execution_id_env_vars or [
            "KESTRA_EXECUTION_ID",
            "EXECUTION_ID",
        ]
        self.task_id_env_vars = task_id_env_vars or ["KESTRA_TASK_ID", "TASK_ID"]

        # Additional context
        self.additional_context = additional_context or {}
        self.additional_env_context = additional_env_context or {}
        self.fallback_value = fallback_value

    def _get_env_value(self, env_var_names):
        """
        Get value from first available environment variable in the list.

        Args:
            env_var_names (list): List of environment variable names to try

        Returns:
            str: Value from first available env var, or fallback_value
        """
        for env_var in env_var_names:
            value = os.getenv(env_var)
            if value:
                return value
        return self.fallback_value

    def filter(self, record):
        # Build base context
        record.otel_ctx = {
            "trace_id": self._get_env_value(self.trace_id_env_vars),
            "execution_id": self._get_env_value(self.execution_id_env_vars),
            "task_id": self._get_env_value(self.task_id_env_vars),
        }

        # Add static additional context
        record.otel_ctx.update(self.additional_context)

        # Add dynamic context from environment variables
        for context_key, env_var_name in self.additional_env_context.items():
            value = os.getenv(env_var_name)
            if value:
                record.otel_ctx[context_key] = value

        return True
