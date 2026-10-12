**Language:** **English** | [简体中文](../zh-CN/concepts/core-design.md)

# Core Design

This page introduces the XC core design and explains what it rests on.

The XC core design is XC's formal statement of what its core is. It sets out the principles the design is judged against, the purposes it serves, and the concerns that carry its normative content, together with the invariants and decision criteria those concerns state. A later change is measured against that statement rather than against a local symptom. This page summarizes the statement as public explanatory material.

## A workflow, not a harness

A harness is a programmatic runtime. It binds one specific Agent and the tools that Agent holds, and it is what actually runs the work: processes, sandboxes, permissions, context, model routing, and tool calls.

A workflow defines how the work should be done: what happens first, what each step must produce, what conditions forbid going further, and who reviews the result. It binds no particular tool. Any Agent that can complete tool and Skill calls normally can follow the same structure.

The distinction decides what belongs in the design. Running the work belongs to the harness; the method stays here. Where the two meet is one fixed project bridge, which supplies the facts about a specific project and nothing else.

## How the workflow attaches to an Agent tool

No per-tool integration plugin is needed. Attachment happens in four layers, each owning one thing:

- A **Skill** is the only attachment mechanism. It is how an Agent tool learns what XC is and how to operate it. A Skill's discovery contract is what the tool loads, so the capabilities reach every supported tool without a bespoke adapter.
- The **CLI** holds everything that can be made deterministic: scheduling, state transitions, integrity checks, identifier generation, schema validation. Anything with a fixed answer given the same input belongs here rather than in repeated model judgement.
- The **project bridge** holds the project's own half — build and test commands, languages, boundaries, constraints. It is read once. The generic design neither guesses those facts nor fills them in on the project's behalf.
- The **workshop** holds the durable records: work orders, artifacts, and runtime state.

Two families of Skill follow from this. **Core Skills** explain what the workflow is, how the CLI is used, and what the design's mechanisms are. **Specialized Skills** explain one stage each: how to state a goal, how to investigate, how to review.

One division of labour governs which family an asset belongs to and what belongs in the CLI at all: **deterministic things go to the CLI; things requiring judgement go to Skills.**

## What the design is for

XC exists to remove four problems its author kept meeting when working with Agents on complex tasks. Each has evidence in the project's history rather than being hypothetical:

- **Work that never goes deep enough.** Investigation has a method — confirmed facts, hypotheses and unknowns kept apart, claims grounded in cited evidence — and how deep to go is decided from the task's facts.
- **Tasks drifting away from their purpose.** A structured goal record, one authoritative progress state, and solution-to-source binding protect the record of the goal. Adherence to the goal over a long run is not yet mechanically guaranteed, and the design says so.
- **Results that are not wrong but violate the project's conventions.** Convention discovery has a mandatory floor, three authority tiers (declared, configured, and undeclared de-facto patterns), and a rule that departing from a declared rule must be recorded with a reason.
- **Work whose process cannot be seen.** The durable record keeps progress, artifacts, and decisions, so understanding of a long-lived project does not decay with the number of tasks run.

Two of these four are solved today and two are not. The design states which is which rather than presenting all four as settled.

## How the design is organised

Three layers, from what is believed to what is required:

**Four principles** are the decision criteria. **Who owns the work**: a unit of work's durable state belongs to the project, not to one conversation and not to a vendor's store, and a party that took no part must be able to reconstruct it. **Attachment by Skill and CLI, not by plugins**: integrating with an Agent tool needs no per-tool integration layer. **Only what can be checked is written down**: a rule that must hold against an execution not intending to comply has to be a checkable condition on represented state, and where that is impossible the design must say so. **One owner per fact**. **A record must distinguish three states**: done, never examined, and not applicable — an absent conclusion is itself a conclusion.

**Three purposes**, each carrying a sunset clause. A purpose is retired by argument when the condition it depends on stops holding, never by silence — the design previously kept a purpose its own later evidence had overturned. The purposes are: remove the four problems above; remain reliable for a party that did not do the work; and avoid adding work as capability grows, so that growth has to earn itself.

**Four concerns** carry the normative content, and each states its claim, its named invariants, a question for judging a departure, and its state today:

- **Who owns the work** — one more owner per durable fact, nothing durable written outside the unit, the runtime tree as the single progress authority, and reconstruction by an absent party.
- **When and how work is managed** — proportional governance that fails closed on missing evidence, proof-carrying admission of declared inputs, tool-owned structure with least-context delivery to each worker, derived state that is read and never written, atomic terminal commits, and a named outcome wherever nothing happened.
- **How the workflow attaches to the outside** — the bridge as the single read point for declarative project facts, one bounded tiered channel for undeclared conventions, no environment-specific fact in a generic asset, generated host targets with staleness checks, and honest adapter support levels.
- **How capabilities are organised** — capability units that own checkable policy, usable through documented public parameters alone, and a set that may grow, merge, and also contract, where contraction must declare its trigger.

## Every invariant declares its enforcement strength

The design requires each of its invariants to state how strongly it holds today, and the vocabulary is deliberately small and honest:

- **Mechanical** — a nameable check, validator, schema, or runtime transition refuses the violation.
- **Default** — the installed value already selects it, and departing is one explicit published act.
- **Convention** — contract text only. Nothing refuses the departure, and the text must say so.

An invariant without a declared strength is unfinished. This requirement exists because the design's own force is documentation discipline plus a small number of mechanical checks, and a reader deserves to know which is which rather than inferring it. The three values are also load-bearing for a second reason: where the deterministic half of an obligation has not yet been split out into the CLI, the honest label is *convention*, and that label is the signal that something could be made checkable and has not been.

## What the design is not

The design is general across tasks. It does not divide itself into a separate layer for software development: software development and software investigation are its main application scenario, not a specialization sitting on top of a generic core. The one rule that survives from that framing is derivable and stays: **acceptance criteria belong to the domain and come through the bridge.**

The design also does not claim more than the implementation provides. The runtime record is an admission-and-continuity record, not proof that work was executed correctly; integrity checks detect edits and do not authenticate; completion receipts are unsigned self-reports; the viewer is read-only, so a user approves rather than editing in place; and the shipped host adapters declare themselves validated-only. The design's value claim is likewise split: cost is measurable, while the benefit is described as designed-for until a pre-registered comparison exists.

## How a change to the design itself is made

Any adjustment, improvement, or change to the core design as a whole requires your prior confirmation before it takes effect, rather than an implementer editing it as a side effect of other work.

Three obligations run across the whole design and are stated in one place. A change must be judged against the whole architecture and not only against its local symptom, so a repair that removes a local symptom while making the whole more tangled is not merged for local convenience. Every change must be proportionate, reusing an existing mechanism rather than adding a new command, state, configuration surface, or node type when a smaller correct fix is enough. Canonical sources are changed first: derived and generated artifacts are never hand-edited, and a change must not create a second authority that has to be kept in step. One further obligation was added with this revision: **a newer conclusion must reach the documents still asserting the older one**, because the design's own history contains a purpose its later evidence had overturned while the document went on asserting it.

This overview summarizes the core design so a reader can place the rest of the public documentation against it. It is an explanation rather than the design itself, and it does not claim to replace it.

For the surrounding context, read [architecture](architecture.md) for canonical sources and ownership boundaries, [workshops and features](workshops-features.md) for the work orders, workshop, and feature baselines the design rests on, and [evolving the workflow](../workflows/evolving.md) for how a deliberate change to the workflow itself is made.
