"""Tests for the fake bank backend (no MCP, no API)."""

import pytest

from bank_agents.backend.mock_bank import BankError, MockBank


@pytest.fixture
def bank():
    return MockBank()


def test_balance(bank):
    result = bank.get_balance("ACC1001")
    assert result["balance"] == "1250.40"
    assert result["currency"] == "CAD"


def test_unknown_account_raises_a_safe_error(bank):
    with pytest.raises(BankError) as info:
        bank.get_balance("ACC9999")
    assert "ACC9999" not in str(info.value)  # messages never echo input


def test_transactions_are_newest_first_and_limited(bank):
    rows = bank.get_transactions("ACC1001", limit=3)["transactions"]
    assert len(rows) == 3
    dates = [r["date"] for r in rows]
    assert dates == sorted(dates, reverse=True)


def test_statement_totals(bank):
    s = bank.get_statement("ACC1001", "2026-11")
    assert s["count"] == 5
    assert s["total_in"] == "2100.00"
    assert s["total_out"] == "-1637.50"


def test_statement_for_an_empty_month(bank):
    s = bank.get_statement("ACC1001", "2025-01")
    assert s["count"] == 0
    assert s["total_in"] == "0.00"


def test_service_requests_get_distinct_references(bank):
    a = bank.request_chequebook("ACC1001", leaves=50)
    b = bank.change_address("CUST001", "1 Example Street")
    assert a["reference"] != b["reference"]
    assert len(bank.requests) == 2


def test_service_rejects_unknown_customer_and_document(bank):
    with pytest.raises(BankError):
        bank.change_address("CUST999", "x")
    with pytest.raises(BankError):
        bank.update_kyc("CUST001", "selfie")
