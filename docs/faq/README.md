# FAQ index

Answers to the questions different teams ask when evaluating, adopting, or reviewing this
repository as a common base for AML alert-triage agents (catalog id **G1**, written `Fcc1` in this
repo's own document headers). Each file is written for a specific audience; skim the one that
matches your role.

| FAQ | For | Answers |
|---|---|---|
| [security-faq.md](security-faq.md) | AppSec / security review | what the service processes, server-side identity and the exposure guard, redaction at every boundary, secrets, supply chain, the anchored audit chain, what is out of scope |
| [portability-faq.md](portability-faq.md) | Architecture / cloud / exit planning | the no-lock-in claim, the three profiles, the executable portability check, the sovereign exit, residency, data export |
| [features-faq.md](features-faq.md) | Product / financial-crime operations / delivery | what the agent produces, what is deterministic vs drafted, and the full "what this repo owns vs what it integrates" map |
| [adoption-faq.md](adoption-faq.md) | Engineering leads forking the repo | the rebrand script, taking upstream fixes, extension points, retuning typologies and policy, the demo guard |
| [compliance-faq.md](compliance-faq.md) | Compliance / MLRO / model risk / privacy | autonomy and maker-checker, PII handling, auditability, the model-risk story, residency enforcement, regulator crosswalk ownership |

These FAQs deliberately do **not** re-document capabilities owned by sibling systems in the
catalog. Where a concern belongs to another repo (the guardrail gateway, the governed knowledge
base, the agent registry, the AI-quality gate, the observability and WORM audit platform, the
human-review console), the FAQ names the owning catalog id and explains the boundary rather than
duplicating it. See [features-faq.md](features-faq.md) for the full map, and
[`../ADOPTING.md`](../ADOPTING.md) for the fork path.
