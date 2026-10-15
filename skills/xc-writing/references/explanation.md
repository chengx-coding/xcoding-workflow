# Explanation and argument

Use this guidance when the difficulty is understanding a mechanism or following a sustained argument. Readers need a route from what they know to what the text asks them to conclude. Technical accuracy supplies the destination; explanation supplies the route.

## Give the reader an object to think about

Introduce the system, phenomenon, or decision before its internal labels. “The cache keeps a local copy of the catalog” gives a reader something to picture. “The catalog replication subsystem” may name the same thing, but naming alone does not explain it. Once the object is established, a precise term can reduce repetition and support deeper discussion.

Replace vague abstractions by the relationship they conceal. Instead of “Lease invalidation enables consistency maintenance,” explain what expires, who stops using it, and what happens next. Keep an abstract term when it identifies a real recurring concept; explain it once and use it consistently. Do not invent a concrete example, measurement, or actor that the evidence does not support.

For a mechanism, follow a meaningful change through the system: an event occurs, a component responds, state changes, and an observable result follows. Include the failure or exception where it changes that sequence. This causal structure often explains more than a catalog of components. A catalog is still useful when the reader's task is to look up a component rather than understand a process.

## Connect evidence to the claim

State what was observed and why it bears on the question. A comparison is easier to assess when the reader can see the relevant baseline, changed condition, result, and limitation. Do not make the prose more decisive than the study or test allows.

For example, a measurement showing lower latency in one workload supports a claim about that workload under the measured conditions. It does not establish that an algorithm is always faster. Explain the possible mechanism as a hypothesis unless it was tested. Preserve alternative explanations, uncertainty, and sampling limits where they matter to the inference.

In scientific prose, distinguish a research question, a method, an observation, an interpretation, and a recommendation. They need not become five headings. The distinction should remain visible in the verbs and transitions: “measured” reports an observation; “may explain” offers an interpretation; “we recommend” makes a judgment. A citation identifies evidence; the surrounding sentence still needs to explain its relevance.

## Let paragraphs carry the reasoning

Begin a paragraph where the reader needs a new step. Establish its point, develop it with the necessary mechanism or evidence, and show its implication when that implication is not obvious. A paragraph can also introduce a complication that the next paragraph resolves. Do not force every paragraph into the same miniature template or add a summary that merely repeats its first sentence.

Transitions should express the actual relationship. “However” signals a qualification or conflict; it should not decorate an unrelated next topic. If a paragraph shifts from correctness to cost, say why cost matters to the decision. If several interpretations remain possible, explain what would distinguish them.

Keep subjects close enough to their verbs that a reader can follow the action. A long sentence is useful when it holds a necessary condition and its consequence together. Split it when independent obligations, nested exceptions, or changes of actor compete for attention. Active voice often clarifies responsibility; passive voice can be appropriate when the affected object matters more or the actor is unknown.

## Use examples and layers without hiding the rule

Choose an example that exposes the difficult relationship. An analogy can provide an entry point, but state where it stops matching the real system. Return to the technical explanation before drawing a conclusion. An example illustrates a rule; it does not prove the rule or replace its exceptions.

Put the core explanation where readers need it, then offer detail for readers who need to inspect assumptions or implementation. A decision-changing limitation belongs with the claim it qualifies, even if supporting derivations come later. Headings should help readers find questions or subjects; they should not impose an artificial hierarchy on a short explanation.
