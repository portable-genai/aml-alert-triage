"""Bank-owned triage policy: the score baseline, the band thresholds and the recommendation map.

These numbers are the client's, not the engine's. They ship here as a frozen dataclass with the
reference defaults, and ``config/settings.yaml`` carries a ``policy:`` block so a bank tightens
its own bands by editing configuration rather than engine code (practices check B4). The engine
takes a :class:`TriagePolicy` by construction and reads every threshold off it; there is no band
number written inline anywhere in ``typology_engine.py``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from .kernel import Severity
from .models import Recommendation

#: Reference band thresholds: the lowest score (inclusive) that reaches each band. The engine
#: walks these most-severe first, so a score at or above ``critical`` bands CRITICAL.
_DEFAULT_BAND_THRESHOLDS: dict[str, float] = {
    "critical": 0.85,
    "high": 0.60,
    "medium": 0.35,
}

#: Reference recommendation per band. ESCALATE_SAR for the two upper bands, REQUEST_INFO for a
#: partial (MEDIUM) signal, CLOSE for LOW. Every one still routes to a human (rule R8).
_DEFAULT_RECOMMENDATIONS: dict[str, str] = {
    "critical": Recommendation.ESCALATE_SAR.value,
    "high": Recommendation.ESCALATE_SAR.value,
    "medium": Recommendation.REQUEST_INFO.value,
    "low": Recommendation.CLOSE.value,
}

_DEFAULT_BASE_SCORE = 0.20
_DEFAULT_MAX_SCORE = 1.0


@dataclass(frozen=True, slots=True)
class TriagePolicy:
    """The adopter-owned numbers the deterministic engine scores against."""

    base_score: float = _DEFAULT_BASE_SCORE
    max_score: float = _DEFAULT_MAX_SCORE
    band_thresholds: Mapping[str, float] = field(
        default_factory=lambda: dict(_DEFAULT_BAND_THRESHOLDS)
    )
    recommendations: Mapping[str, str] = field(
        default_factory=lambda: dict(_DEFAULT_RECOMMENDATIONS)
    )

    def band_for(self, score: float) -> Severity:
        """The severity band a score falls in (thresholds walked most severe first)."""
        if score >= self.band_thresholds["critical"]:
            return Severity.CRITICAL
        if score >= self.band_thresholds["high"]:
            return Severity.HIGH
        if score >= self.band_thresholds["medium"]:
            return Severity.MEDIUM
        return Severity.LOW

    def recommend(self, band: Severity) -> Recommendation:
        """The recommendation for a band (bank-owned map, never a branch in engine code)."""
        return Recommendation(self.recommendations[band.value])

    @classmethod
    def from_mapping(cls, data: Mapping[str, object] | None) -> TriagePolicy:
        """Build from a settings ``policy:`` block, falling back to the reference defaults.

        A block that is present but names only some keys keeps the reference default for the
        rest, so a bank can override one threshold without restating the whole policy.
        """
        if not data:
            return cls()
        bands = data.get("band_thresholds")
        recs = data.get("recommendations")
        base = data.get("base_score")
        top = data.get("max_score")
        merged_bands = dict(_DEFAULT_BAND_THRESHOLDS)
        if isinstance(bands, Mapping):
            merged_bands.update({str(k): float(v) for k, v in bands.items()})
        merged_recs = dict(_DEFAULT_RECOMMENDATIONS)
        if isinstance(recs, Mapping):
            merged_recs.update({str(k): str(v) for k, v in recs.items()})
        return cls(
            base_score=float(base) if base is not None else _DEFAULT_BASE_SCORE,  # type: ignore[arg-type]
            max_score=float(top) if top is not None else _DEFAULT_MAX_SCORE,  # type: ignore[arg-type]
            band_thresholds=merged_bands,
            recommendations=merged_recs,
        )
