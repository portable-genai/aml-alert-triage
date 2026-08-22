"""The AML triage orchestrator: deterministic score, grounded narration, redact-before-audit, R8.

The order mirrors the reference build (``complaints-review`` ``review_service.py``):
score with the pure engine, retrieve governed guidance (narration only), draft the SAR narrative
with the model, VALIDATE that draft against the engine figures and discard it on failure, redact
before the audit write, and return an assessment that ALWAYS requires human review. The routing
to Hrz7 (rule R8) happens on the calling surface (``api``/``cli``/``agent``), in the same call
that produced the result, exactly as the template wires it.

The consequential outputs are the engine's: this service never produces a score, a band or a
recommendation, and the model it calls produces none either. The model only drafts prose, and a
drafted number the engine did not compute is discarded with the whole draft.
"""

from __future__ import annotations

from pii_kit import redact

from ..ports.audit import AuditSinkPort
from ..ports.narration import NarrationPort
from ..ports.observability import ObservabilityTracerPort
from ..ports.retrieval import RetrievalPort
from .grounding import grounded_skeleton, ungrounded_numbers
from .kernel import AuditEvent, Citation, Decision, utcnow
from .models import (
    Alert,
    NarrationDraft,
    NarrationRequest,
    RetrievalQuery,
    RetrievedPassage,
    ScoreCard,
    TriageAssessment,
)
from .pii import PII_PATTERNS
from .typology_engine import TypologyEngine

#: One span per triaged alert. Structural attributes only: see :meth:`TriageService.triage`.
_TRIAGE_SPAN = "aml_triage.triage"


class TriageService:
    """Score, ground, narrate and audit one alert; every outcome routes to a human."""

    def __init__(
        self,
        engine: TypologyEngine,
        retrieval: RetrievalPort,
        narration: NarrationPort,
        audit: AuditSinkPort,
        *,
        tracer: ObservabilityTracerPort,
    ) -> None:
        self._engine = engine
        self._retrieval = retrieval
        self._narration = narration
        self._audit = audit
        self._tracer = tracer

    def triage(self, alert: Alert, *, actor: str) -> TriageAssessment:
        """Triage one alert end to end, inside one span.

        The span's attributes are STRUCTURAL only: the action, the actor and the alert feed,
        never the subject, the alert narrative or the drafted narrative. A trace backend is not
        the WORM audit trail: it has no redaction stage, a wider read audience and no retention
        rule written against a regulator's requirement, so anything content-shaped that reaches
        a span has left the boundary the redact-before-audit call exists to hold, and left it
        silently.
        """
        with self._tracer.span(
            _TRIAGE_SPAN,
            action="triage",
            actor=actor,
            source=alert.source_id,
        ):
            card = self._engine.assess(alert.window)
            passages = self._retrieve(card)
            # Mask the subject HERE, where the feed's row crosses out of the intake edge, so
            # every sink downstream is covered once instead of each remembering separately. An
            # alert on a natural person carries the name and the national id in this field, and
            # it went to the narrator verbatim: the narrative is free text the alert supplied,
            # not a figure the engine computed, and P-04 is about what the model READS as much
            # as about what the record keeps.
            redacted_subject = redact(alert.subject, PII_PATTERNS)
            request = NarrationRequest(
                subject=redacted_subject,
                band=card.band,
                score=card.score,
                recommendation=card.recommendation,
                typology_hits=card.typology_hits,
                passages=passages,
            )
            draft = self._grounded_draft(request)
            citations = self._citations(alert, card, passages)

            summary = (
                f"{redacted_subject}: alert {alert.alert_id} scored {card.score} "
                f"({card.band.value}); recommend {card.recommendation.value}"
            )
            # Redact BEFORE the audit write: no raw identifier from the alert narrative or the
            # drafted text reaches the WORM record.
            self._audit.record(
                AuditEvent(
                    action="triage",
                    actor=actor,
                    decision=Decision.ESCALATED,  # every outcome routes to a human (rule R8)
                    severity=card.band,
                    redacted_summary=redact(
                        f"{summary} :: {alert.narrative} :: {draft.text}", PII_PATTERNS
                    ),
                    citations=citations,
                    timestamp=utcnow(),
                )
            )
            return TriageAssessment(
                alert_id=alert.alert_id,
                subject=alert.subject,
                base_score=card.base_score,
                score=card.score,
                band=card.band,
                recommendation=card.recommendation,
                narrative=draft.text,
                as_of=alert.window.as_of,
                typology_hits=card.typology_hits,
                requires_human_review=True,
                citations=citations,
            )

    def _retrieve(self, card: ScoreCard) -> tuple[RetrievedPassage, ...]:
        """Retrieve governed guidance for the fired typologies (informs the narrative only)."""
        if not card.typology_hits:
            return ()
        query = RetrievalQuery(
            text="; ".join(hit.title for hit in card.typology_hits),
            typology_ids=tuple(hit.typology_id for hit in card.typology_hits),
        )
        return tuple(self._retrieval.retrieve(query))

    def _grounded_draft(self, request: NarrationRequest) -> NarrationDraft:
        """Draft with the model, then DISCARD it unless it is grounded in the engine figures.

        Two ways a draft is rejected: a numeric token the engine did not compute (an invented
        figure), or a cited source id that was not offered to the narrator. Either discards the
        whole draft in favour of the deterministic skeleton, so a triage never ships a number the
        engine did not produce, and never waits on the model to be available.
        """
        available = {passage.source_id for passage in request.passages}
        available |= {hit.citation.source_id for hit in request.typology_hits}
        try:
            draft = self._narration.narrate(request)
        except Exception:
            return grounded_skeleton(request)
        if ungrounded_numbers(draft.text, request):
            return grounded_skeleton(request)
        if not set(draft.cited_source_ids) <= available:
            return grounded_skeleton(request)
        return draft

    @staticmethod
    def _citations(
        alert: Alert, card: ScoreCard, passages: tuple[RetrievedPassage, ...]
    ) -> tuple[Citation, ...]:
        """The distinct citations behind the assessment: alert, instruments and guidance."""
        out: list[Citation] = [
            Citation(
                source_id=f"alert:{alert.alert_id}",
                title="Monitoring alert",
                snippet=f"opened {alert.opened.isoformat()} from {alert.source_id}",
            ),
            Citation(
                # The originating narrative, REDACTED in the domain so no raw identifier ever
                # travels on this citation, whether it goes to the audit sink, the API caller or
                # the outbound Hrz7 review.
                source_id=f"narrative:{alert.alert_id}",
                title="Alert narrative",
                snippet=redact(alert.narrative, PII_PATTERNS),
            ),
            Citation(
                source_id=alert.window.source_id,
                title="Transaction window",
                snippet=f"{len(alert.window.transactions)} transactions as of "
                f"{alert.window.as_of.isoformat()}",
            ),
        ]
        seen = {c.source_id for c in out}
        for hit in card.typology_hits:
            if hit.citation.source_id not in seen:
                out.append(hit.citation)
                seen.add(hit.citation.source_id)
        for passage in passages:
            if passage.source_id not in seen:
                out.append(
                    Citation(
                        source_id=passage.source_id, title=passage.title, snippet=passage.snippet
                    )
                )
                seen.add(passage.source_id)
        return tuple(out)
