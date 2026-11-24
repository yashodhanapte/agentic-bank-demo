"""Integration tests: real MCP server subprocesses, fake model. Still offline and free.

These start the three servers once (about 2 seconds) and share them across the tests.
"""

import pytest

from bank_agents.agent import Agent
from bank_agents.config import Settings
from bank_agents.errors import ToolInputError, ToolServerError
from bank_agents.mcp_client import MCPToolbox
from helpers import FakeClient, reply, text, tool_use


@pytest.fixture(scope="module")
def box():
    with MCPToolbox("accounts", "transactions", "service") as toolbox:
        yield toolbox


@pytest.fixture(scope="module")
def tools(box):
    return {t.name: t for t in box.tools()}


def call(tools, name, **inputs):
    tool = tools[name]
    return tool.func(**tool.validate(inputs))


def test_all_tools_are_discovered(tools):
    assert set(tools) == {
        "get_balance",
        "get_transactions",
        "get_statement",
        "change_address",
        "request_chequebook",
        "update_kyc",
    }


def test_balance_through_mcp(tools):
    assert "1250.40" in call(tools, "get_balance", account_id="ACC1001")


def test_unknown_account_is_a_normal_answer_not_a_crash(tools):
    out = call(tools, "get_balance", account_id="ACC9999")
    assert "account not found" in out
    assert "ACC9999" not in out


def test_statement_through_mcp(tools):
    out = call(tools, "get_statement", account_id="ACC1001", month="2026-11")
    assert "-1637.50" in out


def test_service_requests_change_state(tools):
    a = call(tools, "request_chequebook", account_id="ACC1001", leaves=25)
    b = call(tools, "request_chequebook", account_id="ACC1001", leaves=50)
    assert a != b  # different reference numbers


@pytest.mark.parametrize(
    "name, bad",
    [
        ("get_balance", {"account_id": "ACC12"}),
        ("get_balance", {"account_id": "acc1001"}),
        ("get_transactions", {"account_id": "ACC1001", "limit": 0}),
        ("get_transactions", {"account_id": "ACC1001", "limit": 51}),
        ("get_statement", {"account_id": "ACC1001", "month": "2026-13"}),
        ("request_chequebook", {"account_id": "ACC1001", "leaves": 30}),
        ("update_kyc", {"customer_id": "CUST001", "document_type": "selfie"}),
        ("change_address", {"customer_id": "CUST001", "new_address": "x" * 121}),
        ("get_balance", {"account_id": "ACC1001", "extra": "field"}),
    ],
)
def test_bad_inputs_are_stopped_on_our_side(tools, name, bad):
    with pytest.raises(ToolInputError):
        tools[name].validate(bad)


def test_server_error_text_is_never_forwarded(tools):
    # Skip our own validation on purpose, to see what the server does with bad input.
    with pytest.raises(ToolServerError) as info:
        tools["get_balance"].func(account_id="not-an-account")
    assert "not-an-account" not in str(info.value)


def test_full_path_agent_to_mcp_server(tools):
    client = FakeClient(
        [
            reply([tool_use("t1", "get_balance", account_id="ACC1001")], stop="tool_use"),
            reply([text("Your balance is 1250.40 CAD.")]),
        ]
    )
    agent = Agent(
        "accounts", "You are a banking assistant.", [tools["get_balance"]],
        Settings(tool_retry_delay=0), client,
    )
    result = agent.run("What is my balance?")
    tool_result = result.messages[2]["content"][0]
    assert tool_result["is_error"] is False
    assert "1250.40" in tool_result["content"]
    assert result.tools_called == ["get_balance"]


def test_agent_survives_a_server_side_rejection(tools):
    # The model sends a bad ID. Our validator stops it, and the model gets a clear note.
    client = FakeClient(
        [
            reply([tool_use("t1", "get_balance", account_id="ACC12")], stop="tool_use"),
            reply([text("That account ID looks wrong.")]),
        ]
    )
    agent = Agent(
        "accounts", "x", [tools["get_balance"]], Settings(tool_retry_delay=0), client
    )
    result = agent.run("balance for ACC12")
    tool_result = result.messages[2]["content"][0]
    assert tool_result["is_error"] is True
    assert tool_result["content"].startswith("Invalid input")
    assert "ACC12" not in tool_result["content"]
