# Independent critic loop

The critic is a separate reviewer, not the implementer. It reviews only the screenshots and the
brief's stated visual target. It must not read implementation code, README claims, prior self-reviews
or the evaluation standard.

## Method

1. Review every captured state at each viewport at 1:1 and thumbnail size.
2. Judge against the target: composition/focal hierarchy, depth/space, palette/contrast, object and
   character readability, UI/typography and states, consistency across states, and generic/under-
   composed results. Do not require a preferred style; do require that the result be intentional
   for this target rather than a default template.
3. Return a state x criterion table, severity-ranked findings (`high`/`medium`/`low`) with the
   concrete screenshot/area, a concrete change direction for every high/medium (not "make it
   prettier"), and a one-line verdict.
4. `accepted` requires no high/medium finding. `accepted-with-residuals` is allowed only with no high
   finding, named residuals, and explicit acceptance by the user or project risk gate. Otherwise
   `revision required`.
5. Run at least two cycles; record the critic identity and inputs. A self-review, a colour-bucket
   count or a non-blank screenshot is not a substitute.

## Functional gate

The critic does not test interaction, placement, crafting/output, bounds, save/reload or first-run
controls. Those are covered by the prior accepted capability inventory's real-pointer verification.
A visual pass cannot close while a core control is a no-op, even if every screenshot is accepted.
