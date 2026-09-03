# Adoption FAQ

For an engineering lead forking this repo as their institution's AML alert-triage base. The
step-by-step is [`../ADOPTING.md`](../ADOPTING.md); this answers the "will it hurt later?"
questions. Cross-references: [`CONTRIBUTING.md`](../../CONTRIBUTING.md),
[`SPEC.md`](../../SPEC.md).

### How do I rebrand it for my organisation?

`scripts/rename_fork.py` rewrites the python package name `aml_alert_triage`, the `AMLTRIAGE`
environment prefix, the distribution and resource id `aml-alert-triage`, and (optionally) the
Terraform `name_prefix` default, in one pass. It prints a plan and writes nothing without `--yes`.
Then recreate the venv, `make install`, and run `make gate`.

Two flags do not exist, on purpose. There is no `--cli`: the console script is named after the
package (`[project.scripts]` in `pyproject.toml` binds `aml_alert_triage`), so `--package` renames
it too and a second flag could only drift out of step. There is no `--dist`: `--resource` is one
literal doing four jobs, the distribution name, the GitHub id in `[project.urls]`, the A2A
agent-card name in `agent/agent_card.py`, and the Hrz4 eval bundle id `_BUNDLE` in
`eval/run_eval.py`, and they are one string so a fork's promotion record and its discovery card
cannot disagree about which system they describe. The human decisions (region, IdP, policy numbers,
typology packs, fixtures, eval golden set) are the checklist in
[`../ADOPTING.md`](../ADOPTING.md).

### If several institutions fork this, how does each take upstream fixes?

Track upstream via **git tags**. The repo declares a core-vs-adopter-owned boundary
([`../ADOPTING.md`](../ADOPTING.md) section 2): upstream owns `domain/kernel.py`, `ports/`,
`tests/contract/`, the eval harness mechanics, the `Container` wiring, the IAP verifier and the
demo mechanics; you own the `config/settings.yaml` values, the typology packs, the seeded fixtures,
`adapters/onprem/*`, the UI theming, the golden dataset and the tfvars. Rebase your adopter-owned
changes onto each release rather than merging `main` continuously, so conflicts stay in files you
were told to expect.

### Is there a real kernel module I can keep untouched?

Yes, and it is a physical split rather than a docstring promise. `domain/kernel.py` holds the
vertical-neutral types (`Severity`, `Decision`, `Citation`, `AuditEvent`, `utcnow`) with the
`StrEnum` taxonomies coming from the commons, and `domain/models.py` holds only the AML artifacts.
A fork building a different financial-crime vertical rewrites `models.py`, the detectors and the
packs, and leaves `kernel.py` alone. `tests/unit/test_core_purity.py` enforces that neither module
reaches for a framework or a cloud SDK.

### How do I retune the triage numbers without touching engine code?

That is the design, and it is the B4 practice this repo actually implements rather than owes. Four
surfaces, all configuration:

- **Bands, baseline and dispositions**: the `policy:` block in `config/settings.yaml`, merged over
  the reference defaults in `domain/policy.py:TriagePolicy` by `from_mapping`. A block naming only
  some keys keeps the default for the rest, so you can tighten one threshold without restating the
  whole policy. `TypologyEngine` takes a `TriagePolicy` by construction and reads every threshold
  off it; there is no band number written inline in `typology_engine.py`.
- **Typology weights and detector thresholds**: `src/aml_alert_triage/rulepacks/typologies.yaml`,
  or your own pack pointed at by `AMLTRIAGE_TYPOLOGY_PACK`. Each pack names a detector, supplies
  the thresholds that detector reads, its score `uplift` and the regulator instrument its hit
  cites.
- **Redaction jurisdictions**: `JURISDICTIONS` in `domain/pii.py`.
- **Eval thresholds**: the `THRESHOLDS` dict in `eval/run_eval.py`. Note this repo has no
  `eval/rubrics/` directory; the thresholds are that one dict.

Add a test that pins YOUR values. The shipped numbers are a reference, not your policy, and
[`COMPLIANCE.md`](../../COMPLIANCE.md) explicitly makes second-line review of the deterministic
policy an adopter obligation.

### How do I add a typology, or a whole new market?

A market is a **pack**, never a code edit: the engine carries no jurisdiction branch, so adding
Hong Kong thresholds beside Singapore ones is a YAML entry. A new SHAPE of pattern (something none
of `structuring`, `rapid_movement`, `funnel_account` or `mule_fanout` describes) is a new pure
function in `domain/typology_engine.py:DETECTORS` with the signature
`(window, params) -> (fired, measure, triggering_txn_ids)`, plus a pack that names it and a unit
test that pins its arithmetic. `TypologyEngine.__post_init__` refuses at construction if a pack
names a detector that does not exist, so a typo is a boot error rather than a silently dropped
typology. Keep the detector pure: `signal_key` is a content hash over the firing transactions, and
a detector that read a clock or the network would break replay.

### How do I add a new outbound dependency (a new port)?

There is a fixed touch list and the contract test enforces it in both directions. A port must be
registered in FIVE places or it runs with no enforcement at all: `ports/__init__.py`
(`PORT_PROTOCOLS`), `config.DEFAULT_BINDINGS`, a `Container` accessor, `config/settings.yaml`, and
a `PortCase` in `tests/contract/canonical.py`. Then bind it in all three families, with the cloud
import inside the method and the on-prem adapter RAISING rather than pretending.
`tests/contract/test_port_parity.py` asserts set equality across all five. The full walkthrough,
with the test that enforces each row, is in [`CONTRIBUTING.md`](../../CONTRIBUTING.md).

### Will the demo rot after I diverge?

It is guarded from inside the offline gate. A demo step exists in exactly two places,
`demo.STEPS` and `walkthrough.CHECKS`, and `tests/unit/test_demo_surface.py` holds the two equal,
so a claim the demo narrates but nobody verifies cannot exist. `make demo-selftest` runs the whole
arc headless against the real services and is its own required CI check
(the hosted GitHub Actions check), deliberately NOT folded into `make gate`, because the gate
proves the service and must stay fast and offline. `tests/unit/test_demo_surface.py` also fails the
gate if a script is deleted, stops importing, or stops being listed in `scripts/README.md`, so
adding your own script means adding its row. There is no browser automation anywhere in the demo
surface: the walkthrough drives the demo server over plain loopback HTTP with the standard library,
which is why the presenter tool and the self-test are the same file.

### Does the offline gate run for my fork out of the box?

Yes. `make gate` is `ruff check` plus `ruff format --check`, `mypy src`,
`pytest -m 'not integration'` and the eval smoke run, and it is deliberately offline and
credential-free: no cloud SDK, no project, no network. If a change makes the gate need any of
those, the change is wrong, not the gate. `make audit` (pip-audit over both lockfiles) is separate
precisely because it is the one step that needs a vulnerability feed. The integration suite is
marked and deselected, and `tests/unit/test_test_layout.py` fails if a test is dropped into the
`tests/` root where nobody would notice its marker.

Note what the gate is measuring on day one for you: the eval scores the REFERENCE typology packs
and the reference golden cases. Until you rebuild `eval/datasets/golden_cases.jsonl` for your own
detection policy, a green gate means the harness works, not that your policy is right. That is an
explicit adoption step, not a silent pass, and
`tests/unit/test_not_falsely_green.py` exists so you can trust the metrics are capable of failing.

### What about dependency updates and the lockfiles?

After any dependency change run `make lock` and commit `uv.lock` together with both exported
`requirements-*.lock` files: `uv.lock` is the resolution and the two exports are what the
Dockerfile, CI and every `pip install -r` consume. `make lock` runs `scripts/lock.py` rather than
uv directly, because `uv pip compile` REPLACES the output file and would destroy the tag-to-commit
provenance map that `tests/unit/test_repo_artifacts.py` checks. An uncommitted resolution is a
version set nobody reviewed.
