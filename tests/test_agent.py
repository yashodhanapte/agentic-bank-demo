"""Offline tests for the Agent. A scripted fake client stands in for the real API,
so these run in a second, cost nothing and need no API key."""

from dataclasses import replace

import pytest

from bank_agents.agent import Agent
from bank_agents.config import Settings
from bank_agents.errors import (
    ResponseTruncated,
    StepLimitExceeded,
    TokenBudgetExceeded,
)
from bank_agents.tools import Tool
from helpers import FakeClient, reply, text, tool_use

FAST = Settings(tool_retry_delay=0)


def echo_tool(func=None):
    return Tool(
        name="echo",
        description="Echo a lowercase word.",
        input_schema={
            "type": "object",
            "properties": {
                "word": {"type": "string", "pattern": "[a-z]+", "maxLength": 10}
            },
            "required": ["word"],
        },
        func=func or (lambda word: f"echo:{word}"),
    )


def make_agent(replies, settings=FAST, tool=None):
    client = FakeClient(replies)
    agent = Agent("test", "system prompt", [tool or echo_tool()], settings, client)
    return agent, client


def tool_result_of(result):
    """The tool_result the agent sent back (third message in the conversation)."""
    return result.messages[2]["content"][0]


# ---- tests ------------------------------------------------------------------
def test_answers_without_tools():
    agent, _ = make_agent([reply([text("hi")])])
    result = agent.run("hello")
    assert result.answer == "hi"
    assert result.tools_called == []
    assert result.steps == 1


def test_tool_call_then_answer():
    agent, _ = make_agent(
        [reply([tool_use("t1", "echo", word="abc")], stop="tool_use"),
         reply([text("done")])]
    )
    result = agent.run("say abc")
    assert result.answer == "done"
    assert result.tools_called == ["echo"]
    assert result.steps == 2
    tr = tool_result_of(result)
    assert tr["tool_use_id"] == "t1"
    assert tr["content"] == "echo:abc"
    assert tr["is_error"] is False


def test_invalid_input_is_reported_and_tool_is_not_run():
    ran = []
    agent, _ = make_agent(
        [reply([tool_use("t1", "echo", word="ABC123")], stop="tool_use"),
         reply([text("sorry")])],
        tool=echo_tool(func=lambda word: ran.append(word)),
    )
    result = agent.run("x")
    tr = tool_result_of(result)
    assert tr["is_error"] is True
    assert tr["content"].startswith("Invalid input")
    assert "ABC123" not in tr["content"]  # values never echoed back
    assert ran == []


@pytest.mark.parametrize(
    "bad_inputs",
    [{}, {"word": ""}, {"word": 123}, {"word": True}, {"word": "a" * 11},
     {"word": "abc", "extra": "x"}],
)
def test_validation_rejects_bad_inputs(bad_inputs):
    agent, _ = make_agent([reply([text("unused")])])
    from bank_agents.errors import ToolInputError

    with pytest.raises(ToolInputError):
        agent.tools["echo"].validate(bad_inputs)


def test_validation_trims_spaces():
    agent, _ = make_agent([reply([text("unused")])])
    assert agent.tools["echo"].validate({"word": "  abc  "}) == {"word": "abc"}


def test_unknown_tool_is_reported():
    agent, _ = make_agent(
        [reply([tool_use("t1", "nope", word="a")], stop="tool_use"),
         reply([text("ok")])]
    )
    tr = tool_result_of(agent.run("x"))
    assert tr["is_error"] is True
    assert tr["content"] == "Unknown tool."


def test_tool_crash_gives_the_model_a_generic_message():
    def boom(word):
        raise RuntimeError("secret path C:\\private\\keys")

    agent, _ = make_agent(
        [reply([tool_use("t1", "echo", word="abc")], stop="tool_use"),
         reply([text("sorry")])],
        tool=echo_tool(func=boom),
    )
    tr = tool_result_of(agent.run("x"))
    assert tr["is_error"] is True
    assert "secret" not in tr["content"]


def test_flaky_tool_is_retried_until_it_works():
    attempts = []

    def flaky(word):
        attempts.append(1)
        if len(attempts) < 3:
            raise ConnectionError("blip")
        return "ok"

    agent, _ = make_agent(
        [reply([tool_use("t1", "echo", word="abc")], stop="tool_use"),
         reply([text("fine")])],
        tool=echo_tool(func=flaky),
    )
    tr = tool_result_of(agent.run("x"))
    assert len(attempts) == 3
    assert tr["is_error"] is False
    assert tr["content"] == "ok"


def test_flaky_tool_gives_up_after_the_last_attempt():
    attempts = []

    def always_down(word):
        attempts.append(1)
        raise ConnectionError("down")

    agent, _ = make_agent(
        [reply([tool_use("t1", "echo", word="abc")], stop="tool_use"),
         reply([text("sorry")])],
        tool=echo_tool(func=always_down),
    )
    tr = tool_result_of(agent.run("x"))
    assert len(attempts) == FAST.tool_attempts
    assert tr["is_error"] is True


def test_step_limit_raises():
    looping = [
        reply([tool_use(f"t{i}", "echo", word="a")], stop="tool_use")
        for i in range(10)
    ]
    agent, _ = make_agent(looping, settings=replace(FAST, max_steps=3))
    with pytest.raises(StepLimitExceeded):
        agent.run("x")


def test_token_budget_raises():
    looping = [
        reply([tool_use(f"t{i}", "echo", word="a")], stop="tool_use", tin=600)
        for i in range(10)
    ]
    agent, client = make_agent(looping, settings=replace(FAST, max_total_tokens=1000))
    with pytest.raises(TokenBudgetExceeded):
        agent.run("x")
    assert len(client.calls) == 2  # stopped as soon as the budget was crossed


def test_truncated_reply_raises():
    agent, _ = make_agent([reply([text("cut off mid-sen")], stop="max_tokens")])
    with pytest.raises(ResponseTruncated):
        agent.run("x")


def test_history_is_carried_into_the_next_run():
    agent, client = make_agent([reply([text("again")])])
    history = [
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "ok"},
    ]
    agent.run("second", history=history)
    sent = client.calls[0]["messages"]
    assert [m["content"] for m in sent[:2]] == ["first", "ok"]
