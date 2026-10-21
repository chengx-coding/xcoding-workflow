# Node Contracts

`references/naming.md` owns the names; this file owns the node text the orchestrator must supply. Every `task` leaf with `executor=subagent` is rejected by the runtime unless `instructions`, `deliverables` and `acceptance` are all present, so these three fields are quoted verbatim for each role. Contracts for `executor=main` nodes are strong conventions: nothing enforces them, and a caller that skips them produces an unsupported result.

## How paths enter a node

Node text is fixed when the node is written, and the runtime interpolates nothing. Two mechanisms exist and both are used:

- **Round one**: the four nodes are pre-declared inside the generated template, so they cannot know the debate number. Their text states the derivation rule and the reader resolves it from the blackboard and `naming.md`.
- **Round two and later**: the orchestrator writes the absolute path verbatim into each node's `instructions` when it creates the node. The blackboard publishes `debate.dir`, so the literal value is `debate.dir + "/" + <file>`.

Never write "the path comes from the blackboard automatically" in a node. Nothing does that.

## Mounting

```powershell
# 1. container at the position where the debate must happen
xcoding runtime add-node --tree <tree> --parent <parent-composite> `
  --logical-key deliberation-01 --title "Deliberation 01" `
  --type composite --role dynamic-group --mode sequence --executor main `
  --before <next-pending-node-id>

# 2. the template itself
xcoding runtime embed-subtree --tree <tree> `
  --parent <container-node-id> `
  --template <skill-root>/assets/debate-template.xml `
  --instance-id deliberation-01
```

Use `--before` only when the debate must run before the rest of the work order. Without it the subtree is appended after the parent's existing children. After the embed, `next` returns `r01-plan`.

## Round one (pre-declared)

The template supplies `r01-plan`, `r01-debaters`, `r01-summary` and `r01-wait` with their contracts, and the four gate outcomes. Do not re-create them and do not edit them. Publish `debate.round=1` and the scope keys before starting `r01-plan`.

## Round two and later

Insert four sibling nodes before the sentinel, in this order. Each call repeats the same four `--before <sentinel-id>` and each `instructions` value carries the resolved literal path.

```powershell
# 1. plan
xcoding runtime add-node --tree <tree> --parent <rounds-id> --before <sentinel-id> `
  --logical-key r02-plan --title "Round 02: record the plan" --type task `
  --role deliberation-round-plan --executor main `
  --instructions "<plan contract + literal directory>" `
  --deliverables "<r02-plan.md path>" --acceptance "<plan acceptance>"

# 2. rebuttal group (empty, parallel)
xcoding runtime add-node --tree <tree> --parent <rounds-id> --before <sentinel-id> `
  --logical-key r02-debaters --title "Round 02: collect rebuttals" --type composite `
  --role dynamic-group --mode parallel --executor main

# 3. summary
xcoding runtime add-node --tree <tree> --parent <rounds-id> --before <sentinel-id> `
  --logical-key r02-summary --title "Round 02: summarize independently" --type task `
  --role deliberation-round-summary --executor subagent `
  --instructions "<summary contract + literal directory>" `
  --deliverables "<r02-summary.md path>" --acceptance "<summary acceptance>"

# 4. waiting gate
xcoding runtime add-node --tree <tree> --parent <rounds-id> --before <sentinel-id> `
  --logical-key r02-wait --title "Round 02: await the user's answer" --type gate `
  --role deliberation-round-wait --executor main `
  --metadata-file <gate-metadata-file>
```

`gate-metadata-file` holds exactly:

```text
metadata.gate.outcomes=["continue","exhausted","cost-accepted","time-up"]
metadata.gate.decision_required=true
metadata.gate.outcome_key=debate.outcome
```

A `role=dynamic-group` is required for the rebuttal group because a plain composite may not exist without children. The round wrapper is intentionally absent: the four nodes are flat siblings, which keeps one shape for every round and lets `rNN-` prefixes identify rounds without an extra node.

After inserting the round's nodes, publish `debate.round=<NN>` so the plan node's contract resolves the right number.

## Rebuttal leaves

Add one leaf per participant under `rNN-debaters`, each with a unique `logical_key` (`rNN-debate-01`, `rNN-debate-02`, ...). One parallel batch returns at most eight ready leaves, so a round carries between one and eight rebuttals.

```text
instructions: "You are rebuttal worker <KK> for debate <NN>, round <NN>. Read only: the user's own words for this round, the scope document at <absolute path>, and the inputs the caller listed (<paths>). Do not read any summary, any earlier round's conclusion, or another worker's rebuttal. Either challenge the user's reasoning or report a fact the user did not raise, and say which one you are doing in your first line. Every claim you add must be traceable to a source you name. Write only <rNN-debate-KK.md>; never edit another file. The line-crossing criterion in references/criteria.md does not bind your objections."
deliverables: "<absolute path>/rNN-debate-KK.md"
acceptance: "The rebuttal names whether it challenges reasoning or reports a new fact, cites its sources, stays inside the declared scope, addresses at least one load-bearing claim in the user's own words, and modifies no other file."
```

This is a convention: the roster is final once the caller stops adding leaves, and nothing rejects a later addition to a completed round's group. Choose the worker's stance from the subject: a reasoning challenge when a decision rests on an unexamined inference, a fact-finding stance when the subject depends on facts nobody verified, and a questioning stance when the assumption itself is what needs exposing. The rendered contract for each stance is the same three fields with the stance sentence replaced.

## Round plan (main)

```text
instructions: "Record round <NN> of debate <NN> before it starts. Read the blackboard (debate.number, debate.round, debate.dir) and the previous round's record only. If debate.number is empty, allocate it as one more than the highest existing debate-NN directory under <deliberation-root>; never reuse a number. Write <index.md> and <rNN-plan.md> as node-artifact documents with audience=user, the language of the user's own words, and this node's runtime id as node_id. The plan records the user's own words for the round verbatim, the participants and their roles for this round, the debate number and round number, this round's artefact paths, the previous round's artefact paths with their SHA-256 values (empty only for round one), and any debate topic the user registered as pending. Publish debate.number, debate.round, debate.dir, debate.status=active."
deliverables: "<index.md path>, <rNN-plan.md path>"
acceptance: "The records obey references/records.md; the number appears once and is not reused; the previous round's artefacts and digests are listed; a pending topic is recorded without starting a second debate."
```

## Round summary (subagent)

```text
instructions: "Summarize debate <NN> round <NN> from this round's raw material only: the user's own words recorded for the round and every rebuttal artefact of the round. Never read an earlier round's summary, never read a summary an orchestrator wrote, and never read the conclusion document. State the round's conclusions and one navigation list naming every artefact of the round, what it covers, and its exact path. Write only <rNN-summary.md> as a node-artifact with audience=user, the language of the user's own words, and this node's runtime id as node_id."
deliverables: "<absolute path>/rNN-summary.md"
acceptance: "The summary was produced without reading any earlier summary; every artefact of the round is listed with a path that exists; the summary states conclusions rather than restating the rebuttals."
```

## Waiting gate (main)

```text
instructions: "Wait for the user. Present the round's summary first and the raw rebuttals after it. Ask exactly one question: does the debate continue, and if not, why does it stop. Record one declared outcome and append the user's full reply verbatim to <rNN-user-followup.md>. A stop outcome states the only allowed stop reason; whether another round runs is decided after this gate, never before it."
deliverables: "<rNN-user-followup.md path> with the user's own words"
acceptance: "One declared outcome is recorded; the user's reply is appended without rewriting; no round is added and no merge is started before the answer exists."
```

The four outcomes map to the three allowed stop reasons and one continuation:

| Outcome | Meaning |
| --- | --- |
| `continue` | The debate runs another round. |
| `exhausted` | Stop: nothing new is left to say. |
| `cost-accepted` | Stop: the point is understood and its cost is accepted. |
| `time-up` | Stop: decide now rather than debate further. |

## Convergence advisor (subagent)

Inserted before the next round whenever the completed round is the fifth, tenth, and so on.

```text
instructions: "Advise on whether debate <NN> is converging, after round <NN>. Read the recorded rounds' plans, summaries and raw rebuttals. State whether the recent rounds produced new judgements, repeated earlier ones, or narrowed to a single open question. Do not end the debate, do not write a stop reason, and do not edit any existing record. Write only <rNN-advice.md> as a node-artifact."
deliverables: "<absolute path>/rNN-advice.md"
acceptance: "The advice is produced by an independent worker at the five-round boundary only, distinguishes new judgements from repetition, and contains neither a stop decision nor a stop reason."
```

A caller that cannot insert the advisor because the rounds container already completed must say so in the result rather than claim the check ran.

## Terminal nodes

- **finalize** (main): confirm the user has confirmed the end; make the conclusion a standalone document naming debate number, scope document and the decision reached; publish `debate.status=stopped`. It must not merge anything.
- **merge** (main): re-check the scope document's hash against `debate.source_sha256`; on any difference stop and let the user judge; merge by moving content and aligning format; append the merge record described in `references/merge.md`, including exactly one stop reason line whose value is the gate outcome's meaning.
- **follow-ups** (main): list every part the merged conclusion may affect and give each one action — handled now, or registered as a pending work-order item with its location. Append it to the merge record; create no new artefact type.
