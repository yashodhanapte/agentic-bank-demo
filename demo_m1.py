"""Milestone 1 demo: one agent with one mock banking tool.

Run from the project root, with the virtual environment active and ANTHROPIC_API_KEY set
in your .env file:

    python demo_m1.py

All data below is fake. Note: this demo has NO authorisation yet, so any account ID can
be read. Milestone 4 adds a coordinator that checks who is allowed to see what.
"""

from dotenv import load_dotenv

from bank_agents.agent import Agent
from bank_agents.logging_setup import configure_logging
from bank_agents.tools import Tool

load_dotenv()
configure_logging()

FAKE_BALANCES = {"ACC1001": "1,250.40 CAD", "ACC1002": "87.15 CAD"}


def get_balance(account_id):
    return FAKE_BALANCES.get(account_id, "account not found")


balance_tool = Tool(
    name="get_balance",
    description="Get the current balance of a bank account from its ID "
    "(the letters ACC followed by 4 digits).",
    input_schema={
        "type": "object",
        "properties": {
            "account_id": {"type": "string", "pattern": "ACC[0-9]{4}"}
        },
        "required": ["account_id"],
    },
    func=get_balance,
)

agent = Agent(
    name="accounts",
    system_prompt=(
        "You are a careful banking assistant. Use tools for any account data. "
        "Never guess a balance. If a tool fails, say it is unavailable."
    ),
    tools=[balance_tool],
)

if __name__ == "__main__":
    result = agent.run("What is the balance of account ACC1001?")
    print()
    print(result.answer)
    print(
        f"\n[run {result.run_id}: {result.steps} steps, tools {result.tools_called}, "
        f"tokens {result.input_tokens} in / {result.output_tokens} out]"
    )
