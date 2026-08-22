"""Local AlertFeedPort: a deterministic fictional alert queue (no live monitoring system).

Returns the seeded fixture alerts, so the offline gate, the eval and the demo run the whole
triage without a transaction-monitoring platform. The rows are raw and cited (each alert carries
its ``source_id``); this adapter computes no score.
"""

from __future__ import annotations

from ...config import Settings
from ...domain.models import Alert
from ._fixtures import ALERTS_BY_ID


class LocalAlertFeed:
    """Serve the seeded fictional alerts for the SDK-free ``local`` profile."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def fetch_alert(self, alert_id: str, *, tenant: str) -> Alert:
        """Return the row only when its data tag matches the verified principal's tenant.

        A mismatch raises the same ``KeyError`` as an unknown id, so the caller cannot tell a
        foreign row from an absent one. An untagged row (empty tenant) matches nobody, because
        the fail-closed reading of "we do not know who owns this" is "not you".
        """
        alert = ALERTS_BY_ID.get(alert_id)
        if alert is None or not tenant or alert.tenant != tenant:
            raise KeyError(f"no fixture alert with id {alert_id!r} for tenant {tenant!r}")
        return alert

    def list_open_alerts(self, *, tenant: str) -> tuple[Alert, ...]:
        return tuple(a for a in ALERTS_BY_ID.values() if tenant and a.tenant == tenant)
