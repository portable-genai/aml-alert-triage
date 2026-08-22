"""The deterministic AML typology-and-scoring engine: pure, frozen, replayable.

The consequential outputs (which typologies fired, the risk score, the band and the
close / request-info / escalate-to-SAR recommendation) are ALL produced here, by pure stdlib
arithmetic over bank-owned policy (:class:`~.policy.TriagePolicy`) and typology packs as data
(:class:`~.models.TypologyPack`). **The LLM produces no number and no verdict in this module and
is not imported by it.** Given the same alert, the same packs and the same policy, the whole
:class:`~.models.ScoreCard` is byte-identical, so an investigator can recompute it.

A detector is a pure function ``(window, params) -> (fired, measure, triggering_txn_ids)``. Each
pack names one detector and supplies the thresholds it reads, so no jurisdiction ever branches in
engine code: a bank adds a market by adding a pack, never by editing a function here. The
:func:`signal_key` fingerprint is a stable content hash over the firing transactions, so the same
real-world pattern yields the same key on every run and a re-run diffs exactly.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import timedelta

from .kernel import Citation
from .models import (
    ScoreCard,
    Transaction,
    TransactionWindow,
    TypologyHit,
    TypologyPack,
)
from .policy import TriagePolicy

#: A detector: given the window and its pack params, did the typology fire, what arithmetic
#: fired it (in words, for the narrative), and which transactions triggered it (for the key)?
Detector = Callable[[TransactionWindow, Mapping[str, int]], tuple[bool, str, tuple[str, ...]]]


def signal_key(typology_id: str, subject: str, txn_ids: Sequence[str]) -> str:
    """A stable fingerprint for one fired typology: ``<typology_id>:<16 hex>``.

    The digest is taken over the typology, the normalised subject and the SORTED triggering
    transaction ids, so the same pattern on the same account yields the same key on every run
    while a different set of transactions yields a different one.
    """
    normalised_subject = " ".join(subject.split()).casefold()
    body = "|".join(sorted(txn_ids))
    digest = hashlib.sha256(f"{typology_id}|{normalised_subject}|{body}".encode()).hexdigest()
    return f"{typology_id}:{digest[:16]}"


def _in_txns(window: TransactionWindow) -> tuple[Transaction, ...]:
    return tuple(t for t in window.transactions if t.direction == "in")


def _out_txns(window: TransactionWindow) -> tuple[Transaction, ...]:
    return tuple(t for t in window.transactions if t.direction == "out")


def _detect_structuring(
    window: TransactionWindow, params: Mapping[str, int]
) -> tuple[bool, str, tuple[str, ...]]:
    """Many transfers deliberately sized just under a reporting threshold."""
    threshold = params["threshold_minor"]
    margin = params["margin_minor"]
    min_count = params["min_count"]
    direction = "out" if params.get("direction_out", 1) else "in"
    lo = threshold - margin
    hits = tuple(
        t
        for t in window.transactions
        if t.direction == direction and lo <= t.amount_minor < threshold
    )
    fired = len(hits) >= min_count
    measure = (
        f"{len(hits)} {direction} transfers between {lo} and {threshold} minor units "
        f"(threshold {threshold}, need {min_count})"
    )
    return fired, measure, tuple(t.txn_id for t in hits)


def _detect_rapid_movement(
    window: TransactionWindow, params: Mapping[str, int]
) -> tuple[bool, str, tuple[str, ...]]:
    """Funds arrive and leave again within a short window at a high pass-through ratio."""
    window_hours = params["window_hours"]
    min_ratio_pct = params["min_ratio_pct"]
    min_inflow = params["min_inflow_minor"]
    inflows = _in_txns(window)
    total_in = sum(t.amount_minor for t in inflows)
    if not inflows or total_in < min_inflow:
        return False, f"inflow {total_in} below minimum {min_inflow}", ()
    earliest_in = min(t.ts for t in inflows)
    horizon = earliest_in + timedelta(hours=window_hours)
    passed = tuple(t for t in _out_txns(window) if earliest_in <= t.ts <= horizon)
    out_within = sum(t.amount_minor for t in passed)
    fired = out_within * 100 >= min_ratio_pct * total_in
    ratio = (out_within * 100 // total_in) if total_in else 0
    measure = (
        f"{out_within} of {total_in} minor units moved out within {window_hours}h "
        f"({ratio}% pass-through, need {min_ratio_pct}%)"
    )
    trigger = tuple(t.txn_id for t in inflows) + tuple(t.txn_id for t in passed)
    return fired, measure, trigger


def _detect_funnel_account(
    window: TransactionWindow, params: Mapping[str, int]
) -> tuple[bool, str, tuple[str, ...]]:
    """Many distinct originators pay in, then the balance is consolidated out."""
    min_originators = params["min_originators"]
    min_ratio_pct = params["min_ratio_pct"]
    inflows = _in_txns(window)
    originators = {t.counterparty for t in inflows}
    total_in = sum(t.amount_minor for t in inflows)
    total_out = sum(t.amount_minor for t in _out_txns(window))
    ratio_ok = total_in > 0 and total_out * 100 >= min_ratio_pct * total_in
    fired = len(originators) >= min_originators and ratio_ok
    ratio = (total_out * 100 // total_in) if total_in else 0
    measure = (
        f"{len(originators)} distinct originators paid in (need {min_originators}); "
        f"{ratio}% consolidated out (need {min_ratio_pct}%)"
    )
    return fired, measure, tuple(t.txn_id for t in inflows)


def _detect_mule_fanout(
    window: TransactionWindow, params: Mapping[str, int]
) -> tuple[bool, str, tuple[str, ...]]:
    """One large inflow is fanned out to many beneficiaries in a short window."""
    min_beneficiaries = params["min_beneficiaries"]
    window_hours = params["window_hours"]
    min_inflow = params["min_inflow_minor"]
    inflows = _in_txns(window)
    if not inflows:
        return False, "no inflow to fan out", ()
    largest = max(inflows, key=lambda t: t.amount_minor)
    if largest.amount_minor < min_inflow:
        return False, f"largest inflow {largest.amount_minor} below {min_inflow}", ()
    horizon = largest.ts + timedelta(hours=window_hours)
    fanned = tuple(t for t in _out_txns(window) if largest.ts <= t.ts <= horizon)
    beneficiaries = {t.counterparty for t in fanned}
    fired = len(beneficiaries) >= min_beneficiaries
    measure = (
        f"inflow {largest.amount_minor} fanned to {len(beneficiaries)} beneficiaries "
        f"within {window_hours}h (need {min_beneficiaries})"
    )
    return fired, measure, (largest.txn_id, *(t.txn_id for t in fanned))


#: The pure detector registry. A pack's ``detector`` names one of these; adding a typology KIND
#: (a new shape of pattern) adds a function here, but adding a MARKET only adds a pack file.
DETECTORS: dict[str, Detector] = {
    "structuring": _detect_structuring,
    "rapid_movement": _detect_rapid_movement,
    "funnel_account": _detect_funnel_account,
    "mule_fanout": _detect_mule_fanout,
}


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


@dataclass(frozen=True, slots=True)
class TypologyEngine:
    """Pure, deterministic typology detection, scoring, banding and recommendation."""

    packs: tuple[TypologyPack, ...]
    policy: TriagePolicy = field(default_factory=TriagePolicy)

    def __post_init__(self) -> None:
        for pack in self.packs:
            if pack.detector not in DETECTORS:
                raise ValueError(
                    f"typology pack {pack.typology_id!r} names unknown detector "
                    f"{pack.detector!r}; known detectors are {sorted(DETECTORS)}"
                )

    def assess(self, window: TransactionWindow) -> ScoreCard:
        """Score one transaction window into a :class:`ScoreCard` (pure, replayable)."""
        hits: list[TypologyHit] = []
        for pack in self.packs:
            fired, measure, triggering = DETECTORS[pack.detector](window, pack.params)
            if not fired:
                continue
            hits.append(
                TypologyHit(
                    typology_id=pack.typology_id,
                    signal_key=signal_key(pack.typology_id, window.subject, triggering),
                    title=pack.title,
                    uplift=pack.uplift,
                    measure=measure,
                    citation=pack.citation,
                )
            )
        base = round(self.policy.base_score, 4)
        raw = self.policy.base_score + sum(h.uplift for h in hits)
        score = round(_clamp(raw, 0.0, self.policy.max_score), 4)
        band = self.policy.band_for(score)
        return ScoreCard(
            subject=window.subject,
            base_score=base,
            score=score,
            band=band,
            recommendation=self.policy.recommend(band),
            typology_hits=tuple(hits),
        )

    def hit_citations(self, card: ScoreCard) -> tuple[Citation, ...]:
        """The distinct instrument citations behind the fired typologies (for the assessment)."""
        seen: dict[str, Citation] = {}
        for hit in card.typology_hits:
            seen.setdefault(hit.citation.source_id, hit.citation)
        return tuple(seen.values())
