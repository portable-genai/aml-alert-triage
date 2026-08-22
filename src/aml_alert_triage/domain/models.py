"""Vertical artifact models: the AML alert-triage request and result types.

The artifacts THIS vertical produces, as opposed to the vertical-neutral machinery in
``kernel.py``. The service's own name is deliberately not substituted into this docstring: a
rendered line whose length depends on ``friendly_name`` fails the repo's own format check for no
reason but the length of its name.

Every consequential number on a :class:`ScoreCard` and a :class:`TriageAssessment` is produced by
the pure deterministic engine (``typology_engine.py``), never by a model. A :class:`TypologyPack`
is DATA: the detector name plus adopter-owned thresholds plus the named regulator instrument the
hit cites. The model only narrates the finished assessment, and every claim it makes carries a
:class:`~.kernel.Citation`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime

from hex_service_kit.enums import LenientStrEnum

from .kernel import Citation, Severity


class Recommendation(LenientStrEnum):
    """The disposition the deterministic engine recommends (a human always approves it)."""

    CLOSE = "close"  # no typology fired above the review band
    REQUEST_INFO = "request_info"  # a partial signal: gather more before deciding
    ESCALATE_SAR = "escalate_sar"  # draft a suspicious-activity report for a human to file


@dataclass(frozen=True, slots=True)
class Transaction:
    """One movement in a monitored account (obviously fictional in every fixture).

    ``amount_minor`` is an integer in the currency's minor units (cents), so all arithmetic is
    exact and replayable; a float would make two runs disagree in the last digit.
    """

    txn_id: str
    ts: datetime
    amount_minor: int
    currency: str
    direction: str  # "in" (credit) or "out" (debit)
    counterparty: str
    channel: str
    country: str


@dataclass(frozen=True, slots=True)
class TransactionWindow:
    """The transactions the warehouse returned for one subject over one lookback window."""

    subject: str
    as_of: date
    transactions: tuple[Transaction, ...]
    source_id: str  # the warehouse table/extract the rows were read from (cited, never computed)


@dataclass(frozen=True, slots=True)
class Alert:
    """One monitoring alert to triage: a subject, a free-text narrative and its transactions."""

    alert_id: str
    subject: str
    narrative: str
    opened: date
    source_id: str  # the alert feed the row was read from (cited)
    window: TransactionWindow
    #: The tenant that OWNS this row: the data tag object-level authorization is derived from.
    #: An alert id is a name, not an entitlement, so the feed matches this against the verified
    #: principal's tenant and refuses anything else. Empty means the row predates tagging and
    #: belongs to nobody, so no principal may read it.
    tenant: str = ""


@dataclass(frozen=True, slots=True)
class TypologyPack:
    """A typology as DATA: which detector, its adopter-owned thresholds, and the cited instrument.

    The engine owns the arithmetic; the pack owns the numbers. No jurisdiction ever branches in
    engine code, so a bank tightens a threshold or names a different instrument by editing the
    pack file, never the engine.
    """

    typology_id: str
    title: str
    detector: str  # the pure detector function in ``typology_engine.DETECTORS`` this pack drives
    uplift: float  # the score contribution when the detector fires (bank-owned policy)
    params: Mapping[str, int]
    citation: Citation


@dataclass(frozen=True, slots=True)
class TypologyHit:
    """One fired typology: a stable fingerprint, the score uplift and the cited rationale."""

    typology_id: str
    signal_key: str  # stable content fingerprint, so re-runs diff exactly
    title: str
    uplift: float
    measure: str  # the deterministic arithmetic that fired, in words (for the audit narrative)
    citation: Citation


@dataclass(frozen=True, slots=True)
class ScoreCard:
    """The engine's pure verdict: the arithmetic, the band and the recommendation, no narrative.

    Kept separate from :class:`TriageAssessment` so the deterministic core has a type of its own
    that a test can assert on without a model or a narration port anywhere near it.
    """

    subject: str
    base_score: float
    score: float
    band: Severity
    recommendation: Recommendation
    typology_hits: tuple[TypologyHit, ...] = ()


@dataclass(frozen=True, slots=True)
class RetrievalQuery:
    """A governed-retrieval request: the typologies that fired plus free-text context."""

    text: str
    typology_ids: tuple[str, ...] = ()
    top_k: int = 4


@dataclass(frozen=True, slots=True)
class RetrievedPassage:
    """One cited passage from the typology-guidance corpus (informs narration only)."""

    source_id: str
    title: str
    snippet: str
    score: float = 0.0


@dataclass(frozen=True, slots=True)
class NarrationRequest:
    """Everything the narrator may ground on: the engine figures and the retrieved passages.

    The narrator receives NO raw transaction identifiers and NO subject PII beyond the already
    redaction-safe subject label; it may only restate what the engine computed and cite what
    retrieval returned. That is what makes the groundedness check meaningful.
    """

    subject: str
    band: Severity
    score: float
    recommendation: Recommendation
    typology_hits: tuple[TypologyHit, ...]
    passages: tuple[RetrievedPassage, ...] = ()


@dataclass(frozen=True, slots=True)
class NarrationDraft:
    """The narrator's output: the drafted SAR narrative plus the source ids it grounded on."""

    text: str
    cited_source_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class TriageAssessment:
    """The full triage result: the engine verdict, the cited SAR-narrative draft, always human.

    ``requires_human_review`` is always True: every triage outcome in this vertical is
    consequential decision support and terminates at a human disposition (rule R8), including a
    proposed ``CLOSE``. The system never files a SAR and never closes an alert autonomously.
    """

    alert_id: str
    subject: str
    base_score: float
    score: float
    band: Severity
    recommendation: Recommendation
    narrative: str
    as_of: date
    typology_hits: tuple[TypologyHit, ...] = ()
    requires_human_review: bool = True
    citations: tuple[Citation, ...] = field(default_factory=tuple)
