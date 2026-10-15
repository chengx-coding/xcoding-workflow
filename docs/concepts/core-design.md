**Language:** **English** | [简体中文](../zh-CN/concepts/core-design.md)

# Core Design

This page presents the XC core design: what it commits to, which methods follow from those commitments, which concerns carry its requirements, and which obligations run across all of them.

The core design is XC's formal statement of what its core is. It records principles, invariants, and decision criteria — what the design claims, what must remain true between those claims, and what to weigh when several approaches are all workable. A later change is judged against that statement rather than against the local symptom it repairs.

It states design claims rather than project status. A design claim holds as long as the design is the design it says it is; how far the project has implemented a claim at some point in time is a different kind of statement with a different owner. Keeping the two apart is what lets the design stay stable while the project is completed or adjusted, so the design is rewritten only when the design itself changes.

Read it top down: commitments lead to methods and concerns, followed by the enforcement vocabulary and the obligations that apply across them. The later sections explain how to judge a departure, what the design does not claim, the problems it addresses, and how to find related detail.

## What the design believes

Seven commitments make up the design's fundamental claims. Each states what it claims, what it refuses, what cost it accepts, and which methods derive from it. None of them is a practice; they are the criteria a choice is judged by, and they still hold if the project's tools and file layout change completely.

**1. Progressive deepening is the natural shape of research and execution, but depth and width must never become metrics.** Complex thinking and complex execution advance in layers: a problem is first seen as a few aspects, and pushing into one aspect reveals that it divides again. Breadth on one level and depth below one aspect are the same shape — a tree. Stronger models do not remove that shape, because any problem already thought through can still be divided further; the question is only whether dividing it is worth doing. The design refuses to treat "the tree is deep, therefore the thinking was deep" as a standard, refuses any depth or width metric, refuses extra nodes added to reach a target, and refuses "the model got stronger" as a reason to drop structure. The cost it accepts is that "deep enough" stays a judgement and never becomes a measurement, which is why an expansion carries a record obligation: a node that appears has to say why it appeared.

**2. Work belongs to the project, not to a conversation.** The durable state of a piece of work belongs to the project, not to one session, one vendor's store, or one runtime — and a party that took no part in the work must be able to reconstruct it. That includes a later session, another agent, another model, another runtime, and the maintainer who takes the work over. The design refuses state that lives only in a session, a vendor store, or a runtime; it refuses "the record still exists" as a substitute for "the work still exists". The cost is that records must be materialised, maintained, and given a stable physical home, so every piece of work leaves a durable shape behind even when the work is short.

**3. Write to be judged, not to be admired.** The design says who owns each detail, how a departure is detected, and where its own limits are. It would rather write an unflattering sentence than promise a mechanism it does not have, and it states design intent separately from observed behaviour. It refuses to promise mechanisms it does not own, to present design intent as implemented behaviour, or to look complete through tone and rigorous through length. The cost is that the document must keep repeating its own weaknesses, it will not read as reassuring, and where a reader expects a guarantee it says plainly that there is none.

**4. Attachment goes through declared capability surfaces, not per-tool customisation.** An Agent tool attaches through a set of declared capability surfaces rather than through an integration written for that tool. Writing something into this design is a commitment that it does not depend on one runtime's internals: any Agent that can complete tool and Skill calls normally can follow the same structure. The design refuses per-tool bespoke integration as the way capability arrives, refuses one runtime's internal orchestration as this design's structure, and refuses "tool X is supported" as generality itself. The cost is that the design's reach depends entirely on its discovery contract and its command-line interface continuing to work; if either degrades, attachment degrades and nothing else catches it.

**5. Only what can be checked goes in.** A rule that must hold against an executor that never intended to comply has to be a checkable condition on represented state. Where that is impossible, the design says so outright, because saying it is itself part of the delivery. It refuses to dress an admonition up as a requirement, to treat documentation discipline as mechanical enforcement, to write a "must" that nothing would ever refuse, or to substitute tone for constraint. The cost is that the design must publicly admit where it has no machine, give up wording that would look tidier, and put "there is no machine here" where readers will see it.

**6. Every fact has exactly one source.** A fact, a rule, or a contract has one owner. Consumers resolve it by reference instead of copying it, and generic content meets project-specific fact at exactly one fixed interface. The design refuses the same rule or fact written in two places, consumer-project facts copied into generic content, one contract maintained in two locations, and one process described both in a contract and in a structure. The cost is that every consumer has to resolve by reference rather than copy what is nearby; references break, nothing detects a broken reference automatically, and each therefore needs an explicit judgement question to catch it.

**7. A record must distinguish three states.** A record has to let a party that took no part tell "it was done", "it was never examined", and "it does not apply" apart. An absent conclusion is itself a conclusion. The design refuses to read silence as compliance, to read a check that never ran as a check that passed, to treat "the key is missing" and "the key says no" as the same thing, or to treat an empty result as nothing having happened. The cost is that every empty result needs a named reason, so records grow longer and a place must be reserved for "nothing".

## Principal methods

Each method below traces to a commitment above. Methods are the part that can be acted on directly, so an equivalent method can replace one of these without changing what the design believes.

**A runtime runs the work; the workflow defines how it should be done.** A runtime is programmatic: it binds one specific Agent and the tools that Agent holds, and it handles processes, sandboxes, permissions, context, model routing, tool calls, and cancellation. The workflow defines what happens first, what each step must produce, what forbids going further, who reviews, and what record remains. It binds no particular tool. The two exchange information in one place only: the project bridge, which the workflow reads when it needs project facts. Capability that would merely repeat what the runtime already does better does not belong in this design.

**Attachment is a capability unit plus a command-line interface, not a plugin.** Four layers each own one thing. A **capability unit** — a Skill — is the only attachment mechanism: an Agent tool learns from it what this workflow is and how to operate it, loading it through a discovery contract rather than through a plugin written for that tool. The **command-line interface** holds the operations that can be made programmatic, so the model does not re-decide them each time. The **project bridge** holds the project's own half: build and test commands, language, boundaries, and constraints; the generic design neither guesses those facts nor fills them in. The **workshop** holds the durable records. Capability units divide into core units, which explain what the workflow is and how the interface is used, and specialised units, which explain one stage each.

**Deterministic operations belong to the command line; judgement belongs to capability units.** Scheduling, state transitions, integrity checks, identifier generation, schema validation, and template construction have the same result for the same input and belong in the interface. How to analyse, how to review, what counts as satisfying acceptance, and what counts as having investigated enough require understanding and belong in capability units. This line is also how the design explains its own weaknesses: an obligation is labelled convention-only not because it is unimportant but because the part of it that could be made programmatic has not been split out yet. Closing such a gap therefore means moving the deterministic half into the interface so that a departure shows up as a failure rather than as an instruction.

**Three classes of thing must not be mixed into one list.** Principles, required capabilities, and optional capabilities are three different things, and the consequence of merging them is concrete: the entries of one list read alike, so a written-down practice gets taken for an integrated capability when nothing actually requires it.

**A required capability** is one that has to be executed every time, because without it the conclusion of the work cannot be trusted. The design owes such a capability exactly two things: it states that the obligation exists and which conclusions lose credibility if it is not executed, and it declares that capability's strength today, as every invariant must. The concrete steps, parameters, artifact contract, and acceptance method are carried by the asset that owns it, and this design does not copy them.

**An optional capability** only has value on suitable tasks. **It does not go into this design**, and the design must not write it as something that necessarily happens. In exchange, the asset that owns it must state three things itself: which failure it prevents, under what conditions it applies, and whether it can be mechanically checked today. The third has to be honest — where it cannot be checked, that is what gets written. **Skipping an optional capability is normal, not a defect**; writing an optional capability as something that necessarily happens is the defect.

**The orchestration tree is the execution structure.** Sequence, parallelism, conditional and value-based branching, bounded and unbounded repetition, early exit, nesting, and local rework are all expressed as a tree. The tree carries the hard constraints: each step's artifact contract, the conditions that forbid continuing, and the single progress authority. On control structure a tree and a graph are essentially equivalent — the difference is form, not expressiveness — so "should this become a graph?" is not a question about expressiveness. Choosing a tree is a design decision rather than a logical necessity: tool-neutral orchestration that lives in the project's records is required, and this design represents it as a tree because a branch must be self-contained. The design records a differing opinion as well: some hold that the tree's shape is not the differentiator and that a flat node set with declared dependencies would satisfy the same hard constraints. The disagreement stays in the text so that readers do not have to infer which position governs. The tree's distinctive advantage is that a branch is well defined — it can be read, handed over, and deepened on its own — and its layering gives a top-down reading path, which holds only while branches are self-contained.

**A work order is its own workspace.** The durable content of one piece of work is owned by one durable directory, which is at once where that work's artifacts belong and the single source of progress for the runtime. The files in that directory are also how independent agents that share no session exchange input and conclusions: they do not need to communicate directly. That is how a party which took no part can rebuild the work from files alone.

**A set of capability units has declared ownership and boundaries.** Each unit owns its instructions, reusable subtrees, scripts, artifacts and acceptance contract, capability ceiling, and boundary description, and it may be used only through the public parameters its documentation declares. The set may grow, merge, and also shrink — but contraction must first declare its trigger. Without a trigger it can only be stated as an expectation rather than as a rule, because shrinking the set is a matter of whether the obligation a unit carries still exists, not of how capable the model has become.

**Governance intensity follows confirmed facts, and uncertainty fails to the stricter side.** Whether work takes the managed path, and how heavy that path is, follows confirmed facts rather than task length, wording, or subjective confidence. Missing, unavailable, malformed, or conflicting facts fail to the stricter side. Execution state has to be state rather than an admonition. This is also why process weight varies: as capability grows, process should be able to shrink, and anything added must justify itself. When the conditions that reasoning depends on stop holding, it must be brought up and formally retired rather than left in the text as an unexplained reason to exist.

**What did not happen still needs a name.** A record must separate "the key is missing" from "the key says no"; empty results need a fixed reason vocabulary; a check that never ran must not be read as a check that passed. Failure, recovery, and degradation are first-class subjects: failure is never silently skipped, and recovery semantics are written down by their own owner.

**Project facts are read from exactly one place.** Generic content and project-specific facts meet at the project bridge alone, and the bridge is the only read point for declarative project facts; generic content never hard-codes a consumer project's facts. Alternative bridge locations are not searched for. Undeclared conventions are not bridge facts and travel only through one bounded channel. When the bridge is missing or silent on a point, the order of resolution is fixed: use the bridge when it carries a relevant constraint; otherwise use the default that the owner of that point has declared in advance for the missing case; otherwise invent nothing and confirm with the user or stop at a precise blocker. A declared default may not override a missing constraint related to responsibility, contract, or safety; on those points the rule does not stop at the second layer and falls to the third. The design supplies no global, pre-invented defaults of its own.

**Expansion leaves a trace.** Structure widens by adding sibling nodes and deepens by adding child nodes, and both happen on the executor's judgement together with the user's requirement — never because a process prescribes it, and never against a depth or width target. There is no depth ceiling, because any ceiling becomes a target. What replaces it is a stopping criterion: stop when expansion has stopped producing new judgement, since a new branch that neither corrects nor narrows the level above it nor exposes a previously unknown constraint is only elaborating in place. How far to go is set by what the user asks for: a user who wants speed is entitled to a shallower and narrower pass, which is a legitimate trade rather than a behaviour to correct. That applies to the depth and width of exploration only, and it does not lower the floor for evidence and gates. A node that appears records why it appeared and whether it corrected, narrowed, or overturned the conclusion above it.

**A branch must be self-contained.** A branch should be readable, handable-over, and deepen-able on its own. Where a branch cannot be understood without a conclusion produced by another branch, that dependency is stated explicitly instead of being hidden in execution order, because order is not dependency: forcing B after A when B needs nothing from A makes the implementation stricter than the structure and shows the reader a dependency that does not exist. Cross-branch data edges must be readable from the record, and when views are rendered such an edge must be visible in the rendering — otherwise the top-down reading path loses its precondition.

**What genuinely needs a graph is data flow.** Control structure is expressed with a tree plus loops and conditionals; a graph is needed when one artifact is shared by several later consumers. That is a data dependency rather than a control dependency. The declarative surface already exists and needs no new mechanism: an artifact produced by one node can be read by several later nodes without copying it or chaining them, by publishing the producing node's runtime identifier in a shared blackboard key that each consumer points a category at. Adding a separate layer of artifact dependency edges would only repeat this and would be a mechanism disproportionate to the problem. Two routes are available, and both have a cost: the blackboard route weakens a branch's self-containment, because whether a consumer's delivery packet resolves depends on external state, while writing the path into an input declaration keeps it locally readable but validates nothing. Duplicating the node is not an acceptable substitute, because it produces a second artifact that will drift.

**Every invariant declares its enforcement strength today.** The design and anything normative derived from it must state, for each invariant, how strongly it holds, and the vocabulary is closed at three values. This requirement is itself convention-only, but it is a hard writing requirement for authors and reviewers.

**Design intent and measured behaviour are kept apart.** This design can claim that work goes deeper, stays closer to project conventions, and is more visible; it cannot claim that development gets faster. Measurable costs — time waiting for a user decision, gate latency, node counts, protocol bytes — are written down as costs, not as benefits. A named guarantee may only be written as "designed for" until a pre-registered comparison has been completed, and artifacts this project produced itself may not be used as evidence of this project's own value.

**Domain knowledge and acceptance criteria belong to the project.** What counts as satisfying acceptance is not prescribed by this design or by a generic capability unit; the project states it once, in its bridge. The rule holds for any domain: software development and software investigation are the scenarios this design is most often instantiated in, not a separate layer on top of a generic core. Optimising for large software projects is design intent rather than measured behaviour, and it works as a direction and a decision criterion — an approach that only holds at small scale and fails under a large project's complexity is not acceptable here — but it is not a claim about achieved performance.

## Principal concerns

Four concerns carry the normative content. Each states what it claims, its named invariants with their enforcement strength, one question for judging whether a change departs from it, and its boundaries and costs. The command-line interface is the tool-neutral mechanism these concerns share rather than a concern of its own: it appears wherever one of them needs it and owns no claim.

### Who owns the work

**What it claims.** A piece of work has its own durable record, and that record is the single source of its progress.

**Invariants.**

- **The durable content of one piece of work has exactly one source.** *(Mechanical: a terminal commit checks that declared artifacts fall inside the authorised scope and refuses them if they do not.)*
- **A durable fact may not be written outside this piece of work.** *(Mechanical, for the delegated path only: a terminal commit that declares an artifact outside the current work area is refused. The path an operator writes directly is not covered by that half.)*
- **A durable fact written directly by an operator is bound by the same scope.** *(Convention-only: nothing refuses a direct write that falls outside the current work area.)*
- **A party that took no part must be able to rebuild the record.** *(Convention-only: nothing checks what counts as a successful reconstruction.)*
- **Completed work records form the project's own historical memory of its work.** *(Convention-only.)* When a later action needs to know whether something was investigated before, what was rejected, or what was departed from, it reads the records the project kept rather than a conversation or a model's memory. Those records therefore need an owner and a form that a later reader can approach by topic. Nothing verifies that the reading happened; the guarantee equals the project keeping the records and actually consulting them.
- **The runtime's orchestration tree is the single source of progress.** *(Mechanical for one half only: a leaf operation that changes state derived from the structure instead of recomputing it is refused. The other half -- that a host-provided task list may only be scratch inside a node -- has nothing that refuses it, so it is convention-only.)*
- **The durable content of one piece of work is owned by one durable directory, and that is the definition of its workspace.** *(Convention-only: the runtime fixes the directory layout, but nothing refuses a departure from the claim itself.)*

**Judging a departure.** If the original session, Agent, and runtime are all gone, can a party that took no part say what this work was and how far it got, using files alone?

**Boundaries and costs.** Responsibility moves from a conversation to the project, at the cost that every piece of work leaves a durable shape and completed work has to stay somewhere retrievable rather than in a session. The reconstruction guarantee and the historical-memory guarantee both rest on contract text alone, so review rather than a gate has to carry them — they never hold by themselves; they hold when the project really keeps the records.

### When and how work is managed

**What it claims.** Whether work takes the managed path, and how heavy that path is, follows confirmed facts, and uncertainty moves toward the stricter side. Execution state is state rather than an admonition.

**Invariants.**

- **Insufficient evidence moves toward the stricter side.** *(Mechanical: of the six admission facts, any that is not an explicit "no" routes to the managed path, and an adapter failure also returns a strict result.)*
- **Downstream work may not start before upstream work is in place.** *(Mechanical: the delivery packet sets minimum thresholds for source and artifacts and explicitly forbids lowering a threshold to let work through.)*
- **Structure is owned by the tool and each node is self-contained.** *(Mechanical: what is delivered to an executor excludes the whole tree, its sibling nodes, and the root node, and a missing required input fails to the stricter side. Nothing refuses that delivery being handed to an executor other than the one it was prepared for -- that half is convention-only.)*
- **Derived state may be read but never written.** *(Mechanical: the engine recomputes composite and loop state, and no leaf-node operation can touch it.)*
- **A terminal commit takes effect together with what it declares.** *(Mechanical: a failed commit rolls back the previous state and reports that files were written but not committed.)*
- **What did not happen still needs a name.** *(Convention-only: the record must distinguish "never written" from "written as no", and an empty result must carry a named reason -- but today that holds on the skip branch only. A guard that tests "not equal" over a never-written key runs the node with no marker, so an unexamined case can be read as a passing one.)*
- **A complex task establishes its goal first, and the goal is a structured artifact.** *(Default: the goal stage comes before other stages and no guard blocks it, and the entry point turns that group off when a task does not need it. The default is declared in the template that owns the orchestration structure, not in the design, which only requires the default to exist and to not mean "refusing to work".)*
- **Existing material and project conventions are researched before execution.** *(Convention-only: the discovery record must be consumed and a departure from a declared rule must record its reason, but no key, guard, or check refuses skipping it.)*
- **Failure, recovery, and degradation are first-class subjects.** *(Convention-only: recovery semantics are carried by their own owner and the discipline that failure is never silently skipped rests on contract text.)*

**Judging a departure.** If this rule were violated, which check would stop it?

**Boundaries and costs.** Two costs dominate. First, facts have to actually be collected: admission facts are not decoration, because any unconfirmed item sends the path to the stricter side, so the fast path exists only when the facts permit it. Second, mechanical enforcement covers only part of this concern: the mechanically refused ones sit on the managed path, while the defaulted one and the convention-only ones have no such gate and are carried by review.

### How the workflow attaches to the outside

**What it claims.** Generic practice and project facts meet at one fixed interface, with one bounded channel for undeclared conventions, and the workflow is installed onto runtimes through declarative adapters.

**Invariants.**

- **The bridge is the only read point for declarative project facts.** *(Convention-only: the path is declared fixed, but nothing refuses a project that has no bridge, and nothing refuses a read that goes around it. The verifiable boundary is that such a read must be written down as an explicit departure. Within the scope of declarative facts; undeclared conventions belong to the bounded channel below.)*
- **A read of declarative project facts may happen at the bridge and nowhere else.** *(Convention-only: nothing refuses a read that goes around the bridge.)*
- **No alternative bridge location may be searched for, and no tool-specific substitute may be introduced.** *(Convention-only, and it is the boundary of that channel.)*
- **An undeclared convention is read only through one bounded channel.** *(Convention-only: reads have a budget, failing to read fails to the stricter side, and the third authority tier is inference.)*
- **A generic asset contains no environment-specific fact.** *(Convention-only: nothing refuses a consumer-project fact copied into generic content.)*
- **Runtime targets are generated from a single source and checked for staleness.** *(Mechanical: a result in which a generated target cannot be traced to its declared source -- missing, modified, or not generated from that source -- is refused.)*
- **A declared adapter support level must be true and must have evidence.** *(Convention-only: the format is validated and the content is fixed, but a claim of enforcement is the adapter's own.)*
- **One Agent tool attaches with capability units and the command-line interface alone.** *(Convention-only: an adapter declaration is a product of assembly and validation, but nothing asserts that no plugin was needed.)*

**Judging a departure.** Does this change put an environment-specific fact into generic content, or leave a generated target stale?

**Boundaries and costs.** Generation and staleness checks are mechanical; convention tiering, adapter honesty, and the attachment route itself rest on contract text. The cost is that this concern's reach depends entirely on the discovery contract and the command-line interface staying available.

### How capabilities are organised

**What it claims.** Each capability unit is responsible for its own rules, those rules must be checkable, and the set of units may grow, merge, and shrink.

**Invariants.**

- **A capability unit owns its instructions, subtrees, scripts, artifacts and acceptance contract, capability ceiling, and boundary description.** *(Convention-only.)*
- **A capability unit's contract must be complete, or the unit does not hold.** *(Mechanical for units that become orchestration nodes: a task leaf handed to an executor without its instructions, its deliverables or its acceptance conditions is refused. A capability package's own contract text is not covered by that half.)*
- **A capability unit may be used only through the public parameters its documentation declares.** *(Convention-only: nothing refuses a use that bypasses the public parameters.)*
- **Capabilities divide into core and specialised units with distinct responsibilities.** *(Convention-only.)*
- **The set may grow, merge, and also shrink.** *(Convention-only: shrinking must first declare its trigger, and where no trigger can be written the intent can only be stated as an expectation. Like the reconstruction guarantee above, its force is text alone.)*

**Judging a departure.** Which obligation does this capability unit carry, and what tool makes it checkable?

**Boundaries and costs.** Contract completeness is mechanical; ownership, classification, contraction, and use through the declared public parameters rest on contract text. A unit placed in the wrong class, unable to state a trigger, or used around its public parameters is therefore detectable only by review.

#### Three purposes, and how a purpose is retired

Each layer of purpose carries a sunset clause, used the same way every time: when the condition a purpose depends on stops holding, that purpose must be brought up for discussion and formally retired by the confirmation path rather than left in the text as an unexplained reason to exist. That obligation is convention-only.

1. **It can be relied on.** A party that took no part can tell from the record what was done, what was examined, and what was rejected. *Sunset clause:* if relying on a record turns out to produce no decision value — a successor never consults it when a decision is needed, or it cannot affect any decision — this purpose should be formally retired rather than kept in a reduced form.
2. **It does no unnecessary work.** As capability grows, process should be able to shrink, and anything added has to justify itself. *Sunset clause:* if the design no longer prevents any disproportionate complication, this purpose should be formally retired, because it no longer constrains any decision.
3. **It converts a capability unit's step-by-step narrative into a reusable orchestration subtree template.** A prose sequence is a legitimate equivalent input, and the conversion pays twice: it saves context and it installs structural constraint. *Boundary caution:* the conversion replaces only the step-by-step narrative — not intent, domain knowledge, acceptance criteria, or public contracts. *Sunset clause:* if the conversion no longer delivers either context economy or structural constraint, this purpose should be formally retired.

**The third purpose is a diagnosis, not a rhetorical flourish.** A purely textual sequence can be selectively ignored or partially followed, and when that makes the work fall short, the correct repair is stronger structural constraint rather than another paragraph of prose advice. That diagnosis is where the rule that only what can be checked goes in comes from.

A concern's claim that serves no purpose does not belong here.

## Enforcement strength

The design requires each of its invariants to state how strongly it holds today, and the vocabulary is deliberately small and honest:

- **Mechanical** — a nameable check, validator, schema, or runtime transition refuses the violation. Writing "mechanical" is allowed only when that thing can be named.
- **Default** — the installed value already selects it, and departing is one explicit published act. The default's declaration site must be nameable.
- **Convention** — contract text only. Nothing refuses the departure, and the text must say so.

The three values are closed: the text may not introduce a fourth or fifth strength word. Where part of an obligation is mechanically guaranteed and part is not, the correct form is two statements — one naming the mechanical half, one marking the rest convention. **An invariant without a declared strength is unfinished.** The strength is declared on the sentence that states the invariant, not on a chapter or section, because a chapter-level declaration hides which of its statements would be refused.

This requirement exists because the design's own force is documentation discipline plus a small number of mechanical checks, and a reader deserves to know which is which instead of inferring it. The values are also load-bearing for a second reason: where the deterministic half of an obligation has not yet been split out into the command-line interface, the honest label is *convention*, and that label is itself the signal that something could be made checkable and has not been.

## Obligations that run across the design

Eight obligations govern the design itself, and this page states all eight. Each declares its own strength rather than being covered by a section-level label. Two further items follow them: the stability dependence on detail owners, and the path for judging whether a change departs from the core.

**Each design statement has one owner, resolved by reference.** Maintain a normative statement in one place and refer to its owner by path when another document needs it. This avoids two failures: detail burying the principles that guide a change, and independently maintained copies drifting apart. An explanation may restate a principle for its reader, but must not establish a competing normative owner. *(Convention-only: no check rejects every duplicate statement; ownership and review evidence carry this discipline.)*

**The whole-architecture judgement is recorded where the change is designed.** A change is judged against the whole architecture and not only against its local symptom, and a change that removes a local symptom while making the whole more tangled is not merged for local convenience. The judgement answers at least: which of the four concerns does it fall in, and does it also touch relations between them; does it reuse an existing mechanism or add one disproportionate to the problem; does it repair a real defect or build scaffolding for an unconfirmed assumption; and is the system more coherent or more tangled afterwards. The judgement has to be written down, in the place where the change is designed — a work order's solution document, a capability unit's contract change note, or an equivalent design artifact. **A whole-architecture judgement that is not recorded was not made.** *(Convention-only.)* Two further criteria hold: a smaller repair that reuses an existing mechanism or pattern and is equally correct must be preferred over a new command, new state, new configuration surface, new node type, or new cross-cutting check; and a minor or low-value problem must not justify durable added complexity. *(Convention-only.)*

**A permitted departure is distinguished from a violation.** A specification resolved only by reference will meet situations it did not foresee, and the correct outlet is registering them rather than quietly proceeding. A departure is permitted only when all three hold: it is explicitly named, it is registered before it happens, and it carries a scope and an expiry condition — or an explicitly written statement that there is none, with the reason. Any other departure is a violation, even when its result looks better. Registration is owned by the project's structured notes, which already own known deferred decisions and accepted trade-offs; the design builds no second register and names no current exception. *(Convention-only.)*

**A newer conclusion must catch up with documents still asserting the older one.** When a new conclusion conflicts with what a document still in force states, that document must be caught up in the same change that puts the conclusion into effect: update it, correct its placement, or confirm that the reference has lapsed and deal with it. **Two documents still in force must never go on stating contradictory conclusions.** *(Convention-only: no automatic check finds this kind of lapse, so the obligation itself is the only mechanism, and all that can be pointed at is whether a reference has broken or quietly lapsed.)* It applies to conflicts between documents, to a proposition overturned by later evidence that stays in the text as a reason, and to one design claim written with two different scopes in two places.

**Deliberately deferred work is durably recorded.** Deferred work, accepted trade-offs, and "not now, possibly later" decisions must be written as durable, structured project notes rather than left in a conversation or implicit in one line of reasoning, so that a later evolution can reconsider them with the original reasoning intact. *(Convention-only: no key, guard, or check fails because a deferral went unrecorded.)*

**Any adjustment to the core requires user confirmation.** Any modification of the core design — addition, refinement, rewording, or structural rewrite — requires the user's confirmation before it takes effect. The reason is that the design's uniqueness makes changing it an explicitly authorised act rather than a by-product of implementation: one unconfirmed "incidental correction" is enough to put the single authoritative copy out of step with what every participant has been relying on. When an implementer believes the core should change, the correct action is to propose it and obtain confirmation, not to change or bypass it during implementation, and differing readings of the core are not settled separately inside implementations. *(Convention-only: no mechanism can verify that an iteration really read the core design or that the user really confirmed a change, so what refuses an unconfirmed modification is the path of obtaining confirmation itself.)*

**Evolution follows the core and rechecks it every round.** Continued evolution of this workflow should follow the core design and recheck it as it proceeds. Every iteration begins by reading the design again and judging, against its principles, purposes, concerns, and criteria, how the coming change relates to the core — and having checked once is no reason to skip checking the next time. Capability units involved in self-evolution record these obligations in their own contracts rather than leaving them as verbal understandings. *(Convention-only.)* Two conditions must be satisfied together: **not departing from the core**, so that the principles, purposes, claims, invariants, and criteria stated above govern whether a change is sound and are not bypassed because a change is more convenient or a requirement more pressing; and **not letting detail drown the core**, so that growth in features and detail never makes the core unrecognisable. The design carrying only principles, invariants, and criteria, with detail referenced by path, is that requirement applied to the document itself — when this document starts carrying implementation detail, it is already drowning the core. The executable check at the end of an evolution is therefore whether the design still carries only principles, purposes, and criteria, and whether its four concerns can still each be read on their own.

**Whether information is handed over through files is judged while the change is in flight.** The criterion is whether a change hands information over through files or depends on what is left of a conversation. Handing over through files is how work is made to belong to the project: it lets a party that took no part take the work over. Depending on conversation residue is a departure, because when the conversation ends the information is gone and the record gives no sign of what is missing. This criterion applies earlier than the reconstruction question above: that one asks whether the record can be rebuilt afterwards, while this one asks whether this change left understanding in a conversation. *(Convention-only: nothing reads a record and decides that it depends on conversation residue; all that can be pointed at is the criterion itself and a gap in the record that cannot be explained.)*

**Evidence, gates, and verification are not weakened for a small-scale scenario.** Nothing may be relaxed on the grounds that it is more convenient at small scale. *(Convention-only: this guards a design judgement rather than a violation any check could detect.)* It answers a particular argument: when someone proposes that a requirement can be dropped at small scale, the right response is to ask which failure that requirement prevents, not to lower it according to size. It is not the same rule as the one that lets a user who wants speed accept a shallower and narrower pass. That rule narrows the depth of exploration only; the floor for evidence and gates does not come down with the scale of the work.

**Two further items complete these obligations.** The design also accepts a stability dependence on detail owners and defines how to judge a departure from the core. Both are stated in the next subsection.

### Stability dependence on detail owners, and judging a departure

Several concerns depend on documents that own their detail. One class of that dependence needs saying separately: **if a detail owner is moved, renamed, deleted, or substantially rewritten, the affected invariants point at nothing and no automatic check notices.** *(Convention-only.)* The dependence is explicitly recorded and accepted, and any change touching a detail owner begins by confirming that the design's references into it still hold.

**Judging whether a change departs from the core.** For any change, whether it departs from the core is a question with a definite path rather than a matter of feel:

1. Does it conflict with a claim, invariant, or criterion of one of the four concerns? A conflict is a departure.
2. Does it conflict with one of the fundamental commitments or one of the principal methods? A conflict is a departure; the scope covers the whole normative surface, not only the concerns.
3. Does it create another independently maintained normative copy of a design statement instead of referring to its owner? If so, it is a departure. An explanatory summary that does not claim that ownership is different.
4. Does it require a mechanism, node type, command, configuration surface, or state that no concern describes and no existing mechanism carries? Without an explanation of why existing mechanisms cannot carry it, it is a departure.
5. Does it let a concern's detail start replacing that concern's claim, or let detail drown the core? If so, it is a departure.
6. Does it modify the core design itself? That requires the user's prior confirmation rather than an implementer's unilateral decision.
7. Has it broken or quietly lapsed a reference anywhere? Did it move, rename, delete, or substantially rewrite a document the design references by path? Did it leave an invariant pointing at a target that no longer holds? If so, it is a departure even when the first six questions all pass. This question targets a real failure mode: no automatic check notices a detail owner that has been changed, or a referenced document that no longer states what it was claimed to state.

With no conflict on any of these, a change is consistent with the core. Where there is a conflict but the author believes the core itself should change, the path is to obtain confirmation first rather than to depart quietly during implementation.

## What the design is not

The design does not claim more than the implementation provides. The runtime record exists so that work can continue and be accounted for, not as proof that the work was executed correctly: integrity checks detect edits and do not authenticate who invoked them; completion receipts are unsigned self-reports; the viewer is read-only, so a user approves rather than editing in place; and the shipped host adapters declare themselves validated-only. The design's value claim is split the same way: cost is measurable, while benefit is described as designed-for until a pre-registered comparison exists.

The design generalises across tasks. It does not divide itself into a separate layer for software development: software development and software investigation are its main application scenario, not a specialisation sitting on top of a generic core. The one rule that survives from that framing is derivable and stays — **acceptance criteria belong to the domain and come through the bridge.**

**An open question is recorded as open.** Whether the design's single normative status deserves mechanical enforcement has not been assessed. Any proposal to make it mechanical must first show, under the whole-architecture obligation, that it is proportionate to the problem, and then obtain the user's confirmation. Until it is assessed, that status is convention-only.

## Where the project came from

This section is background rather than a layer of the design, and the commitments, methods, and concerns above govern wherever a statement here conflicts with them.

The project began with problems its author kept meeting while developing software with Agents. The first four instances named were: **work that never goes deep enough or thorough enough**; **tasks that drift away from their purpose as they run**; **results that are not wrong but violate the project's own conventions**; and **a process that cannot be seen, so understanding of the project decays**. Those four were the starting point and only part of the picture: they came from examples in a conversation, they are neither a complete account of the problem nor a statement of guiding principle, and no chapter of the design is divided along them.

The design's obligations can be traced to the full set of real problems its capabilities address, and that set is carried by evidence rather than asserted by the design. Back-derived from the capabilities the workflow already has, the problems are:

1. **Unaccountable autonomy** — substantive work proceeds with no record of whether it should have been managed, so the investment cannot be shown to match the facts.
2. **Goal drift** — after a long run and repeated dispatch, execution quietly stops serving the user's stated goal, and it is noticed only afterwards.
3. **Shallow work taken for thorough** — a stage is declared complete while the material it claims to have examined was never examined enough to support the conclusion.
4. **Results that violate the project's own declared conventions** — the work is not wrong, but it breaks rules, formats, commands, or patterns the project has already declared.
5. **Silence read as compliance** — something never checked, never published, or never applicable is read as having passed.
6. **Records that cannot be trusted as evidence** — a durable record cannot support the claim that a stated thing happened.
7. **No legitimate way to continue after a failure** — a failed, blocked, or rejected flow has no legitimate and recorded continuation path.
8. **Delegation that overreaches** — a delegated executor receives more context, more authority, or a wider scope than its single node needs.
9. **Invisible process and lost project understanding** — people cannot see work while it happens, and the understanding built up during it has no durable home.
10. **Unbounded repetition** — revision, review, or retry loops fail to converge and never stop.
11. **Existing feature behaviour changed without declaration** — behaviour the project already depends on is altered with no record that this was deliberate.
12. **Documentation and asset drift** — one fact written in two places diverges, or a generated artifact no longer matches its canonical source.
13. **Binding to one Agent tool or one project** — when the tool, model vendor, or consumer project changes, the workflow stops working.

The enumeration is for judgement, not for use as a checklist: every claim above can be asked which of these it prevents, and a newly proposed capability can be asked the same question. The design does not guarantee the enumeration is complete — it is a best enumeration back-derived from the capabilities and can be re-derived as the set of capabilities changes.

### How the design's relations to other documents are judged

The core design writes principles, invariants, and decision criteria only; it does not write implementation detail. Each topic's detail has its own owner, and that ownership is given by topic category rather than by naming a file, because a particular file gets moved, renamed, or split while a rule about who owns a topic does not. Reading the owner by path is how detail is obtained; the design's principles are enough when detail is not needed. The design references those documents and does not restate their content. *(Convention-only.)*

Explanations, contracts, and implementation details serve different reader needs. An explanatory summary must preserve a rule’s conditions and limits, identify the contract that owns operational detail, and avoid establishing a competing rule. *(Convention-only: semantic consistency requires review.)*

**Version matters are not prescribed here.** The design states no version number and no version rule; where version policy is needed it is read from the document that owns it.

## For the surrounding context

For canonical sources and ownership boundaries, read [architecture](architecture.md). For the workflow’s work-order records, workshop model, and explicit feature baselines, read [workshops and features](workshops-features.md). For how a deliberate change to the workflow itself is made, read [evolving the workflow](../workflows/evolving.md).
