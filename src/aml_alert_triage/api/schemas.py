"""API request/response schemas (Pydantic) mapped to/from the pure-domain models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from ..domain.models import Alert, TriageAssessment, TypologyHit


class TriageRequest(BaseModel):
    """Triage one alert from the monitoring feed. The caller names an alert; the feed and the
    warehouse supply the rows, so the client never asserts the transactions to be scored."""

    alert_id: str


class CitationModel(BaseModel):
    source_id: str
    title: str
    snippet: str = ""


class TypologyHitModel(BaseModel):
    typology_id: str
    signal_key: str
    title: str
    uplift: float
    measure: str
    citation: CitationModel

    @classmethod
    def from_domain(cls, hit: TypologyHit) -> TypologyHitModel:
        return cls(
            typology_id=hit.typology_id,
            signal_key=hit.signal_key,
            title=hit.title,
            uplift=hit.uplift,
            measure=hit.measure,
            citation=CitationModel(
                source_id=hit.citation.source_id,
                title=hit.citation.title,
                snippet=hit.citation.snippet,
            ),
        )


class TriageResponse(BaseModel):
    alert_id: str
    subject: str
    base_score: float
    score: float
    band: str
    recommendation: str
    narrative: str
    requires_human_review: bool
    #: Where the escalation WENT (rule R8): the human-review-console review id, or the local queue
    #: reference. Empty exactly when ``review_routing`` is not ``routed``.
    review_ref: str = ""
    #: What happened to the hand-off: routed, failed, off or not_required. ``failed`` means the
    #: result is NOT queued for review, and the console says so.
    review_routing: Literal["routed", "failed", "off", "not_required"] = "not_required"
    typology_hits: list[TypologyHitModel] = []
    citations: list[CitationModel] = []

    @classmethod
    def from_domain(
        cls, result: TriageAssessment, *, review_ref: str = "", review_routing: str = "not_required"
    ) -> TriageResponse:
        return cls(
            alert_id=result.alert_id,
            subject=result.subject,
            base_score=result.base_score,
            score=result.score,
            band=result.band.value,
            recommendation=result.recommendation.value,
            narrative=result.narrative,
            requires_human_review=result.requires_human_review,
            review_ref=review_ref,
            review_routing=review_routing,  # type: ignore[arg-type]
            typology_hits=[TypologyHitModel.from_domain(h) for h in result.typology_hits],
            citations=[
                CitationModel(source_id=c.source_id, title=c.title, snippet=c.snippet)
                for c in result.citations
            ],
        )


class AlertSummary(BaseModel):
    """One row of the open-alert queue (``list_alert_queue``): no transactions, no scoring."""

    alert_id: str
    subject: str
    opened: str

    @classmethod
    def from_domain(cls, alert: Alert) -> AlertSummary:
        return cls(alert_id=alert.alert_id, subject=alert.subject, opened=alert.opened.isoformat())


class HealthResponse(BaseModel):
    status: str
    profile: str
    region: str
    #: What the UI's model pill states before any answer (then it shows ``X-Answered-By``):
    #: where the runtime sits and which model the bound generator calls. Both are read off the
    #: service because the browser cannot know either.
    runtime: str = "local"  # "gcp" | "local"
    generator_model: str = "deterministic-offline-stub"
