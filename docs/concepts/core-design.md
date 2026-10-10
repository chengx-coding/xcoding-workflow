**Language:** **English** | [简体中文](../zh-CN/concepts/core-design.md)

# Core Design

This page introduces the XC core design and explains what it rests on.

The XC core design is XC's formal statement of what its core is: the principles, invariants, and decision criteria that its five dimensions together rest on, and the shared frame of reference that people and agents use when they judge a later change. This page summarizes that statement as public explanatory material.

The design rests on five dimensions. A work order is the workbench: every piece of delegated substantive work owns a persistent, self-contained directory with a clear owner. An orchestration tree plans execution: it carries how that work is planned, driven, constrained, and observed. A project bridge is the single read point that connects the generic flow to one project's facts. An agent Skill collection supplies the set and boundary of the reusable capabilities that complex tasks need. A software-development specialization layer sits on top of the generic design and adapts it to software work.

Their dependency runs one way: the work order is the carrying unit, the orchestration tree is the execution plan, the bridge is the entry point for project facts, the Skill collection is the supply of capability, and the software-development layer is the application specialization. The work order gives the orchestration tree its durable location and artifact ownership; the orchestration tree gives the Skill collection a reusable flow carrier; the bridge supplies project-specific facts to the other four; and the software-development layer is constrained both by the generic flow and by the project bridge.

This overview groups three obligations that run through all five dimensions. A change must be judged against the whole architecture and not only against its local symptom, so a repair that removes a local symptom while making the whole more tangled is not merged for local convenience. Every change must be proportionate, reusing an existing mechanism rather than adding a new command, state, configuration surface, or node type when a smaller correct fix is enough. Canonical sources are changed first: derived and generated artifacts are never hand-edited, and a change must not create a second authority that has to be kept in step.

Any adjustment, improvement, or change to the core design as a whole requires your prior confirmation before it takes effect, rather than an implementer editing it as a side effect of other work.

This overview summarizes the core design so a reader can place the rest of the public documentation against it. It is an explanation rather than the design itself, and it does not claim to replace it.

For the surrounding context, read [architecture](architecture.md) for canonical sources and ownership boundaries, [workshops and features](workshops-features.md) for the work orders, workshop, and feature baselines the design rests on, and [evolving the workflow](../workflows/evolving.md) for how a deliberate change to the workflow itself is made.
