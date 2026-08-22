"""Local RetrievalPort: a deterministic fixture corpus of typology guidance (no live Hrz2).

Returns cited guidance passages keyed by the typologies that fired. Retrieval informs the
NARRATIVE only, never the score or the band, so this offline corpus changes nothing about the
consequential decision (a test asserts the assessment is identical with retrieval stubbed empty).
"""

from __future__ import annotations

from ...config import Settings
from ...domain.models import RetrievalQuery, RetrievedPassage

#: One cited passage per typology id (obviously paraphrased guidance, not verbatim regulation).
_CORPUS: dict[str, RetrievedPassage] = {
    "structuring": RetrievedPassage(
        source_id="kb:typology/structuring",
        title="Typology note: structuring",
        snippet=(
            "Break-up of a larger sum into multiple sub-threshold transfers to avoid a mandatory "
            "cash-transaction report; corroborate with round-value clustering and timing."
        ),
        score=0.9,
    ),
    "rapid_movement": RetrievedPassage(
        source_id="kb:typology/rapid-movement",
        title="Typology note: rapid movement of funds",
        snippet=(
            "Funds credited and debited within a short window with little economic purpose "
            "indicate pass-through layering; assess pass-through ratio and dwell time."
        ),
        score=0.85,
    ),
    "funnel_account": RetrievedPassage(
        source_id="kb:typology/funnel-account",
        title="Typology note: funnel accounts",
        snippet=(
            "Many dispersed originators funding one account that is then consolidated out is a "
            "third-party layering pattern; check originator diversity and consolidation ratio."
        ),
        score=0.82,
    ),
    "mule_fanout": RetrievedPassage(
        source_id="kb:typology/mule-fanout",
        title="Typology note: money-mule fan-out",
        snippet=(
            "A single large credit rapidly dispersed to multiple unrelated payees is a hallmark "
            "of mule distribution; assess beneficiary count and dispersal speed."
        ),
        score=0.88,
    ),
}


class LocalRetrieval:
    """Serve fixture typology guidance for the SDK-free ``local`` profile."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def retrieve(self, query: RetrievalQuery) -> tuple[RetrievedPassage, ...]:
        hits = [self._CORPUS_get(tid) for tid in query.typology_ids]
        passages = tuple(p for p in hits if p is not None)
        return passages[: query.top_k]

    @staticmethod
    def _CORPUS_get(typology_id: str) -> RetrievedPassage | None:
        return _CORPUS.get(typology_id)
