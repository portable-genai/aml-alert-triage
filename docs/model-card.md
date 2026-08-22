# Model card: AML Alert Triage (G1)

This is a STARTER model card. It records the model boundary as built and the controls that must be
completed before a managed deployment. The deterministic engine is the system of record; the model
is a bounded, replaceable component that sits on exactly one seam.

**State the honest headline first: no model runs in this repository today.** The one model-shaped
port, `NarrationPort`, is bound in all three profiles, but the `local` binding is a deterministic
stdlib narrator, the `gcp` binding lazily imports the Google GenAI client and then raises
`NotImplementedError`, and the `onprem` binding refuses on principle. The seam is real, it is
validated at both ends, and the managed inference call behind it is the piece an adopter wires.
Nothing below claims a model that has been evaluated in this repo.

## What the model does, and does not do

- **Does**: draft the SAR narrative prose. It receives a `NarrationRequest`
  (`domain/models.py`) carrying the subject, the engine's score, band and recommendation, the
  `TypologyHit` rows that fired with their measures and instrument citations, and the retrieved
  typology-guidance passages, and it returns a `NarrationDraft` of text plus the source ids it
  cited. The `RetrievalPort` that supplies those passages is the grounding half of the same seam;
  it informs the NARRATIVE only, and
  `tests/unit/test_triage_service.py::test_the_assessment_is_identical_with_retrieval_stubbed_empty`
  proves the assessment does not move when retrieval returns nothing.
- **Does NOT**: produce any number, band, verdict or disposition. Which typologies fired, each
  hit's `measure` arithmetic, the stable `signal_key` fingerprint, the base score, the risk score,
  the severity band and the close / request-info / escalate-to-SAR recommendation are ALL computed
  by `domain/typology_engine.py` (`TypologyEngine.assess` over the four pure detectors in
  `DETECTORS`) in pure stdlib, reading its thresholds off `domain/policy.py` (`TriagePolicy`) and
  the packs in `src/aml_alert_triage/rulepacks/typologies.yaml`. `domain/typology_engine.py`
  imports no model and no port. Given the same window, the same packs and the same policy, the
  whole `ScoreCard` is byte-identical, so an investigator can recompute it without the model. The
  standing gates are `test_bands_and_recommendations_are_deterministic`,
  `test_the_score_is_base_plus_uplifts_clamped` and `test_the_signal_key_is_stable_across_runs`,
  all in `tests/unit/test_triage_service.py`. A model change cannot move a figure.

## Boundary and validation

- **What reaches the model is minimised by construction, not by trusting a filter.** The alert's
  free-text `narrative`, which is where a raw identifier actually lives in this vertical, is never
  put in the `NarrationRequest`: `TriageService.triage` builds that request from the engine's
  `ScoreCard` fields and the retrieved passages only. There is no prompt path for the raw alert
  text to take.
- **Redaction is applied at every boundary that does carry free text (P-04).** Before the WORM
  audit write, in `domain/triage_service.py`, using `redact(..., PII_PATTERNS)` over the
  jurisdiction pattern selection in `domain/pii.py`; before the review payload leaves the process,
  in `adapters/_review_payload.py`, against EVERY jurisdiction's rows because the Hrz7 console is a
  shared sink; and before a tool result can become a model's context, in `agent/tools.py`, which
  walks the whole JSON structure rather than three named fields. Proven by
  `tests/unit/test_triage_service.py::test_pii_is_redacted_before_the_audit_write`,
  `tests/unit/test_review_routing.py::test_the_payload_is_redacted_before_it_leaves_the_process`
  and `tests/unit/test_agent_surface.py::test_the_tool_output_is_masked_before_it_can_reach_a_model`.
  The alert narrative is also redacted inside the domain before it is attached as a citation, so
  no raw identifier travels on the API response either.
- **The draft is validated against the engine, and a bad draft is discarded rather than
  repaired.** `TriageService._grounded_draft` rejects a draft on either of two conditions:
  `domain/grounding.py:ungrounded_numbers` finds a numeric token absent from the narrator's own
  inputs (an invented figure), or the draft cites a source id that was never offered to it. Either
  one discards the WHOLE draft in favour of `domain/grounding.py:grounded_skeleton`, the
  deterministic cited narrative built from engine figures alone. A narrator that raises is treated
  the same way, so a triage never waits on a model to be available.
  `tests/unit/test_triage_service.py::test_a_narrator_that_invents_a_number_is_discarded` proves
  the rejection, and the eval harness scores it as the `groundedness` metric with a threshold of
  1.0, which `tests/unit/test_not_falsely_green.py::test_groundedness_can_go_red` proves can fail.
- **R8: every outcome is routed, not merely flagged.** `requires_human_review` is unconditionally
  true on every `TriageAssessment`, including a proposed CLOSE, and the API, the CLI and the agent
  tool each call `ReviewRouterPort.route` in the same call that produced the result, returning a
  `review_ref`. CRITICAL demands two approvals (`adapters/_review_payload.py`). The managed router
  REFUSES when no console is configured rather than swallowing the escalation, and the on-prem
  placeholder refuses rather than dropping it. `tests/unit/test_review_routing.py` is the standing
  gate. The system never files a SAR and never closes an alert autonomously.

## Adapters and profiles

| Profile | Narration adapter | Behaviour |
|---|---|---|
| `local` | `adapters/local/narration.py` | Deterministic grounded narrator: returns `grounded_skeleton(request)`. No model, no SDK, grounded by construction. This is what the offline gate, the eval harness and the demo run. |
| `gcp` | `adapters/gcp/narration.py` | Placeholder for Gemini on the Agent Platform. Lazily imports `google.genai`, then raises `NotImplementedError` naming the runbook. Listed in `managed_readiness.py` as `narration.CloudNarration.narrate`, so the API preflight REFUSES to start a `gcp` process while it is bound. |
| `onprem` | `adapters/onprem/narration.py` | Fail-fast placeholder for a client-hosted model (P-12): raises `NotImplementedError` naming `docs/onprem-migration.md`. |

The grounding half of the seam follows the same shape: `adapters/local/retrieval.py` serves a
fixture typology-guidance corpus, `adapters/gcp/retrieval.py` is the seam for the Hrz2 governed
knowledge base and raises today (also listed in `managed_readiness.py`), and
`adapters/onprem/retrieval.py` refuses.

There is no speech, audio or OCR port in this repo. The only model-shaped seam is narration.

## Remaining controls (TODO, repo owner)

- **Implement the managed narration call at all, then pin its model id and version** (P-07,
  P-11). `adapters/gcp/narration.py` is construction-only. Write the real call and its prompt
  template, add the integration test that proves the response mapping, remove the entry from
  `INCOMPLETE_MANAGED_OPERATIONS` in `managed_readiness.py`, and record the exact model id here.
  Note that the single model id currently written in this repo, `gemini-3.5-flash` in
  `eval/run_eval.py`, is a label passed to the Hrz4 `PromotionGateClient`; it names no inference
  call this repo makes.
- **Budget, rate controls and a kill switch** (P-10, P-11). None exist, because no model call
  exists: [`COMPLIANCE.md`](../COMPLIANCE.md) records P-10 and P-11 as TODO honestly. When the
  managed narrator is wired, add a per-request token budget, a request rate limit, a timeout and a
  circuit breaker, and a switch that forces deterministic-only operation. The fallback path for
  that switch already exists and is tested: the orchestrator already falls back to
  `grounded_skeleton` whenever the narrator fails.
- **Evaluate the live model through the Hrz4 gate** (P-08, R5). The offline eval scores the
  deterministic local narrator against the golden oracle in `eval/datasets/golden_cases.jsonl`, so
  `groundedness` is currently proving the harness rather than a model. Register the bundle
  `aml-alert-triage` and its thresholds with Hrz4, then add a managed-profile eval run
  (`eval/run_eval.py --mode gate`) that scores real drafted narratives against the same cases.
- **Prompt-injection screening through Hrz1** (R1). The retrieved guidance passages and, in any
  fork that widens the request, the alert text are untrusted input to a model. Bind a guardrail
  port to the Hrz1 gateway at the model boundary for input screening and output filtering, failing
  closed to the deterministic skeleton when the screen is unavailable. No `GuardrailPort` exists
  today.
- **Route the prompt and response record to Hrz5** (R2). Spans from `adapters/gcp/tracer.py`
  deliberately carry structural attributes only (action, actor, alert feed) and never content, so
  a managed model path needs the redacted prompt/response record to reach the shared immutable
  sink rather than only this process's WORM log.

Until these are complete the system is safe to run offline: the deterministic engine plus the
deterministic narrator produce a fully cited, replayable assessment that always routes to a human.
The managed model path is not production-cleared, and it is not merely undocumented as such: the
process preflight in `managed_readiness.py` refuses to start it.
