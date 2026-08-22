"""Grounding helpers: the deterministic SAR-narrative skeleton and the number-groundedness check.

Two pure functions the service relies on and a test proves red:

* :func:`grounded_skeleton` builds a cited narrative from engine figures ALONE. It is both the
  ``local`` narrator's output and the orchestrator's fallback when a model's draft fails
  validation, so a triage never depends on a model answering.
* :func:`ungrounded_numbers` returns any numeric token in a drafted narrative that does NOT
  appear in the engine's own figures. A non-empty result means the narrator invented a figure,
  and the orchestrator discards that draft. This is the groundedness contract made executable:
  the narrator may restate engine numbers, never introduce new ones.
"""

from __future__ import annotations

import re

from .models import NarrationDraft, NarrationRequest

#: A maximal run of digits, optionally with thousands separators and a decimal part.
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _normalise(token: str) -> str:
    return token.replace(",", "")


def numbers_in(text: str) -> set[str]:
    """The set of normalised numeric tokens appearing in ``text``."""
    return {_normalise(match) for match in _NUMBER.findall(text)}


def allowed_numbers(request: NarrationRequest) -> set[str]:
    """Every number the narrator is allowed to state: any number present in its INPUTS.

    Gathered from every text field the narrator is handed (the score, and each hit's uplift,
    measure, title and citation id, and each passage's title, id and snippet), so a numeric
    token outside this set is one the narrator INVENTED rather than restated. A digit inside a
    citation id like ``fatf_r20_str`` or a title like "FATF Recommendation 20" is an identifier
    the narrator may legitimately quote, not a fabricated quantity.
    """
    parts: list[str] = [str(request.score), request.subject]
    for hit in request.typology_hits:
        parts.append(str(hit.uplift))
        parts.append(hit.measure)
        parts.append(hit.title)
        parts.append(hit.citation.source_id)
        parts.append(hit.citation.title)
    for passage in request.passages:
        parts.append(passage.title)
        parts.append(passage.source_id)
        parts.append(passage.snippet)
    allowed: set[str] = set()
    for part in parts:
        allowed |= numbers_in(part)
    return allowed


def ungrounded_numbers(text: str, request: NarrationRequest) -> set[str]:
    """Numeric tokens in ``text`` absent from the engine figures (empty means grounded)."""
    return numbers_in(text) - allowed_numbers(request)


def grounded_skeleton(request: NarrationRequest) -> NarrationDraft:
    """Build a deterministic, fully cited SAR narrative from engine figures alone."""
    lines = [
        f"Subject {request.subject}: risk score {request.score} banded "
        f"{request.band.value}; recommended disposition {request.recommendation.value}.",
    ]
    cited: list[str] = []
    if request.typology_hits:
        lines.append("Typologies that fired:")
        for hit in request.typology_hits:
            lines.append(f"- {hit.title} [{hit.citation.source_id}]: {hit.measure}.")
            if hit.citation.source_id not in cited:
                cited.append(hit.citation.source_id)
    else:
        lines.append("No typology fired above the review threshold.")
    if request.passages:
        lines.append("Relevant guidance:")
        for passage in request.passages:
            lines.append(f"- {passage.title} [{passage.source_id}]: {passage.snippet}")
            if passage.source_id not in cited:
                cited.append(passage.source_id)
    lines.append(
        "This assessment is decision support: a human reviewer must approve it before any "
        "suspicious-activity report is filed or the alert is closed."
    )
    return NarrationDraft(text="\n".join(lines), cited_source_ids=tuple(cited))
