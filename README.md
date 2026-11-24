# bank-agents

A multi-agent banking assistant built from scratch in Python with the Claude API, as a
learning project in production-minded agent engineering: guardrails, logging, retries,
evals and tests from the first commit.

> **All data is fake.** No real accounts, customers or banking systems are involved.

## Status

| Milestone | What it adds | Status |
|---|---|---|
| 1 | Reusable `Agent` class with guardrails, offline tests | done |
| 2 | Fake bank backend and three MCP servers | done |
| 3 | Three specialist agents (Accounts, Transactions, Service) | planned |
| 4 | Coordinator agent and authorisation | planned |
| 5 | PII redaction, session store, boundary checks | planned |
| 6 | Trace IDs across agents | planned |
| 7 | Eval suite, CLI demo | planned |

## What the `Agent` already does

- Runs the tool loop: model call, tool request, validated tool run, result, repeat.
- **Validates every tool input** in our own code (types, required and unexpected fields,
  length, format). Error messages never echo input values.
- **Limits:** step limit, per-run token budget, per-request timeout, SDK retries.
- **Retries flaky tools** (connection errors and timeouts only, never bad input).
- **Fails loudly** with specific exceptions (`StepLimitExceeded`, `TokenBudgetExceeded`,
  `ResponseTruncated`, `ModelCallError`) instead of returning half-finished answers.
- **Keeps the model safe from leaks:** tool crashes give the model a generic message;
  details stay in server-side logs.
- **Structured logs** with a `run` id on every line: step, stop reason, token counts,
  tool name, success and duration. Tool inputs and results are deliberately not logged.

## Milestone 2: the fake bank behind MCP

Three MCP servers (separate subprocesses speaking MCP over stdio) front a fake bank:

| Server | Tools |
|---|---|
| accounts | `get_balance` |
| transactions | `get_transactions`, `get_statement` |
| service | `change_address`, `request_chequebook`, `update_kyc` |

`bank_agents/mcp_client.py` bridges the async MCP client into the synchronous `Agent`:
each connection lives on a background thread, calls have a timeout, and tools are
discovered from the server, so the agent validates inputs against exactly the schema the
server publishes. Server error text is never forwarded to the model (it can echo inputs).
Servers are launched without your `ANTHROPIC_API_KEY`, because a tool server never needs it.

```powershell
python demo_m2.py --list                              # no API key needed
python demo_m2.py "What is the balance of ACC1001?"   # uses the API
```

## Quick start (Windows PowerShell)

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt

copy .env.example .env      # then put your real key in .env

pytest                      # offline tests, no API key or cost
python demo_m1.py           # real run, uses the API
```

On Mac or Linux: `source .venv/bin/activate` and `cp .env.example .env`.

## Project layout

```
bank_agents/
  agent.py          the Agent class (loop, limits, tool execution)
  tools.py          Tool definition and input validation
  mcp_client.py     bridge from async MCP servers into the sync Agent
  config.py         all limits in one Settings object
  errors.py         specific exception types
  logging_setup.py  logging configuration
  backend/
    mock_bank.py    the fake bank (all data invented)
  servers/
    accounts.py  transactions.py  service.py   the three MCP servers
tests/
  test_agent.py     Agent guardrails, with a scripted fake model
  test_mock_bank.py backend logic
  test_mcp.py       real MCP server subprocesses, fake model
  helpers.py        fake client used by the tests
demo_m1.py          one agent, one mock tool
demo_m2.py          the agent using the fake bank through MCP
```

## Security notes

- The API key lives in `.env`, which is git-ignored. Never commit it. If a key is ever
  committed, treat it as leaked and revoke it, even after deleting the file.
- Tool inputs are untrusted model output and are validated before anything runs.
- There is no authorisation yet, so any account ID can be read and the service tools change
  state without confirmation. Milestone 4 adds both. Do not point this at real data.
- Needs Python 3.10 or newer (the MCP SDK requires it).
