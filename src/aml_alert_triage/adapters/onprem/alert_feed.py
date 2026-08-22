"""On-prem AlertFeedPort: fail-fast portability placeholder (the sovereign-exit proof, P-12)."""

from __future__ import annotations

from ...config import Settings
from ...domain.models import Alert


class OnPremAlertFeed:
    """Satisfies AlertFeedPort but refuses: the client binds its own monitoring feed."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def fetch_alert(self, alert_id: str, *, tenant: str) -> Alert:
        raise NotImplementedError(
            "on-prem alert feed is a portability placeholder: bind the client's own "
            "transaction-monitoring feed (see docs/onprem-migration.md)"
        )

    def list_open_alerts(self, *, tenant: str) -> tuple[Alert, ...]:
        raise NotImplementedError(
            "on-prem alert feed is a portability placeholder: bind the client's own feed"
        )
