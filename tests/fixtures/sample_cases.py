"""Canonical synthetic alerts, shared by the unit and contract suites.

Every party is obviously fictional and every address is an ``.example`` domain or an RFC 5737 /
RFC 3849 literal. One canonical escalating alert (structuring, bands HIGH) and one canonical
routine alert (nothing fires, bands LOW) are enough for the contract suite: parity means the SAME
request through every implementation, so the request has to have one home rather than being
retyped per test.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from aml_alert_triage.domain.models import Alert, Transaction, TransactionWindow

#: The verified principal the tests attribute work to (never a client-asserted actor).
ACTOR = "analyst@bank.example"

#: A tenant partition, so the outbound-review assertions are not all on the empty string.
TENANT = "demo-bank"

#: A planted identifier, so a redaction assertion has an independent literal to look for
#: rather than trusting the pattern pack to agree with itself. Checksum-valid so it is masked.
PLANTED_NRIC = "S1234567D"

_AS_OF = date(2026, 8, 1)
_WAREHOUSE = "warehouse:test.windows"
_FEED = "feed:test.alerts"


def _ts(day: int, hour: int) -> datetime:
    return datetime(2026, 7, day, hour, 0, tzinfo=UTC)


def _structuring_window(subject: str) -> TransactionWindow:
    txns = (
        Transaction("S-a", _ts(10, 9), 900000, "SGD", "out", "Kestrel (FICTIONAL)", "wire", "SG"),
        Transaction("S-b", _ts(12, 10), 950000, "SGD", "out", "Kestrel (FICTIONAL)", "wire", "SG"),
        Transaction("S-c", _ts(15, 11), 990000, "SGD", "out", "Harbour (FICTIONAL)", "wire", "SG"),
    )
    return TransactionWindow(subject=subject, as_of=_AS_OF, transactions=txns, source_id=_WAREHOUSE)


def _clean_window(subject: str) -> TransactionWindow:
    txns = (
        Transaction("C-a", _ts(11, 9), 100000, "SGD", "in", "Blue Ridge (FICTIONAL)", "wire", "SG"),
    )
    return TransactionWindow(subject=subject, as_of=_AS_OF, transactions=txns, source_id=_WAREHOUSE)


#: An alert that MUST escalate: structuring fires, the deterministic band is HIGH, so rule R8
#: routing applies.
ESCALATING_ALERT = Alert(
    alert_id="TEST-HIGH",
    subject="Acme Holdings (FICTIONAL)",
    narrative="Repeated round-value outbound wires just below the reporting threshold.",
    opened=date(2026, 7, 20),
    source_id=_FEED,
    window=_structuring_window("Acme Holdings (FICTIONAL)"),
)

#: An alert that bands LOW: nothing fires. Every outcome still routes to a human (rule R8), so
#: "routine" here means the recommendation is CLOSE, not that routing is skipped.
ROUTINE_ALERT = Alert(
    alert_id="TEST-LOW",
    subject="Beta Trading (FICTIONAL)",
    narrative="Routine supplier settlement; no unusual pattern noted.",
    opened=date(2026, 7, 18),
    source_id=_FEED,
    window=_clean_window("Beta Trading (FICTIONAL)"),
)

#: A second planted identifier, in an ordinary place for one: an alert on a NATURAL PERSON, whose
#: subject key is a name and an id rather than a company. The narrative and the subject reach
#: different sinks, so a redaction proof that only plants in the narrative cannot see the other.
PLANTED_EMAIL = "wei.ming.tan@fictional.example"

#: An escalating alert whose SUBJECT carries personal data, for the redact-before-anything proofs.
PII_SUBJECT_ALERT = Alert(
    alert_id="TEST-PII-SUBJECT",
    subject=f"Tan Wei Ming (FICTIONAL) NRIC {PLANTED_NRIC}, {PLANTED_EMAIL}",
    narrative="Structuring pattern on a personal account; no further detail on file.",
    opened=date(2026, 7, 19),
    source_id=_FEED,
    window=_structuring_window(f"Tan Wei Ming (FICTIONAL) NRIC {PLANTED_NRIC}"),
)

#: An escalating alert that also carries personal data, for the redact-before-anything proofs.
PII_ALERT = Alert(
    alert_id="TEST-PII",
    subject="Gamma LLP (FICTIONAL)",
    narrative=(
        f"Structuring pattern; relationship manager NRIC {PLANTED_NRIC}, mail ops@gamma.example."
    ),
    opened=date(2026, 7, 19),
    source_id=_FEED,
    window=_structuring_window("Gamma LLP (FICTIONAL)"),
)
