---
name: "xc-conventions"
description: "Discovers a project's own development conventions at a proportional depth before a substantive change. Invoke for the mandatory L1 scan in every managed mutation (and the lightweight L0 direct-path tripwire), regardless of whether the bridge declared convention locations."
---

# XC Conventions

`xc-conventions` owns the discovery of development conventions that live inside a project but are not contained in, or explicitly pointed to by, the project bridge. It closes the gap where convention discovery was left to agent initiative and disappeared entirely in shallow, proportional work.

It is a discovery and classification contract, not an authority. `AGENTS.md`, host and security rules, and explicit user instructions always outrank what this Skill surfaces. It never rewrites product code, fabricates a knowledge base, or invents project commands.

## Parameters

- `project_root` - `path`; required
  - Scope: Business repository root to scan.

- `tier` - `enum`; required
  - Allowed values: `l0-tripwire`, `l1-scan`, `l2-study`.
  - Scope: Selects the proportional discovery depth.

- `targets` - `string[]`; optional
  - Scope: Files or directories the work order intends to touch. Used only for nearest-neighbor relevance; never to filter C1 candidates out of existence.

- `bridge_locations` - `string[]`; optional
  - Scope: Extra convention locations the project bridge explicitly declares, in addition to the tool-neutral families the scanner knows.

- `workbench_path` - `path`; optional
  - Scope: When supplied, the scanner and semantic read keep process files under its `tmp/`.

## Convention Authority Model

| Tier | Source | Nature | Binding force |
| --- | --- | --- | --- |
| C1 declared | The project bridge, `AGENTS.md` files up the tree, and other instruction files such as `CLAUDE.md`, `GEMINI.md`, `.cursor/rules/**`, `.cursorrules`, `.github/copilot-instructions.md`, and `CONTRIBUTING.md` | Rules a person explicitly wrote | Must be followed; a deviation must be recorded with its reason |
| C2 configured | `.editorconfig`, formatter/linter/type-check configuration, build manifests, and CI workflows | Facts a machine enforces | Followed as facts; used to choose verification commands |
| C3 de-facto | Patterns repeated in nearby code or docs but never declared | Inference, weak evidence | Not mandatory; referenced only when C1/C2 are silent, labeled as inference, and escalated on conflict |

Higher authority wins on conflict. A same-level conflict or genuine ambiguity is a main-session user gate in managed work and a direct question on the direct path; never silently pick one side.

## Tiers

### L0 — direct-path tripwire

Used after governance returns `direct`, before the first substantive action. Read the bridge and inspect only the smallest locality: instruction files on the target path and one or two neighboring files. The purpose is not complete discovery but a tripwire. A non-trivial declared convention set, a conflict, multiple governance sources, or evidence the task is not truly local means the six-fact vector no longer supports direct execution; re-classify through `xc-work` and escalate to managed.

### L1 — mandatory managed floor

Runs inside preparation for every managed mutation, on both `run` and `adaptive-run`, at the same point the report baseline is captured. It adds no node or group and is independent of the analysis capability, so proportional pruning of analysis cannot remove it.

Two layers are deliberately separated:

1. Run `scripts/scan_conventions.py`, a deterministic, read-only enumeration. It answers only "which candidates exist, at what authority tier, how near the targets, and whether readable", honoring `.gitignore`, declared bridge locations, and a file/time budget.
2. Read the applicable C1 files and extract the rules relevant to this work order; read C2 as facts; produce one compact `convention-discovery` record: applicable files with reasons, relevant rules/commands/format requirements, conflicts, and scan boundaries.

A record is mandatory even when the result is "no applicable convention"; the terminal status `not-applicable` is the legal, required way to say the check ran. A scanner failure is `scan-unavailable`, never "no conventions"; the work fails closed by escalating or blocking rather than proceeding undiscovered. The short status and the record path are published to the blackboard; the long record is an artifact, never blackboard content. The record is routed into `xc-implementation` and `xc-verification` inputs.

### L2 — deep study

Selected by confirmed facts (cross-cutting scope, high risk, uncertain clarity, a review/approval bridge policy) or by L1 evidence (conflict, ambiguity, multiple governance sources, an unusually large convention set). It reuses the existing `xc-analysis` capability, preferably with `analysis_scope=convention-review`, for deep reading, reconciliation, and mapping rules to the solution and acceptance. `pace=fast` may trim optional L2 depth but never removes L1.

## Mechanical / Semantic Boundary

The script only enumerates and classifies candidates; it never parses natural-language rule semantics. Applicability and how much of a file to read are agent judgments. Tool-neutral, ecosystem-wide instruction-file families and the discovery method (nearest-neighbor, climb the directory tree, read bridge-named locations, respect `.gitignore` and the budget) belong in the generic core; consumer language or framework specific signal files are declared by the project bridge, not hard-coded here.

`xc-conventions` discovers local project conventions only. When `.xcoding/KNOWLEDGE.md` declares a knowledge source that holds conventions, the main session obtains that material through the public `xc-knowledge` boundary; this Skill does not connect to a knowledge base or read another Skill's private references.

## Constraints

- Generic assets stay English, tool-neutral, and free of consumer paths, commands, frameworks, and business rules.
- Do not drop a C1 candidate merely because a relevance heuristic rates it distant; heuristics are hints, not filters.
- Do not treat a C3 de-facto pattern as mandatory and do not silently apply it over a C1/C2 rule.
- A bridge may tighten discovery, declare extra locations, and set scan boundaries or exclusions; it cannot declare an applicable C1 rule unreadable.
- Temporary and process files belong under the active workbench `tmp/`; the discovery record is the declared artifact.
