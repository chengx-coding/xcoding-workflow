# Generality and Applicability

Every self-evolution rule states where it applies and where it does not. A rule is not universal
because its wording avoids the originating task's nouns; it becomes broader only by application to
another task class.

## 1. Declaration

Record: `scope` (`universal`, `task-class`, `project-specific`, `sample-specific`), `applies_when`,
`does_not_apply`, `evidence_surface`, `owner`, `promotion_status`, `generality_evidence`. A rule
without these fields is incomplete; a missing declaration is not permission to apply it everywhere.

## 2. Ownership

- Universal: surface-neutral state/transition/error/recovery/persistence/evidence in the generic Skill.
- Task-class: the owning Skill's public contract/table, never the universal path. Visual rules apply
  only when the task has a visual surface; pure code/docs tasks use their own evidence.
- Project-specific: bridge/AGENTS/domain policy.
- Sample-specific: sample prompt/evaluation only; never portable Skills.

One owner per rule. A task selects its surface in analysis; a surface with no applicable evidence is
recorded with a reason, not silently skipped.

## 3. Status

`proposed` → `validated-in-class` → `promoted-universal`; a rule can also be `demoted` or `retired`.
A rule cannot move backward silently: record the reason and the affected owner.

## 4. Promotion ladder

1. **Instance** — one task/sample; `sample-specific` or `task-class`.
2. **Validated in class** — a second independent instance of the same class.
3. **Promoted universal** — a probe in a different task class plus a negative/not-applicable probe.
   The different class must produce meaningful evidence; wording, or absence of the originating
   domain's nouns, is not evidence.

If the different-class probe fails, keep the rule in its class or retire it. Visual rules are
task-class by default and cannot be promoted universal by a visual sample alone.

## 5. Review

The independent review applies the rule to a non-originating class (for CLI/library, docs, or visual,
as applicable) and records the class, surface, applicability decision, executed evidence or a
not-applicable reason, and whether the rule creates meaningless work. A wording-only review cannot
support universal promotion. The meta-review asks which owner is correct and whether the rule should
be kept, demoted, promoted or retired.

## 6. Force

Convention-only unless an existing mechanical check enforces a specific part. No runtime check proves
a rule is universal.
