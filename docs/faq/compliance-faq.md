# Compliance FAQ

For compliance, MLRO, model-risk and privacy teams assessing the repo's regulatory posture.
Cross-references: [`COMPLIANCE.md`](../../COMPLIANCE.md) (the full principle-to-control map with an
evidence column, plus the adopter-owned crosswalk), [`SPEC.md`](../../SPEC.md),
[`../model-card.md`](../model-card.md).

### Is this making AML decisions autonomously?

No, and it cannot be configured into doing so. It is **decision support**, and every outcome
terminates at a human disposition. `requires_human_review` is unconditionally true on every
`TriageAssessment`, and the result is routed through `ReviewRouterPort` to the Hrz7 human-review
console in the same call that produced it (dependency rule R8), including a proposed CLOSE. The
flag alone is not the escalation: `tests/unit/test_review_routing.py` asserts the routing, and
`test_even_a_low_band_close_is_routed` is the case that matters, because a system that only routed
the alarming outcomes would be auto-dispositioning the quiet ones. A CRITICAL band demands two
approvals. The managed router REFUSES to run with no console configured rather than swallowing an
escalation, and the on-prem placeholder refuses rather than dropping it. **The system never files a
suspicious-activity report and never closes an alert.**

### Is the decision explainable to a second line or a regulator?

Yes, and it is replayable rather than merely logged. The score arithmetic is pure stdlib:
`domain/typology_engine.py` sums each fired pack's `uplift` onto the policy `base_score`, clamps,
bands against `domain/policy.py` thresholds and maps the band to a recommendation. Each
`TypologyHit` carries the `measure` string stating exactly which arithmetic fired it (for example
how many sub-threshold transfers were found against how many were needed) and a `Citation` to the
regulator or standard-setter instrument behind the typology. Given the same window, packs and
policy, the whole `ScoreCard` is byte-identical, so an investigator or an auditor recomputes it
without any model. The `signal_key` is a stable content hash over the firing transactions, so the
same pattern yields the same key on every run and a re-run diffs exactly.

### What does the model do, and how is its output controlled?

It drafts the SAR narrative prose and nothing else. A draft that states a number the engine did not
compute, or cites a source that was never offered to it, is DISCARDED whole in favour of
`domain/grounding.py:grounded_skeleton`, the deterministic cited narrative. Read
[`../model-card.md`](../model-card.md) for the full boundary, including the point a model-risk
reviewer needs first: **no model runs in this repo today.** The `local` narrator is deterministic,
the managed Gemini narrator is still a construction-only placeholder listed in
`managed_readiness.py`, and the API preflight refuses to start a `gcp` process while it is bound.
So the managed model path is not production-cleared, and it is not merely undocumented as such: it
is actively refused.

### How is customer PII handled?

This service has a real personal-data surface (subjects, counterparties, free-text alert
narratives) and the controls are correspondingly load-bearing. Redaction runs **before** every
boundary crossing, using the shared `pii-kit` with a jurisdiction selection this deployment owns
(`domain/pii.py:JURISDICTIONS`, shipped as SG, HK, JP, AU, with the national-identifier rows
ordered before the universal email and phone rows): before the WORM audit write, before the review
payload leaves the process (against every jurisdiction's rows, because the console is a shared
sink), and before any agent tool result can become model context. The alert narrative is redacted
inside the domain before it is attached as a citation, so no raw identifier travels on the API
response either. The `pii_safety` eval metric has a two-part oracle, a pack scan plus an
independent planted-literal check that fires even if a pattern row is broken, and
`tests/unit/test_not_falsely_green.py::test_pii_safety_can_go_red` proves it can fail. What this
repo does NOT own is the runtime guardrail and injection defence: that is **Hrz1**, and rule R1 in
[`COMPLIANCE.md`](../../COMPLIANCE.md) records honestly that no `GuardrailPort` is bound yet.

### How is the audit trail held?

Append-only and hash-chained, and externally ANCHORED, which matters more than it sounds. The chain
catches an edit, a deletion or a reorder; only the anchor catches a truncated tail, because a
shorter chain still verifies perfectly. `audit_anchor_path` points at a file on a different volume
that every append writes the chain head to, and once store and anchor disagree the service refuses
to append rather than re-anchoring, so an ordinary write cannot launder a divergence.
`tests/unit/test_audit_anchor.py` proves both halves including the control case. The audit actor is
the server-verified principal, never the request body. In production the enterprise WORM sink is
**Hrz5** plus the locked Cloud Logging bucket (`infra/terraform/logging_worm.tf`, retention locked
at a six-month floor by default and irreversible once applied).

### Is data residency actually enforced, or only documented?

Enforced at deploy time, and this is the row an assessor should test rather than take on trust. The
region is chosen once (`asia-southeast1`), carried by `config/settings.yaml`, reported by
`/healthz` and printed on the agent card. Beyond that visibility: `infra/terraform/variables.tf`
validates the EFFECTIVE region against the residency allowlist at plan time, the allowlist
defaulting to exactly the region this repo was rendered for
(`infra/terraform/render.tf.json`); `org_policy.tf` pins `constraints/gcp.resourceLocations` to
that region's location group and forbids exportable service-account keys; and every regional
resource is created in it, the CMEK key ring, the locked WORM audit bucket and, when the opt-in
serving edge is enabled, the Cloud Run service and its regional network endpoint group.
`infra/terraform/production_edge.tftest.hcl` is the executable check, running against a mocked
provider so it needs no project and no credentials:
`residency_defaults_are_in_country` fails if any of those drifts off region and
`reject_region_outside_the_residency_allowlist` fails if the allowlist stops refusing.

The honest gap is the BUILD WIRING, not the enforcement. This repo has no `tf-check` make target
and no terraform CI job, so those runs happen only when somebody types
`terraform -chdir=infra/terraform test` by hand. An adopter should wire that into a pipeline as
part of adoption.

### What is the model-risk and promotion story?

`eval/run_eval.py` has two named layers. `--mode smoke` is the offline pre-merge check the gate
runs on every change: it drives the real triage pipeline against
`eval/datasets/golden_cases.jsonl` with the SDK-free adapters and scores five metrics against the
dataset's OWN `expected_*` oracle rather than against the pipeline's verdict:
`recommendation_accuracy` at 0.80, `typology_recall` at 0.90, `groundedness` at 1.0,
`review_safety` at 1.0 and `pii_safety` at 0.99. Each is proven able to go red in
`tests/unit/test_not_falsely_green.py`. `--mode gate` is the promotion verdict and delegates to the
sibling **Hrz4** AI-quality and model-risk gate under the bundle id `aml-alert-triage`,
refusing to run off the managed profile. Registering that bundle and its thresholds with Hrz4 is an
adopter step that [`COMPLIANCE.md`](../../COMPLIANCE.md) records as open under P-08 and R5. A fork
must rebuild the golden set for its own typologies, or the gate measures the wrong detection
policy.

### Which rows in COMPLIANCE.md are still open, and are any of them stale?

Read the status column rather than the row count: the document deliberately distinguishes
**Covered** (a test fails the build if it regresses) from **Partial** (the in-repo half exists, the
deploy-time or platform half does not) from **TODO (repo owner)** (not covered, and the row names
what must be added). The substantive open items today are the VPC-SC and Interconnect perimeter
(P-01), the guardrail binding (R1), the Hrz5 observability sink and Hrz3 registration (R2, R4), the
Hrz4 bundle registration (P-08, R5), resilience and cost controls that only become meaningful once
a real model call exists (P-10, P-11), and object-level tenant authorisation once this service
gains a queryable store.

One caveat worth raising with the repo owner rather than working around: the **P-05 and R3 rows
still describe an earlier state** in which this scaffold had no retrieval port and no model call.
Both now exist (`ports/retrieval.py`, `ports/narration.py`, bound in every profile, with the `gcp`
retrieval binding pointed at Hrz2), so those two rows are due a refresh.
[`ARCHITECTURE.md`](../../ARCHITECTURE.md) is the accurate description of the pipeline, and the
documentation authority order in `AGENTS.md` puts it above `COMPLIANCE.md` for exactly this reason.

### Which regulators does this map to?

`COMPLIANCE.md` maps the internal P-01 to P-13 principles and the R1 to R8 dependency rules to
concrete code with an evidence column naming real files, aligned to MAS TRM, APRA CPS 234 and
CPS 230, HKMA and PDPA-class regimes. The mapping from those to a specific regulation, and the
decision that a control is SUFFICIENT for that regulation, is explicitly **adopter-owned**: it
depends on your risk appetite, your regulator, your licence conditions and your existing control
library. No row in that file should be quoted as regulatory assurance. You are expected to add the
crosswalk to your own control ids, the risk acceptance for every row still Partial or TODO at
go-live, the second-line review of the deterministic policy in `domain/` (it is bank-owned logic,
not a vendor default to inherit unexamined), and the retention schedule and legal basis for the
audit trail this service writes.

Separately, note that the regulator instruments cited in the typology packs (FATF Recommendation
20, MAS Notice 626, FATF funnel-account typologies, AUSTRAC money-mule guidance) are real named
publications summarised in a short paraphrase so an investigator can find the source. Nothing there
is a verbatim quotation and nothing there is legal advice. The thresholds and uplift weights beside
them are adopter-owned policy, NOT quoted regulatory limits, and the pack file says so.

### Can we run it against real alerts today?

Not without your own legal, security and model-risk sign-off. Every subject, counterparty and
identifier in the repo is obviously synthetic (parties suffixed FICTIONAL, `.example` domains, one
checksum-valid synthetic national id that exists solely so the redaction check has an independent
literal to look for). The adoption checklist in [`../ADOPTING.md`](../ADOPTING.md) lists the steps
that must precede any live use: your residency region, your IdP, your policy numbers reviewed by
second line, your typology packs, your fixtures replaced, and your own eval golden set.
