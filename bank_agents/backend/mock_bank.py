"""A fake bank. Everything here is invented: names, IDs, balances, transactions.

State lives in memory inside whichever process creates a MockBank. Each MCP server runs
as its own process, so each has its own copy. That is fine for a mock, and it mirrors the
real design, where each server fronts a separate backend system.
"""

from dataclasses import dataclass
from decimal import Decimal
from itertools import count


class BankError(Exception):
    """A business-level problem (for example, unknown account).

    Messages must be safe to show to the model: no input values, no internals.
    """


@dataclass(frozen=True)
class Account:
    account_id: str
    customer_id: str
    kind: str
    currency: str
    balance: Decimal


@dataclass(frozen=True)
class Transaction:
    txn_id: str
    account_id: str
    date: str  # YYYY-MM-DD
    description: str
    amount: Decimal  # negative = money out


_ACCOUNTS = [
    Account("ACC1001", "CUST001", "chequing", "CAD", Decimal("1250.40")),
    Account("ACC1002", "CUST001", "savings", "CAD", Decimal("8700.15")),
    Account("ACC2001", "CUST002", "chequing", "CAD", Decimal("87.15")),
]

_TRANSACTIONS = [
    Transaction("T0001", "ACC1001", "2026-11-20", "Sample Grocery Mart", Decimal("-84.30")),
    Transaction("T0002", "ACC1001", "2026-11-18", "Payroll deposit", Decimal("2100.00")),
    Transaction("T0003", "ACC1001", "2026-11-15", "Sample Hydro bill", Decimal("-96.45")),
    Transaction("T0004", "ACC1001", "2026-11-10", "Sample Coffee House", Decimal("-6.75")),
    Transaction("T0005", "ACC1001", "2026-11-03", "Rent transfer", Decimal("-1450.00")),
    Transaction("T0006", "ACC1001", "2026-10-28", "Sample Pharmacy", Decimal("-23.10")),
    Transaction("T0007", "ACC1001", "2026-10-18", "Payroll deposit", Decimal("2100.00")),
    Transaction("T0008", "ACC1001", "2026-10-03", "Rent transfer", Decimal("-1450.00")),
    Transaction("T0101", "ACC1002", "2026-11-01", "Transfer from chequing", Decimal("500.00")),
    Transaction("T0102", "ACC1002", "2026-10-31", "Interest", Decimal("12.15")),
    Transaction("T0103", "ACC1002", "2026-10-01", "Transfer from chequing", Decimal("500.00")),
    Transaction("T0201", "ACC2001", "2026-11-19", "Sample Bookshop", Decimal("-31.50")),
    Transaction("T0202", "ACC2001", "2026-11-12", "Payroll deposit", Decimal("640.00")),
    Transaction("T0203", "ACC2001", "2026-10-25", "Sample Transit pass", Decimal("-156.00")),
]

_CUSTOMERS = {"CUST001", "CUST002"}
_KYC_DOCUMENTS = {"passport", "drivers_license", "utility_bill"}


def _money(value: Decimal) -> str:
    return f"{value:.2f}"


class MockBank:
    def __init__(self):
        self._accounts = {a.account_id: a for a in _ACCOUNTS}
        self._transactions = list(_TRANSACTIONS)
        self._requests = []
        self._ref = count(1)

    # ----------------------------------------------------------------- lookups
    def _account(self, account_id: str) -> Account:
        try:
            return self._accounts[account_id]
        except KeyError:
            raise BankError("account not found") from None

    def _customer(self, customer_id: str) -> str:
        if customer_id not in _CUSTOMERS:
            raise BankError("customer not found")
        return customer_id

    def _new_reference(self, kind: str, subject_id: str, detail: str) -> dict:
        reference = f"SR-{next(self._ref):04d}"
        self._requests.append(
            {"reference": reference, "kind": kind, "subject": subject_id, "detail": detail}
        )
        return {"status": "submitted", "reference": reference}

    # ---------------------------------------------------------------- accounts
    def get_balance(self, account_id: str) -> dict:
        a = self._account(account_id)
        return {
            "account_id": a.account_id,
            "type": a.kind,
            "currency": a.currency,
            "balance": _money(a.balance),
        }

    # ------------------------------------------------------------ transactions
    def get_transactions(self, account_id: str, limit: int = 10) -> dict:
        self._account(account_id)
        rows = [t for t in self._transactions if t.account_id == account_id]
        rows.sort(key=lambda t: t.date, reverse=True)
        return {
            "account_id": account_id,
            "transactions": [
                {
                    "id": t.txn_id,
                    "date": t.date,
                    "description": t.description,
                    "amount": _money(t.amount),
                }
                for t in rows[:limit]
            ],
        }

    def get_statement(self, account_id: str, month: str) -> dict:
        a = self._account(account_id)
        rows = [
            t for t in self._transactions
            if t.account_id == account_id and t.date.startswith(month)
        ]
        rows.sort(key=lambda t: t.date)
        money_in = sum((t.amount for t in rows if t.amount > 0), Decimal("0"))
        money_out = sum((t.amount for t in rows if t.amount < 0), Decimal("0"))
        return {
            "account_id": account_id,
            "currency": a.currency,
            "month": month,
            "count": len(rows),
            "total_in": _money(money_in),
            "total_out": _money(money_out),
            "transactions": [
                {"date": t.date, "description": t.description, "amount": _money(t.amount)}
                for t in rows
            ],
        }

    # ----------------------------------------------------------------- service
    def change_address(self, customer_id: str, new_address: str) -> dict:
        self._customer(customer_id)
        return self._new_reference("change_of_address", customer_id, new_address)

    def request_chequebook(self, account_id: str, leaves: int = 25) -> dict:
        self._account(account_id)
        return self._new_reference("chequebook", account_id, f"{leaves} leaves")

    def update_kyc(self, customer_id: str, document_type: str) -> dict:
        self._customer(customer_id)
        if document_type not in _KYC_DOCUMENTS:
            raise BankError("unsupported document type")
        return self._new_reference("kyc_update", customer_id, document_type)

    @property
    def requests(self) -> list:
        """Service requests submitted so far (for tests and debugging)."""
        return list(self._requests)
