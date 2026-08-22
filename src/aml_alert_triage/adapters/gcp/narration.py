"""GCP NarrationPort: Gemini on the Agent Platform drafts the SAR narrative (SDK import lazy).

The model DRAFTS prose only. Its output is schema-validated and discarded on failure by the
orchestrator, which falls back to the deterministic skeleton, so the managed narrator can never
introduce a number the engine did not compute. The ``google`` client is imported inside the
method so the offline profiles import this module with no SDK installed.
"""

from __future__ import annotations

from ...config import Settings
from ...domain.models import NarrationDraft, NarrationRequest


class CloudNarration:
    """Draft the SAR narrative with a Gemini model, region-pinned by settings."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def narrate(self, request: NarrationRequest) -> NarrationDraft:  # pragma: no cover - live GCP
        from google import genai  # noqa: F401

        raise NotImplementedError(
            "wire the Gemini narration call (see docs/runbook.md); the offline profile uses the "
            "deterministic grounded narrator"
        )
