# Records

Each round's plan node and its summary node load this file before writing anything, and the merge node loads it when it has to look back at what the debate produced. It owns what a round is, which file each class of raw material lands in, and what every record carries. Names and paths are `references/naming.md`; who may read which record is `references/inputs.md`.

## One round

One round is one exchange: the user has said everything they want to say, the workers have finished, and the user answers. The answer ends the round, whether it continues the debate or stops it.

Nothing inside a round is a record of its own. The user's words, the rebuttals, the follow-up and the summary are the round, and they are files rather than fragments of a conversation.

## The four classes of raw material

| Raw material | Where it lands |
| --- | --- |
| The user's own words for the round | recorded inside the round's plan file |
| Each worker's rebuttal | its own `rNN-debate-KK.md` |
| The user's additional replies at the gate | appended to `rNN-user-followup.md` |
| The workers' subsequent replies | the next round's `rNN-debate-KK.md` |

Parallel workers never append to a shared file. Two writers on one file in one batch interleave or overwrite, and afterwards the record no longer shows which worker said what. One file per worker also keeps each objection separately addressable, which is what a reader needs when asking whether a particular objection was softened before it reached the conclusion.

## The round plan

The plan is written before the round starts. It names the participants and their roles for this round, the debate number and the round number, the artefact paths this round will write, the previous round's artefact paths with their SHA-256 values, any debate topic the user registered as pending, and the user's own words for the round.

The previous round's paths and digests are empty only for round one. They are the reason an append-only record can be checked later: a reader recomputes a file's digest and compares it with the value the next round recorded.

The plan is not amended afterwards. Its own products do not exist yet when it is written, so it cannot carry their digests, and the round that follows is where that baseline belongs.

## The round summary

The summary carries the round's conclusions and one navigation list: which artefacts this round produced, what each one covers, and its exact path. It states conclusions rather than restating the rebuttals, and every path in the list has to open.

One list, not several. The reader uses it to leave the summary and reach the raw material, so a list that omits an artefact has removed the reader's way back to it.

## The derived index

A derived index is optional. When one exists it maps each objection to who raised it, whether it was rejected and whether it is still open, and it labels itself `derived` and states that it can be recomputed from the raw material.

The raw material is the authority and the index never is. The value of the index is that it can be thrown away and computed again: a reader who suspects an objection was quietly softened recomputes and compares. An index that has been edited is deleted and regenerated, never corrected in place.

## What every record carries

Every record is a `node-artifact` document with the standard frontmatter, and six values have to be right.

| Field | Value |
| --- | --- |
| `document_kind` | `node-artifact`, the existing kind; no new document kind is introduced |
| `audience` | `user` |
| `content_language` | the language of the user's own words |
| `node_id` | the runtime id of the node that wrote the file |
| `work_order_id` | the work order the debate belongs to |
| `orchestration.tree_ref` | the tree that owns the debate |

The audience is `user` and never `internal`. The document validator requires an internal node-artifact to be written in English and requires `content_language` on a user-audience artifact; the user's words must not be translated, so a record in the user's language would be refused as `internal`. Choosing `user` is a document-contract constraint rather than a stylistic preference.

## Append-only

Records are append-only. A correction is a new round, not an edit to an old file. Once editing is allowed, "the record" becomes a story that can be polished gradually, and the reason for keeping it is gone.

This is a convention: the validator reads frontmatter and not the body, so nothing detects that a file changed after it was written. What a later reader has instead is the digest in the next round's plan, which can be recomputed and compared.

## Sensitivity

Raw material is the most sensitive product of the work: unpolished reasoning, drafts that were refuted, uncertainty that was admitted. It may live inside the project workshop, and it must never be quoted or linked from public documentation.

## The merge record

The merge record is not a record file of its own. It sits at the end of the conclusion document, because it explains that document's content and has to travel with it. `references/merge.md` owns what it contains.
