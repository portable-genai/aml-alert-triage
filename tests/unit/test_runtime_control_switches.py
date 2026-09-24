"""Review routing has a switch, default on, and every caller says what happened to a hand-off.

The fleet's runtime-control contract (2026-09-24). Review routing is the one cheap runtime
control this service has: ``AMLTRIAGE_REVIEW_ROUTING`` is read in three states; off binds a
disabled router and says so at startup; on under the managed profile refuses to boot without a
console; and the API, the agent tool and the CLI report ``review_routing`` rather than failing
an already-scored triage when the console is unreachable.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from aml_alert_triage.adapters.controls import (
    DisabledReviewRouter,
    RecordingReviewRouter,
    ReviewRouting,
)
from aml_alert_triage.adapters.local._fixtures import ALERTS_BY_ID
from aml_alert_triage.agent import tools
from aml_alert_triage.api import app as api_module
from aml_alert_triage.api.app import app
from aml_alert_triage.config import (
    REVIEW_ROUTING_ENV,
    Container,
    ControlSwitches,
    Settings,
    build_container,
    warn_switched_off,
)
from aml_alert_triage.domain.models import TriageAssessment
from aml_alert_triage.envread import ConfiguredEmptyError

_LOOPBACK = ("127.0.0.1", 50000)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.delenv(REVIEW_ROUTING_ENV, raising=False)
    monkeypatch.delenv("HUMAN_REVIEW_URL", raising=False)
    # The API caches its container for the process; each test here states its own posture.
    api_module._container.cache_clear()
    yield
    api_module._container.cache_clear()


def _result(alert_id: str = "FCC-1001") -> TriageAssessment:
    settings = Settings(profile="local", audit_path=":memory:", tenant="demo-bank")
    return (
        build_container(settings)
        .triage_service()
        .triage(ALERTS_BY_ID[alert_id], actor="analyst@bank.example")
    )


# --------------------------------------------------------------------------- #
# Three states
# --------------------------------------------------------------------------- #
def test_routing_is_on_when_nothing_is_said() -> None:
    assert Settings.load().controls == ControlSwitches(review_routing=True)


def test_routing_switched_off_is_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(REVIEW_ROUTING_ENV, "off")
    assert Settings.load().controls.switched_off() == (REVIEW_ROUTING_ENV,)


def test_an_emptied_switch_refuses_at_load(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(REVIEW_ROUTING_ENV, "")
    with pytest.raises(ConfiguredEmptyError, match=REVIEW_ROUTING_ENV):
        Settings.load()


def test_an_unrecognised_switch_refuses_at_load(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(REVIEW_ROUTING_ENV, "sometimes")
    with pytest.raises(ValueError, match=REVIEW_ROUTING_ENV):
        Settings.load()


# --------------------------------------------------------------------------- #
# Off binds the disabled router, and says so once
# --------------------------------------------------------------------------- #
def test_off_binds_the_disabled_router() -> None:
    settings = Settings(profile="local", controls=ControlSwitches(review_routing=False))
    assert isinstance(Container(settings).review_router, DisabledReviewRouter)


def test_on_binds_the_profile_router() -> None:
    settings = Settings(profile="local")
    assert not isinstance(Container(settings).review_router, DisabledReviewRouter)


def test_the_off_posture_is_logged_once_however_many_containers(
    caplog: pytest.LogCaptureFixture,
) -> None:
    warn_switched_off.cache_clear()
    settings = Settings(profile="local", controls=ControlSwitches(review_routing=False))
    with caplog.at_level(logging.WARNING, logger="aml_alert_triage.config"):
        for _ in range(3):
            build_container(settings)
    assert caplog.text.count(REVIEW_ROUTING_ENV) == 1


# --------------------------------------------------------------------------- #
# On has to work: checked at boot under the managed profile
# --------------------------------------------------------------------------- #
def test_routing_on_under_gcp_without_a_console_refuses_at_boot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "aml_alert_triage.config.resolve_profile",
        lambda environ=None: _choice("gcp"),
    )
    with pytest.raises(ConfiguredEmptyError, match="HUMAN_REVIEW_URL"):
        Settings.load()


def test_routing_stated_off_under_gcp_needs_no_console(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "aml_alert_triage.config.resolve_profile",
        lambda environ=None: _choice("gcp"),
    )
    monkeypatch.setenv(REVIEW_ROUTING_ENV, "false")
    assert Settings.load().controls.review_routing is False


def test_routing_on_under_gcp_with_a_console_loads(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "aml_alert_triage.config.resolve_profile",
        lambda environ=None: _choice("gcp"),
    )
    monkeypatch.setenv("HUMAN_REVIEW_URL", "https://review.example.test")
    assert Settings.load().review_url == "https://review.example.test"


def _choice(profile: str):  # type: ignore[no-untyped-def]
    from aml_alert_triage.config import ProfileChoice

    return ProfileChoice(profile, True)


# --------------------------------------------------------------------------- #
# The four routing outcomes
# --------------------------------------------------------------------------- #
class _Accepting:
    def route(self, result: TriageAssessment, *, maker: str, tenant: str = "") -> str:
        return "review-1"


class _Refusing:
    def route(self, result: TriageAssessment, *, maker: str, tenant: str = "") -> str:
        raise ConnectionError("console unreachable")


def test_routing_outcomes_take_each_of_their_four_values() -> None:
    result = _result()

    assert RecordingReviewRouter(_Accepting()).outcome is ReviewRouting.NOT_REQUIRED

    routed = RecordingReviewRouter(_Accepting())
    assert routed.route(result, maker="m") == "review-1"
    assert routed.outcome is ReviewRouting.ROUTED

    off = RecordingReviewRouter(DisabledReviewRouter(Settings()))
    assert off.route(result, maker="m") == ""
    assert off.outcome is ReviewRouting.OFF


def test_a_failed_hand_off_is_reported_and_logged_never_raised(
    caplog: pytest.LogCaptureFixture,
) -> None:
    failed = RecordingReviewRouter(_Refusing())
    with caplog.at_level(logging.WARNING, logger="aml_alert_triage.adapters.controls"):
        assert failed.route(_result(), maker="m") == ""
    assert failed.outcome is ReviewRouting.FAILED
    assert "ConnectionError" in caplog.text


# --------------------------------------------------------------------------- #
# Every caller reports it: the API, the agent tool, the CLI
# --------------------------------------------------------------------------- #
def _triage(client: TestClient) -> dict[str, object]:
    return client.post(
        "/v1/triage", json={"alert_id": "FCC-1001"}, headers={"X-Dev-Persona": "auditor"}
    ).json()


def test_the_api_reports_a_routed_hand_off() -> None:
    body = _triage(TestClient(app, client=_LOOPBACK))
    assert body["review_routing"] == "routed"
    assert body["review_ref"]


def test_the_api_reports_routing_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(REVIEW_ROUTING_ENV, "off")
    body = _triage(TestClient(app, client=_LOOPBACK))
    assert body["review_routing"] == "off"
    assert body["review_ref"] == ""


def test_the_api_reports_a_failed_hand_off_instead_of_failing_the_triage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "aml_alert_triage.adapters.local.review_router.LocalReviewRouter.route",
        _Refusing.route,
    )
    response = TestClient(app, client=_LOOPBACK).post(
        "/v1/triage", json={"alert_id": "FCC-1001"}, headers={"X-Dev-Persona": "auditor"}
    )
    assert response.status_code == 200
    assert response.json()["review_routing"] == "failed"
    assert response.json()["review_ref"] == ""


def test_the_agent_tool_reports_the_hand_off() -> None:
    payload = tools.triage_alert("FCC-1001", tenant="demo-bank")
    assert payload["review_routing"] == "routed"
