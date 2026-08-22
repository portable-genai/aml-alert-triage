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
)

#: Alerts keyed by id, in a stable insertion order (the queue order the feed returns).
ALERTS_BY_ID: dict[str, Alert] = {alert.alert_id: alert for alert in _ALERTS}

#: Transaction windows keyed by subject, for the warehouse adapter.
WINDOWS_BY_SUBJECT: dict[str, TransactionWindow] = {
    alert.subject: alert.window for alert in _ALERTS
}
