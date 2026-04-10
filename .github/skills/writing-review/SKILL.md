---
name: writing-review
description: Structured procedure for reviewing research text — checking evidence grounding, overclaiming, terminology, and code-claim alignment.
---

# Writing Review

## Goal

Critically evaluate research text for scientific soundness, evidence grounding, and defensibility against peer review.

## Checklist

### Evidence Grounding
- [ ] Every quantitative claim cites a specific run ID, metric, or data file.
- [ ] Numbers match what the code/data actually produces (spot-check at least 3).
- [ ] Figures accurately represent the underlying data (no misleading axes, no cherry-picked runs).
- [ ] Qualitative claims ("improves", "outperforms", "ensures") are backed by metrics with statistical context.

### Contribution Scope
- [ ] Contributions are stated as what the work *shows*, *provides*, or *demonstrates* — not universal proofs.
- [ ] The distinction between this work's contribution and prior work is clear.
- [ ] Limitations are stated explicitly and specifically (not generic hedges like "future work will address...").
- [ ] No hidden assumptions — every assumption is stated.

### Overclaiming Patterns
- [ ] "Guarantees" / "proves" / "ensures" — is there actually a proof or formal argument?
- [ ] "Outperforms" — compared to what baseline, on what metric, with what statistical confidence?
- [ ] "General" / "any" / "all" — is the claim actually shown for all cases, or only tested ones?
- [ ] "Novel" — is it clearly differentiated from the closest prior work?
- [ ] "Zero violations" — across all regimes and seeds, or only favorable conditions?

### Terminology
- [ ] Key terms used consistently: structural uncertainty, feasible action set, supervisor-enabled set, containment, evidence, belief, trace, invariant, admissible, regime.
- [ ] Terms match field conventions (DES/SCT, holonic manufacturing, digital twin literature).
- [ ] No term is used with conflicting meanings in different sections.

### Code–Claim Alignment
- [ ] The algorithm described in the paper matches the code implementation.
- [ ] Config parameters mentioned in the paper match actual config files.
- [ ] The experimental setup described matches the scenario/batch definitions.
- [ ] Architecture diagrams match the actual module structure.

### Reproducibility in Text
- [ ] Enough detail for an independent researcher to reproduce (or clear reference to the repo).
- [ ] Seed policy, number of replications, and confidence intervals documented.
- [ ] Simulation parameters either listed or referenced to a config file.

## Severity Levels

| Level | Meaning | Action |
|-------|---------|--------|
| CRITICAL | Claim is false, unsupported, or contradicted by evidence | Must fix before submission |
| SIGNIFICANT | Claim is overstated or evidence is weak | Should fix; weakens the paper |
| MINOR | Imprecise wording or missing context | Fix if possible; not a blocker |
| SUGGESTION | Could strengthen the text but not required | Optional improvement |

## Report

For each issue:
- Severity level.
- The specific claim or sentence.
- What the evidence shows vs. what is claimed.
- Suggested rephrasing or additional evidence needed.
