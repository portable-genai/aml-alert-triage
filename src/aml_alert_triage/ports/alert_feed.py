"""AlertFeedPort: the boundary that returns monitoring alerts to triage (raw, cited, no scoring).

The feed returns rows and never computes: a returned :class:`~..domain.models.Alert` carries its
``source_id`` so every downstream claim can be traced to the feed it came from, and the port does
no banding, scoring or narration. Families: a managed transaction-monitoring feed (gcp, SDK
imported lazily), a deterministic fictional fixture feed (local), an on-premises fail-fast
placeholder (onprem).

**Every read is tenant-scoped, and the tenant is a required argument.** This port took an alert
id and nothing else, so an authenticated caller from any tenant who named an id received the
whole alert behind it, and `list_open_alerts` handed over the entire queue with no id to guess
at all. Object-level authorization cannot live at the call site, because there are five of them
(api, cli, agent, eval, demo) and only one has to forget; making ``tenant`` a keyword-only
parameter of the protocol means a caller with no tenant to pass does not compile rather than
silently reading everything.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..domain.models import Alert


@runtime_checkable
class AlertFeedPort(Protocol):
    def fetch_alert(self, alert_id: str, *, tenant: str) -> Alert:
        """Return ``tenant``'s alert with ``alert_id``.

        Raises ``KeyError`` when the feed has no such row FOR THAT TENANT. A row owned by another
        tenant is indistinguishable from a row that does not exist, deliberately: answering
        "exists, but not for you" tells the caller the id is real somewhere.
        """
        ...

    def list_open_alerts(self, *, tenant: str) -> tuple[Alert, ...]:
        """Return ``tenant``'s open alert queue (deterministic order), possibly empty."""
        ...
