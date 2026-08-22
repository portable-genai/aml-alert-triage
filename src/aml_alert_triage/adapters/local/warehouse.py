"""Local WarehousePort: deterministic fictional transaction windows (no live warehouse).

Returns the seeded transaction window for a subject, so the engine scores real-shaped movements
offline. The rows are raw and cited (the window carries its ``source_id``); this adapter computes
nothing.
"""

from __future__ import annotations

from datetime import date

from ...config import Settings
from ...domain.models import TransactionWindow
from ._fixtures import WINDOWS_BY_SUBJECT


class LocalWarehouse:
    """Serve the seeded fictional transaction windows for the SDK-free ``local`` profile."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def fetch_window(self, subject: str, as_of: date) -> TransactionWindow:
        try:
            return WINDOWS_BY_SUBJECT[subject]
        except KeyError as exc:
            raise KeyError(f"no fixture transaction window for subject {subject!r}") from exc
