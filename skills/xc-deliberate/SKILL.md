---
name: "xc-deliberate"
description: "Runs a user-led debate in which independent rebuttal workers argue against the user's own reasoning while the user keeps authorship. Invoke only when the user explicitly asks to debate, stress-test, challenge, or be argued against on a named document and sub-question inside an existing managed work order."
---

# XC Deliberate

`xc-deliberate` runs a debate in which the user thinks, speaks, and decides, while independent rebuttal workers attack the reasoning. The user's mental model stays with the user; the workers add facts the user did not know and objections the user did not consider. It produces a conclusion the user owns, a record of how it was reached, and a merge of that conclusion into the document it argues about.

It is not `xc-review`. Review is a later judgement of finished work; deliberation is sustained in-process challenge of work still being decided. It is not `xc-writing`, which covers writing the agent performs. It does not replace analysis, clarification, review, implementation, or verification.

## Parameters

- `workbench_path` - `path`; required
  - Scope: The caller's existing managed workbench. The debate's records live beneath its `artifacts/` directory.

- `scope_document` - `path`; required
  - Scope: The document the debate is about. Its content hash is recorded at start and re-checked before any merge.

- `scope_question` - `string`; required
  - Scope: The sub-question inside that document that this debate is trying to settle. A debate without one is not a debate; ask the user for it.

- `instance_id` - `string`; required
  - Scope: Lowercase kebab-case instance id used when mounting the template, unique in the caller's tree.

- `inputs` - `path[]`; optional
  - Scope: Material the user wants the rebuttal workers to be able to read besides the scope document and the user's own words.

- `rebuttals_per_round` - `integer`; optional, defaults to `3`
  - Scope: How many rebuttal workers the caller adds per round. Allowed range 1-8, because a round's rebuttal group runs in parallel and one batch returns at most eight ready leaves.

## Enablement

Only the user enables a debate. The workflow never decides that a subject needs one, and no other Skill may start one on the user's behalf. The declaration must name the document and the sub-question; if either is missing, ask for it before mounting anything. A user may end a debate at any round; nothing in this contract bounds the number of rounds.

## Caller Contract

`xc-deliberate` is an embedded subtree, not a standalone work order. The caller keeps ownership of its own runtime tree and of every document the debate does not merge. To mount a debate:

1. Confirm the scope with the user and record their words verbatim; they are the raw material for round one.
2. Publish these short blackboard values on the caller's tree before the first round starts: `debate.scope_document`, `debate.scope_question`, `debate.source_sha256`, `debate.status=planned`, `debate.round=1`. `debate.number` and `debate.dir` are published by the first round's plan node.
3. Create a container at the position where the debate must happen: `add-node --type composite --role dynamic-group --mode sequence`, inserted before the next pending node when the debate must not wait for the rest of the work order.
4. Embed `assets/debate-template.xml` into that container with `--instance-id <instance_id>`. The next `next` call returns the first round's plan node.
5. Only one debate may be active in one work order at a time. A topic raised while a debate is active is registered as pending in the current round's plan and starts no second debate. This is a convention: nothing in the runtime refuses a second concurrent debate, and no lock or lease exists for one.

The caller must not modify the embedded rounds, nodes, or instructions after mounting. Everything that changes per round is either published on the blackboard or added as new nodes before the sentinel.

## Entry Points

These are behaviours, not command names. The template already runs round one.

- **Start**: confirm scope and authorship, record the user's own words, mount the subtree as above. The first round's plan node then allocates the debate number and writes the debate header.
- **Advance a round**: after each round's gate completes, decide from `debate.outcome` whether another round runs. Continuing means adding the next round's four nodes before the sentinel; stopping means closing the sentinel and letting the terminal nodes run.
- **Resume**: a new process resumes by calling `next` on the same tree. There is no resume command. Recover the debate number from `index.md`, the round from `debate.round`, and the waiting gate from the tree's running node, never from conversation.
- **Stop and merge**: the stop is the user's, recorded as one gate outcome. The terminal nodes finalize the conclusion, merge it into the scope document, and register knock-on effects. Stopping without merging is a legal outcome only when the user says so; record that they did.

## Round Protocol

Four nodes per round. Round one is pre-declared in the template; rounds two and later are added at run time by the caller, using the templates in `references/node-contracts.md`.

| Node | Executor | Role |
| --- | --- | --- |
| `rNN-plan` | main | Records the round plan before the round starts: the user's own words for the round, number, round, participants, artefact paths, the previous round's artefact list with digests, and any pending debate topic. |
| `rNN-debaters` | main | An empty `role=dynamic-group`, `mode=parallel` extension point. The caller adds one rebuttal leaf per participant. |
| `rNN-summary` | subagent | Independent reading of this round's raw material only. Never reads an earlier summary. Produces the round conclusion and a navigation list of the round's artefacts. |
| `rNN-wait` | main | The user's answer point. Declares four outcomes: `continue`, `exhausted`, `cost-accepted`, `time-up`. |

The empty `rounds-open` sentinel after the round nodes is what makes "another round or stop" a machine-visible decision point. While it is open and empty the rounds container cannot complete, so `finalize`, `merge` and `follow-ups` stay pending behind it. After a round's gate completes, the caller either inserts the next round's four nodes before the sentinel or closes it.

Every fifth round the caller inserts one convergence-advisor leaf before the next round. It produces advice only: it does not end the debate and it does not write a stop reason. The user decides what to do with it. This is a convention: nothing schedules the advisor, and a caller that skips it leaves no machine-visible trace.

## Two Failure Directions

The debate fails in two opposite ways, and the rules are asymmetric on purpose. `references/criteria.md` carries the operative rules.

- **Crossing the line**: every sentence in the conclusion document that cannot point back to a component of the user's own words must carry a source annotation or an explicit "this is an addition, please confirm". The criterion governs the product's body text only, by the source of the assertion and never by length.
- **Agreeing with everything**: each rebuttal worker must be able to disagree, must investigate rather than only question, must say whether it is challenging the reasoning or reporting a new fact, and is never bound by the line-crossing criterion. Applying that criterion to rebuttals forbids reporting new facts, which returns the debate to agreement.

Attribution is judged per artefact, not per task: a design document may be written by the user while a record is written by a worker.

## Input Discipline

Three rules, carried by `references/inputs.md`:

1. A rebuttal worker receives the user's own words and the artefacts themselves, never an earlier round's conclusion or summary.
2. The user reads the raw rebuttals, not a summary an orchestrator wrote. A summary produced by an independent subagent is acceptable, and the user reads it first only because it is navigable, then returns to the raw artefacts.
3. Several workers agreeing is weaker than several independent people agreeing: they share one base model and one framing.

The round summary is produced by an independent subagent that reads no earlier summary. That is a record rule, not a fourth input rule. This is a convention: no check reads a summary and detects that an earlier one was opened, so the instruction is the only control.

## Records

`references/records.md` owns the record contract: the round definition, the four classes of raw material and the file each one lands in, the round-plan fields, the summary fields and its navigation list, the optional derived index, the append-only rule, the artefact frontmatter, and the sensitivity of raw material. Records are `node-artifact` documents with `audience: user` and the language of the user's own words; raw material may exist inside the workshop and must never be quoted in public documentation.

## Merging

`references/merge.md` owns the merge contract: the source hash is re-checked before merging and any drift stops the merge for the user's judgement; merging moves content rather than rewriting it; every rewrite is recorded with its reason; the conclusion stays a separate document until the user confirms the end; and every knock-on effect carries one follow-up action. The merge record is appended to the conclusion document, not created as a new artefact type.

## References

| File | Load it when |
| --- | --- |
| `references/criteria.md` | Any rebuttal node runs; the orchestrator judges a conclusion before merging. |
| `references/inputs.md` | The orchestrator assembles a rebuttal node contract; a rebuttal worker starts. |
| `references/records.md` | A round plan or round summary is written; a merge needs to look back at the record. |
| `references/naming.md` | The orchestrator mounts the debate or adds nodes; anything must be named or found again. |
| `references/merge.md` | The finalize, merge and follow-up nodes run. |
| `references/node-contracts.md` | Before every `add-node` call for a round, a rebuttal, an advisor, or a terminal node. |

## Constraints

- Use `xc-orchestration-runtime` for every tree read and write; never open, summarise, or edit a runtime tree file.
- Use `xc-document` for artefact structure and validation. Do not add a document kind, extend the validator, or copy another Skill's private references.
- Keep long content out of the blackboard: it holds the debate number, round, directory, status, scope and outcome only.
- Never make a rebuttal worker read another worker's conclusion; never let an orchestrator write the round summary.
- No timeout, retry, watchdog, or auto-convergence fields exist for a waiting gate. The waiting step carries no time condition in this contract.
- Requirements without a runtime mechanism stay labelled as conventions, in this file and in every reference; none of them may be presented as guaranteed by the engine.
- Temporary scripts and process files belong under the caller's workbench `tmp/` directory and are never declared as artefacts.
