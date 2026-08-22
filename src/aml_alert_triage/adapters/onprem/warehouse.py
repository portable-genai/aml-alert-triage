"""On-prem WarehousePort: fail-fast portability placeholder (the sovereign-exit proof, P-12)."""

from __future__ import annotations

from datetime import date

from ...config import Settings
from ...domain.models import TransactionWindow


class OnPremWarehouse:
    """Satisfies WarehousePort but refuses: the client binds its own transaction warehouse."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def fetch_window(self, subject: str, as_of: date) -> TransactionWindow:
        raise NotImplementedError(
            "on-prem warehouse is a portability placeholder: bind the client's own "
            "transaction store (see docs/onprem-migration.md)"
        )
