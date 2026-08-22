"""On-prem NarrationPort: fail-fast portability placeholder (the sovereign-exit proof, P-12)."""

from __future__ import annotations

from ...config import Settings
from ...domain.models import NarrationDraft, NarrationRequest


class OnPremNarration:
    """Satisfies NarrationPort but refuses: the client binds its own on-prem model."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def narrate(self, request: NarrationRequest) -> NarrationDraft:
        raise NotImplementedError(
            "on-prem narration is a portability placeholder: bind the client's own on-prem "
            "model (see docs/onprem-migration.md)"
        )
