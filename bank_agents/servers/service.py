"""Service MCP server (fake data). Run it directly:  python -m bank_agents.servers.service

These tools CHANGE state (in memory only, in this mock). In a real system, tools like these
need authorisation and usually a confirmation step. Milestone 4 adds both.
"""

from typing import Annotated, Literal

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from bank_agents.backend.mock_bank import BankError, MockBank

mcp = MCPServer("service", log_level="WARNING")
bank = MockBank()

AccountId = Annotated[
    str, Field(pattern=r"ACC[0-9]{4}", description="Account ID: ACC followed by 4 digits")
]
CustomerId = Annotated[
    str, Field(pattern=r"CUST[0-9]{3}", description="Customer ID: CUST followed by 3 digits")
]


@mcp.tool()
def change_address(
    customer_id: CustomerId,
    new_address: Annotated[str, Field(max_length=120, description="The new postal address")],
) -> dict:
    """Submit a change-of-address request for a customer."""
    try:
        return bank.change_address(customer_id, new_address)
    except BankError as e:
        return {"error": str(e)}


@mcp.tool()
def request_chequebook(
    account_id: AccountId,
    leaves: Literal[25, 50] = 25,
) -> dict:
    """Request a new chequebook (25 or 50 leaves) for an account."""
    try:
        return bank.request_chequebook(account_id, leaves)
    except BankError as e:
        return {"error": str(e)}


@mcp.tool()
def update_kyc(
    customer_id: CustomerId,
    document_type: Literal["passport", "drivers_license", "utility_bill"],
) -> dict:
    """Start a KYC (identity document) update for a customer."""
    try:
        return bank.update_kyc(customer_id, document_type)
    except BankError as e:
        return {"error": str(e)}


if __name__ == "__main__":
    mcp.run()
