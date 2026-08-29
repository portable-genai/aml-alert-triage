# Security FAQ

For an AppSec reviewer sizing up this repo. It explains what the attack surface is, what is
deliberately out of scope (and why that is honest, not a gap), and where the evidence lives.
Cross-references: [`ARCHITECTURE.md`](../../ARCHITECTURE.md), [`SPEC.md`](../../SPEC.md),
[`../practices-audit.md`](../practices-audit.md).

## What does this system actually process?

Financial-crime alert data, and it is genuinely sensitive. A monitoring alert carries a subject
(an account holder or entity), a free-text alert narrative, and a transaction window of individual
transactions with counterparties, amounts, currencies, channels and country codes. Unlike the
aggregate-only systems in this catalog, **this one has a real personal-data surface**, so the
controls below are load-bearing rather than declared not-applicable. It produces a risk score, a
band, a disposition recommendation, a cited SAR narrative and an audit record.

## Where is PII redacted, and can I see it fail?

At every boundary that carries free text, not once. The pattern selection is
`domain/pii.py:PII_PATTERNS`, built from the shared `pii-kit` (national-identifier rows for the
configured `JURISDICTIONS`, then the universal email and phone rows, in that order deliberately).
The three boundaries:

- **Before the WORM audit write.** `domain/triage_service.py` redacts the summary, the alert
  narrative and the drafted text in the same expression that constructs the `AuditEvent`. Proven by
  `tests/unit/test_triage_service.py::test_pii_is_redacted_before_the_audit_write`.
- **Before the review payload leaves the process.** `adapters/_review_payload.py` masks against
  EVERY jurisdiction's rows plus the universal ones, not just this deployment's, because the Hrz7
  console is a shared sink and a case filed in one market can still quote another market's
  identifier. Proven by
  `tests/unit/test_review_routing.py::test_the_payload_is_redacted_before_it_leaves_the_process`.
- **Before a tool result can become model context.** `agent/tools.py` walks the whole JSON
  structure rather than three named fields, so a field added later cannot arrive unredacted.
  Proven by
  `tests/unit/test_agent_surface.py::test_the_tool_output_is_masked_before_it_can_reach_a_model`.

You can see it fail: the eval harness scores `pii_safety` with a two-part oracle (a pack scan plus
an independent planted-literal check that fires even if a pattern row is broken), and
`tests/unit/test_not_falsely_green.py::test_pii_safety_can_go_red` proves the metric is capable of
going red rather than being decorative.

## How is identity handled? Can a caller spoof the actor?

No. Identity is resolved server-side on every route. `api/schemas.py:TriageRequest` carries no
`actor` field, and `api/app.py:get_principal` builds a `RequestContext` and resolves a verified
`Principal` through the bound `IdentityPort`; the verified actor is what reaches the audit event
and the review maker, never the request body. Under `gcp`, `adapters/gcp/identity.py` verifies the
IAP-injected assertion against the configured `AMLTRIAGE_IAP_AUDIENCE`, using IAP's own key set
rather than google-auth's OAuth2 default, and checking the issuer itself; an unset or emptied
audience refuses every caller rather than verifying without one, because `audience=None` means the
audience is not verified and would accept any Google-signed token from any project. Caller faults
are 401 with the reason kept in the log; deployment faults are 503 naming the fix.
`tests/unit/test_iap_identity.py` runs in every gate and `tests/unit/test_iap_crypto_matrix.py`
drives the real verifier over locally minted assertions.

## What stops the unauthenticated local profile from being served on a network?

The loopback exposure guard, bound at MODULE scope in `api/app.py` because the Dockerfile `CMD`
and `make run-api` serve the app OBJECT, so a bind that lived only in `main()` would never run in a
shipped process. Its posture is derived from the identity BINDING alone: an adapter declares
`VERIFIED`, `CLIENT_ASSERTED` or `UNIMPLEMENTED` (`ports/identity.py`), and only `VERIFIED` lets
the guard stand down. The service-to-service token takes no part in that decision, which is the
specific defect the design exists to prevent: while it did, setting `AMLTRIAGE_S2S_TOKEN` switched
the guard off for the end-user routes it was protecting.
`tests/unit/test_serving_path_exposure.py` and `tests/unit/test_end_user_auth_posture.py` are the
standing gates. Interactive docs (`/docs`, `/redoc`, `/openapi.json`) are ABSENT rather than
guarded under any profile other than the deliberate `local` one.

## What happens if the profile variable goes missing in a deployment?

The deployment fails visibly rather than serving a stranger. `AMLTRIAGE_PROFILE` resolves once, at
import, into a `ProfileChoice` with three states: unset is NO CHOICE (the SDK-free adapters still
bind, but the seeded personas are refused, no S2S scheme is selected, the dev CORS allowlist and
the `X-Dev-Persona` header are withdrawn, and the guard refuses every non-loopback peer);
set-and-empty raises at import; set-and-unknown, including a mis-capitalised `Local` or `GCP`,
raises at import. Only `config.py` may read the variable, enforced by
`tests/unit/test_profile_single_source.py`, and `tests/unit/test_three_state_env_reads.py` walks
the AST of `src/`, `scripts/` and `eval/` and fails the build on ANY two-state environment read
that ships.

## Are there secrets in the repo?

No literal secret material. `config/settings.yaml` carries only `${VAR:-default}` interpolation
tokens and non-secret policy numbers; `.env.example` documents the non-secret variable names and
`.env.secrets.example` documents the secret NAMES with placeholder values. Inbound and outbound
credentials are deliberately distinct variables: this service's own inbound `AMLTRIAGE_S2S_TOKEN`
is not the outbound `HUMAN_REVIEW_S2S_TOKEN` / `HUMAN_REVIEW_S2S_SIGNING_KEY` it presents to the review console.
The IAP audience is read from settings at adapter construction and is never logged.

## What is the supply-chain posture?

Committed lockfiles (`requirements-dev.lock`, `requirements-gcp.lock`, plus `uv.lock` as the
resolution) installed with `--no-deps` by `make install`, CI and the Dockerfile. The four commons
packages (`pii-kit`, `hex-service-kit`, `agent-eval-kit`, `review-kit`) are declared by tag
in `pyproject.toml` and pinned in the lockfiles to the 40-character COMMIT each tag resolved to,
because a tag can be moved and a commit cannot;
`tests/unit/test_repo_artifacts.py` asserts that three-way agreement offline. Ruff is pinned
exactly. The base image is digest-pinned and the container runs non-root. `pip-audit` over both
lockfiles is `make audit` and a hard-failing CI job, kept out of `make gate` because it is the one
step that needs a network.

## Is the audit trail tamper-evident?

Yes, within honest limits, and it is anchored rather than only chained. `adapters/local/audit.py`
wraps the commons hash-chained WORM log, and `audit_anchor_path` points at a file on a DIFFERENT
volume that every append writes the chain head to. The chain alone catches an edit, a deletion or a
reorder; only the anchor catches a truncated tail, because a truncated chain still verifies
perfectly. Once store and anchor disagree the service refuses to append rather than re-anchoring,
so an ordinary write cannot launder a divergence. `tests/unit/test_audit_anchor.py` proves both
halves including the control case that goes undetected without an anchor. In production the
enterprise WORM sink is **Hrz5** plus the locked Cloud Logging bucket in
`infra/terraform/logging_worm.tf`; the in-repo store is the offline stand-in.

## What is explicitly out of scope for this repo?

Prompt-injection screening and output filtering (**Hrz1**, and note that this is currently NOT
integrated: rule R1 in [`COMPLIANCE.md`](../../COMPLIANCE.md) names it as the open half), the
governed knowledge base (**Hrz2**), the agent registry and entitlements (**Hrz3**), the AI-quality
and promotion gate (**Hrz4**), the enterprise WORM audit and tracing sink (**Hrz5**), and the
human-review console with its case state and SLA clocks (**Hrz7**). This repo integrates those
through ports rather than re-implementing them. See [features-faq.md](features-faq.md) for the full
boundary map and which of them are wired today.
