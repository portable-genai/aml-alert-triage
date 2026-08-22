"""Tool functions an agent runtime calls: thin, side-effect-honest wrappers on the services.

Design rules, in the order they matter:

* **No business logic here.** The domain service decides HOW; the model only decides WHICH tool
  to call. A rule that lives in a tool wrapper is a rule the CLI and the API do not have.
* **Rule R8 applies on this path too.** An escalated result is ROUTED from inside the tool, in
  the same call that produced it. An agent surface that only returned the flag would be a third
  place an escalation can quietly stop, after the API and the CLI.
* **Import-safe without a runtime.** ``google.adk`` is imported lazily inside
  :func:`build_function_tools`, so these callables are importable, testable and runnable with
  no ADK and no cloud SDK installed.
* **Typed and documented.** A runtime derives each tool's name, description and JSON parameter
  schema from the signature and the docstring, so both are part of the contract.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from hex_service_kit.serialization import to_jsonable
from pii_kit import redact

from ..config import Container, Settings, build_container
from ..domain.pii import PII_PATTERNS

if TYPE_CHECKING:  # pragma: no cover - typing only, never imported at runtime
    from google.adk.tools import FunctionTool

#: The identity a tool call is attributed to when the runtime propagates none. It names the
#: SERVICE, not a person, so an unattributed action is never mistaken for a human's.
DEFAULT_ACTOR = "aml-alert-triage-agent"


def _container(settings: Settings | None) -> Container:
    return build_container(settings)


def _tenant(asserted: str, container: Container) -> str:
    """The data scope for this tool call: the caller's tenant, else the configured one.

    The agent runtime supplies the tenant from the principal it resolved; the configured value is
    the single-tenant deployment's answer. Either way the feed is scoped, because an alert id is
    a name and not an entitlement, and a tool that reads any row by id is the widest surface in
    the repo: the model chooses the argument.
    """
    return asserted or container.settings.tenant


def _redacted(node: Any) -> Any:
    """Mask personal data in every string of a tool result, however deeply it is nested.

    A tool result is not an API response. The API returns to the authenticated caller the text
    that caller just submitted; a TOOL result goes into a model's context, and P-04 says
    minimise the data that reaches a model. The evidence snippet a caller may legitimately read
    back is therefore masked here, on the way to the agent, using the same pattern pack the
    audit write masks with. Walking the whole structure rather than three named fields means a
    future field cannot arrive unredacted just because nobody remembered to add it.
    """
    if isinstance(node, str):
        return redact(node, PII_PATTERNS)
    if isinstance(node, dict):
        return {key: _redacted(value) for key, value in node.items()}
    if isinstance(node, list):
        return [_redacted(value) for value in node]
    return node


def _triage(alert_id: str, actor: str, tenant: str, settings: Settings | None) -> dict[str, Any]:
    """Fetch, triage and route one alert; return the redacted JSON payload plus ``review_ref``."""
    container = _container(settings)
    try:
        alert = container.alert_feed.fetch_alert(alert_id, tenant=_tenant(tenant, container))
    except KeyError as exc:
        raise ValueError(str(exc)) from exc
    result = container.triage_service().triage(alert, actor=actor)
    # Every outcome is consequential and routes to a human (rule R8), in the same call.
    review_ref = container.review_router.route(result, maker=actor, tenant=tenant)
    payload = _redacted(to_jsonable(result))
    if not isinstance(payload, dict):  # pragma: no cover - dataclasses serialise to objects
        raise TypeError("a triage result must serialise to a JSON object")
    # Attached after the redaction pass: it is a routing reference, not narrative text, and
    # masking an identifier would break the caller's ability to look the review up.
    payload["review_ref"] = review_ref
    return payload


def triage_alert(
    alert_id: str,
    actor: str = DEFAULT_ACTOR,
    tenant: str = "",
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Triage one monitoring alert and route it for human review (rule R8).

    Scores the alert's transaction window into a deterministic risk band and recommendation with
    the pure engine, drafts a grounded SAR narrative, writes an already-redacted audit event, and
    submits the result to the human-review console. The band and recommendation are the engine's;
    the model produces no number.

    Args:
      alert_id: The monitoring alert to triage (from ``list_alert_queue``).
      actor: The verified identity this call is attributed to.
      tenant: Tenant partition asserted on the outbound review.

    Returns:
      A JSON-safe assessment with every string masked for personal data (P-04: a tool result
      goes into a model's context), plus ``review_ref``: where the escalation WENT.
    """
    return _triage(alert_id, actor, tenant, settings)


def draft_sar_narrative(
    alert_id: str,
    actor: str = DEFAULT_ACTOR,
    tenant: str = "",
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Draft the cited SAR narrative for one alert (the narrative slice of a full triage).

    Runs the same deterministic triage and returns the drafted narrative, the recommendation and
    the citations, plus ``review_ref``. The narrative restates only figures the engine computed;
    an invented number is discarded with the whole draft.

    Args:
      alert_id: The monitoring alert to draft for.
      actor: The verified identity this call is attributed to.
      tenant: Tenant partition asserted on the outbound review.

    Returns:
      A JSON-safe dict with ``alert_id``, ``band``, ``recommendation``, ``narrative``,
      ``citations`` and ``review_ref``, every string masked for personal data.
    """
    full = _triage(alert_id, actor, tenant, settings)
    return {
        "alert_id": full["alert_id"],
        "band": full["band"],
        "recommendation": full["recommendation"],
        "narrative": full["narrative"],
        "citations": full["citations"],
        "review_ref": full["review_ref"],
    }


def list_alert_queue(tenant: str = "", settings: Settings | None = None) -> dict[str, Any]:
    """List one tenant's open-alert queue: alert ids and subjects, no scoring.

    Args:
      tenant: The tenant whose queue to list. Empty falls back to the configured tenant.

    Returns:
      A JSON-safe dict with an ``alerts`` list of ``{alert_id, subject, opened}`` rows, each
      string masked for personal data.
    """
    container = _container(settings)
    rows = [
        {"alert_id": a.alert_id, "subject": a.subject, "opened": a.opened.isoformat()}
        for a in container.alert_feed.list_open_alerts(tenant=_tenant(tenant, container))
    ]
    result = _redacted({"alerts": rows})
    if not isinstance(result, dict):  # pragma: no cover - always a dict
        raise TypeError("the alert queue must serialise to a JSON object")
    return result


def verify_audit_trail(settings: Settings | None = None) -> dict[str, Any]:
    """Verify the audit trail's hash chain and its external head anchor.

    Returns:
      A dict with ``ok``, the record counts and a ``detail`` string. ``ok`` is false for an
      edited, deleted or reordered record, and, when an external anchor is configured, for a
      truncated tail as well. Without an anchor a truncation cannot be detected, and the detail
      says so rather than implying a stronger guarantee than the store provides.
    """
    resolved = settings or Settings.load()
    audit = _container(resolved).audit
    verify = getattr(audit, "verify", None)
    if verify is None:
        raise NotImplementedError(
            f"the {resolved.profile} audit adapter does not expose chain verification; a "
            "managed WORM sink is verified by its own retention policy, not from here"
        )
    report = verify()
    return {
        "ok": report.ok,
        "entries": report.entries,
        "chained": report.chained,
        "legacy": report.legacy,
        "first_bad_seq": report.first_bad_seq,
        "detail": report.detail,
        "anchored": bool(resolved.audit_anchor_path),
    }


#: The tool table. The agent card advertises exactly these, by function name.
TOOL_FUNCTIONS = (triage_alert, draft_sar_narrative, list_alert_queue, verify_audit_trail)


def build_function_tools() -> list[FunctionTool]:
    """Wrap each callable as a runtime FunctionTool (the only ADK-dependent code path).

    The import is deliberately here rather than at module scope: without it this module, the
    card and every tool would need an agent runtime installed to be imported at all, and the
    offline gate installs none.
    """
    # No ignore comment: the missing-import error for this module is already reported (and
    # ignored) at the TYPE_CHECKING import above, and a second one would be flagged as unused.
    from google.adk.tools import FunctionTool

    return [FunctionTool(func=function) for function in TOOL_FUNCTIONS]
