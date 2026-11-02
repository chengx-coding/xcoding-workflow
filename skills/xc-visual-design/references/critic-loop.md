# Independent critic loop

The critic is a separate reviewer, not the implementer. It reviews **only the supplied screenshots**
at matched states and the project's stated visual target. It must not read implementation code,
README claims, prior self-reviews or the evaluation standard.

## Method

1. Review each state at each viewport at 1:1 and at thumbnail size.
2. Judge:
   - composition and focal hierarchy;
   - depth/space and layering;
   - palette/contrast and state separation;
   - character/object readability and animation;
   - UI typography, spacing, alignment, focus/disabled/empty states;
   - consistency across states;
   - anti-slop: generic template, default fonts, random gradients, centered-card-only, flat
     single-band composition, decorative noise without hierarchy.

   Do not require a particular style. A plain result can pass if the project target is plain; a
   generic or under-composed result cannot pass merely because it is functional.
3. Return a state x criterion table, severity-ranked findings (`high`/`medium`/`low`) with the
   concrete screenshot/area, a concrete change direction for every high/medium (not "make it
   prettier"), and one-line verdict.
4. `accepted` requires no high/medium finding. `accepted-with-residuals` is allowed only when there
   is no high finding, the residuals are named, and the caller explicitly accepts them. Otherwise
   `revision required`.
5. The implementer fixes findings and re-renders; run at least two cycles. Do not substitute a
   self-review, a colour-bucket count or a non-blank screenshot for the critic.

## Functional gate

The critic does not test interaction, placement, crafting output, bounds, save/reload or first-run
controls. Those are covered by the real-pointer preservation gate. A visual pass cannot close while
a core control is a no-op, even if every screenshot is accepted.
