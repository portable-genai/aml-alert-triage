"""WarehousePort: the boundary that returns a subject's transaction window (raw, cited rows).

The warehouse returns the transactions the engine scores and never computes a score itself: the
returned :class:`~..domain.models.TransactionWindow` carries its ``source_id`` (the extract or
table the rows were read from) so every typology measure can be traced back. Families: managed
BigQuery (gcp, SDK imported lazily), a deterministic fictional fixture warehouse (local), an
on-premises fail-fast placeholder (onprem).
"""

from __future__ import annotations

from datetime import date
from typing import Protocol, runtime_checkable

from ..domain.models import TransactionWindow


@runtime_checkable
class WarehousePort(Protocol):
    def fetch_window(self, subject: str, as_of: date) -> TransactionWindow:
        """Return the transaction window for ``subject`` as of ``as_of`` (raw rows, cited)."""
        ...
