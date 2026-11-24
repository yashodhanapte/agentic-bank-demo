"""Accounts MCP server (fake data). Run it directly:  python -m bank_agents.servers.accounts

It speaks MCP over stdio, so you normally don't start it by hand: the agent's MCP client
launches it as a subprocess.
"""

from typing import Annotated

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from bank_agents.backend.mock_bank import BankError, MockBank

mcp = MCPServer("accounts", log_level="WARNING")
bank = MockBank()

AccountId = Annotated[
    str, Field(pattern=r"ACC[0-9]{4}", description="Account ID: ACC followed by 4 digits")
]


@mcp.tool()
def get_balance(account_id: AccountId) -> dict:
    """Get the current balance of one bank account."""
    try:
        return bank.get_balance(account_id)
    except BankError as e:
        return {"error": str(e)}


if __name__ == "__main__":
    mcp.run()
