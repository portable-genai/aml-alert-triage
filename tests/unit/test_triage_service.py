"""The deterministic AML triage: engine bands, always-human disposition, redact-before-audit.

The consequential outputs (score, band, recommendation, which typologies fired) come from the
pure engine and are asserted here directly; the orchestrator adds grounded narration,
redact-before-audit and the always-human flag. Two slice proofs live here too: the assessment is
identical with retrieval stubbed empty (retrieval informs narration only), and a narrator that
invents a figure is discarded in favour of the deterministic skeleton.
"""

from __future__ import annotations

import json
from dataclasses import asdict

from aml_alert_triage.adapters._review_payload import result_to_review
from aml_alert_triage.adapters.local._fixtures import ALERTS_BY_ID
from aml_alert_triage.config import Settings, build_container
from aml_alert_triage.domain.kernel import Decision, Severity
from aml_alert_triage.domain.models import (
    NarrationDraft,
    NarrationRequest,
    Recommendation,
    RetrievalQuery,
    RetrievedPassage,
)
from aml_alert_triage.domain.policy import TriagePolicy
from aml_alert_triage.domain.triage_service import TriageService
from aml_alert_triage.domain.typology_engine import TypologyEngine
from aml_alert_triage.typology_packs import load_packs

from tests.conftest import local_settings
from tests.fixtures import sample_cases


def _engine() -> TypologyEngine:
    return TypologyEngine(packs=load_packs(), policy=TriagePolicy())


def _assess(alert_id: str):
    return _engine().assess(ALERTS_BY_ID[alert_id].window)


def test_bands_and_recommendations_are_deterministic() -> None:
    high = _assess("FCC-1001")  # structuring only
    assert high.band is Severity.HIGH
    assert high.recommendation is Recommendation.ESCALATE_SAR
    assert [h.typology_id for h in high.typology_hits] == ["structuring"]

    low = _assess("FCC-1002")  # nothing fires
    assert low.band is Severity.LOW
    assert low.recommendation is Recommendation.CLOSE
    assert low.typology_hits == ()

    critical = _assess("FCC-1003")  # rapid movement + mule fan-out
    assert critical.band is Severity.CRITICAL
    assert critical.recommendation is Recommendation.ESCALATE_SAR
    assert {h.typology_id for h in critical.typology_hits} == {"rapid_movement", "mule_fanout"}

    medium = _assess("FCC-1004")  # funnel account only
    assert medium.band is Severity.MEDIUM
    assert medium.recommendation is Recommendation.REQUEST_INFO


def test_the_score_is_base_plus_uplifts_clamped() -> None:
    card = _assess("FCC-1003")
    assert card.base_score == 0.20
    # base 0.20 + rapid 0.35 + mule 0.40 = 0.95, clamped below max 1.0.
    assert card.score == 0.95


def test_the_signal_key_is_stable_across_runs() -> None:
    first = _assess("FCC-1001").typology_hits[0].signal_key
    second = _assess("FCC-1001").typology_hits[0].signal_key
    assert first == second and first.startswith("structuring:")


def test_every_outcome_requires_human_review_even_a_close() -> None:
    """A proposed CLOSE is still consequential decision support: it routes to a human (R8)."""
    service = build_container(local_settings()).triage_service()
    low = service.triage(ALERTS_BY_ID["FCC-1002"], actor=sample_cases.ACTOR)
    assert low.recommendation is Recommendation.CLOSE
    assert low.requires_human_review is True


def test_pii_is_redacted_before_the_audit_write() -> None:
    container = build_container(Settings(profile="local", audit_path=":memory:"))
    audit = container.audit
    container.triage_service().triage(sample_cases.PII_ALERT, actor=sample_cases.ACTOR)
    records = audit.log.read_all()  # type: ignore[attr-defined]
    assert records, "an audit event should have been recorded"
    summary = records[-1]["redacted_summary"]
    assert sample_cases.PLANTED_NRIC not in summary
    assert "REDACTED" in summary
    assert records[-1]["actor"] == sample_cases.ACTOR
    assert records[-1]["decision"] == Decision.ESCALATED.value
    assert audit.log.verify_chain().ok  # type: ignore[attr-defined]


def test_no_planted_identifier_reaches_the_model_the_worm_record_or_the_console() -> None:
    """The three sinks, one test: what the model reads, what the WORM record keeps, what leaves.

    The planted identifiers are in the alert SUBJECT, which is where an alert on a natural person
    carries them. The subject took a different route from the narrative: the narrative was masked
    on its way into the citation and the summary, while the subject went to ``NarrationRequest``
    verbatim, so the model read the raw national id of the person under investigation.
    """
    seen: list[NarrationRequest] = []
    container = build_container(Settings(profile="local", audit_path=":memory:"))
    service = container.triage_service()
    inner = service._narration  # noqa: SLF001 - tapping the port is the point of the test

    class _Tap:
        def narrate(self, request: NarrationRequest) -> NarrationDraft:
            seen.append(request)
            return inner.narrate(request)

    service._narration = _Tap()  # type: ignore[assignment]  # noqa: SLF001
    result = service.triage(sample_cases.PII_SUBJECT_ALERT, actor=sample_cases.ACTOR)
    planted = (sample_cases.PLANTED_NRIC, sample_cases.PLANTED_EMAIL)

    # 1. The model. Every field of the request, not only the ones somebody remembered to mask.
    assert seen, "the narrator must have been called"
    read_by_model = json.dumps(asdict(seen[-1]), default=str)
    for token in planted:
        assert token not in read_by_model, f"{token} reached the model in {read_by_model!r}"

    # 2. The WORM record. Content fields only: `actor` is the verified principal and is an
    #    address by design, so scanning it would make this unfailable in the wrong direction.
    rows = [dict(row) for row in container.audit.log.read_all()]
    assert rows
    for row in rows:
        stored = row["redacted_summary"] + json.dumps(row["citations"], default=str)
        for token in planted:
            assert token not in stored, f"{token} survived into the WORM record: {stored!r}"

    # 3. What LEAVES for the review console (rule R8), locator and source key included.
    outbound = json.dumps(
        asdict(result_to_review(result, maker=sample_cases.ACTOR, tenant=sample_cases.TENANT)),
        default=str,
    )
    for token in planted:
        assert token not in outbound, f"{token} left for human-review-console in {outbound!r}"


def test_the_assessment_is_identical_with_retrieval_stubbed_empty() -> None:
    """Retrieval informs the NARRATIVE only; it must not move the score, band or recommendation."""
    engine = _engine()
    container = build_container(local_settings())

    class _EmptyRetrieval:
        def retrieve(self, query: RetrievalQuery) -> tuple[RetrievedPassage, ...]:
            return ()

    class _Skeleton:
        def narrate(self, request: NarrationRequest) -> NarrationDraft:
            from aml_alert_triage.domain.grounding import grounded_skeleton

            return grounded_skeleton(request)

    with_retrieval = (
        build_container(local_settings())
        .triage_service()
        .triage(ALERTS_BY_ID["FCC-1001"], actor=sample_cases.ACTOR)
    )
    without = TriageService(
        engine, _EmptyRetrieval(), _Skeleton(), container.audit, tracer=container.tracer
    ).triage(ALERTS_BY_ID["FCC-1001"], actor=sample_cases.ACTOR)
    assert without.score == with_retrieval.score
    assert without.band == with_retrieval.band
    assert without.recommendation == with_retrieval.recommendation
    assert [h.signal_key for h in without.typology_hits] == [
        h.signal_key for h in with_retrieval.typology_hits
    ]


def test_a_narrator_that_invents_a_number_is_discarded() -> None:
    """Groundedness: a figure the engine never computed discards the whole draft (slice 4)."""
    engine = _engine()
    container = build_container(local_settings())

    class _LyingNarrator:
        def narrate(self, request: NarrationRequest) -> NarrationDraft:
            # 4242 is not any engine figure for this alert: the whole draft must be discarded.
            return NarrationDraft(text="Fabricated total of 4242 units moved.", cited_source_ids=())

    result = TriageService(
        engine, _stub_retrieval(), _LyingNarrator(), container.audit, tracer=container.tracer
    ).triage(ALERTS_BY_ID["FCC-1001"], actor=sample_cases.ACTOR)
    assert "4242" not in result.narrative
    # The deterministic skeleton restates a real engine figure instead.
    assert "0.65" in result.narrative


def _stub_retrieval():
    class _R:
        def retrieve(self, query: RetrievalQuery) -> tuple[RetrievedPassage, ...]:
            return ()

    return _R()
