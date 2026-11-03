# Visual review record

`review_path` is the closure artifact. It must contain:

## Target and inputs

- visual target source (request/bridge):
- brief path:
- screenshot manifest (states, viewports, hashes):
- critic identity and independence statement:
- functional evidence path(s):

## Cycles

For each cycle:

- cycle number:
- critic verdict:
- findings: severity, screenshot/area, change direction;
- fixes applied and re-render evidence;
- unresolved findings.

## Dual gate

- visual gate: `accepted` / `accepted-with-residuals` / `revision required`;
- high findings remaining:
- named residuals and their acceptance source (user or project risk gate only):
- functional gate: `pass` / `fail` / `not applicable`;
- prior capability inventory / verification evidence:
- final decision and reason.

A visual pass with an unresolved high finding or a failed functional gate is not accepted. The
implementer/caller cannot accept residuals on the user's behalf.
