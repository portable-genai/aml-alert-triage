# Adopting this repo as your base

This repository (catalog id **G1**, AML Alert Triage, carried as `Fcc1` in this repo's own
document headers) is a **common base** that a bank, a payments firm or another regulated
institution forks to build its own **AML alert triage service**: it takes a transaction-monitoring
alert, scores its transaction window against typology packs with a pure deterministic engine,
bands it, recommends close / request-info / escalate-to-SAR, drafts a cited SAR narrative that may
restate only figures the engine computed, redacts before it audits, and routes EVERY outcome to a
human reviewer. Forking it gives you a reusable hexagonal core (a pure-stdlib domain, typed ports,
three swappable adapter families, a green offline gate, an executable portability claim, an
asserted demo) plus a fully worked four-typology AML vertical you can keep, retune, or replace
with your own detection policy.

This guide is the step-by-step for making it yours. It has two halves: a **mechanical rebrand**
(one script) and the **human decisions** the script cannot make for you.

> Related reading: [`ARCHITECTURE.md`](../ARCHITECTURE.md) (the port table and the request
> pipeline), [`SPEC.md`](../SPEC.md) (the locked contracts), [`CONTRIBUTING.md`](../CONTRIBUTING.md)
> (the file-by-file touch list for a new adapter or port), [`model-card.md`](model-card.md) (the
> model boundary as built), the [`faq/`](faq/) directory.

---

## 1. What you keep vs what you rewrite

The domain is a physical module split with an enforced dependency direction:
`domain/kernel.py` holds the vertical-neutral machinery and `domain/models.py` holds the AML
artifacts, so a fork building a different financial-crime vertical rewrites `models.py` and leaves
`kernel.py` alone. `tests/unit/test_core_purity.py` fails the build if anything in `domain/`
imports a web framework or a cloud SDK, in either module.

| Layer | Where | For a new vertical or institution |
|---|---|---|
| **Vertical-neutral machinery** | `domain/kernel.py` (`Severity`, `Decision`, `Citation`, `AuditEvent`, `utcnow`), every Protocol in `ports/` plus the `PORT_PROTOCOLS` map, the `Settings` / `Container` wiring in `config.py`, the fail-closed preflight shape in `managed_readiness.py`, the contract suite in `tests/contract/` | keep untouched |
| **Policy (your numbers)** | the `policy:` block in `config/settings.yaml` and its reference defaults in `domain/policy.py` (`base_score`, `max_score`, `band_thresholds`, `recommendations`), the `uplift` weights and `params` thresholds in `src/aml_alert_triage/rulepacks/typologies.yaml`, `JURISDICTIONS` in `domain/pii.py`, and the `THRESHOLDS` dict in `eval/run_eval.py` | change deliberately (see section 4) |
| **Vertical (AML itself)** | the artifacts in `domain/models.py` (`Alert`, `Transaction`, `TransactionWindow`, `TypologyPack`, `TypologyHit`, `ScoreCard`, `NarrationRequest`, `NarrationDraft`, `TriageAssessment`, `Recommendation`), the four detectors in `domain/typology_engine.py:DETECTORS`, the narrative wording in `domain/grounding.py:grounded_skeleton`, the seeded alert queue in `adapters/local/_fixtures.py`, the typology-guidance corpus in `adapters/local/retrieval.py`, `eval/datasets/golden_cases.jsonl`, and the advertised `SKILLS` in `agent/agent_card.py` | rewrite for your detection policy |

If your product is another financial-crime investigation gate (sanctions disposition, fraud case
triage, claims integrity), most of the hexagon, the three profiles, the deterministic-score
pattern, the redact-before-audit rule, the groundedness check and the Hrz7 review routing transfer
directly. You replace the detectors and the artifact models, and you retune the policy numbers.

## 2. Core-vs-adopter-owned files (so upstream merges stay mechanical)

Upstream keeps evolving these; avoid diverging from them so you can pull fixes cleanly:

- **Upstream-owned** (take our changes): `domain/kernel.py`, `ports/`, `tests/contract/`, the
  eval harness mechanics in `eval/run_eval.py`, the hexagon wiring (`config.py` `Container` and
  `DEFAULT_BINDINGS`), the identity vocabulary in `ports/identity.py` and the IAP verifier in
  `adapters/gcp/identity.py`, the CI workflows, and the demo mechanics in `scripts/`.
- **Adopter-owned** (yours; expect to edit): `config/settings.yaml` *values* (including the whole
  `policy:` block), `src/aml_alert_triage/rulepacks/typologies.yaml`, `domain/policy.py` if you
  move a default, the seeded fixtures (`adapters/local/_fixtures.py`,
  `adapters/local/retrieval.py`, `tests/fixtures/sample_cases.py`), `adapters/onprem/*`, the
  `ui/` theming and branding, `eval/datasets/golden_cases.jsonl`, the tfvars under
  `infra/terraform/`, and the crosswalk rows in [`COMPLIANCE.md`](../COMPLIANCE.md).

Track upstream via git tags; rebase your adopter-owned changes onto each release rather than
merging `main` continuously, so conflicts stay in files you were told to expect.

## 3. The mechanical rebrand (one script)

`scripts/rename_fork.py` rewrites the python package name `aml_alert_triage` (which is ALSO the
console-script name: see `[project.scripts]` in `pyproject.toml`), the `AMLTRIAGE` environment
prefix behind every `AMLTRIAGE_*` variable, the distribution and resource id
`aml-alert-triage`, and the Terraform `name_prefix` default, in one pass. Preview first, then
apply:

```bash
# Preview (writes nothing):
python scripts/rename_fork.py --package acme_aml_triage \
    --env-prefix ACMEAML --resource acme-aml-triage \
    --name-prefix acme-aml --dry-run

# Apply:
python scripts/rename_fork.py --package acme_aml_triage \
    --env-prefix ACMEAML --resource acme-aml-triage \
    --name-prefix acme-aml --yes

# Then recreate the environment (the distribution name changed) and prove it is green:
python3.12 -m venv .venv && source .venv/bin/activate
make install
make gate
```

Three things about the flags. There is deliberately **no `--cli` flag**: the console script is
named after the package, so `--package` renames it too and a second flag could only drift out of
step. There is deliberately **no `--dist` flag**: `--resource` is one literal doing four jobs at
once, the distribution name in `pyproject.toml`, the GitHub id in `[project.urls]`, the A2A
agent-card name in `agent/agent_card.py`, and the Hrz4 eval bundle id (`_BUNDLE` in
`eval/run_eval.py`), and they are the same string on purpose so a fork's promotion record and its
discovery card cannot disagree about which system they describe. `--name-prefix` is optional and
is rewritten only inside its own variable block in `infra/terraform/variables.tf`, because a
whole-tree replacement of a short word is how a rename script corrupts prose it was never asked to
touch. Add `--include-docs` to sweep Markdown prose too. The script deliberately does NOT touch
the human decisions below.

## 4. The human decisions (the script can't make these)

1. **Region and residency.** The region is chosen once and shared by the runtime and Terraform.
   Set `GCP_REGION` (read through `region:` in `config/settings.yaml`), set BOTH the Terraform
   `region` and `allowed_regions` in your tfvars, and change `render_region` in
   `infra/terraform/render.tf.json` if you are re-basing the fork on a different in-country
   region. The build defaults to `asia-southeast1`. Both Terraform variables default to null,
   which means "exactly the rendered region": `naming.tf` derives
   `local.region = coalesce(var.region, local.render_region)` and
   `local.allowed_regions = [local.render_region]`, and the validation on `var.region` in
   `variables.tf` fails at plan time if the effective region is not in the effective allowlist.
   Enforcement is real rather than described: `org_policy.tf` pins
   `constraints/gcp.resourceLocations` to that region's location group, the CMEK key ring
   (`kms.tf`), the locked WORM audit bucket (`logging_worm.tf`) and, when the opt-in serving edge
   is enabled, the Cloud Run service and its regional network endpoint group (`production_edge.tf`)
   are all created in it. The piece your fork must add is the BUILD WIRING: this repo has no
   `tf-check` make target and no terraform CI job, so `infra/terraform/production_edge.tftest.hcl`
   (which needs no project and no credentials, it runs against a mocked provider) only executes
   when somebody types `terraform -chdir=infra/terraform test` by hand. Wire that into your
   pipeline. See [`runbook.md`](runbook.md).
2. **Identity and the IdP.** This repo owns no login flow, and it never will: identity is
   resolved server-side and the client-supplied actor is discarded. Under `gcp` the
   `adapters/gcp/identity.py` adapter verifies the IAP-injected assertion against
   `AMLTRIAGE_IAP_AUDIENCE` (the IAP-protected backend service), with IAP's own key set and an
   explicit issuer check; unset or emptied, it refuses every caller with a 503 rather than
   verifying without an audience. Under `local` the seeded dev personas resolve from
   `X-Dev-Persona` and authenticate nobody, which is why the app-object loopback exposure guard
   keeps that posture off the network. Under `onprem` the placeholder refuses with a 501 naming
   the binding you must supply. Configure auth ON the deployed service (IAP behind the HTTPS load
   balancer), or implement the on-prem adapter against your OIDC/SAML issuer. See
   [`onprem-migration.md`](onprem-migration.md).
3. **The policy numbers your compliance function owns.** Four sets, and none of them is a vendor
   default to inherit unexamined. The band thresholds, the score baseline and the recommendation
   map live in the `policy:` block of `config/settings.yaml`, merged over the reference defaults
   in `domain/policy.py:TriagePolicy` (a block that names only some keys keeps the default for the
   rest). The per-typology `uplift` weights and detector `params` live in
   `src/aml_alert_triage/rulepacks/typologies.yaml`, or in your own pack pointed at by
   `AMLTRIAGE_TYPOLOGY_PACK`. The jurisdictions whose national-identifier rows are redacted live
   in `JURISDICTIONS` in `domain/pii.py` (shipped as `SG`, `HK`, `JP`, `AU`). The eval thresholds
   live in the `THRESHOLDS` dict in `eval/run_eval.py`; this repo has no `eval/rubrics/`
   directory. Add a test that pins YOUR values, so a later refactor cannot quietly move a band.
4. **Typology coverage.** A market or a tightened threshold is a PACK edit, never a code edit: the
   engine carries no jurisdiction branch. A new SHAPE of pattern (something none of
   `structuring`, `rapid_movement`, `funnel_account`, `mule_fanout` describes) is a new pure
   function registered in `domain/typology_engine.py:DETECTORS`, with a unit test that pins its
   arithmetic. Keep detectors pure: the `signal_key` fingerprint is a content hash over the
   firing transactions, and a detector that read a clock or a network would break replay.
5. **Reference data is fictional.** Every subject, counterparty and identifier in the repo is
   obviously synthetic (parties suffixed FICTIONAL, `.example` domains, one checksum-valid
   synthetic national id that exists solely so the redaction check has an independent literal to
   look for). Replace `adapters/local/_fixtures.py`, the `_CORPUS` in `adapters/local/retrieval.py`
   and `tests/fixtures/sample_cases.py` with your own synthetic data. **Do not run this against
   real alerts, real customers or real transaction data without your own legal, security and
   model-risk sign-off.**
6. **The eval golden set.** Rebuild `eval/datasets/golden_cases.jsonl` for your typologies and
   your policy: a fork inherits a green gate that measures the WRONG detection set until you do.
   Every metric scores against the dataset's own `expected_*` oracle rather than against the
   pipeline's verdict, and `tests/unit/test_not_falsely_green.py` proves each one can go red, so
   keep that property when you rewrite the cases. The five metrics
   (`recommendation_accuracy`, `typology_recall`, `groundedness`, `review_safety`, `pii_safety`)
   are generic; the golden cases are yours.
7. **Deployment posture.** Review the Dockerfile (digest-pinned base, non-root, installs from the
   committed lockfile), `infra/terraform/` (Org Policy, CMEK, locked WORM logging, the dry-run-first
   VPC-SC perimeter, the opt-in serving edge), and the loopback-by-default API binding before you
   expose anything. Read `managed_readiness.py` before you plan a managed rollout: the operations
   listed in `INCOMPLETE_MANAGED_OPERATIONS` are still construction-only placeholders, and the API
   preflight refuses to start a `gcp` process while any of them is bound.

## 5. Do not duplicate the platform

This repo is one system in a catalog of composable GRC systems. Several concerns it *touches* are
owned by sibling platform services, and you should integrate rather than rebuild them (see
[`faq/features-faq.md`](faq/features-faq.md) for the full map). What is honestly wired today and
what is still a stub differ, so both are stated:

- **Hrz1** guardrail gateway: **not integrated yet.** Redaction is in place at every boundary
  (`domain/pii.py` plus `pii-kit`), but there is no `GuardrailPort` and no injection screening.
  Rule R1 in [`COMPLIANCE.md`](../COMPLIANCE.md) records that as the open half. Bind it, do not
  write your own screener.
- **Hrz2** governed knowledge base: the `gcp` binding of `RetrievalPort`
  (`adapters/gcp/retrieval.py`) is the seam for Hrz2's governed corpus; it raises today and is
  listed in `managed_readiness.py`. The `local` profile serves a fixture typology-guidance corpus.
  Retrieval informs the NARRATIVE only and never the score.
- **Hrz3** agent registry: this agent builds its A2A card from the same tool table the runtime
  binds and serves it at `/.well-known/agent-card.json` (`agent/agent_card.py`). Registering the
  card and taking the agent's identity and entitlements from Hrz3 is your step.
- **Hrz4** AI-quality and model-risk gate: `eval/run_eval.py --mode gate` is the client half, it
  refuses to run off the managed profile, and it names the bundle `aml-alert-triage` at
  `AMLTRIAGE_QUALITY_URL`. Registering that bundle and its thresholds with Hrz4 is your step; the
  offline `--mode smoke` gate mirrors them.
- **Hrz5** observability and immutable WORM audit: `adapters/gcp/tracer.py` sends OTLP to the
  Hrz5 collector when `OTEL_EXPORTER_OTLP_ENDPOINT` is set and to Cloud Trace when it is not.
  Spans carry structural attributes only, never alert content. The WORM audit half is local and
  hash-chained today (`adapters/local/audit.py`); pointing it at the shared sink is your step.
- **Hrz7** human-review and maker-checker console: fully wired, and the one rule this repo does
  not owe you. Every triage sets `requires_human_review` AND routes through `ReviewRouterPort` to
  the console over the shared `review-kit` in the same call (rule R8), with the payload
  redacted against every jurisdiction's rows before the wire and CRITICAL demanding dual control.
  Set `HUMAN_REVIEW_URL` and the `HUMAN_REVIEW_S2S_*` credentials; do not re-implement the console.
- **Rsk3** architecture and requirements validator: rule R6 is an intake action, not a code
  control. Record your validation reference in `COMPLIANCE.md`.

Adjacent financial-crime verticals in the same catalog own different points of the journey and
should not be rebuilt here: **Doc1** customer due diligence and source of wealth, **G2** sanctions,
PEP and payment-message screening, **G3** scam and authorised-push-payment real-time interdiction,
**G4** account-takeover investigation, **G5** the SOC fraud-fusion copilot, and **Ins1** insurance
claims integrity. G1 starts at a monitoring alert that already exists and ends at a human
disposition; it neither generates the alert nor files the report.

## 6. Adoption checklist

- [ ] Ran `scripts/rename_fork.py` (preview then `--yes`), recreated the venv, `make gate` green.
- [ ] Set `GCP_REGION`, the Terraform `region` / `allowed_regions` tfvars and, if re-basing,
      `render_region` in `infra/terraform/render.tf.json` to your in-country region.
- [ ] Wired `terraform -chdir=infra/terraform test` into a build, so the residency assertions run
      on every change rather than by hand.
- [ ] Wired your IdP on the deployed service and set `AMLTRIAGE_IAP_AUDIENCE` (this repo owns no
      login flow).
- [ ] Owned the policy numbers with your compliance function: the `policy:` block, the pack
      `uplift` and `params` values, `JURISDICTIONS`, and the eval `THRESHOLDS`.
- [ ] Reviewed the typology pack, added the markets you serve, and unit-tested any new detector.
- [ ] Replaced every synthetic fixture and the local guidance corpus.
- [ ] Rebuilt `eval/datasets/golden_cases.jsonl` and kept the not-falsely-green property.
- [ ] Reviewed the deploy posture (Dockerfile, Terraform, bind address,
      `INCOMPLETE_MANAGED_OPERATIONS`).
- [ ] Set `HUMAN_REVIEW_URL` and decided which other sibling services you integrate vs stub.
- [ ] Recorded your baseline upstream tag so you can take future fixes.
