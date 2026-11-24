"""All tunable limits in one place, so they are easy to find, review and test."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    model: str = "claude-sonnet-5-5"
    max_tokens: int = 1000            # cap per model call
    max_steps: int = 5                # cap on model calls per run
    max_total_tokens: int = 20_000    # cap on tokens (in + out) per run
    request_timeout: float = 30.0     # seconds, per model API request
    sdk_max_retries: int = 2          # the SDK retries timeouts and server errors
    tool_attempts: int = 3            # tries per tool call (flaky backends)
    tool_retry_delay: float = 0.5     # seconds, multiplied by the attempt number
    mcp_call_timeout: float = 10.0    # seconds, per MCP tool call
    mcp_start_timeout: float = 20.0   # seconds, to launch an MCP server and connect

    @classmethod
    def from_env(cls) -> "Settings":
        """Defaults, with the model overridable through BANK_AGENT_MODEL."""
        return cls(model=os.getenv("BANK_AGENT_MODEL", cls.model))
