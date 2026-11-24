"""Custom exceptions. Each failure mode gets its own type so callers can react differently."""


class AgentError(Exception):
    """Base class for agent-level failures."""


class StepLimitExceeded(AgentError):
    """The model was still asking for tools when the step limit ran out."""


class TokenBudgetExceeded(AgentError):
    """The run used more tokens than its budget allows."""


class ResponseTruncated(AgentError):
    """The model hit max_tokens, so its answer (or tool call) may be incomplete."""


class ModelCallError(AgentError):
    """The call to the model API failed (after the SDK's own retries)."""


class ToolInputError(ValueError):
    """The model sent tool input that failed validation.

    Messages must never contain the offending value, only the field name and the rule,
    so they are safe to show to the model and to write to logs.
    """
