# Coverage Protocol

Normative protocol for the coverage manifest, the enumeration algorithm, the baseline, the
exclusion rules, staleness, the refresh edge and the validator.

**The coverage proof belongs to the work order's author alone.** `units_total` is not "how
much the worktree changed"; it is "how much this work order changed". Edits that were already
in the worktree when the work order opened are classified as pre-existing, recorded with their
ranges and hashes, and never turned into units.

## Change set: the enumeration algorithm

The change set is defined by four values, all recorded in the manifest: the baseline, the
head, the enumeration algorithm and the exclusion rules. Any third party can recompute the
same change set on the same repository.

**C29** The algorithm is fixed and does **not** rely on `git diff <baseline_commit>` alone:
that command compares tracked paths only and never reports untracked files, so a whole class of
changes (new files, the most common thing a work order does) would disappear from the proof.
The six steps run in this order:

1. **Enumerate tracked paths.** `git diff --no-renames --name-status -z <baseline_commit> --`.
   `--no-renames` is passed explicitly: git enables rename detection by default, so without it
   the same edit is grouped as a rename on one machine and as delete+add on another, and the
   proof stops being recomputable.
2. **Enumerate untracked paths.** `git ls-files --others --exclude-standard -z`. `.gitignore`
   is never modified and `git add -N` is never used: both would change the user's worktree
   view.
3. **Merge into a path set.** For every path, compare the baseline-side content with the
   head-side content: absent to present is `added`, present to absent is `deleted`, present to
   present with different bytes is `modified`, and equal content is dropped. Exactly equal
   content between a deletion and an addition is paired into a `renamed` entry (C11). Paths
   captured in the baseline untracked snapshot are candidates too, otherwise a file that was
   never tracked and is now gone would be invisible (C4a).
4. **Read content per path.** The baseline side is `git show <baseline_commit>:<path>` for
   tracked paths and the C4a snapshot bytes for paths that were untracked at that time. The
   head side is the worktree file. A missing side is empty content. Both sides are raw bytes.
5. **Pair renames and cut units.** Content hashes pair deletions with additions (C11); hunks
   come from `git diff --no-renames --no-color --diff-algorithm=myers --unified=3
   <baseline_commit> -- <path>` so the grouping matches git's own hunk grouping. The explicit
   algorithm and context values make the grouping independent of the user's `diff.algorithm`
   and `diff.context` configuration; the exact command is recorded in the manifest. Added and
   deleted paths are whole-file units, windowed by C31. Paths that were untracked at baseline
   use `git diff --no-index --no-color --diff-algorithm=myers --unified=3 -- <before> <after>`
   because they have no commit-side hunk.
6. **Sort and index.** Paths sort by UTF-8 byte order, units inside a path by line range, and
   the global `unit_index` is assigned afterwards. The rules are fixed, so two runs over the
   same repository state produce the same manifest.

- **C30** The algorithm is versioned: the manifest records
  `enumeration.version = "xc-change-report/enumeration/v1"`. The same version on the same
  repository state must produce a byte-identical manifest.
- **C31** A large added file never becomes one unanalysable block:
  - at most `MAX_ADDED_UNIT_LINES = 400` lines: the whole file is one unit;
  - above that: consecutive blocks of `ADDED_UNIT_BLOCK_LINES = 200` lines, no re-flowing
    across blank lines, no merging of adjacent blocks. The cut points are a built-in rule, not
    a model decision;
  - deleted files are windowed the same way;
  - every block is its own unit with its own anchor and its own A1-A8 analysis.
  An exact-content rename (C11) stays exactly one unit even when it is large, because the
  contract analyses the move as a single fact; a large renamed file therefore yields one large
  unit. This is the accepted cost of "one rename, one unit".
- **C32** Each change kind is its own `files[]` entry; one entry is one path and the units
  (`hunks[]`) belong to it.
- **C33** A newly created Skill's own files are not on the exclusion side:
  `skills/xc-change-report/**` and `tests/fixtures/change_report/**` match no exclusion
  category and are analysed as `added` units like any other deliverable.

## Baseline and authorship

- **C1** The baseline is recorded **once**, when the work order opens: the branch commit
  (`baseline.commit`), a digest of the tracked paths as they existed in the worktree
  (`baseline.worktree_digest`) and the digest algorithm name. It is never rewritten later.
- **C2** The head is the worktree state at manifest time, including uncommitted edits. The
  report must describe the code that is actually delivered, and that code may exist before any
  commit does.
- **C3** The change set means "every difference from the baseline content, committed or not".
  The implementation is the filesystem enumeration plus per-file baseline comparison; a git
  diff is one means of obtaining hunk grouping, not the definition of the change set.
- **C4** The baseline must be recomputable by a third party. The digest is

  ```text
  sha256 over: for each tracked path in UTF-8 byte order:
      "<relative-path>" + 0x00 + "<sha256 of the file bytes>" + "\n"
  algorithm name: sha256(path-nul-contenthash-lf/v1)
  ```

  Recompute it with the baseline worktree checked out, or with the recorded snapshot
  directory. `baseline.commit` must be a resolvable commit id.
- **C4a** Baseline content for paths that were untracked at open time is kept under
  `<workbench>/tmp/baseline-untracked/`, mirrored by relative path, with the directory, file
  count and digest algorithm recorded in `baseline.untracked_snapshot`. `tmp/` is neither an
  artefact nor a managed path of the workshop repository: record its location and reason, and
  verify its removal; do not write it into the project repository and do not change
  `.gitignore` for it. When the directory is missing, recomputation involving untracked paths
  degrades to "not recomputable" and the generated `analyzable` decision stays valid, but the
  review must see the degradation note.
- **C5** The baseline is written by the work order's preparation step into
  `work_order.report_baseline`. A late baseline lets earlier implementation edits escape the
  change set.
- **C37** Authorship is decided deterministically. For each tracked path let `O` be the
  baseline commit content, `B` the content on disk when the work order opened and `H` the head
  content:
  1. write `O`, `B` and `H` as temporary files under `<workbench>/tmp/`;
  2. `git diff --no-index --no-color -U0 -- O B` gives the baseline-side line ranges,
     `git diff --no-index --no-color -U0 -- B H` gives the work-order-side line ranges;
  3. map the baseline-side ranges into head line numbers and intersect them with the work
     order's ranges. Work-order-only ranges get `provenance=work_order`; pre-existing-only
     ranges get `provenance=pre_existing` with `exclude_reason=pre_existing_change` and never
     enter `units_total`; ranges covered by both get `provenance=work_order` plus
     `overlaps_pre_existing=true`;
  4. the overlap rule is fixed and conservative: the whole overlapping stretch belongs to the
     work order, because the work order touched it. Deciding who wrote a line first needs
     history, which this protocol does not consult; the flag exposes the uncertainty instead;
  5. when alignment is impossible (binary content, decode failure, an unavailable diff) the
     whole file is treated as `analyzed_as=pre_existing` with the reason recorded. This is the
     fail-closed direction: a change is excluded and annotated rather than attributed to the
     author who must then explain it.
- **C38** Pre-existing work is recorded at both levels:
  - path level: `files[].analyzed_as in {work_order, pre_existing, mixed}`, derived from the
    hunks under the path;
  - hunk level: `hunks[].provenance in {work_order, pre_existing}`,
    `hunks[].exclude_reason` (`pre_existing_change`) and `hunks[].overlaps_pre_existing`.
  Pre-existing hunks keep their ranges and content hashes so the classification itself is
  recomputable, but they are excluded and carry `unit_index: null` and `anchor: ""`, which
  keeps the unit numbering contiguous from 1. `pre_existing_total` counts them,
  `pre_existing_files` lists the affected paths, and both appear in the report's exclusion
  table. A path with both kinds of hunk becomes `mixed` and the report states that the file had
  already been edited when the work order opened.

## Manifest format

- **C6** The manifest is generated by `scripts/build_manifest.py` from a real worktree and a
  real baseline. Top-level fields: `schema_version`, `work_order_id`, `enumeration{version}`,
  `baseline{kind,commit,worktree_digest,algorithm,captured_at,worktree_snapshot,
  untracked_snapshot}`, `head{kind,digest,algorithm}`, `generated_at`, `files[]`,
  `units_total`, `excluded_total`, `pre_existing_total`, `pre_existing_files[]`. The
  implementation also records `enumeration.commands`, `enumeration.environment`,
  `strength`, `run_required`, `redacted_units`, `degradations` and
  `normalization`, which V1 tolerates and the report reads.
- **C6a** One counting vocabulary, fixed meanings:
  - `units_total` = the number of analysable change units, i.e. hunks with `excluded=false`.
    One unit is one `unit_index` and one `#unit-<unit_index>` section.
  - `excluded_total` = the number of excluded **paths**, i.e. `files[]` entries with
    `analyzable=false`. Names are never mixed: this is not a unit count and never takes part in
    a subtraction.
  - `pre_existing_total` = the number of excluded pre-existing **hunks**;
    `pre_existing_files` = the affected paths.
  - An excluded path has `hunks: []`, so no unit ever disappears because its file was
    excluded, and the coverage equation subtracts nothing.
  - The two equations are therefore **change-map rows = `units_total`** (H17) and
    **exclusion-table rows = `excluded_total` + `pre_existing_total`**, each labelled by
    category (H18, V5).
- **C7** Each `files[]` entry has `path`, `change_kind in {added,modified,deleted,renamed}`,
  `renamed_from` (renames only), `analyzable`, `exclude_reason` (required when excluded),
  `analyzed_as`, `source_sha256` (raw bytes of the head content, also for excluded paths so the
  exclusion itself is recomputable), and `hunks[]`. The implementation adds
  `baseline_sha256`, `origin_sha256`, `encoding_unsupported`, `baseline_source`,
  `provenance_degraded` and `sensitive_path_pattern`.
- **C8** Each `hunks[]` entry has `unit_index` (globally monotonic, starting at 1 and
  contiguous across files), `old_range`, `new_range`, `content_sha256` (normalised per H26a),
  `anchor` (`#unit-<unit_index>`), `provenance`, `overlaps_pre_existing`, `excluded` and
  `exclude_reason`. Ranges are objects `{"start": N, "end": M}` where `end < start` marks an
  empty range. The implementation adds `content_side`, `changed_new_lines`,
  `changed_old_lines`, `presentation`, `redacted`, `redacted_line_count`, `line_count` and the
  formatted `old_anchor_range` / `new_anchor_range` used by the change map.
- **C9** Content addressing: every unit records a content hash, not just line numbers. Change
  the code and the hash stops matching, so the proof fails detectably.
- **C10** The manifest fixes the anchors and the report must use the same names. The binding is
  one-way, and neither side may improvise.
- **C10a** The `units_total` in the receipt must equal the number of sections the validator
  actually counts in the HTML. When they differ, the validator's count wins and the run fails,
  which rules out a manifest and a page that agree only with each other.

## Rename, deletion, addition, unanalysable files

- **C11** Renames are decoupled from git's rename detection and match only exact content
  hashes:
  1. enumeration always passes `--no-renames`, so no similarity heuristic takes part;
  2. the script pairs a `deleted` path with an `added` path whose content hashes are exactly
     equal, producing one `renamed` entry with the new path and `renamed_from`;
  3. a rename whose content also changed does not satisfy equality and stays a `deleted` entry
     plus an `added` entry. This is a deterministic outcome with no similarity threshold;
  4. exact-hash pairing needs no threshold parameter and is therefore recomputable, which is
     exactly why a similarity threshold was rejected.
- **C12** Deleted units must be analysed, with the negative diff as their content. Deletions
  are where coverage gaps hide most easily, so "the code is gone" is never a reason to skip
  one. Over the C31 window they are split by the same rule.
- **C13** Added units carry all added lines and are analysed under A12. Over the C31 window
  they are split, so no added file is too large to analyse.
- **C14** Binary files are marked `analyzable=false` with `exclude_reason=binary`, counted in
  `excluded_total` and listed in the exclusion table. Detection is a NUL byte in the first
  8192 bytes.
- **C15** The exclusion categories are a closed enumeration: `generated`, `lockfile`,
  `vendor`, `binary`, `minified`, `sensitive`, `encoding_unsupported`, `pre_existing_change`.
  Adding a category requires changing this contract first; an implementation never invents a
  value.
- **C16** Exclusion hides no gap: excluded paths stay in `files[]`, count towards
  `excluded_total`, and appear in the exclusion table with path, category and reason;
  pre-existing entries count towards `pre_existing_total` and `pre_existing_files` and are
  listed the same way.
- **C17** Exclusion decisions are deterministic and recomputable, taken from path patterns or
  `.gitattributes` semantics, never from a per-run judgement by the model. The built-in tables
  are:
  - `GENERATED_PATTERNS`: `*.pb.go`, `*_pb2.py`, `*_pb2_grpc.py`, `*.generated.*`, `*.gen.*`,
    `*.designer.cs`, `*.g.cs`, `*.g.dart`, `generated/*`, `*/generated/*`,
    `__generated__/*`, `*/__generated__/*`;
  - `LOCKFILE_NAMES`: `package-lock.json`, `npm-shrinkwrap.json`, `yarn.lock`,
    `pnpm-lock.yaml`, `poetry.lock`, `Pipfile.lock`, `Cargo.lock`, `composer.lock`,
    `Gemfile.lock`, `go.sum`, `uv.lock`;
  - `VENDOR_PATTERNS`: `vendor/*`, `*/vendor/*`, `node_modules/*`, `*/node_modules/*`,
    `third_party/*`, `*/third_party/*`;
  - `MINIFIED_PATTERNS`: `*.min.js`, `*.min.css`, `*.min.mjs`, `*.min.*`.
  Matching is case-insensitive and uses case-folding comparison, so the result does not depend
  on the host filesystem's case rules. Classification order is fixed:
  binary, sensitive, generated, lockfile, vendor, minified, encoding-degraded.
- **C18** `units_total == 0` means zero analysable change units and is recorded as a skip
  reason. The equation has no subtraction: excluded files were never part of `units_total`.

## Sensitive and non-decodable content

- **C34** Sensitive exclusion is fail-closed. A path is marked `analyzable=false` with
  `exclude_reason=sensitive` when any of these holds:
  1. a file-name segment matches the built-in credential pattern table: `.env`, `.env.*`,
     `*.pem`, `*.key`, `*.p12`, `*.pfx`, `*.jks`, `*.keystore`, `id_rsa*`, `id_ed25519*`,
     `*.kdbx`, `credentials*`, `secrets*`, `*secret*.json`, `.npmrc`, `.pypirc`, `.netrc`,
     `*_rsa`, `*service-account*.json`;
  2. `.gitattributes` marks the path `export-ignore` **and** the path also matches the
     credential table (in practice rule 1 already covers this combination);
  3. the head content matches one of the built-in high-confidence secret shapes:
     a PEM private-key header, a GitHub `ghp_` or `github_pat_` prefix, an AWS `AKIA`
     prefix, or a Slack `xox[baprs]-` prefix.
  A hit means exclusion; the model never decides that something "does not look sensitive".
- **C35** Redaction is the explicit exception to H26's verbatim rule. A sensitive path is
  excluded whole and its text never appears in the report; the report may state the path, the
  category and why it was excluded. When an analysable unit would otherwise print a
  secret-shaped line - typically a removed line that is part of the diff while the head content
  is already clean - the script replaces that line with the fixed marker
  `<<redacted:sha256=<first-12-hex-of-the-line-hash>>>` and annotates the unit and the report
  information section. The hash is taken over the original line, so the structure stays
  recomputable and the text does not. Redaction is never silent.
- **C36** Non-decodable content degrades honestly:
  - strict UTF-8 decoding succeeds: normal processing; `content_sha256` is the normalised
    UTF-8 text hash and `files[].source_sha256` is the raw byte hash;
  - strict decoding fails: decode with `errors="replace"`, still generate the units, take
    `content_sha256` over the replaced text (so H26a and V10 keep working), set
    `files[].encoding_unsupported=true`, keep `source_sha256` over the raw bytes, and annotate
    the unit visibly as "this file is not valid UTF-8, the quoted text contains replacement
    characters";
  - when a replaced decode leaves no usable text at all, the path is excluded with
    `exclude_reason=encoding_unsupported`; a file that cannot yield meaningful text at all is
    `binary`.
  Decoding is never guessed and no charset sniffing is performed: only the success or failure
  of a strict UTF-8 decode decides.
  Justification for the ordering: C34's content rule scans the head content, so a file whose
  current content holds a secret is excluded whole; C35 then covers the residual case of a
  secret that only survives in the baseline side of a diff, which the whole-file rule cannot
  see.

## Validator and fail-closed checks

`scripts/validate_report.py` runs every check; any failure fails the whole run. The receipt is
the normalised form of the result.

- **V1 Manifest is trustworthy**: parseable, matching `schema_version`, matching
  `enumeration.version`, matching `work_order_id`, complete `baseline` and `head` fields,
  `units_total` equal to the number of `analyzable` hunks, `excluded_total` equal to the number
  of `analyzable=false` entries, `pre_existing_total` equal to the number of pre-existing
  hunks, contiguous `unit_index` from 1 with matching anchors, empty `hunks[]` on excluded
  paths, and `excluded=true` on every pre-existing hunk - a pre-existing hunk that claims
  `excluded=false` is a field defect and fails V1 there rather than surfacing later as a
  missing recomputation code block at V10.
- **V2 Coverage is complete**: every `analyzable=true` unit anchor exists in the HTML and is
  named by some `data-covers` set.
- **V3 Nothing out of scope**: the page contains no change section and no `data-covers` anchor
  outside the manifest.
- **V4 Analysis has substance**: all eight fields exist per unit section, are non-empty, meet
  the A13 threshold and carry no placeholder. V4 guarantees non-blank text only; it does not
  guarantee that the text is correct or even related to the code - V10 and V11 do that.
- **V5 Structure is compliant**: the nine sections exist in order, the change map has
  `units_total` body rows with six columns and a non-empty code location, the exclusion table
  has `excluded_total + pre_existing_total` body rows with valid categories, no template
  placeholder survives, the `<meta>` declarations are present and the declared manifest hash
  matches, the report information section states the baseline commit, and the first round
  record has `refresh_reason=initial`.
- **V6 Links and anchors**: every in-page link resolves, the table of contents has no dangling
  entry and uses native `<details>`, and every unit section has previous/next navigation.
- **V7 Offline self-containment**: the H33 enumeration is empty; URL text is checked with the
  H37a element-interval exclusion; no logical `<script>` block exists (H36 predicate).
- **V8 Diagrams are compliant**: each specification's type is supported, referenced nodes
  exist, the render mode matches the type, the figure equals a re-render of its own spec,
  `svg` diagrams satisfy D14-D17 (canvas caps, font floor, integer grid, text cap, truncation
  titles, golden fixture when one is supplied) and `table` diagrams have a structured carrier
  within the cell-length cap.
- **V9 Not stale**: the head digest declared by the report equals the digest recomputed from
  the worktree. Failure is a refresh edge, not a node failure.
- **V10 Analysis is bound to code (hash)**: for every unit, the text recovered from its
  `data-unit` code block by the H26a normalisation hashes to the manifest's
  `content_sha256`. A mismatch reports the unit number, the expected hash and the recomputed
  hash.
- **V11 Analysis is bound to code (tokens)**: at least one code token of the unit's diff
  appears in the analysis prose. Tokens are identifiers of four or more characters from the
  unit's changed lines, backtick-quoted fragments in that code, and path fragments (full path,
  file name, stem and path segments of four or more characters). Zero hits fail and the
  available token set is printed as a repair hint. The rule makes "paste one generic paragraph
  into every unit" fail; it does not judge whether the text is right.
- **V12 Gate routing and the refresh latch**: the declared gate outcomes are exactly
  `accepted`, `revision-required`, `rejected`, `accepted-with-followup`; where the spec declares
  value-by-value routes, they correspond one to one with the declaration (no orphan value, no
  undeclared route); where it routes through the two derived booleans instead, both keys must
  be published; the rework group is driven by a single boolean gate key and never by the
  outcome string, so `accepted-with-followup` cannot enter it; both loops declare
  `max_iterations=3` and `on_limit=failed` with their exact continue conditions and a main
  session owner; and where the spec declares its latch publishers, every terminating path
  publishes the rework key exactly once and resets it exactly once.
- **V13 Redaction and degradation are visible**: a path matching a C34 credential pattern must
  be excluded as `sensitive` and none of its content may appear in the report; a redacted unit
  must carry the marker; a file with `encoding_unsupported=true` must have a unit that
  announces the degradation.
- **V14 Accuracy verdicts**: `change-report-verdicts.json` exists and parses, has a matching
  `schema_version`, covers exactly the analysable units (no more, no fewer), uses only
  `accurate`, `misleading` or `wrong`, gives a non-empty reason for every `wrong` and
  `misleading` verdict, has at most `MAX_WRONG = 0` wrong and at most `MAX_MISLEADING = 0`
  misleading verdicts, and agrees with the blackboard's `report.accuracy_open_issues`. V14 runs
  at the **final** stage, not at coverage time: the coverage step runs before the review loop,
  when the verdict file does not exist yet.

Failure behaviour is uniform: a failed check fails the node and is never downgraded to a
warning. The single exception is staleness, which is an edge back to the refresh entry point.

## Failure mode table

| Failure mode | Detector | Reported as |
|---|---|---|
| A change has no analysis in the report | V2 | the missing anchors |
| The report has change sections outside the manifest | V3 | the out-of-scope anchors |
| An analysis field is missing, placeholder or below the floor | V4 | the field and the reason |
| The analysis is filler that is unrelated to the cited code | V11 | the available token set and "zero hits" |
| The code block was swapped for another unit's diff | V10 | unit number, expected and recomputed hash |
| A section is missing or misordered, or a table row count is wrong | V5 | measured and expected values |
| A table-of-contents entry or in-page link dangles | V6 | the dangling anchor |
| An external resource, embedding element or logical script appears | V7 | the position and the enumeration item |
| URL text is excused outside a code block | V7 | the failure stands when the match is outside the exclusion zone |
| A diagram type is unsupported, the render mode mismatches, geometry is out of range, or a golden fixture differs | V8 | the diagram id and the reason; no guessing, no downgrade |
| The report is stale | V9 | declared and measured digests; routed to the refresh edge |
| A gate outcome is declared without a route, or routed without being declared | V12 | declared and routed sets |
| A secret reaches the report | V13 | the path and the matched pattern |
| Non-UTF-8 content is silently turned into mojibake | V13 | the paths missing their degradation note |
| The manifest is corrupt or belongs to another work order | V1 | the field-level reason |
| The analysis contradicts the code while hash and tokens match | accuracy review worker (judgement, not proof) | the unit anchors and code locations; the revision loop |
| The reviewer judges wrongly | no mechanical detector | only a human gate or a later review can find it |
| Granularity is wrong but the text is about the right unit | V11 gives only a warning-level signal | token intersection stops unrelated text, not "right tokens, wrong conclusion" |

The last two rows are the honestly admitted limits of this mechanism. Neither Skill text nor
report may describe them as covered. V10 and V11 raise the mechanical floor from "nothing" to
"binding exists and the content corresponds"; they do not turn "the explanation is correct"
into a mechanical decision.

## Three failure states, all visible

1. **Generation failure**: the script errors; the node fails.
2. **Validation failure**: the node fails, and is never downgraded to a warning. The one
   exception is staleness, which is an edge back to the refresh entry point; the edge itself is
   bounded by `max_iterations` and `on_limit`, and exhaustion is still a node failure.
3. **Wrong analysis content**: hash and tokens both match and the explanation is false. The
   accuracy review worker carries this first, with the optional human gate as a second layer.
   The gate is closed by default, so on the default path only the worker carries it, and a
   worker that judges wrongly still has no mechanical detector.

## The code changed after generation

- **C19** Staleness is content-addressed: any change to a covered path changes the head digest
  and V9 fails immediately. A report that says "current" while the content says otherwise has
  exactly one handling: failure.
- **C19a** Staleness routes to a refresh, not to a block:
  1. the owner is the main session;
  2. the node sequence is `prepare-manifest`, `author-report`, `validate-coverage`,
     `report-gate`, `validate-final`; a refresh adds no node type, no document and no report
     file;
  3. before entering the refresh round: increment `report.round`; when the round was caused by
     code rework (`refresh_reason in {rework_rejected, review_driven_repair}`) also increment
     `report.refresh_count`; write this round's `report.refresh_reason`;
     `report.gate_rework_required` is reset by the rework group, never by hand;
  4. the outer loop declares `max_iterations=3` and `on_limit=failed`. Exhaustion blocks the
     work order and reports "three refresh rounds did not pass validation" rather than retrying
     forever or quietly passing;
  5. a rework-driven refresh carries its cause:
     `report.refresh_reason in {rework_rejected, rework_revision_required, stale_head,
     review_driven_repair}`, written into the round records.
- **C20** After a failure, regenerate the manifest and rewrite the affected sections, then
  validate again. The prose is not rewritten wholesale and no second report file is appended:
  "targeted rewrite" means the text layer only, while the skeleton and every mechanical part are
  rebuilt in full (C22).
- **C21** The report carries a round record section listing, per round, the round number, the
  refresh reason, the change scope, the manifest hash, the refresh time and the sections added
  or changed. The first round is recorded too (`refresh_reason=initial`), so "only one round
  ran" and "a round record was lost" stay distinguishable.
- **C22** Every refresh regenerates the same file in full. Incremental append was rejected
  because it needs a cross-round diff ledger that the runtime does not have, and because it
  would give the coverage proof two sources of truth, leaving the validator unable to say which
  analysis is current.
- **C23** One work order has one report. History lives in that report's round records, not in
  historical files, so there are no cross-links between historical reports to maintain.
- **C24** Cross-work-order continuity is pointer-based only: the result document gives the
  path of this work order's report, and the report itself accumulates nothing across work
  orders.
- **C24a** How a human finds and opens the report:
  1. the absolute path comes from engine return values and is written into the result
     document's report section as `报告：<absolute-path>` (or the work order language's
     equivalent label), together with the workbench path and the manifest's absolute path;
  2. it opens by double-clicking, in the system browser. No server, no network, no adjacent
     file (H3);
  3. the workbench is not inside the project repository, but this is not "two git
     repositories": the project repository ignores `.xcoding/` and the workshop content is
     carried by the context repository. The report must therefore give absolute paths and state
     which work order and which project repository it belongs to;
  4. the result document is the human entrance; the manifest path is the recomputer's
     entrance. Both live in the same section, and neither requires reading runtime state.
- **C24b** A change set spanning several work orders behaves as follows: one report covers one
  work order's change set, and no delivery-level aggregate report is produced, because an
  aggregate would need a cross-work-order ledger and the runtime's single authoritative
  progress state is per work order. Each work order proves its own coverage through its own
  `units_total`; the result document lists the other reports of the same delivery and states
  that coverage is proven per work order; a human answering "what did this delivery change"
  opens the listed reports in turn.

## Honest boundaries

- **C25** The `--check-result-json` receipt is an untrusted caller self-report. The runtime
  accepts a structurally matching receipt even if its content is fabricated; it is unsigned and
  has no source verification. **Every fact value in the receipt is a string** (`"7"`, `"true"`)
  because the runtime compares facts against blackboard values as exact text; a number or a
  boolean there fails node completion with `check_fact_mismatch`.
- **C26** The real strength of the proof is the recomputability of V1-V14: any third party can
  rerun the same validator against the same worktree, baseline and HTML and reach the same
  conclusion without trusting the model that produced them. V10 and V11 raise "analysis exists"
  to "analysis is bound to the code it cites"; binding is still not correctness.
- **C27** The validator emits an independently checkable summary - unit, anchor, field presence
  and length, hash recomputation and token-hit count - instead of only an `ok`. The accuracy
  verdicts stay out of the receipt and live in `change-report-verdicts.json`, recomputed by V14
  at the final stage. Receipt shape:

  ```json
  {"schema_version":1,"check":"xc-change-report","ok":true,"subject":"<normalized-path>",
   "facts":{"units_total":"7","units_covered":"7","excluded_total":"2",
            "pre_existing_total":"1","hash_bound":"7","token_bound":"7",
            "coverage":"complete","self_contained":"true","head_current":"true",
            "strength":"standard","rounds":"1"}}
  ```

- **C28** The caller requires exit code 0, top-level `ok=true` and a valid receipt structure,
  and passes **only** the `.receipt` sub-object to `--check-result-json`.

## Orchestration contract (machine-readable forms)

The subtree specification is `assets/change-report-flow.json`, and
`assets/change-report-template.xml` is built from it by `template_builder.py`. Never
hand-write the XML.

- **O1** The refresh edge is the outer `report-pass-loop` (loop, main session,
  `role=report-pass`), continuing while `report.gate_rework_required == true`, with
  `max_iterations=3` and `on_limit=failed` (the runtime vocabulary for the design's
  `on_limit=fail`). The rework key has three publishers: `validate-final` on its stale path
  (true), `validate-final` on its success path (false), and the review loop on exit (false).
  Every terminating path of a round must publish the key once and reset it once.
- **O2** The gate declaration is exactly the four contract outcomes. Routing is either declared
  value by value in `metadata.gate.routes` (a JSON object mapping outcome to destination) or
  derived from the two boolean keys, because the runtime's condition syntax compares a single
  key and has no `||`. When routes are declared, V12 requires a one-to-one correspondence with
  the declaration.
- **O2a** Where a template wants the O1 latch pairing checked mechanically it declares, on the
  outer loop node,
  `metadata.rework_publishers = "[{\"node\":\"…\",\"publishes\":\"true|false\",\"terminates_round\":\"gate-rework|review-loop-exit|validate-final-stale\"}]"`.
  V12 enforces one `true` and one `false` per terminating path and rejects a fourth path; a
  specification that omits the declaration is reported as `latch_pairing: undeclared` rather
  than silently treated as satisfied.
- **O3** A code-rework segment must append the refresh sequence
  (`prepare-manifest`, `author-report`, `validate-coverage`) before returning to the gate; a
  rework segment without it is incomplete, because the covered paths changed and V9 will fail.
- **O4** `report.round` starts at 1 and is incremented by the loop; `report.refresh_count`
  starts at 0 and counts code-driven refreshes; `report.refresh_reason` is written on entering
  each round. The rework key is reset by nodes, never by hand.
- **O5** The inner `report-review-loop` (review, then revise while
  `report.accuracy_open_issues == true`) sits inside the outer loop body, so every refresh
  re-reviews the rewritten text. Both loops declare `max_iterations=3` and `on_limit=failed`.
- **O6** The gate sits inside the loop body, so it reopens on every round and the human always
  reads the refreshed report.
- **O7** Staleness is not a node failure: `validate-final` publishes the rework key and returns
  control to the next outer round. Its success path publishes the reset. Only loop exhaustion
  or a non-staleness validation failure fails the node.
- **O8** No configuration may skip `validate-coverage`, the review loop or `validate-final`.
  The gate may be closed; validation and the accuracy review may not. That distinction is the
  entire reason this stage can be trusted.
