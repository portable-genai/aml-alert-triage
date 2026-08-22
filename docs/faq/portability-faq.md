# Portability FAQ

For architecture, cloud, and exit-planning reviewers who want to know how real the "no lock-in"
claim is and how an off-cloud or sovereign exit would actually work. Cross-references:
[`ARCHITECTURE.md`](../../ARCHITECTURE.md), [`../onprem-migration.md`](../onprem-migration.md),
[`../runbook.md`](../runbook.md).

## What is the no-lock-in claim, concretely?

The `domain/` package is pure standard library: no Google Cloud SDK, no FastAPI, no httpx, no
pydantic, no HTTP at all. Every boundary is a `@runtime_checkable` `Protocol` in `ports/`
(`AlertFeedPort`, `WarehousePort`, `RetrievalPort`, `NarrationPort`, `AuditSinkPort`,
`ReviewRouterPort`, `ObservabilityTracerPort`, plus the commons `IdentityPort`), and the whole
adapter stack is selected by one setting. `tests/unit/test_core_purity.py` walks the imports of
`domain/` and fails the build on anything the core does not own, and it proves its own scan can see
a violation rather than trusting that a green run means anything.

## What are the three profiles?

`AMLTRIAGE_PROFILE` selects the whole adapter family, and this repo ships three rather than four:

- **`local`** (the dev, test, CI and demo stack): SDK-free and genuinely working. A seeded
  fictional alert queue and transaction windows, a fixture typology-guidance corpus, a
  deterministic grounded narrator, a hash-chained SQLite WORM audit log from the commons, seeded
  dev personas, and a review-kit outbox that really enqueues rather than silently returning.
- **`gcp`**: the managed stack, with every cloud SDK imported LAZILY inside the method so the other
  two profiles import the same modules with nothing installed. Cloud Logging WORM, IAP identity,
  OTLP or Cloud Trace, the Hrz7 console over service-to-service auth, and the Hrz4 promotion gate
  are wired; the BigQuery alert feed and warehouse, the Hrz2 retrieval and the Gemini narration are
  still construction-only placeholders, listed by name in `managed_readiness.py`.
- **`onprem`**: fail-fast placeholders that satisfy the same Protocols and RAISE
  `NotImplementedError` naming the migration target. That is the reversibility proof (P-12): a
  review router that silently returned would convert every consequential result into an unreviewed
  one, which is worse than a missing feature.

## Is the managed profile allowed to pretend it is complete?

No, and this is the part most repos get wrong. `managed_readiness.py` holds
`INCOMPLETE_MANAGED_OPERATIONS`, a tuple naming every managed adapter operation that is still a
placeholder, and `assert_managed_profile_ready` refuses to let a `gcp` process start while any of
them is actually bound by the selected binding map. So a Cloud Run service cannot become healthy
while an operation on its primary journey is construction-only. `tests/unit/test_managed_readiness.py`
holds that behaviour, and the Terraform side has a matching serving-authorization check
(`check "managed_profile_is_implemented_before_serving"` in `infra/terraform/managed_readiness.tf`,
exercised by the `serving_edge_contract` run in `infra/terraform/production_edge.tftest.hcl`).

## Is the portability claim tested, or just asserted?

Tested, and bounded. `make portability` runs `scripts/portability_demo.py` offline and exits
non-zero on any failed check. The eight named checks are: port map complete, adapters construct and
conform, offline family answers, exit family refuses, rewrite detected, truncation detected when
anchored, record leaves intact, and no cloud SDK imported. The script also prints what it does NOT
prove: that an on-premises deployment exists or that anyone has run one, infrastructure or model or
network portability, and anything at all about the managed profile's live behaviour, which needs a
cloud project and lives in `tests/integration/`. An unbounded claim is the one an auditor disproves
for you.

Alongside it, the contract suite is structural: `tests/contract/test_port_parity.py` asserts set
equality of the port registry across FIVE places (`ports/__init__.py`'s `PORT_PROTOCOLS`,
`config.DEFAULT_BINDINGS`, the `Container` accessors, `config/settings.yaml`, and the canonical-call
table in `tests/contract/canonical.py`), in both directions, so a port that is bound but
unregistered fails the build instead of running with no enforcement.
`tests/contract/test_behavioral_parity.py` drives one canonical request per port through the local
and exit families and asserts they behave identically at the boundary.

## How would a sovereign or on-prem exit actually go?

The `onprem` profile is the scaffold and each refusal marks a seam a client fills: their alert
feed, their transaction warehouse, their retrieval store, their own hosted model, their IdP, their
audit store, their review console. Because the domain never changes, the exit is an adapter
exercise rather than a rewrite: `domain/typology_engine.py` and `domain/policy.py` compute the same
score and band with no infrastructure at all. The refusals even have a SHAPE: the on-prem identity
placeholder raises a 501-carrying error rather than a bare `NotImplementedError`, so an operator
gets a reason instead of a stack-trace-shaped 500, while keeping `NotImplementedError` in its
ancestry so the uniform exit-family claim stays true. See
[`../onprem-migration.md`](../onprem-migration.md).

## How is data residency handled?

The region is selected ONCE and shared by the runtime and the infrastructure: `GCP_REGION` feeds
`region:` in `config/settings.yaml`, which is reported by `/healthz` and printed on the A2A agent
card, and `render_region` in `infra/terraform/render.tf.json` is the same value on the Terraform
side. Both `var.region` and `var.allowed_regions` default to null, meaning "exactly the rendered
region", and `variables.tf` validates the EFFECTIVE region against the EFFECTIVE allowlist at plan
time, so both mistakes fail fast: a region outside the allowlist, and an allowlist customised to
exclude the rendered default while the region was left unset. A second region is a tfvars change,
not a fork. See [compliance-faq.md](compliance-faq.md) for what is enforced versus what is still
manual.

## Can the data be exported in an open format?

Yes. The audit trail exports to and restores from JSON Lines, so the exit for the record of what
this service decided is a file copy rather than a migration project, and the `record leaves intact`
portability check proves the round trip in-process. The domain artifacts are frozen dataclasses
serialised through the commons `to_jsonable` walker, so the API response, the agent card and the
audit payload are all plain JSON with no vendor envelope.

## What is honestly NOT portable?

Tamper-evidence and export-reload are scoped to what the local sink can prove, and
`portability_demo.py` says so rather than overclaiming. Production tamper-evidence is the managed
WORM sink's job: **Hrz5** plus the locked Cloud Logging bucket in `infra/terraform/logging_worm.tf`,
whose retention lock is irreversible by design. Nothing here proves the managed profile's live
behaviour either, because proving that needs a real project, which is exactly why those tests are
marked `integration` and deselected from the offline gate.
