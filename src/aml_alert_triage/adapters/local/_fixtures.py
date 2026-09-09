"""Deterministic, obviously fictional alert and transaction fixtures for the offline profile.

These drive the ``local`` alert-feed and warehouse adapters, the offline gate, the eval golden
set and the demo. Every party is invented, every identifier is synthetic, and the four cases are
chosen to exercise each band and each recommendation the engine can reach:

* ``FCC-1001`` structuring only            -> HIGH  -> escalate_sar
* ``FCC-1002`` nothing fires               -> LOW   -> close
* ``FCC-1003`` rapid movement + mule fan-out -> CRITICAL -> escalate_sar (dual control)
* ``FCC-1004`` funnel account only         -> MEDIUM -> request_info

The amounts are in minor units (cents), so the numbers the detectors read are exact. One alert
narrative carries a checksum-valid synthetic NRIC and a ``.example`` email so the redact-before-
audit path has something real-shaped to mask.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from ...domain.models import Alert, Transaction, TransactionWindow

_AS_OF = date(2026, 8, 1)
_WAREHOUSE = "warehouse:txn_monitoring.windows"
_FEED = "feed:txn_monitoring.alerts"

#: The tenant every fixture alert belongs to. The feed matches this against the verified
#: principal, so the offline profile exercises the same object-level authorization the managed
#: one must: the seeded ``other-tenant`` persona reads none of these rows.
FIXTURE_TENANT = "demo-bank"


def _t(day: int, hour: int) -> datetime:
    return datetime(2026, 7, day, hour, 0, tzinfo=UTC)


def _structuring_window() -> TransactionWindow:
    subject = "Redwood Timber Trading Pte Ltd (FICTIONAL)"
    txns = (
        Transaction(
            "T-1001-a",
            _t(10, 9),
            900000,
            "SGD",
            "out",
            "Kestrel Supplies (FICTIONAL)",
            "wire",
            "SG",
        ),
        Transaction(
            "T-1001-b",
            _t(12, 10),
            950000,
            "SGD",
            "out",
            "Kestrel Supplies (FICTIONAL)",
            "wire",
            "SG",
        ),
        Transaction(
            "T-1001-c",
            _t(15, 11),
            970000,
            "SGD",
            "out",
            "Harbour Freight (FICTIONAL)",
            "wire",
            "SG",
        ),
        Transaction(
            "T-1001-d",
            _t(18, 14),
            990000,
            "SGD",
            "out",
            "Harbour Freight (FICTIONAL)",
            "wire",
            "SG",
        ),
        Transaction(
            "T-1001-e", _t(9, 8), 400000, "SGD", "in", "Cedar Mills (FICTIONAL)", "wire", "SG"
        ),
    )
    return TransactionWindow(subject=subject, as_of=_AS_OF, transactions=txns, source_id=_WAREHOUSE)


def _clean_window() -> TransactionWindow:
    subject = "Azure Freight Holdings (FICTIONAL)"
    txns = (
        Transaction(
            "T-1002-a", _t(11, 9), 100000, "SGD", "in", "Blue Ridge Co (FICTIONAL)", "wire", "SG"
        ),
        Transaction(
            "T-1002-b", _t(14, 10), 100000, "SGD", "in", "Blue Ridge Co (FICTIONAL)", "wire", "SG"
        ),
        Transaction(
            "T-1002-c", _t(16, 12), 50000, "SGD", "out", "Utilities Board (FICTIONAL)", "giro", "SG"
        ),
    )
    return TransactionWindow(subject=subject, as_of=_AS_OF, transactions=txns, source_id=_WAREHOUSE)


def _mule_window() -> TransactionWindow:
    subject = "Meridian Logistics LLP (FICTIONAL)"
    inflow = Transaction(
        "T-1003-in", _t(20, 9), 1000000, "SGD", "in", "Offshore Trust (FICTIONAL)", "wire", "SG"
    )
    fanned = tuple(
        Transaction(
            f"T-1003-o{i}",
            _t(20, 10 + i),
            180000,
            "SGD",
            "out",
            f"Beneficiary {i} (FICTIONAL)",
            "fast",
            "SG",
        )
        for i in range(5)
    )
    return TransactionWindow(
        subject=subject, as_of=_AS_OF, transactions=(inflow, *fanned), source_id=_WAREHOUSE
    )


def _funnel_window() -> TransactionWindow:
    subject = "Coral Bay Enterprises (FICTIONAL)"
    inflows = tuple(
        Transaction(
            f"T-1004-i{i}",
            _t(13, 9 + i),
            200000,
            "SGD",
            "in",
            f"Originator {i} (FICTIONAL)",
            "fast",
            "SG",
        )
        for i in range(6)
    )
    outflow = Transaction(
        "T-1004-out", _t(16, 15), 900000, "SGD", "out", "Shell Co (FICTIONAL)", "wire", "SG"
    )
    return TransactionWindow(
        subject=subject, as_of=_AS_OF, transactions=(*inflows, outflow), source_id=_WAREHOUSE
    )


# --------------------------------------------------------------------------------------- #
# The suppression corpus. Alerts a hand-review says should CLOSE.
#
# This is the eval that carries the whole business case and there was no corpus for it. The
# pitch for alert triage is not "it finds the structuring case", which a rule already did; it is
# "it closes the ninety-odd alerts that should never have reached an investigator". Nothing
# measured that, because the golden set held one clean alert against three that escalate, and a
# false-positive rate over one negative is not a rate.
#
# Each window below is a benign pattern a monitoring rule genuinely fires on, and each is benign
# for a DIFFERENT reason, because a suppression metric over one shape of clean alert proves only
# that the engine can close that shape. All parties are fictional; amounts are in minor units.
# --------------------------------------------------------------------------------------- #
def _payroll_window() -> TransactionWindow:
    """A monthly salary run: many small identical outflows to unrelated payees, on one day."""
    subject = "Harbourfront Marine Services (FICTIONAL)"
    txns = (
        Transaction(
            "T-2001-in", _t(1, 9), 4_500_000, "SGD", "in", "Client Escrow (FICTIONAL)", "wire", "SG"
        ),
        *tuple(
            Transaction(
                f"T-2001-s{index}",
                _t(2, 9),
                320_000,
                "SGD",
                "out",
                f"Employee {index} (FICTIONAL)",
                "giro",
                "SG",
            )
            for index in range(1, 9)
        ),
    )
    return TransactionWindow(subject=subject, as_of=_AS_OF, transactions=txns, source_id=_WAREHOUSE)


def _supplier_settlement_window() -> TransactionWindow:
    """Regular settlement to two long-standing suppliers, same counterparties every month."""
    subject = "Kestrel Provisions Pte Ltd (FICTIONAL)"
    txns = (
        Transaction(
            "T-2002-a", _t(5, 10), 900_000, "SGD", "in", "Retail Receipts (FICTIONAL)", "giro", "SG"
        ),
        Transaction(
            "T-2002-b", _t(8, 11), 400_000, "SGD", "out", "Dockside Foods (FICTIONAL)", "giro", "SG"
        ),
        Transaction(
            "T-2002-c", _t(9, 11), 350_000, "SGD", "out", "Dockside Foods (FICTIONAL)", "giro", "SG"
        ),
    )
    return TransactionWindow(subject=subject, as_of=_AS_OF, transactions=txns, source_id=_WAREHOUSE)


def _loan_repayment_window() -> TransactionWindow:
    """Round-number outflows on the same day each month: a scheduled loan repayment."""
    subject = "Tamarind Property Holdings (FICTIONAL)"
    txns = (
        Transaction(
            "T-2003-a", _t(3, 9), 2_000_000, "SGD", "in", "Rental Income (FICTIONAL)", "giro", "SG"
        ),
        Transaction(
            "T-2003-b", _t(4, 9), 1_500_000, "SGD", "out", "Bank Loan Account", "giro", "SG"
        ),
    )
    return TransactionWindow(subject=subject, as_of=_AS_OF, transactions=txns, source_id=_WAREHOUSE)


def _intragroup_sweep_window() -> TransactionWindow:
    """A treasury sweep between two accounts of the same group: one counterparty, both ways."""
    subject = "Northwind Group Treasury (FICTIONAL)"
    txns = (
        Transaction(
            "T-2004-a",
            _t(6, 17),
            3_000_000,
            "SGD",
            "in",
            "Northwind Operating Co (FICTIONAL)",
            "wire",
            "SG",
        ),
        Transaction(
            "T-2004-b",
            _t(7, 9),
            3_000_000,
            "SGD",
            "out",
            "Northwind Operating Co (FICTIONAL)",
            "wire",
            "SG",
        ),
    )
    return TransactionWindow(subject=subject, as_of=_AS_OF, transactions=txns, source_id=_WAREHOUSE)


def _seasonal_spike_window() -> TransactionWindow:
    """Turnover well above the account's norm, from the account's usual customers."""
    subject = "Lantern Festival Foods (FICTIONAL)"
    txns = (
        Transaction(
            "T-2005-a",
            _t(10, 10),
            1_200_000,
            "SGD",
            "in",
            "Marketplace Co (FICTIONAL)",
            "giro",
            "SG",
        ),
        Transaction(
            "T-2005-b",
            _t(11, 10),
            1_400_000,
            "SGD",
            "in",
            "Marketplace Co (FICTIONAL)",
            "giro",
            "SG",
        ),
        Transaction(
            "T-2005-c",
            _t(12, 15),
            900_000,
            "SGD",
            "out",
            "Dockside Foods (FICTIONAL)",
            "giro",
            "SG",
        ),
    )
    return TransactionWindow(subject=subject, as_of=_AS_OF, transactions=txns, source_id=_WAREHOUSE)


def _single_large_receipt_window() -> TransactionWindow:
    """One large inbound credit that stays put. The size is the only unusual thing about it."""
    subject = "Selat Marine Engineering (FICTIONAL)"
    txns = (
        Transaction(
            "T-2006-a",
            _t(13, 11),
            8_000_000,
            "SGD",
            "in",
            "Shipyard Buyer (FICTIONAL)",
            "wire",
            "SG",
        ),
    )
    return TransactionWindow(subject=subject, as_of=_AS_OF, transactions=txns, source_id=_WAREHOUSE)


def _dormant_reactivation_window() -> TransactionWindow:
    """An account that had been quiet transacts twice with a known counterparty."""
    subject = "Ivory Gate Consulting (FICTIONAL)"
    txns = (
        Transaction(
            "T-2007-a",
            _t(15, 14),
            250_000,
            "SGD",
            "in",
            "Client Retainer (FICTIONAL)",
            "giro",
            "SG",
        ),
        Transaction(
            "T-2007-b",
            _t(20, 14),
            180_000,
            "SGD",
            "out",
            "Office Landlord (FICTIONAL)",
            "giro",
            "SG",
        ),
    )
    return TransactionWindow(subject=subject, as_of=_AS_OF, transactions=txns, source_id=_WAREHOUSE)


def _tax_payment_window() -> TransactionWindow:
    """A single large outflow to a government body, funded from the operating balance."""
    subject = "Bluewater Precision Tools (FICTIONAL)"
    txns = (
        Transaction(
            "T-2008-a",
            _t(18, 9),
            2_500_000,
            "SGD",
            "in",
            "Trade Receipts (FICTIONAL)",
            "giro",
            "SG",
        ),
        Transaction(
            "T-2008-b", _t(21, 9), 1_100_000, "SGD", "out", "Revenue Authority", "giro", "SG"
        ),
    )
    return TransactionWindow(subject=subject, as_of=_AS_OF, transactions=txns, source_id=_WAREHOUSE)


_ALERTS: tuple[Alert, ...] = (
    Alert(
        alert_id="FCC-1001",
        subject="Redwood Timber Trading Pte Ltd (FICTIONAL)",
        narrative=(
            "Monitoring rule flagged repeated round-value outbound wires just below the "
            "reporting threshold. Relationship manager NRIC S1234567D noted; escalation email "
            "sent to mlro@fictional.example."
        ),
        opened=date(2026, 7, 19),
        source_id=_FEED,
        tenant=FIXTURE_TENANT,
        window=_structuring_window(),
    ),
    Alert(
        alert_id="FCC-1002",
        subject="Azure Freight Holdings (FICTIONAL)",
        narrative=(
            "Threshold alert on routine supplier settlement raised from host 192.0.2.10; "
            "no unusual pattern noted."
        ),
        opened=date(2026, 7, 17),
        source_id=_FEED,
        tenant=FIXTURE_TENANT,
        window=_clean_window(),
    ),
    Alert(
        alert_id="FCC-1003",
        subject="Meridian Logistics LLP (FICTIONAL)",
        narrative=(
            "Single large inbound credit immediately dispersed to multiple new payees within "
            "hours; velocity rule and fan-out rule both triggered. Session seen on host "
            "2001:db8::7."
        ),
        opened=date(2026, 7, 20),
        source_id=_FEED,
        tenant=FIXTURE_TENANT,
        window=_mule_window(),
    ),
    Alert(
        alert_id="FCC-1004",
        subject="Coral Bay Enterprises (FICTIONAL)",
        narrative=(
            "Many small inbound credits from unrelated parties consolidated into one payment."
        ),
        opened=date(2026, 7, 16),
        source_id=_FEED,
        tenant=FIXTURE_TENANT,
        window=_funnel_window(),
    ),
    # ---- the suppression corpus: alerts a hand-review says should CLOSE --------------------
    Alert(
        alert_id="FCC-2001",
        subject="Harbourfront Marine Services (FICTIONAL)",
        narrative="Fan-out rule fired on the monthly salary run to eight employees.",
        opened=date(2026, 7, 3),
        source_id=_FEED,
        tenant=FIXTURE_TENANT,
        window=_payroll_window(),
    ),
    Alert(
        alert_id="FCC-2002",
        subject="Kestrel Provisions Pte Ltd (FICTIONAL)",
        narrative="Velocity rule fired on two settlements to the same long-standing supplier.",
        opened=date(2026, 7, 9),
        source_id=_FEED,
        tenant=FIXTURE_TENANT,
        window=_supplier_settlement_window(),
    ),
    Alert(
        alert_id="FCC-2003",
        subject="Tamarind Property Holdings (FICTIONAL)",
        narrative="Round-value rule fired on the scheduled monthly loan repayment.",
        opened=date(2026, 7, 5),
        source_id=_FEED,
        tenant=FIXTURE_TENANT,
        window=_loan_repayment_window(),
    ),
    Alert(
        alert_id="FCC-2004",
        subject="Northwind Group Treasury (FICTIONAL)",
        narrative="Pass-through rule fired on an intra-group treasury sweep, returned next day.",
        opened=date(2026, 7, 8),
        source_id=_FEED,
        tenant=FIXTURE_TENANT,
        window=_intragroup_sweep_window(),
    ),
    Alert(
        alert_id="FCC-2005",
        subject="Lantern Festival Foods (FICTIONAL)",
        narrative="Turnover-deviation rule fired on a seasonal spike from the usual customers.",
        opened=date(2026, 7, 13),
        source_id=_FEED,
        tenant=FIXTURE_TENANT,
        window=_seasonal_spike_window(),
    ),
    Alert(
        alert_id="FCC-2006",
        subject="Selat Marine Engineering (FICTIONAL)",
        narrative="Large-value rule fired on a single inbound credit that was not moved on.",
        opened=date(2026, 7, 14),
        source_id=_FEED,
        tenant=FIXTURE_TENANT,
        window=_single_large_receipt_window(),
    ),
    Alert(
        alert_id="FCC-2007",
        subject="Ivory Gate Consulting (FICTIONAL)",
        narrative="Dormancy rule fired when a quiet account transacted with a known counterparty.",
        opened=date(2026, 7, 16),
        source_id=_FEED,
        tenant=FIXTURE_TENANT,
        window=_dormant_reactivation_window(),
    ),
    Alert(
        alert_id="FCC-2008",
        subject="Bluewater Precision Tools (FICTIONAL)",
        narrative="Large-value rule fired on a single outflow to a government body.",
        opened=date(2026, 7, 22),
        source_id=_FEED,
        tenant=FIXTURE_TENANT,
        window=_tax_payment_window(),
    ),
)

#: Alerts keyed by id, in a stable insertion order (the queue order the feed returns).
ALERTS_BY_ID: dict[str, Alert] = {alert.alert_id: alert for alert in _ALERTS}

#: Transaction windows keyed by subject, for the warehouse adapter.
WINDOWS_BY_SUBJECT: dict[str, TransactionWindow] = {
    alert.subject: alert.window for alert in _ALERTS
}
