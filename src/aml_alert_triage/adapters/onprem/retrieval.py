"""On-prem RetrievalPort: fail-fast portability placeholder (the sovereign-exit proof, P-12)."""

from __future__ import annotations

from ...config import Settings
from ...domain.models import RetrievalQuery, RetrievedPassage


class OnPremRetrieval:
    """Satisfies RetrievalPort but refuses: the client binds its own knowledge base."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def retrieve(self, query: RetrievalQuery) -> tuple[RetrievedPassage, ...]:
        raise NotImplementedError(
            "on-prem retrieval is a portability placeholder: bind the client's own "
            "governed knowledge base (see docs/onprem-migration.md)"
        )
