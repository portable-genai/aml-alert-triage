# Features FAQ

For product, financial-crime operations, and delivery teams: what this agent produces, what is
deterministic vs drafted, and, importantly, where its responsibilities **stop** and a sibling
catalog system takes over. Cross-references: [`README.md`](../../README.md),
[`DEMO.md`](../../DEMO.md), [`ARCHITECTURE.md`](../../ARCHITECTURE.md).

### What does G1 actually produce?

A cited **triage assessment** for one transaction-monitoring alert. From an alert id it fetches the
alert and its transaction window, scores the window against typology packs, and returns a
`TriageAssessment` (`domain/models.py`) carrying: the base score and the risk score, the severity
band, the disposition recommendation (`close`, `request_info` or `escalate_sar`), every
`TypologyHit` that fired with the arithmetic that fired it and the regulator instrument it cites, a
drafted SAR narrative, the full citation set, `requires_human_review`, and the `review_ref` of the
human-review item it just created. The reference build ships four typologies: structuring below a
cash-transaction reporting threshold, rapid movement with high pass-through, funnel accounts, and
mule fan-out.

### What is deterministic vs done by the model?

The consequential decision is **deterministic and replayable** (pure stdlib, unit-tested):
`domain/typology_engine.py` runs the four pure detectors in `DETECTORS` over the window, sums each
fired pack's `uplift` onto the policy `base_score`, clamps to `max_score`, bands the result against
the thresholds in `domain/policy.py` (`TriagePolicy`), and maps the band to a recommendation. The
model only **drafts the SAR narrative prose**. It never sets a number: an investigator can
recompute the whole `ScoreCard` from the same window, packs and policy without any model.
`grep -rE "google|fastapi|httpx|pydantic" src/aml_alert_triage/domain/` returns nothing, and
`tests/unit/test_core_purity.py` fails the build if that changes. See
[`../model-card.md`](../model-card.md) for the model boundary in full, including the fact that no
model runs in this repo today: the `local` narrator is deterministic and the managed one is still a
placeholder the process preflight refuses to serve.

### How can a drafted narrative be trusted not to invent a figure?

Because an invented figure discards the whole draft. `domain/grounding.py:ungrounded_numbers`
extracts every numeric token from the draft and subtracts every number present in the narrator's
own inputs; a non-empty remainder means the narrator produced a quantity nobody computed. A cited
source id that was never offered to the narrator is rejected the same way. Either rejection falls
back to `grounded_skeleton`, the deterministic cited narrative built from engine figures alone, so
a triage never ships an ungrounded number and never waits on a model to be available. This is
scored as the `groundedness` eval metric at a threshold of 1.0.

### Is anything auto-approved? Does it file a SAR or close an alert?

No, and the design makes that structural rather than configurable. EVERY outcome is consequential:
`requires_human_review` is unconditionally true on every assessment, **including a proposed
close**, and the result is routed to the human-review console in the same call that produced it
(rule R8), on the API, the CLI and the agent tool alike. `tests/unit/test_review_routing.py`
asserts the routing rather than the flag, and
`test_even_a_low_band_close_is_routed` is the case that matters: a system that only escalated the
scary ones would be auto-dispositioning the quiet ones. A CRITICAL band demands two approvals. The
system never files a suspicious-activity report and never closes an alert autonomously.

### What does it NOT do in the AML lifecycle?

It does not generate the alert (that is the bank's transaction-monitoring system, upstream of the
alert feed), it does not perform customer due diligence or source-of-wealth analysis, it does not
screen names or payment messages against sanctions and PEP lists, it does not interdict a payment
in flight, and it does not file the report with the financial intelligence unit. It starts at an
alert that already exists and ends at a human disposition with an audit trail.

### Which capabilities does this repo own vs integrate from the catalog?

This is one system in a catalog of composable GRC systems. It **owns** the deterministic typology
engine, the triage policy surface, the groundedness contract and the audit trail. It **integrates**
several cross-cutting concerns that are owned by sibling platform systems. Do not rebuild these in
a fork; the state column is honest about which are wired today.

| Concern | Owned by (catalog id) | G1's role, as built |
|---|---|---|
| Runtime guardrail: prompt-injection defence, I/O screening | `agent-guardrail-gateway` agent guardrail gateway | **Not integrated yet.** No `GuardrailPort` exists; rule R1 in `COMPLIANCE.md` records the open half. In-repo redaction (`domain/pii.py` over `pii-kit`) is not a substitute for it. |
| Governed, ACL-aware knowledge base with citations | `enterprise-knowledge-base` | The `gcp` binding of `RetrievalPort` (`adapters/gcp/retrieval.py`) is the seam; it raises today. The `local` profile serves a fixture typology-guidance corpus. Retrieval informs the narrative only. |
| Agent registry, versioning, identity, entitlements | `agent-registry` | Publishes its A2A card at `/.well-known/agent-card.json`, built from the same tool table the runtime binds. Registration with `agent-registry` is the adopter's step (rule R4). |
| AI-quality, eval and model-risk promotion gate | `model-quality-gate` | `eval/run_eval.py --mode gate` is the client half and refuses to run off the managed profile; the bundle id is `aml-alert-triage`. The offline `--mode smoke` gate mirrors the thresholds. |
| Observability, tracing, immutable WORM audit | `agent-observability` and WORM audit | `adapters/gcp/tracer.py` sends OTLP to the `agent-observability` collector when `OTEL_EXPORTER_OTLP_ENDPOINT` is set. Spans carry structural attributes only. The WORM audit half is local and hash-chained today. |
| Human review, maker-checker, case state, SLA clocks | `human-review-console` human-review and maker-checker console | **Fully wired.** Every outcome routes over the shared `review-kit` (rule R8), redacted before the wire, with dual control on CRITICAL. You wire your endpoint; you do not re-implement the console. |
| Project intake validation | `architecture-validator` architecture and requirements validator | Rule R6 is an intake action, not a code control. |

So the guardrail, the knowledge base, the registry, the eval platform, the audit sink and the
review console are *dependencies*, not features of this repo.

### How does this relate to the other financial-crime systems in the catalog?

G1 is the alert-disposition step. Adjacent systems own different points of the journey and should
not be duplicated here: `cdd-sow-research` customer due diligence and source of wealth (the onboarding and
periodic-review side), **G2** sanctions, PEP and payment-message screening (name and message
matching, a different engine and a different false-positive problem), **G3** scam and
authorised-push-payment real-time interdiction (in-flight, latency-bound), **G4** account-takeover
investigation (session and device signals), **G5** the SOC fraud-fusion copilot (cross-channel
correlation), and `claims-integrity-investigator` insurance claims integrity. Check the catalog before building a
capability that may already have a home.

### Can I use it for a different market or a different typology set?

Yes, and without an engine edit. A market or a tightened threshold is a **pack** change:
`src/aml_alert_triage/rulepacks/typologies.yaml` carries each typology's detector name, its
thresholds, its score uplift and its instrument citation, and an adopter can point
`AMLTRIAGE_TYPOLOGY_PACK` at its own file instead. The engine carries no jurisdiction branch. Only
a new SHAPE of pattern, one that none of the four detectors describes, needs a new pure function in
`DETECTORS`. The bands and the recommendation map move through the `policy:` block in
`config/settings.yaml`. See [`../ADOPTING.md`](../ADOPTING.md) and
[adoption-faq.md](adoption-faq.md).

### How do I see it working?

`make demo` runs the real `TriageService` over the `local` profile and drives a presenter-paced
walkthrough: bind the stack, triage a routine case, triage a consequential one and route it, plant
a national id and watch it masked before the audit write, show the reviewer's queue, verify and
export the audit trail, tamper with a record and detect it, then swap to the exit profile and watch
every seam refuse. `make demo-selftest` runs the same arc headless and asserts every step;
`make demo-static` writes the panels as dependency-free HTML for screenshots;
`aml_alert_triage triage FCC-1001` does one alert from the CLI. Everything runs on synthetic,
obviously fictional data (parties suffixed FICTIONAL, `.example` domains) with no cloud, no
credential and no API key.
