"""GCP WarehousePort: BigQuery transaction warehouse (SDK imports stay lazy).

The ``performance-marketing-optimisation`` repo's ``adapters/gcp/bigquery_metrics.py``
is the BigQuery reference:
the ``google.cloud.bigquery`` client is constructed inside the method, so ``local``/``onprem``
import this module with no GCP SDK installed. The adapter returns raw cited rows and computes no
score.
"""

from __future__ import annotations

from datetime import date

from ...config import Settings
from ...domain.models import TransactionWindow


class CloudWarehouse:
    """Read a subject's transaction window from BigQuery, region-pinned by settings."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def fetch_window(self, subject: str, as_of: date) -> TransactionWindow:  # pragma: no cover
        from google.cloud import bigquery  # noqa: F401

        raise NotImplementedError(
            "wire the transaction-window query against the client's warehouse "
            "(see docs/runbook.md); the offline profile serves fixtures"
        )
