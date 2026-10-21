# Inputs

The orchestrator loads this file when it assembles a rebuttal node contract, and a rebuttal worker loads it when it starts. It owns the three rules that decide what a debate participant may read. What a worker owes as an argument is `references/criteria.md`; where the material is filed is `references/records.md`.

## Rule one: raw material only

A worker receives the user's own words recorded for the round and the artefacts themselves.

It must not receive an earlier round's conclusion or an earlier round's summary. Not as a path in its instructions, not as a quotation, not as "the previous round established that ...".

The failure this prevents is inherited drift. A conclusion is already the product of one reading; hand it to the next worker and every later round argues from that reading instead of from the user. The user's position then moves without the user moving it, and the movement is invisible because each step looks small.

The artefacts are the documents under discussion: the scope document and whatever the caller declared. The debate's own output is never an artefact for this purpose, which is why the rule can be written as a list a contract names rather than as a filter a worker applies to a directory.

## Rule two: the user reads the objections

The user reads the raw rebuttals. An orchestrator must not put its own digest in their place, and must not select the "important" objections for the user to look at.

The failure this prevents is laundering. An orchestrator that summarises is an orchestrator that can soften, reorder and re-frame, usually without deciding to, and an objection the user never sees cannot change the user's mind. The agreement-seeking direction returns through the summary rather than through the debate.

A summary produced by an independent subagent is allowed, and the user reads it first only because it is navigable, then goes back to the raw artefacts for the parts that matter. A summary is usable only if it carries a navigation list with exact paths: which artefacts the round produced, what each covers, and where each one sits. `references/records.md` owns that field list; this file owns why the list exists.

The rule limits what stands in the objections' place, not whether the orchestrator writes. The plan and the merge record are the orchestrator's to write, and it writes them without competing with the rebuttals for the user's attention.

## Rule three: agreement is not corroboration

A worker shares the round's raw material with its siblings and does not receive their rebuttals. That isolation keeps the batch from settling on one framing before it reports, but it does not make the batch independent.

Several workers agreeing is still weaker than several independent people agreeing, because the workers share one base model and one framing of the problem. What the user is holding is one answer repeated, not several confirmations.

The failure this prevents is false corroboration. Nothing in the batch's output distinguishes four correlated answers from four independent ones, so the orchestrator must not present unanimity as independent corroboration. It presents the objections and lets the user weigh them.

Correlation is not a defect to engineer away. Hiding the user's framing would make the batch less relevant rather than more independent, because the framing is the subject. What can be said honestly is what the batch is: several readings of one question, not several unrelated judgements.

## Assembling a rebuttal contract

A legitimate input is one of three things: the user's own words recorded for the round, the scope document, and an input artefact the caller declared before the debate started. A record the user wrote counts as the user's own words, including a follow-up the user gave at an earlier gate; a record a worker or the orchestrator wrote does not.

The contract names its inputs one by one, with their paths, and names nothing else. A worker does not browse the debate directory: the directory holds summaries and conclusions that rule one keeps away from it. A contract that cannot list its inputs is not ready, and a worker left to guess at them has been handed a directory instead of a task.

A summary is quarantined from the next round in three steps. It can appear in the next round's plan only because that plan lists the previous round's artefacts as an edit baseline rather than as a reading list, which `references/records.md` owns. No rebuttal contract names it. The next round's workers receive the user's words, which already carry what the user took from the summary, so nothing the debate needs is lost by withholding it.

This is a convention: no field refuses a contract that lists a summary, and nothing detects that a worker read one. It holds because the orchestrator writes the input list and the worker stays inside it.
