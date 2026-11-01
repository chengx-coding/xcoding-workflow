# Generality and Applicability

Every self-evolution rule must state **where it applies and where it does not**. A rule derived from
one task is not universal because its wording avoids that task's nouns; it becomes broader only when
it is applied to another task class and still produces meaningful evidence.

## 1. Scope declaration

Every new or revised rule records:

| Field | Meaning |
| --- | --- |
| `scope` | `universal`, `task-class`, `project-specific`, or `sample-specific` |
| `applies_when` | Observable facts that make the rule applicable |
| `does_not_apply` | Explicit negative conditions, not silence |
| `evidence_surface` | UI, CLI stdout/stderr/exit, API status/body, file/diff, rendered docs, logs, persistence, etc. |
| `owner` | Universal Skill, task-class profile, project bridge, or sample evaluation |
| `promotion_status` | `proposed`, `validated-in-class`, or `promoted-universal` |
| `generality_evidence` | Cross-class probes and a negative/not-applicable probe; not wording |

A rule without these fields is incomplete. A missing applicability record is not permission to apply
the rule everywhere.

## 2. Ownership by scope

- **Universal** rules live in the generic Skill: state transitions, errors/recovery, persistence,
  observable output, evidence and review obligations. They must be surface-neutral.
- **Task-class** rules live in a profile under the owning Skill (for example
  `xc-work/references/profiles/`), never in the universal section.
- **Project-specific** rules live in the project bridge/AGENTS/domain policy.
- **Sample-specific** rules live only in the sample prompt/evaluation; they must not enter portable
  Skills.

## 3. Task-class profiles

At minimum:

- `visual` — UI/page/canvas/rendered document: visible before/after, background/occlusion, two
  materially different visual states, spatial/layer, responsive and accessibility.
- `cli-library-api` — stdout/stderr/exit code, status/body, success/error/empty/limit, side effects,
  recovery; no screenshot as evidence.
- `docs` — source/rendered content, links/anchors/navigation/search/cross-references; no game/UI
  checks.

A task selects its surface(s) in analysis. A task without a visual surface must not be required to
produce visual evidence. A visual requirement must be labeled `task-class`, not `universal`.

## 4. Applicability map

Analysis records a small map:

| Surface | Applies? | Evidence | Not-applicable reason |
| --- | --- | --- | --- |
| UI/render | yes/no | screenshot + executed state assertion / — | no rendered output |
| CLI/API | yes/no | command + exit/stdout/status / — | no command/API |
| Files/docs | yes/no | diff/render/link check / — | no file/doc output |

A "not applicable" entry is legitimate only with a reason and a surface check; it is not a blanket
skip. If no surface is applicable, record that and do not invent visual evidence.

## 5. Promotion ladder

1. **Instance** — observed in one task/sample. Label `sample-specific` or `task-class`.
2. **Validated in class** — reproduce on a second independent instance of the same class. Label
   `validated-in-class`.
3. **Promoted universal** — require at least one probe in a **different task class** plus a
   negative/not-applicable probe. The rule must produce meaningful evidence in the different class;
   wording alone, or the absence of the originating domain's nouns, is not evidence.

Record the probes, the class, the evidence and the counterexample. If the different-class probe fails,
keep the rule in its profile or retire it. Do not promote a visual rule to the generic path.

## 6. Generality review

The independent review must apply the rule to at least one non-originating class (CLI/library or
docs) and record:

- the class and surface;
- the applicability decision;
- the executed evidence (or a recorded not-applicable reason);
- whether the rule would create meaningless work in that class;
- any required demotion or profile move.

A review that only reads the Skill text and checks for sample nouns is a wording review, not a
generality review. It cannot support `promoted-universal`.

## 7. Meta-review questions

At the self-evolution meta-review, ask:

- Which class did this rule come from? Is it in the right owner?
- Does the negative condition hold in another class? What would be irrelevant work?
- Is the evidence cross-class or only wording?
- Should it stay in a profile, be promoted, demoted, or retired?
- Did the sample score hide a class-specific rule being treated as global?

## 8. Force

The applicability declaration, profile ownership, promotion ladder and cross-class review are
convention-only unless an existing mechanical check enforces a specific part. No runtime check
proves that a rule is universal.
