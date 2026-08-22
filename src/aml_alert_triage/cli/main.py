"""Minimal stdlib CLI: triage an alert (printing the score arithmetic), or list the queue.

argparse only, no extra deps. The ``triage`` command prints the per-typology uplift lines and the
base-plus-uplifts arithmetic so the score is auditable at the terminal, then routes the result to
human review (rule R8) exactly as the API and the agent do.
"""

from __future__ import annotations

import argparse
import sys

from hex_service_kit.logging import configure_logging

from ..config import Container, build_container

#: What the operator's terminal is entitled to read. The CLI runs with the DEPLOYMENT's identity,
#: so the tenant it may read is the deployment's own, with an explicit flag to name another when
#: one installation serves several. It is separate from the Hrz7 routing partition only because
#: the flag already meant that; both default to the same configured value.
_TENANT_HELP = "Tenant whose alerts to read, and the partition asserted to Hrz7."


def _tenant(args: argparse.Namespace, container: Container) -> str:
    """The data scope for this invocation: the flag when given, else the configured tenant."""
    return str(getattr(args, "tenant", "") or container.settings.tenant)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aml_alert_triage")
    sub = parser.add_subparsers(dest="command", required=True)

    triage_cmd = sub.add_parser("triage", help="Triage a single alert by id.")
    triage_cmd.add_argument("alert_id")
    triage_cmd.add_argument("--actor", default="cli-user@bank.example")
    triage_cmd.add_argument("--tenant", default="", help=_TENANT_HELP)

    queue_cmd = sub.add_parser("queue", help="List the open-alert queue.")
    queue_cmd.add_argument("--tenant", default="", help=_TENANT_HELP)

    args = parser.parse_args(argv)
    container = build_container()
    # Idempotent: a process that is both an API app and a CLI configures once.
    configure_logging(container.settings.profile, service="aml-alert-triage")

    if args.command == "triage":
        try:
            alert = container.alert_feed.fetch_alert(args.alert_id, tenant=_tenant(args, container))
        except KeyError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        result = container.triage_service().triage(alert, actor=args.actor)
        print(f"{result.subject}: alert {result.alert_id}")
        print(f"  base score        : {result.base_score}")
        for hit in result.typology_hits:
            print(f"  + {hit.uplift:>5} {hit.typology_id}: {hit.measure}")
        print(f"  = score {result.score} -> band {result.band.value}")
        print(f"  recommendation    : {result.recommendation.value}")
        print(f"  requires_human_review: {result.requires_human_review}")
        # Rule R8 on the CLI path too: the same escalation, the same router. A surface that only
        # printed the flag would be a second place for an escalation to stop.
        ref = container.review_router.route(result, maker=args.actor, tenant=args.tenant)
        print(f"  routed to human review: {ref}")
        return 0

    if args.command == "queue":
        for alert in container.alert_feed.list_open_alerts(tenant=_tenant(args, container)):
            print(f"{alert.alert_id}  {alert.opened.isoformat()}  {alert.subject}")
        return 0

    return 2  # pragma: no cover - argparse requires a subcommand


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))
