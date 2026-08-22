"""NarrationPort: the LLM seam that DRAFTS the SAR narrative from engine figures (never scores).

The narrator restates what the engine computed and cites what retrieval returned; it produces no
number and no verdict. Its output is schema-validated and DISCARDED on failure by the
orchestrator, which falls back to a deterministic skeleton so a triage never depends on a model
answering. Families: Gemini on the Agent Platform (gcp, SDK imported lazily), a deterministic
grounded template (local), an on-premises fail-fast placeholder.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..domain.models import NarrationDraft, NarrationRequest


@runtime_checkable
class NarrationPort(Protocol):
    def narrate(self, request: NarrationRequest) -> NarrationDraft:
        """Draft a SAR narrative grounded ONLY in ``request`` (engine figures + passages)."""
        ...
