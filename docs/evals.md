# How the AML alert triage agent is evaluated

Read this page if you decide what this service is allowed to close. The metrics, the bars and the
corpus below are generated from the artifacts that actually gate the build, so they cannot drift
from what runs: `make evals-doc-check` fails the build when this page and those artifacts
disagree.

## How to run it

```sh
make eval              # offline, no credentials
make evals-doc-check   # this page is still true
```

`make gate` runs both on every change.

## The metric that carries the business case, and why it did not exist

The pitch for alert triage is not "it finds the structuring case". A monitoring rule already
found that, which is why the alert exists. The pitch is that it **closes the alerts that should
never have reached an investigator**, and nothing measured that.

The golden set held one clean alert against three that escalate. A false-positive rate over one
negative is not a rate; it is an anecdote with a percentage sign. Eight benign alerts are now in
the corpus, each benign for a different reason, and `suppression_rate` scores what share of them
the engine actually closes.

**It closes six of the eight, and the two it does not are recorded rather than relabelled.**

- `FCC-2001`, a monthly salary run to eight employees, fires the fan-out rule and escalates. A
  salary run is structurally identical to a mule fan-out in transaction data alone.
- `FCC-2004`, an intra-group treasury sweep that goes out and comes back to the SAME counterparty
  the next day, fires the rapid-movement rule. Layering and a treasury sweep differ by whether the
  counterparty is inside the same legal group.

Both need **counterparty context** the transaction window does not carry: a payee role, and a
group membership. That is a product change, not a threshold change. Until it lands, the bar holds
the line at where the engine is, so a regression is caught even though the gap is not closed; the
rubric records the target and what would have to change to reach it.

`recommendation_accuracy` reads 0.833 rather than 1.000 for the same reason. That drop is the
corpus working.

## What is measured, and against what bar

Every bar below lives in `eval/rubrics/*.yaml` next to the argument for it, and the
runner reads it from there. There is no dict of thresholds in the runner any more: a
metric scored with no reviewed bar fails the build, and so does a bar that names no
metric, which is the direction that rots quietly because it rots toward looking well
governed.

The third column is the denominator rule, and it applies only where a score is a
FRACTION over scored positives: such a threshold `t` tolerates a single miss only over
at least `1/(1-t)` of them. `all or nothing` marks a bar that already asks for no
headroom, so a bigger corpus would not change what it means. Each rubric declares which
it is rather than the rule being guessed from the number.

| Metric | Bar | Denominator | What it measures |
|---|---|---|---|
| `groundedness` | 1 | all or nothing | The triage narrative states no number the engine did not compute. |
| `pii_safety` | 0.99 | all or nothing | No raw identifier survives into any audit record, checked by the shared pack and by an independent planted literal. |
| `recommendation_accuracy` | 0.8 | a rate; needs 5 positives | The recommendation the engine reaches equals the one a hand-review assigned, across escalating and closing alerts alike. |
| `review_safety` | 1 | all or nothing | Every triage outcome requires human review and routes to the review console. |
| `suppression_rate` | 0.75 | a rate; needs 4 positives | Share of the alerts a hand-review marked as should-close that the engine actually recommends closing. The false-positive rate, from the investigator's side. |
| `typology_recall` | 0.9 | a rate; needs 10 positives | Every typology a reviewer recorded for an alert is fired by the engine. |

Scored over 12 golden alerts.

## What is exercised

- **12 golden alerts** in `eval/datasets/golden_cases.jsonl`, with the band,
  recommendation and typologies a hand-review assigned. The oracle is the reviewer's,
  never a re-read of the pipeline's verdict.
- **4 that escalate**, one per typology, which is what `typology_recall`
  is measured over.
- **8 that a hand-review says should CLOSE**, which is what
  `suppression_rate` is measured over. There was one. Each is benign for a DIFFERENT
  reason, because a suppression metric over one shape of clean alert proves only that
  the engine can close that shape:

  - `FCC-2001` monthly salary run to eight employees
  - `FCC-2002` settlement to a long-standing supplier
  - `FCC-2003` scheduled round-value loan repayment
  - `FCC-2004` intra-group treasury sweep, returned next day
  - `FCC-2005` seasonal turnover spike from the usual customers
  - `FCC-2006` one large inbound credit that was not moved on
  - `FCC-2007` dormant account transacting with a known counterparty
  - `FCC-2008` single large outflow to a government body

- **1 alert plants a raw identifier**, so the leak metric has a target it could
  miss.

## How a metric is prevented from being decoration

1. **The bars are read from the rubrics, in both directions.** This repository had no rubric
   directory at all: every bar was an unlabelled module constant, which is exactly what practice
   E1 asks a repository not to do. `assert_covers` now fails the build when a metric has no
   reviewed bar AND when a bar names no metric.
2. **The corpus must be able to express its own bars.** `recommendation_accuracy` at 0.80 was
   arithmetically identical to 1.0 over four alerts: a 0.80 bar tolerates one miss only over five.
   Twelve alerts make it expressible for the first time.
3. **The suppression corpus has a floor of its own.** The runner refuses a golden set with fewer
   than five should-close alerts, because a false-positive rate over a handful of negatives says
   nothing whatever its value.

## What is NOT measured here

- **A real model's words.** Every metric scores a deterministic core against a deterministic fake
  model adapter.
- **Precision of the typology hits.** `typology_recall` is deliberately one-directional: an extra
  typology on an alert that is escalating anyway costs an investigator a paragraph, while a missed
  one is the reason the escalation says the wrong thing to a regulator.
- **Production traffic.** Everything here is a golden set. Nothing samples live requests.
