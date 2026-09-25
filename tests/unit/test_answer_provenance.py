"""The service half of the model pills: which model ANSWERED, and whether it searched.

The console shows two pills at the top right: the model that answered the last request, and
``Search`` when that answer used an online search tool. Both come from response headers the kit
emits (``install_answer_provenance`` in ``api/app.py``) for whatever the model adapters NOTED as
they called. Before a request is answered the pill shows ``generator_model`` from ``/healthz``,
so that value must be the model the bound adapter calls, never one a configuration flag names
while the adapter calls another.

The narration request carries no sampling parameter: the ``local`` narrator is the grounded
skeleton, and the ``gcp`` narrator refuses rather than answering, so it notes nothing.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from hex_service_kit import provenance

from aml_alert_triage import config
from aml_alert_triage.adapters.local.narration import LocalNarration
from aml_alert_triage.domain.models import NarrationDraft, NarrationRequest

from tests import REPO_ROOT
from tests.conftest import local_settings

ANSWERED_BY = "x-answered-by"
SEARCH_USED = "x-search-used"
STUB = LocalNarration.MODEL
_BODY = {"alert_id": "FCC-1001"}
_AUDITOR = {"X-Dev-Persona": "auditor"}


def _triage(api_client: TestClient) -> dict[str, str]:
    response = api_client.post("/v1/triage", json=_BODY, headers=_AUDITOR)
    assert response.status_code == 200, response.text
    return dict(response.headers)


def test_the_local_narrator_answers_as_the_stub_the_pill_first_names(
    api_client: TestClient,
) -> None:
    """Under ``local`` the pill before and after the answer name the same stub."""
    headers = _triage(api_client)
    assert headers[ANSWERED_BY] == STUB == local_settings().generator_model
    assert SEARCH_USED not in headers


def test_a_call_that_searched_says_so_and_the_next_request_starts_fresh(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = LocalNarration.narrate

    def searching(self: LocalNarration, request: NarrationRequest) -> NarrationDraft:
        provenance.note_model("fake-searching-model")
        provenance.note_search()
        return original(self, request)

    monkeypatch.setattr(LocalNarration, "narrate", searching)
    headers = _triage(api_client)
    assert headers[ANSWERED_BY] == f"fake-searching-model, {STUB}"
    assert headers[SEARCH_USED] == "true"
    monkeypatch.setattr(LocalNarration, "narrate", original)
    headers = _triage(api_client)
    assert headers[ANSWERED_BY] == STUB
    assert SEARCH_USED not in headers


def test_a_request_that_noted_nothing_sends_neither_header(api_client: TestClient) -> None:
    response = api_client.get("/healthz")
    assert response.status_code == 200
    assert ANSWERED_BY not in response.headers
    assert SEARCH_USED not in response.headers


# --------------------------------------------------------------------------------------- #
# generator_model is the model the adapter calls.
# --------------------------------------------------------------------------------------- #
def test_no_flag_swaps_in_a_model_the_adapter_never_calls() -> None:
    """The latent false banner: a flag that moved the pill but not the model that answered."""
    models = SimpleNamespace(
        reasoning="the-model-the-adapter-calls",
        hard_reasoning="a-model-nobody-calls",
        use_hard_reasoning=True,
    )
    named = config._model_from_settings(SimpleNamespace(models=models), "models.reasoning")
    assert named == "the-model-the-adapter-calls"


def test_the_hard_reasoning_flag_does_not_exist() -> None:
    settings_file = (REPO_ROOT / "config" / "settings.yaml").read_text(encoding="utf-8")
    assert "use_hard_reasoning" not in settings_file
    for source in sorted((REPO_ROOT / "src").rglob("*.py")):
        assert "use_hard_reasoning" not in source.read_text(encoding="utf-8"), source
