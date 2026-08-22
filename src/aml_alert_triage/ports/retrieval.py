"""RetrievalPort: governed retrieval over the typology-guidance corpus (narration only).

Retrieval informs the NARRATIVE and nothing else: the score, the band and the recommendation are
the engine's and are unaffected by what retrieval returns (a test asserts the assessment is
identical with retrieval stubbed empty). Families: a platform adapter calling the Hrz2 governed
knowledge base (gcp, SDK imported lazily), a local fixture corpus, an on-premises fail-fast
placeholder. Every returned passage carries a citation so a drafted narrative can be grounded.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..domain.models import RetrievalQuery, RetrievedPassage


@runtime_checkable
class RetrievalPort(Protocol):
    def retrieve(self, query: RetrievalQuery) -> tuple[RetrievedPassage, ...]:
        """Return ranked cited passages for ``query`` (possibly empty; never raises on no hit)."""
        ...
