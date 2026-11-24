"""A reusable agent: the Step 3 loop plus the guardrails from Steps 4 to 6.

The model never runs anything. It asks for a tool, this code validates the request, runs
the tool, and sends the result back. Limits keep a confused agent from running forever.
"""

import logging
import time
import uuid
from dataclasses import dataclass

import anthropic

from .config import Settings
from .errors import (
    ModelCallError,
    ResponseTruncated,
    StepLimitExceeded,
    TokenBudgetExceeded,
    ToolInputError,
)
from .tools import Tool

log = logging.getLogger("bank_agents.agent")


@dataclass
class AgentResult:
    answer: str
    tools_called: list
    steps: int
    input_tokens: int
    output_tokens: int
    run_id: str
    messages: list  # the full conversation, so a session store can save it later


class Agent:
    def __init__(self, name, system_prompt, tools, settings=None, client=None):
        self.name = name
        self.system_prompt = system_prompt
        self.tools = {tool.name: tool for tool in tools}
        self.settings = settings or Settings.from_env()
        self.client = client or anthropic.Anthropic(
            timeout=self.settings.request_timeout,
            max_retries=self.settings.sdk_max_retries,
        )

    # ------------------------------------------------------------------ the loop
    def run(self, user_message, history=None, run_id=None) -> AgentResult:
        s = self.settings
        run_id = run_id or uuid.uuid4().hex[:8]
        messages = list(history or []) + [{"role": "user", "content": user_message}]
        tools_called = []
        tokens_in = tokens_out = 0

        for step in range(s.max_steps):
            response = self._call_model(messages, run_id, step)
            tokens_in += response.usage.input_tokens
            tokens_out += response.usage.output_tokens
            log.info(
                "run=%s agent=%s step=%d stop_reason=%s tokens_in=%d tokens_out=%d",
                run_id, self.name, step, response.stop_reason,
                response.usage.input_tokens, response.usage.output_tokens,
            )

            if tokens_in + tokens_out > s.max_total_tokens:
                raise TokenBudgetExceeded(f"run {run_id} exceeded its token budget")
            if response.stop_reason == "max_tokens":
                raise ResponseTruncated(f"run {run_id}: the model's reply was cut off")

            messages.append({"role": "assistant", "content": response.content})
            if response.stop_reason != "tool_use":
                break

            results = [
                self._run_tool_block(block, run_id, tools_called)
                for block in response.content
                if block.type == "tool_use"
            ]
            messages.append({"role": "user", "content": results})
        else:
            raise StepLimitExceeded(f"run {run_id} hit the step limit ({s.max_steps})")

        answer = "".join(b.text for b in response.content if b.type == "text")
        return AgentResult(
            answer=answer,
            tools_called=tools_called,
            steps=step + 1,
            input_tokens=tokens_in,
            output_tokens=tokens_out,
            run_id=run_id,
            messages=messages,
        )

    # --------------------------------------------------------------- model calls
    def _call_model(self, messages, run_id, step):
        s = self.settings
        kwargs = {
            "model": s.model,
            "max_tokens": s.max_tokens,
            "system": self.system_prompt,
            "messages": messages,
        }
        if self.tools:
            kwargs["tools"] = [tool.to_api() for tool in self.tools.values()]
        try:
            return self.client.messages.create(**kwargs)
        except anthropic.APIError as e:
            # Log the error type only. The details can hold request data.
            log.error(
                "run=%s agent=%s step=%d model call failed: %s",
                run_id, self.name, step, type(e).__name__,
            )
            raise ModelCallError(type(e).__name__) from e

    # --------------------------------------------------------------------- tools
    def _run_tool_block(self, block, run_id, tools_called):
        """Run one tool request and ALWAYS return a tool_result, never raise."""
        tools_called.append(block.name)
        tool = self.tools.get(block.name)
        is_error = False
        start = time.perf_counter()

        if tool is None:
            content, is_error = "Unknown tool.", True
        else:
            try:
                content = self._execute_with_retry(tool, block.input, run_id)
            except ToolInputError as e:
                # Safe by construction: these messages never contain the input values.
                # Telling the model what was wrong lets it correct itself.
                content, is_error = f"Invalid input: {e}", True
            except Exception as e:
                # Anything else may leak paths or secrets, so the model gets a generic text.
                log.error(
                    "run=%s agent=%s tool=%s failed: %s",
                    run_id, self.name, block.name, type(e).__name__,
                )
                content = "The tool failed. Tell the user it is unavailable."
                is_error = True

        ms = (time.perf_counter() - start) * 1000
        log.info(
            "run=%s agent=%s tool=%s ok=%s ms=%.1f",
            run_id, self.name, block.name, not is_error, ms,
        )
        return {
            "type": "tool_result",
            "tool_use_id": block.id,  # ties this result to the exact request
            "content": content,
            "is_error": is_error,
        }

    def _execute_with_retry(self, tool, raw_inputs, run_id):
        s = self.settings
        clean = tool.validate(raw_inputs)  # bad input is never retried
        for attempt in range(1, s.tool_attempts + 1):
            try:
                return str(tool.func(**clean))
            except (ConnectionError, TimeoutError):
                log.warning(
                    "run=%s agent=%s tool=%s attempt %d/%d failed",
                    run_id, self.name, tool.name, attempt, s.tool_attempts,
                )
                if attempt == s.tool_attempts:
                    raise
                time.sleep(s.tool_retry_delay * attempt)
