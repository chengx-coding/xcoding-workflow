# Naming

The orchestrator loads this file when it mounts a debate and whenever it adds nodes, and anything that has to find a debate, a round or an artefact again loads it first. It owns numbers, names and layout. What goes inside the files it names is `references/records.md`; the node text that accompanies these names is `references/node-contracts.md`.

## Numbers

A debate number is two digits, and the first round's plan node allocates it: scan the deliberation root for directories named `debate-NN`, take the largest number, add one.

There is no registry to consult and no counter to update. This is a convention: nothing rejects a directory that reuses a number, so the allocation is only as good as the computation behind it, and the plan node reads the directory every time instead of trusting a remembered value.

Deleting a directory does not release its number for the next debate to take: the next allocation still adds one to the highest number that remains, so a gap stays a gap and the debates after it keep their numbers.

A round number is also two digits, and it restarts at `01` in every debate. Debate ten, round three is `debate-10` and `r03`.

## Layout

```text
<workbench>/artifacts/deliberation/debate-NN/
  index.md
  rNN-plan.md
  rNN-debate-KK.md
  rNN-user-followup.md
  rNN-summary.md
  rNN-advice.md
  conclusion.md
```

`index.md` heads the debate: the first round's plan node writes it, and a process resuming the debate reads the number from it rather than from a conversation. `conclusion.md` is the debate's conclusion and the file the merge works on. `rNN-advice.md` exists only when a convergence advisor ran, which happens at five-round boundaries and not before.

## Node names and file names

A node created at run time carries a `logical_key`, and its file is that key plus `.md`: `r02-plan` writes `r02-plan.md`, `r02-debate-01` writes `r02-debate-01.md`.

A duplicate `logical_key` in one tree is refused, so two nodes cannot share a key. That the file matches the key, in contrast, is a convention: nothing compares them. The correspondence is still what lets a reader move from a node to its record and back without a lookup table.

## Round one is pre-declared

The template declares round one with the labels `r01-plan`, `r01-debaters`, `r01-summary` and `r01-wait`. Rounds created at run time use the same four shapes under their own number: `r02-plan`, `r02-debaters`, `r02-summary`, `r02-wait`.

The rebuttal leaves under a round's group are `rNN-debate-KK`, numbered from `01` inside that round, so one parallel batch carries no repeated key. The convergence advisor is `rNN-advice` and joins no round group.

## Finding the container and the sentinel

The rounds container and the sentinel are found through the runtime's `find` query by template id: `--template-id rounds` for the container, `--template-id rounds-open` for the sentinel.

Never derive either from a child's node id. Runtime node ids are flat and carry no ancestry, so a trimmed id points at nothing.

## Titles carry the identity

A node's title carries what the runtime does not compute: the debate's container names the debate, and every round node names its round, as in `Deliberation 03` and `Round 04: await the user's answer`.

A new session has to be able to say which debate, which round, and what it is waiting for, and the title is what it reads first. This is a convention: a title is free text, and nothing rejects a vague one.

## Pending topics

A topic the user raises while a debate is running starts no second debate. It is recorded as pending in the round plan of the round in which the user raised it, in the user's own words, and it starts only after the current debate has ended.

Recording it in a later round's plan loses the fact that the user raised it earlier, which is the fact the next reader needs.
