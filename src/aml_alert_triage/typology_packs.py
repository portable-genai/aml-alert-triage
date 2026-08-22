"""Load the typology packs from YAML into frozen domain dataclasses (the edge, not the domain).

The domain stays pure stdlib: ``typology_engine.py`` operates on :class:`TypologyPack` objects and
never parses YAML. This module is the loader at the package edge (the ``green_pack`` pattern in
``marketing-compliance-gate``): it reads the shipped ``rulepacks/typologies.yaml`` (or an adopter
path), validates the shape and returns the packs the engine is constructed with. A malformed pack
raises here, at load time, rather than surfacing as a mis-scored alert later.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from .domain.kernel import Citation
from .domain.models import TypologyPack
from .domain.typology_engine import DETECTORS

#: The shipped reference pack, resolved relative to this file so it works installed as a wheel.
DEFAULT_PACK_PATH = Path(__file__).resolve().parent / "rulepacks" / "typologies.yaml"


def _citation(data: Mapping[str, Any], typology_id: str) -> Citation:
    try:
        return Citation(
            source_id=str(data["source_id"]),
            title=str(data["title"]),
            snippet=str(data.get("snippet", "")).strip(),
        )
    except KeyError as exc:  # pragma: no cover - defensive; the shipped pack is well formed
        raise ValueError(f"typology {typology_id!r} citation is missing {exc}") from exc


def _pack(entry: Mapping[str, Any]) -> TypologyPack:
    typology_id = str(entry["typology_id"])
    detector = str(entry["detector"])
    if detector not in DETECTORS:
        raise ValueError(
            f"typology {typology_id!r} names unknown detector {detector!r}; "
            f"known detectors are {sorted(DETECTORS)}"
        )
    raw_params = entry.get("params") or {}
    if not isinstance(raw_params, Mapping):
        raise ValueError(f"typology {typology_id!r} params must be a mapping")
    params = {str(k): int(v) for k, v in raw_params.items()}
    return TypologyPack(
        typology_id=typology_id,
        title=str(entry["title"]),
        detector=detector,
        uplift=float(entry["uplift"]),
        params=params,
        citation=_citation(entry["citation"], typology_id),
    )


def load_packs(path: Path | None = None) -> tuple[TypologyPack, ...]:
    """Load and validate the typology packs, defaulting to the shipped reference pack."""
    target = path or DEFAULT_PACK_PATH
    if not target.exists():
        raise FileNotFoundError(f"typology pack file {target} does not exist")
    loaded = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    if not isinstance(loaded, Mapping):
        raise ValueError(f"typology pack file {target} must contain a mapping at the top level")
    entries = loaded.get("packs")
    if not isinstance(entries, list) or not entries:
        raise ValueError(f"typology pack file {target} must carry a non-empty 'packs' list")
    packs = tuple(_pack(entry) for entry in entries)
    ids = [p.typology_id for p in packs]
    if len(set(ids)) != len(ids):
        raise ValueError(f"typology pack file {target} has duplicate typology ids: {ids}")
    return packs
