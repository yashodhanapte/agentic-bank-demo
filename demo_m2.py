"""Milestone 2 demo: the agent uses the fake bank through three MCP servers.

    python demo_m2.py --list                 no API key needed: shows what each server offers
    python demo_m2.py "your question"        one agent with ALL six tools (uses the API)

Example questions:
    python demo_m2.py "What is the balance of ACC1001?"
    python demo_m2.py "Give me my November statement for ACC1001"
    python demo_m2.py "Order a 50 leaf chequebook for ACC1001"

In Milestone 3 this single do-everything agent is split into three specialists, each
connected to only ITS server. All data is fake, and there is still no authorisation.
"""

import sys

from dotenv import load_dotenv

from bank_agents.agent import Agent
from bank_agents.errors import AgentError, ModelCallError
from bank_agents.logging_setup import configure_logging
from bank_agents.mcp_client import SERVERS, MCPConnection, MCPToolbox

load_dotenv()
configure_logging()


def list_tools() -> None:
    for server in SERVERS:
        with MCPConnection(server) as connection:
            print(f"\n[{server} server]")
            for tool in connection.tools():
                print(f"  {tool.name}: {tool.description}")


def ask(question: str) -> None:
    with MCPToolbox(*SERVERS) as box:
        agent = Agent(
            name="bank-assistant",
            system_prompt=(
                "You are a careful banking assistant. Use tools for any account data "
                "and never guess numbers. If a tool reports an error or is unavailable, "
                "say so plainly. Money is in the account's currency."
            ),
            tools=box.tools(),
        )
        try:
            result = agent.run(question)
        except ModelCallError as e:
            sys.exit(
                f"The model call failed ({e}). Check that ANTHROPIC_API_KEY is set in "
                ".env and that your Console account has credits."
            )
        except AgentError as e:
            sys.exit(f"The agent stopped before finishing: {type(e).__name__}: {e}")
    print()
    print(result.answer)
    print(
        f"\n[run {result.run_id}: {result.steps} steps, tools {result.tools_called}, "
        f"tokens {result.input_tokens} in / {result.output_tokens} out]"
    )


if __name__ == "__main__":
    args = sys.argv[1:]
    if args == ["--list"]:
        list_tools()
    elif args:
        ask(" ".join(args))
    else:
        print(__doc__)
