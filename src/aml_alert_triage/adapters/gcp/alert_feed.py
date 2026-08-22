"""GCP AlertFeedPort: managed transaction-monitoring alert feed (SDK imports stay lazy)."""

from __future__ import annotations

from ...config import Settings
from ...domain.models import Alert


class CloudAlertFeed:
    """Read monitoring alerts from BigQuery. The SDK import is lazy (offline import stays clean)."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def fetch_alert(
        self, alert_id: str, *, tenant: str
    ) -> Alert:  # pragma: no cover - needs live GCP
        from google.cloud import bigquery  # noqa: F401

        raise NotImplementedError(
            "wire the alert-feed query against the client's monitoring dataset "
            "(see docs/runbook.md); the offline profile serves fixtures"
        )

    def list_open_alerts(
        self, *, tenant: str
    ) -> tuple[Alert, ...]:  # pragma: no cover - needs live GCP
        from google.cloud import bigquery  # noqa: F401

        raise NotImplementedError("wire the open-alert-queue query against the client's dataset")
