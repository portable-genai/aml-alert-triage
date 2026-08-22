"""ONE canonical request per port, shared by the structural and behavioural contract suites.

Parity means the same request through every implementation, so the request needs a single home.
Retyping it per suite is how two "parity" tests end up asserting different things.

Each :class:`PortCase` answers three questions about one port:

* ``invoke``   : what a single canonical call to this port looks like;
* ``answered`` : what it means for the OFFLINE family to have actually answered (a port that
  returns ``None`` and records nothing has not answered, it has merely not raised);
* ``managed_refusal`` : what the MANAGED family must do when called with no cloud reachable.
  Never a silent success: either it refuses because it is unconfigured, or its lazy SDK import
  fails. Both are honest; returning as if the work happened is not.

Adding a port means adding a case here. ``test_port_parity.py`` fails the build if this table
and the port map ever disagree, so the touch list in ``CONTRIBUTING.md`` is enforced rather than
merely written down.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any

from agent_eval_kit import EvalReport
from hex_service_kit.identity import IdentityError, Principal, RequestContext
from hex_service_kit.observability import TokenUsage

from aml_alert_triage.domain.kernel import (
    AuditEvent,
    Citation,
    Decision,
    Severity,
)
from aml_alert_triage.domain.models import (
    Alert,
    NarrationDraft,
    NarrationRequest,
    Recommendation,
    RetrievalQuery,
    RetrievedPassage,
    TransactionWindow,
    TriageAssessment,
)

from tests.fixtures import sample_cases

#: A subject and an alert id present in the local (adapter) fixture feed/warehouse, so the
#: offline family has a real row to answer with.
_FIXTURE_ALERT_ID = "FCC-1001"
_FIXTURE_SUBJECT = "Redwood Timber Trading Pte Ltd (FICTIONAL)"

#: The audit record every audit-port implementation is handed. Already redacted, as the port
#: requires: a raw identifier must never reach a WORM record.
CANONICAL_EVENT = AuditEvent(
    action="triage",
    actor=sample_cases.ACTOR,
    decision=Decision.ESCALATED,
    severity=Severity.HIGH,
    redacted_summary="Acme Holdings (FICTIONAL): triaged high",
    citations=(Citation(source_id="case:acme", title="Case description", snippet="urgent"),),
)

#: The escalated result every review-router implementation is handed (rule R8's payload).
CANONICAL_RESULT = TriageAssessment(
    alert_id=sample_cases.ESCALATING_ALERT.alert_id,
    subject=sample_cases.ESCALATING_ALERT.subject,
    base_score=0.20,
    score=0.65,
    band=Severity.HIGH,
    recommendation=Recommendation.ESCALATE_SAR,
    narrative="Structuring pattern; recommend SAR.",
    as_of=sample_cases.ESCALATING_ALERT.window.as_of,
    requires_human_review=True,
    citations=(
        Citation(source_id="fatf_r20_str", title="FATF Recommendation 20", snippet="reporting"),
    ),
)

#: The inbound transport context every identity implementation is handed.
CANONICAL_CONTEXT = RequestContext(headers={"x-dev-persona": "auditor"})


@dataclass(frozen=True, slots=True)
class PortCase:
    """One port's canonical call plus the two verdicts the parity suites need."""

    invoke: Callable[[Any], Any]
    answered: Callable[[Any, Any], bool]
    managed_refusal: tuple[type[BaseException], ...]
    detail: str


def _audit_invoke(adapter: Any) -> Any:
    return adapter.record(CANONICAL_EVENT)


def _audit_answered(adapter: Any, _result: Any) -> bool:
    stored = adapter.log.read_all()
    return bool(stored) and stored[-1]["actor"] == sample_cases.ACTOR and adapter.verify().ok


def _identity_invoke(adapter: Any) -> Any:
    return adapter.resolve(CANONICAL_CONTEXT)


def _identity_answered(_adapter: Any, result: Any) -> bool:
    return isinstance(result, Principal) and bool(result.actor)


def _review_invoke(adapter: Any) -> Any:
    return adapter.route(CANONICAL_RESULT, maker=sample_cases.ACTOR, tenant=sample_cases.TENANT)


def _review_answered(adapter: Any, result: Any) -> bool:
    return bool(result) and len(adapter.outbox.pending()) == 1


def _alert_feed_invoke(adapter: Any) -> Any:
    return adapter.fetch_alert(_FIXTURE_ALERT_ID, tenant=sample_cases.TENANT)


def _alert_feed_answered(_adapter: Any, result: Any) -> bool:
    return isinstance(result, Alert) and result.alert_id == _FIXTURE_ALERT_ID


def _warehouse_invoke(adapter: Any) -> Any:
    return adapter.fetch_window(_FIXTURE_SUBJECT, date(2026, 8, 1))


def _warehouse_answered(_adapter: Any, result: Any) -> bool:
    return isinstance(result, TransactionWindow) and bool(result.transactions)


def _retrieval_invoke(adapter: Any) -> Any:
    return adapter.retrieve(RetrievalQuery(text="structuring", typology_ids=("structuring",)))


def _retrieval_answered(_adapter: Any, result: Any) -> bool:
    return bool(result) and all(isinstance(p, RetrievedPassage) for p in result)


def _narration_invoke(adapter: Any) -> Any:
    return adapter.narrate(
        NarrationRequest(
            subject=_FIXTURE_SUBJECT,
            band=Severity.HIGH,
            score=0.65,
            recommendation=Recommendation.ESCALATE_SAR,
            typology_hits=(),
        )
    )


def _narration_answered(_adapter: Any, result: Any) -> bool:
    return isinstance(result, NarrationDraft) and bool(result.text)


def _tracer_invoke(adapter: Any) -> Any:
    with adapter.span("canonical.unit", action="canonical"):
        adapter.record_token_usage(TokenUsage(input_tokens=7, output_tokens=2), "canonical-model")
    return True


def _tracer_answered(adapter: Any, result: Any) -> bool:
    return bool(result)


def _evaluation_invoke(adapter: Any) -> Any:
    return adapter.evaluate("eval/datasets/canonical.jsonl")


def _evaluation_answered(adapter: Any, result: Any) -> bool:
    return isinstance(result, EvalReport) and result.dataset.endswith("canonical.jsonl")


CANONICAL_CALLS: dict[str, PortCase] = {
    "alert_feed": PortCase(
        invoke=_alert_feed_invoke,
        answered=_alert_feed_answered,
        # The lazy `google.cloud.bigquery` import is the first thing the managed feed does.
        managed_refusal=(ImportError,),
        detail="return a cited alert row",
    ),
    "warehouse": PortCase(
        invoke=_warehouse_invoke,
        answered=_warehouse_answered,
        managed_refusal=(ImportError,),
        detail="return a cited transaction window",
    ),
    "retrieval": PortCase(
        invoke=_retrieval_invoke,
        answered=_retrieval_answered,
        managed_refusal=(ImportError,),
        detail="return cited guidance passages",
    ),
    "narration": PortCase(
        invoke=_narration_invoke,
        answered=_narration_answered,
        # The lazy `from google import genai` import is the first thing the managed narrator does.
        managed_refusal=(ImportError,),
        detail="draft a grounded narrative",
    ),
    "audit": PortCase(
        invoke=_audit_invoke,
        answered=_audit_answered,
        # The lazy `google.cloud` import is the first thing the managed sink does.
        managed_refusal=(ImportError,),
        detail="write one already-redacted WORM record",
    ),
    "identity": PortCase(
        invoke=_identity_invoke,
        answered=_identity_answered,
        # No IAP assertion header offline, so the managed adapter refuses before importing.
        managed_refusal=(IdentityError,),
        detail="resolve a verified principal from transport context",
    ),
    "review_router": PortCase(
        invoke=_review_invoke,
        answered=_review_answered,
        # Rule R8: with no console configured the managed router must refuse, not swallow.
        managed_refusal=(RuntimeError,),
        detail="route one escalated result to human review",
    ),
    "tracer": PortCase(
        invoke=_tracer_invoke,
        answered=_tracer_answered,
        # NOTHING. Tracing is not essential to correctness, so the managed adapter must not refuse
        # offline either: with no SDK it degrades to a no-op and the traced body still runs. An
        # adapter that raised here would take a request down over a diagnostic.
        managed_refusal=(),
        detail="open one span and report the cost of a model call",
    ),
    "evaluation": PortCase(
        invoke=_evaluation_invoke,
        answered=_evaluation_answered,
        # The managed gate reaches Hrz4 over HTTP, which is unreachable offline.
        managed_refusal=(Exception,),
        detail="score one golden dataset through the promotion authority",
    ),
}
