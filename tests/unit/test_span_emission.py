"""The triage path opens ONE span, and that span carries no content.

A trace backend is not the WORM audit trail. It has no redaction stage, no retention policy
written against a regulator's requirement, and a far wider read audience than the audit store.
So the value of tracing the triage path depends entirely on the span carrying structural
attributes only: which action, whose, which alert feed, how long. A subject name, an alert
narrative or the drafted SAR text reaching a span has left the boundary that the
redact-before-audit call exists to hold, and it has left it silently.

The content case drives the alert whose narrative carries a planted NRIC, so the check runs
against input that would actually leak if any attribute were content-shaped.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest

from aml_alert_triage.config import build_container
from aml_alert_triage.domain.models import Alert, TriageAssessment
from aml_alert_triage.domain.triage_service import TriageService

from tests.conftest import local_settings
from tests.fixtures import sample_cases

#: Every attribute key the triage span is allowed to carry. A verdict that started explaining
#: itself on the span (a band, a subject, a narrative fragment) would widen this set, which is
#: the point of asserting on the set rather than on the individual keys.
_TRIAGE_KEYS = {"action", "actor", "source"}


class _RecordingTracer:
    """Captures every span name and attribute so the test can inspect what was emitted."""

    def __init__(self) -> None:
        self.spans: list[tuple[str, dict[str, str]]] = []

    @contextmanager
    def span(self, name: str, **attributes: str) -> Iterator[None]:
        self.spans.append((name, dict(attributes)))
        yield

    def record_token_usage(self, usage: object, model: str) -> None:
        return None


def _triage(alert: Alert) -> tuple[_RecordingTracer, TriageAssessment]:
    """The REAL local adapters for every port except the tracer under inspection."""
    container = build_container(local_settings())
    tracer = _RecordingTracer()
    service = TriageService(
        container.build_engine(),
        container.retrieval,
        container.narration,
        container.audit,
        tracer=tracer,
    )
    result = service.triage(alert, actor=sample_cases.ACTOR)
    return tracer, result


def _emitted(tracer: _RecordingTracer) -> str:
    """Every span name, attribute KEY and attribute VALUE, as one searchable blob."""
    parts: list[str] = []
    for name, attributes in tracer.spans:
        parts.append(name)
        parts.extend(attributes)
        parts.extend(attributes.values())
    return " ".join(parts)


def test_triaging_one_alert_opens_exactly_one_named_span() -> None:
    tracer, _ = _triage(sample_cases.ROUTINE_ALERT)
    assert [name for name, _ in tracer.spans] == ["aml_triage.triage"]


def test_the_span_carries_the_structural_attributes_an_operator_needs() -> None:
    """Enough to answer "whose triage is slow, and on which alert feed", and nothing more."""
    tracer, _ = _triage(sample_cases.ROUTINE_ALERT)
    _, attributes = tracer.spans[0]
    assert attributes["action"] == "triage"
    assert attributes["actor"] == sample_cases.ACTOR
    assert attributes["source"] == sample_cases.ROUTINE_ALERT.source_id


@pytest.mark.parametrize(
    "alert",
    [sample_cases.ROUTINE_ALERT, sample_cases.ESCALATING_ALERT, sample_cases.PII_ALERT],
    ids=["close", "escalate", "pii"],
)
def test_the_attribute_set_is_a_fixed_allowlist_whatever_the_verdict(alert: Alert) -> None:
    """An escalating alert must not start attaching its findings to the span to explain itself."""
    tracer, _ = _triage(alert)
    for _, attributes in tracer.spans:
        assert set(attributes) == _TRIAGE_KEYS


def test_no_span_attribute_carries_alert_content_or_the_planted_identifier() -> None:
    """The alert used here has an NRIC planted in its narrative, so a leak would show."""
    tracer, result = _triage(sample_cases.PII_ALERT)
    emitted = _emitted(tracer)

    forbidden: list[str] = [
        sample_cases.PLANTED_NRIC,
        sample_cases.PII_ALERT.narrative,
        sample_cases.PII_ALERT.subject,
        sample_cases.PII_ALERT.alert_id,
        "ops@gamma.example",
        # The drafted SAR narrative is the other content-shaped value in reach of this call.
        result.narrative,
    ]
    for literal in forbidden:
        assert literal, "an empty needle would pass this test for the wrong reason"
        assert literal not in emitted, f"a span attribute carried {literal!r}"
        assert literal.lower() not in emitted.lower(), f"a span attribute carried {literal!r}"

    # Belt and braces: no distinctive token of the free-text narrative appears either, so a
    # truncated or reformatted fragment cannot slip through the whole-string check above.
    narrative_tokens = {
        token
        for token in sample_cases.PII_ALERT.narrative.replace(",", " ").split()
        if len(token) > 6
    }
    emitted_tokens = set(emitted.lower().split())
    assert not {t.lower() for t in narrative_tokens} & emitted_tokens


def test_every_emitted_attribute_value_is_a_string_the_port_declares() -> None:
    """``span(name, **attributes: str)``: a non-string would serialise however the SDK felt."""
    tracer, _ = _triage(sample_cases.ESCALATING_ALERT)
    values: list[Any] = [v for _, attributes in tracer.spans for v in attributes.values()]
    assert values
    assert all(isinstance(value, str) for value in values)
