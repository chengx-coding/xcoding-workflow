# Merge

The finalize, merge and follow-up nodes load this file when they run. It owns the path a conclusion takes from a separate document into the document it argues about, and what that move has to leave behind. The frontmatter every record carries is `references/records.md`; what the conclusion's body text may assert is `references/criteria.md`.

## The conclusion stays separate

While the debate runs, the conclusion is a document of its own and the scope document is untouched. It is merged only after the user confirms the end. The confirmation is the user's, never inferred from a quiet round, a converging advisor or an argument that looks complete.

A debate that stops without a merge is a legal outcome when the user says so. The conclusion then stands alone, and the user's choice is recorded rather than left as a merge that quietly never happened.

## The drift gate

Before any merged result exists, recompute the scope document's SHA-256 and compare it with the value recorded when the debate started.

On any difference, stop before producing a merged result, show the differing fragment, and let the user judge whether the change affects the conclusion.

A judgement that it does affect the conclusion means no merge: the scope document is not written. A judgement that it does not affect the conclusion lets the merge go ahead. Either way the judgement and its content are recorded — the fragment, the user's wording, and the date — because a later reader has to see that a person decided this and what they saw.

The gate compares hashes and then asks a person. This is a convention: no field blocks the write, so a merge node that skips the comparison produces a merged document that looks perfectly normal.

## Moving, not rewriting

Merge by moving content. The conclusion's sentences are placed into the scope document, and the format around them is aligned so the result reads as one document: heading level, list style, table style, link style. Aligning format is not rewriting.

A rewrite is any of these: changed wording, a split or merged paragraph, an added transition, a dropped sentence, a reordered paragraph. A rewrite is allowed. An unrecorded one is not.

Every rewrite is recorded with three things: what was moved, which places changed at paragraph level, and why each change was made. The list is shown to the user rather than buried in the merged result, because a rewrite that only the resulting document knows about has been hidden. A list that names only "minor edits" has recorded nothing, because a later reader cannot check it.

## The merge record

The merge record is appended to the conclusion document as its last section. It is never a new artefact type and never a second file, because it explains that document's content and a reader who has the document must get the explanation with it.

A second merge of the same debate appends a dated subsection instead of rewriting the earlier record. Merge history reads in order, and an edited record hides exactly the thing it exists to show.

## The stop reason

Exactly one stop reason line is written for a debate. Its value is the gate outcome that ended the debate — `exhausted`, `cost-accepted` or `time-up` — and the line states that value together with its meaning, on one line. The gate's recorded outcome is the authority; the line restates the same value and adds nothing.

The line closes the merge record. Only the knock-on-effects section comes after it, and nothing else does.

`continue` is never a stop reason: it is the outcome that opens another round. A later merge of the same debate writes no second stop line, because the debate stopped once and the reason belongs to that stop.

This is a convention: no field counts stop reasons, so a second line is caught only by a reader who reads the record.

## Knock-on effects

Every part of the project the merged conclusion may affect is listed, and each item names exactly one action: handled now, with what was done; or registered as a pending work-order item, with the place it is registered.

An item that only names a possible effect is unfinished. "This may affect the verification plan" is a sentence, not a follow-up, and the node that produced it has not finished its work.

This is the section that prevents a merge from quietly becoming a change with no owner. It is a convention: no check balances the list against the project, so an omitted effect is simply absent.

## What the record has to let a reader check

The record is written for someone who arrives months later with the merged document and nothing else. That reader must be able to check whether the moved text is the conclusion's text, whether anything was rewritten and why, whether the drift gate ran and what the user judged if it did, which outcome ended the debate and that it is one of the three stop values, and for each possible effect the single action attached to it.

A record that answers those questions is enough. It does not need to retell the debate, and it does not repeat the round records, which remain the raw material behind it.
