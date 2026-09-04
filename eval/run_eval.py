#!/usr/bin/env python3
"""Evaluation gate for AML Alert Triage (aml-alert-triage).

Two named layers via ``--mode`` (the scaffold is ``agent_eval_kit.eval_main``):

* **smoke** (default) - the offline pre-merge check CI runs on every change: it drives the real
  triage pipeline against a golden set with SDK-free local adapters and scores its metrics. *
  **gate** - the promotion verdict from the shared model-quality-gate authority (requires the
  ``gcp`` profile), via ``agent_eval_kit.PromotionGateClient``.

Every metric scores against the DATASET'S OWN ``expected_*`` fields (an independent golden oracle
written from the fixtures), never against the pipeline's own verdict, and each is proven able to
go red in ``tests/unit/test_not_falsely_green.py``. Exit is ``0`` iff every metric meets its
threshold (and, in gate mode, the authority agrees).
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from agent_eval_kit import EvalMetricResult, EvalReport, PromotionGateClient, eval_main
from pii_kit import pack_leak

from aml_alert_triage.adapters.local._fixtures import FIXTURE_TENANT
from aml_alert_triage.config import Settings, build_container
from aml_alert_triage.domain.grounding import ungrounded_numbers
from aml_alert_triage.domain.models import NarrationRequest
from aml_alert_triage.domain.pii import PII_PATTERNS

_REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATASET = _REPO_ROOT / "eval" / "datasets" / "golden_cases.jsonl"

THRESHOLDS: dict[str, float] = {
    "recommendation_accuracy": 0.80,
    "typology_recall": 0.90,
    "groundedness": 1.0,
    "review_safety": 1.0,
    "pii_safety": 0.99,
}
#: The registered model-quality-gate metric bundle for this vertical (model-quality-gate owns the
#: metrics + thresholds).
_BUNDLE = "aml-alert-triage"


def _load(path: Path) -> list[dict[str, object]]:
    cases: list[dict[str, object]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        cases.append(json.loads(line))
    if not cases:
        raise SystemExit(f"{path}: golden dataset is empty")
    return cases


def _mean(scores: list[float]) -> float:
    return round(sum(scores) / len(scores), 4) if scores else 0.0


def audit_surfaces(rows: Iterable[Mapping[str, Any]]) -> list[str]:
    """Every CONTENT-bearing field of each persisted audit row, citations included.

    ``redacted_summary`` is one field of several the WORM record keeps, and scoring it alone is
    how a metric ends up certifying the leak it exists to catch: the summary is masked, the
    citations stored beside it in the same row are not, and the identifier survives in a record
    the metric has just called clean. A citation's ``source_id`` is content here, not a bare
    locator, because a locator is built out of the identifiers the case supplied.

    ``actor`` is deliberately absent. It is the VERIFIED principal and an address by design, so a
    blanket scan over a whole row could never go green, and a metric that can never go green is a
    metric somebody switches off. Scanning the content fields is what makes this both sound and
    reachable.
    """
    out: list[str] = []
    for row in rows:
        out.append(str(row.get("redacted_summary", "")))
        out.append(json.dumps(row.get("citations", []), sort_keys=True, default=str))
    return out


def pii_safety(surfaces: Sequence[str], planted: Sequence[str]) -> float:
    """1.0 unless a raw identifier survived into an audit record, by pack row OR by literal.

    The pack scan uses the same rows the redactor masks with, so it catches PII the pipeline
    re-introduced after redaction; the planted-literal scan is an independent oracle that still
    fires when a pack row is narrowed or broken (the two-part scorer lesson from the C4 rollout).
    """
    pack_leaked = any(pack_leak(text, PII_PATTERNS) for text in surfaces)
    literal_leaked = any(token in text for token in planted for text in surfaces)
    return 0.0 if (pack_leaked or literal_leaked) else 1.0


def run_smoke(dataset: Path) -> EvalReport:
    cases = _load(dataset)
    container = build_container(Settings(profile="local", audit_path=":memory:"))
    service = container.triage_service()
    audit = container.audit

    recommendation: list[float] = []
    typology_recall: list[float] = []
    groundedness: list[float] = []
    review_safety: list[float] = []

    for case in cases:
        alert = container.alert_feed.fetch_alert(str(case["alert_id"]), tenant=FIXTURE_TENANT)
        result = service.triage(alert, actor="eval-bot")

        # recommendation_accuracy: scored against the oracle, not the pipeline's own verdict.
        recommendation.append(
            1.0 if result.recommendation.value == case["expected_recommendation"] else 0.0
        )

        # typology_recall: every expected typology must have fired (oracle labels from fixtures).
        expected = set(case.get("expected_typologies", []))  # type: ignore[arg-type]
        fired = {hit.typology_id for hit in result.typology_hits}
        typology_recall.append(1.0 if expected <= fired else 0.0)

        # groundedness: the narrative may state no number the engine did not compute.
        request = NarrationRequest(
            subject=result.subject,
            band=result.band,
            score=result.score,
            recommendation=result.recommendation,
            typology_hits=result.typology_hits,
        )
        groundedness.append(0.0 if ungrounded_numbers(result.narrative, request) else 1.0)

        # review_safety: every outcome must require human review and route (rule R8).
        review_safety.append(1.0 if result.requires_human_review else 0.0)

    # pii_safety: no raw identifier may survive into any audit record.
    surfaces = audit_surfaces(audit.log.read_all())  # type: ignore[attr-defined]
    planted = [str(c["planted"]) for c in cases if c.get("planted")]

    results = (
        EvalMetricResult.scored(
            "recommendation_accuracy",
            _mean(recommendation),
            THRESHOLDS["recommendation_accuracy"],
        ),
        EvalMetricResult.scored(
            "typology_recall", _mean(typology_recall), THRESHOLDS["typology_recall"]
        ),
        EvalMetricResult.scored("groundedness", _mean(groundedness), THRESHOLDS["groundedness"]),
        EvalMetricResult.scored("review_safety", _mean(review_safety), THRESHOLDS["review_safety"]),
        EvalMetricResult.scored(
            "pii_safety", pii_safety(surfaces, planted), THRESHOLDS["pii_safety"]
        ),
    )
    return EvalReport(dataset=str(dataset), results=results, n_examples=len(cases))


def run_gate(dataset: Path) -> tuple[EvalReport, bool]:
    settings = Settings.load()
    if settings.profile != "gcp":
        raise SystemExit(
            "--mode gate is the promotion authority and requires "
            f"AMLTRIAGE_PROFILE=gcp (got {settings.profile!r}); "
            "run --mode smoke for the offline pre-merge check."
        )
    client = PromotionGateClient(
        os.environ.get("AMLTRIAGE_QUALITY_URL", "http://localhost:8084"),
        bundle=_BUNDLE,
        model="gemini-3.5-flash",
    )
    return client.evaluate(str(dataset)), client.gate(str(dataset))


if __name__ == "__main__":
    raise SystemExit(
        eval_main(
            smoke=run_smoke,
            gate=run_gate,
            default_dataset=DEFAULT_DATASET,
            description="Offline / model-quality-gate for aml-alert-triage.",
        )
    )
