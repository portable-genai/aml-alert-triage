"""GCP RetrievalPort: governed retrieval over the Hrz2 knowledge base (SDK imports stay lazy).

Hrz2's managed backend is Agent Search (formerly Vertex AI Search); the client is imported inside
the method so the offline profiles import this module with no SDK present. Retrieval informs the
narrative only.
"""

from __future__ import annotations

from ...config import Settings
from ...domain.models import RetrievalQuery, RetrievedPassage


class CloudRetrieval:
    """Retrieve cited typology guidance from the Hrz2 governed corpus."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def retrieve(self, query: RetrievalQuery) -> tuple[RetrievedPassage, ...]:  # pragma: no cover
        from google.cloud import discoveryengine  # noqa: F401

        raise NotImplementedError(
            "wire retrieval against the Hrz2 governed knowledge base (see docs/runbook.md); "
            "the offline profile serves a fixture corpus"
        )
