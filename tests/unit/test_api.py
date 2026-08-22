"""API surface: verified-principal identity, fail-closed S2S, security headers.

The client comes from the shared ``api_client`` fixture, which pins a loopback peer: the
app-object exposure guard refuses the unauthenticated local posture to any other peer, and
TestClient's default peer is the literal host "testclient".
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

_TOKEN_ENV = "AMLTRIAGE_S2S_TOKEN"


def _triage_body(alert_id: str = "FCC-1001") -> dict[str, str]:
    return {"alert_id": alert_id}


def test_triage_uses_the_verified_principal_as_actor(api_client: TestClient) -> None:
    resp = api_client.post(
        "/v1/triage",
        json=_triage_body(),
        headers={"X-Dev-Persona": "auditor"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["band"] == "high"
    assert body["recommendation"] == "escalate_sar"
    assert body["requires_human_review"] is True
    # Rule R8: the outcome was routed, not merely flagged (see test_review_routing.py).
    assert body["review_ref"]
    assert body["typology_hits"], "an escalating result must show which typologies fired"


def test_an_alert_of_another_tenant_is_not_readable(api_client: TestClient) -> None:
    """Object-level authorization: naming an id is not entitlement to the row behind it.

    The verified principal `other-tenant` belongs to `other-bank`. The alert feed took no
    principal at all, so any authenticated caller who knew (or guessed) an alert id received the
    whole alert of another bank, scored it, and had the result routed to a console under their
    own tenant. The refusal is 404 rather than 403: telling the caller that the id exists
    somewhere else is itself a disclosure.
    """
    resp = api_client.post(
        "/v1/triage",
        json=_triage_body("FCC-1001"),
        headers={"X-Dev-Persona": "other-tenant"},
    )
    assert resp.status_code == 404, (
        f"a foreign tenant read the alert: {resp.status_code} {resp.text[:200]}"
    )


def test_the_alert_queue_is_scoped_to_the_principals_tenant(api_client: TestClient) -> None:
    """The queue is a query, and an unscoped query is the same defect with no id to guess."""
    own = api_client.get("/v1/alerts", headers={"X-Dev-Persona": "analyst"})
    other = api_client.get("/v1/alerts", headers={"X-Dev-Persona": "other-tenant"})
    assert own.status_code == 200 and other.status_code == 200
    assert [a["alert_id"] for a in own.json()], "the home tenant must still see its own queue"
    assert other.json() == [], f"a foreign tenant enumerated the queue: {other.json()}"


def test_unknown_persona_is_401(api_client: TestClient) -> None:
    resp = api_client.post(
        "/v1/triage",
        json=_triage_body("FCC-1002"),
        headers={"X-Dev-Persona": "ghost"},
    )
    assert resp.status_code == 401


def test_the_alert_queue_lists_open_alerts(api_client: TestClient) -> None:
    resp = api_client.get("/v1/alerts", headers={"X-Dev-Persona": "auditor"})
    assert resp.status_code == 200
    ids = [row["alert_id"] for row in resp.json()]
    assert "FCC-1001" in ids


def test_healthz_reports_profile_and_region(api_client: TestClient) -> None:
    body = api_client.get("/healthz").json()
    assert body["status"] == "ok"
    assert body["profile"] == "local"
    assert body["region"] == "asia-southeast1"


def test_security_headers_present(api_client: TestClient) -> None:
    headers = api_client.get("/healthz").headers
    assert headers["Content-Security-Policy"] == "frame-ancestors 'self'"
    assert headers["X-Content-Type-Options"] == "nosniff"


@pytest.fixture()
def token_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    monkeypatch.setenv(_TOKEN_ENV, "s3cret-service-token")
    yield "s3cret-service-token"


def test_s2s_endpoint_open_when_secret_unset(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(_TOKEN_ENV, raising=False)
    assert api_client.post("/v1/audit/ping").status_code == 200


def test_s2s_endpoint_rejects_missing_token_when_enforced(
    api_client: TestClient, token_env: str
) -> None:
    assert api_client.post("/v1/audit/ping").status_code == 401


def test_s2s_endpoint_accepts_correct_token(api_client: TestClient, token_env: str) -> None:
    resp = api_client.post("/v1/audit/ping", headers={"Authorization": f"Bearer {token_env}"})
    assert resp.status_code == 200
