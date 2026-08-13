# Governance Loop Review

Closed-loop policy for reviewing managed-governance evidence. Tool-neutral;
all runtime access below uses public runtime commands.

## When to run

Run a governance loop review when a work order completes, a milestone seals, or the main session notices repeated interception, retry, or block patterns. Reviews are evidence collection and policy review only; they change no runtime state and no policy on their own.

## Collecting evidence

Collect statistics with the read-only helper:

    python skills/xc-work/scripts/governance_stats.py \
      --trees <runtime-tree.xml> [--trees ...]

The helper reads only through the public runtime CLI, never mutates, and accepts one or more tree paths or a JSON list. Unreadable or sealed trees are skipped with per-tree reasons; a skip list is itself a signal (audit what made trees unreadable).

## Reviewing deviations

Compare the collected numbers against the expectations encoded in the plan
and policy:

- Gates that never intercepted an error: if an approval or verification
  gate records zero `rejected` or `revision-required` outcomes while
  reviews and verification recorded failures, inspect whether the gate is
  positioned too late, its outcomes are too weak, or workers treat it as
  a formality.
- Frequent interceptors: a gate that intercepts most work orders is
  evidence of a planning gap, not gate health.
- Retry hotspots: repeated archived attempts indicate unstable contracts,
  environment flakiness, or acceptance criteria the executor cannot meet.
  Fix the owning Skill's contract, not the node.
- Block hotspots: many blocked leaves on one dependency chain indicate a
  missing decision source; recover through the documented recovery
  patterns, then review whether the owning workflow declares that source.
- Route share drift: when summaries record `route=` values, a large
  managed share on small tasks or a large direct share on high-impact
  tasks signals that classification evidence is wrong or stale;
  re-confirm facts, do not edit the numbers.

## Calibration boundary

Proportionality floors, gate thresholds, and default depths are workflow
policy. Runtime numbers must never change them automatically.
Calibration changes flow only through the workflow-evolution review path,
with explicit human gates. A governance review may recommend calibration;
it may not apply it.

## Standing rules

- Governance is fact-driven: decisions cite collected evidence and
  confirmed task facts.
- Model-independent: no decision may depend on model name, vendor, or
  context-window size.
- Reviews are read-only over runtime state; record findings as artifacts.
