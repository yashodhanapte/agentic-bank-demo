"""Transactions MCP server (fake data). Run it directly:  python -m bank_agents.servers.transactions"""

from typing import Annotated

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from bank_agents.backend.mock_bank import BankError, MockBank

mcp = MCPServer("transactions", log_level="WARNING")
bank = MockBank()

AccountId = Annotated[
    str, Field(pattern=r"ACC[0-9]{4}", description="Account ID: ACC followed by 4 digits")
]
Month = Annotated[
    str,
    Field(pattern=r"20[0-9]{2}-(0[1-9]|1[0-2])", description="Month as YYYY-MM, e.g. 2026-11"),
]


@mcp.tool()
def get_transactions(
    account_id: AccountId,
    limit: Annotated[int, Field(ge=1, le=50, description="How many, newest first")] = 10,
) -> dict:
    """List the most recent transactions of one account, newest first."""
    try:
        return bank.get_transactions(account_id, limit)
    except BankError as e:
        return {"error": str(e)}


@mcp.tool()
def get_statement(account_id: AccountId, month: Month) -> dict:
    """Get a monthly statement for one account: totals in and out, and every transaction."""
    try:
        return bank.get_statement(account_id, month)
    except BankError as e:
        return {"error": str(e)}


if __name__ == "__main__":
    mcp.run()
