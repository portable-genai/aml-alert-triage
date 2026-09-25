"""Local NarrationPort: the SDK-free deterministic narrator (the ``local`` stand-in for Gemini).

There is no Gemini emulator, so this path is unconditional and imports no cloud package. It builds
the SAR narrative from the engine figures ALONE via the shared grounded skeleton, so its output
is grounded by construction: every number it states is one the engine computed, and every source
id it cites was offered to it. The orchestrator still validates and discards on failure, so the
seam behaves exactly as the managed model seam does.
"""

from __future__ import annotations

from hex_service_kit import provenance

from ...config import Settings
from ...domain.grounding import grounded_skeleton
from ...domain.models import NarrationDraft, NarrationRequest


class LocalNarration:
    """Deterministic grounded narrator for the SDK-free ``local`` profile."""

    #: What this narrator answers as, for the console's model pill: the name ``generator_model``
    #: reports under ``local``, so the pill before and after an answer agree.
    MODEL = "deterministic-offline-stub"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def narrate(self, request: NarrationRequest) -> NarrationDraft:
        provenance.note_model(self.MODEL)
        return grounded_skeleton(request)
