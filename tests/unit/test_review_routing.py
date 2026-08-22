"""Rule R8: every outcome is ROUTED to Hrz7, not left in a per-repo boolean.

This is the standing gate for the failure the rule exists to prevent. A repo can set
``requires_human_review = True``, pass every other test, and still auto-execute in practice
because nothing ever reads the flag. So the assertions here are about the ROUTING, not the flag.
In this vertical EVERY outcome is consequential (even a proposed CLOSE needs human sign-off), so
every triage produces an outbound review; the payload leaves redacted, the critical band demands
dual control, and the managed and on-prem placeholders refuse rather than swallowing an escalation.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from aml_alert_triage.adapters.gcp.review_router import CloudReviewRouter
from aml_alert_triage.adapters.local._fixtures import ALERTS_BY_ID
from aml_alert_triage.adapters.local.review_router import LocalReviewRouter
from aml_alert_triage.adapters.onprem.review_router import OnPremReviewRouter
from aml_alert_triage.api.app import app
from aml_alert_triage.config import Settings, build_container
from aml_alert_triage.domain.kernel import Severity
from aml_alert_triage.domain.models import TriageAssessment


def _settings(profile: str = "local") -> Settings:
    return Settings(profile=profile, audit_path=":memory:", tenant="demo-bank")


def _result(alert_id: str) -> TriageAssessment:
    container = build_container(_settings())
    return container.triage_service().triage(ALERTS_BY_ID[alert_id], actor="analyst@bank.example")


def test_an_outcome_produces_an_outbound_review() -> None:
    router = LocalReviewRouter(_settings())
    ref = router.route(_result("FCC-1001"), maker="analyst@bank.example")
    assert ref, "routing must return a reference, so the caller can record where it went"
    pending = router.outbox.pending()
    assert len(pending) == 1
    review = pending[0].review
    assert review.maker == "analyst@bank.example"
    assert review.tenant == "demo-bank"
    assert review.severity == Severity.HIGH.value
    assert review.source_key, "a durable outbox needs an idempotency key"


def test_even_a_low_band_close_is_routed() -> None:
    """Every AML outcome is consequential: a proposed CLOSE still reaches a human."""
    router = LocalReviewRouter(_settings())
    ref = router.route(_result("FCC-1002"), maker="analyst@bank.example")
    assert ref
    assert len(router.outbox.pending()) == 1


def test_a_critical_result_demands_dual_control() -> None:
    router = LocalReviewRouter(_settings())
    router.route(_result("FCC-1003"), maker="analyst@bank.example")
    assert router.outbox.pending()[0].review.required_approvals == 2


def test_the_payload_is_redacted_before_it_leaves_the_process() -> None:
    """Hrz7 is a shared sink; a raw identifier must never reach the wire."""
    router = LocalReviewRouter(_settings())
    router.route(_result("FCC-1001"), maker="analyst@bank.example")
    review = router.outbox.pending()[0].review
    wire = repr(review.to_payload())
    assert "S1234567D" not in wire
    assert "REDACTED" in wire


def test_the_managed_router_refuses_when_no_console_is_configured() -> None:
    """An escalation with nowhere to go must fail loudly, not return as if it were reviewed."""
    router = CloudReviewRouter(Settings(profile="gcp", audit_path=":memory:", review_url=""))
    with pytest.raises(RuntimeError, match="R8"):
        router.route(_result("FCC-1001"), maker="analyst@bank.example")


def test_the_onprem_placeholder_refuses_rather_than_dropping_the_escalation() -> None:
    router = OnPremReviewRouter(_settings("onprem"))
    with pytest.raises(NotImplementedError, match="R8"):
        router.route(_result("FCC-1001"), maker="analyst@bank.example")


def test_the_api_routes_the_outcome_in_the_same_request() -> None:
    """The serving path, not just the adapter: an outcome must not depend on a later job."""
    client = TestClient(app, client=("127.0.0.1", 50000))
    body = client.post(
        "/v1/triage",
        json={"alert_id": "FCC-1001"},
        headers={"X-Dev-Persona": "auditor"},
    ).json()
    assert body["requires_human_review"] is True
    assert body["review_ref"], "an outcome with no routing reference went nowhere"

    low = client.post(
        "/v1/triage",
        json={"alert_id": "FCC-1002"},
        headers={"X-Dev-Persona": "auditor"},
    ).json()
    # Every outcome routes: a proposed close is still human-approved.
    assert low["recommendation"] == "close"
    assert low["review_ref"], "even a low-band close must be routed for human sign-off"
