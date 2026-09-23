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
  The window applies to **additions and deletions only**, and that limitation is the second
  recorded accepted cost: a modified path stays one unit over its whole changed region, so a
  900-line modification is one 863-line unit and the analysis obligation for a modified file is
  unbounded in the file's size. A unit ceiling for modified files was considered and rejected,
  because it would move `units_total` for every consumer that edits a large file in order to
  bound a case that is correct but large; what a reviewer gets instead is the unit's own
  `line_count` and its `new_anchor_range` in the manifest and the change map, so the size of the
  unit is visible before the analysis is read. `MAX_ADDED_UNIT_LINES`, `ADDED_UNIT_BLOCK_LINES`
  and `MAX_UNIT_LINES_SNIPPET` are recorded in the calibration record below.
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
  review must see the degradation note. The open-state record also carries `untracked_paths`, the
  **names** that were untracked at open, because a path that was untracked at open and has since
  left the worktree is otherwise in no candidate set at all: it is no longer untracked, no longer
  in the index, and the directory that held it may be gone, so `untracked_snapshot_path_lost:`
  can name it only if the record kept the name. That field is an addition to the record's schema
  and not a replacement of it: the thirteen core fields named above stay the required set, the
  three open-state facts stay optional, and a record that carries only the core set still loads
  and still verifies.
- **C4b** The **worktree snapshot** has a fixed path and a fixed content set. It lives at
  `<workbench>/tmp/baseline-worktree/` (the capture tool's `--baseline-worktree-dir` overrides the
  location, and the open-state record carries the location actually used), and it mirrors **every
  tracked path of `baseline.commit`**, by repository-relative path, holding that path's bytes as
  they were in the worktree when the work order opened, and nothing else. This directory is the
  recomputation source C4's "with the recorded snapshot directory" clause names: C4's digest is
  recomputable from that directory alone, without checking the commit out and without a second
  capture. The open-state record also carries `index_modes`, the index mode of every path at open.
  It is the only evidence that can separate a mode-only change made before the open from one made
  after it: the bytes are identical on all three sides, the baseline commit records only its own
  committed mode, and the executable bit lives in the index alone, so without the open mode a
  `mode_change` row is charged to the work order unconditionally and additionally carries
  `mode_provenance_unknown:`, whose presence is the honest statement that the evidence is missing.
  It carries `degradations` as well: a tracked or untracked path the capture could not open is
  skipped and **named** there instead of blocking the work order at open, and each such name is
  merged into the manifest's own degradation list so the review sees it.
  **These three fields are an addition to the record's schema, not a replacement of it**: the
  thirteen core fields stay the required set, a record that carries only them still loads and
  still verifies, and every one of the three exists because a defect could not be named without
  it.
  Availability is decided by **content, not by a directory test**. The manifest records
  `baseline.worktree_snapshot.state` as exactly one of four values, and
  `baseline.worktree_snapshot.available` is true only for `complete`:
  1. `absent` - the directory does not exist; degradation `baseline_worktree_snapshot_missing`,
     the state C4a already describes as "not recomputable";
  2. `empty` - the directory exists and holds no captured path; degradation
     `baseline_worktree_snapshot_empty`;
  3. `incomplete` - the directory exists and holds at least one tracked path but not all of them;
     degradation `baseline_worktree_snapshot_incomplete`;
  4. `complete` - the captured path set equals the tracked path set of `baseline.commit`; no
     degradation, `available: true`.
  `provenance_degraded` is true for the first three states and false for the fourth. A
  present-but-empty or present-but-incomplete directory is therefore a recorded degradation and
  never a silent success: it is what makes a pre-existing edit separable, so a capture that
  produced no files must not claim to have produced them.
  When a validator recomputes the C4 digest and cannot, because the worktree snapshot is in one
  of the three unavailable states, it emits the note `baseline_worktree_snapshot_unavailable` and
  does not fail the run; the note is a degradation of the proof, not a manifest field.
  The untracked directory keeps its own path, rule and string: `<workbench>/tmp/baseline-untracked/`
  and `baseline_untracked_snapshot_missing` (C4a). The two directories are never merged, and
  neither is a substitute for the other.
- **C5** The baseline is written by the work order's preparation step into
  `work_order.report_baseline`. A late baseline lets earlier implementation edits escape the
  change set. The capture tool is the producer: `scripts/capture_baseline.py` writes the open-state
  record, and its `--format keys` output is the publishable form of the three flat keys the report
  nodes read (`report.baseline_commit`, `report.baseline_digest`, `report.baseline_algorithm`).
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
     history, which this protocol does not consult; the flag exposes the uncertainty instead.
     The flag is also **counted**: the manifest records the top-level counter
     `overlapped_pre_existing_total`, equal to the number of hunks with `provenance=work_order`
     and `overlaps_pre_existing=true`. That counter is where the overlapped region enters the
     accounting, because the region itself stays attributed to the work order by this rule and
     `pre_existing_total` legitimately stays at 0 for it. The counter counts hunks that are
     already inside `units_total`, so it is never added to or subtracted from the two equations
     of C6a and never becomes an exclusion-table row;
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
  `units_total`, `excluded_total`, `pre_existing_total`, `pre_existing_files[]`,
  `overlapped_pre_existing_total`. The
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
  - `overlapped_pre_existing_total` = the number of analysable hunks that also intersect a
    pre-existing range (`provenance=work_order` with `overlaps_pre_existing=true`, C37.4). It
    counts hunks that are **inside** `units_total`, so it takes part in neither equation and is
    never an exclusion-table row; it is the recorded size of the region the conservative
    attribution rule charges to the work order.
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
- **C14a** A **symbolic link** (index mode `120000`) is analysed as the **link target text**. The
  content is read from the git objects - the index blob and, for the baseline side, the blob of
  `baseline.commit` - and never by opening the path, because opening it follows the link. The
  target is never followed: the target file's bytes are not the link's content, so a link that
  points outside the repository cannot quote outside content into a user-facing document, and a
  dangling link keeps its own text and is analysed normally instead of being dropped for having
  no reachable target. `files[].source_sha256` is therefore the hash of the link text, and a
  change that only retargets a link is a content change with its own unit.
- **C15** The exclusion categories are a closed enumeration: `generated`, `lockfile`,
  `vendor`, `binary`, `minified`, `sensitive`, `encoding_unsupported`, `mode_change`,
  `submodule`, `adapter_install`, `pre_existing_change`.
  Adding a category requires changing this contract first; an implementation never invents a
  value. Three of the eleven describe a path whose **shape**, not whose text, is the change, and
  each of them exists because the alternative is an invisible deliverable change:
  - `mode_change` - the index mode changed while the bytes did not, for example `100644` to
    `100755`. The path stays in `files[]` with `exclude_reason=mode_change`, `hunks: []` and its
    two content hashes, so the report's exclusion table states that a delivered file became
    executable instead of saying nothing about it.
  - `submodule` - the index mode is `160000`, so the path is a gitlink whose recorded content is
    a commit id rather than analysable text. It is reported the same way, because a moved
    submodule pointer is a change a human reads.
  - `adapter_install` - the path lies under a host-adapter or installed-Skill root, matched by
    the `ADAPTER_INSTALL_PATTERNS` table C17 declares. `xcoding setup --project-root --host`
    installs packaged Skill resources and host-adapter definitions into those roots and
    `xc-workflow-evolution`'s installer copies `xc-*` packages into a consumer asset root;
    no lifecycle node owns those writes, so no work order can report them. Declaring the roots
    as an exclusion is the closure: the path still appears in `files[]` with the category and the
    reason, so the report states that the installer wrote under the project root rather than
    silently dropping it.
- **C16** Exclusion hides no gap: excluded paths stay in `files[]`, count towards
  `excluded_total`, and appear in the exclusion table with path, category and reason;
  pre-existing entries count towards `pre_existing_total` and `pre_existing_files` and are
  listed the same way.
- **C17** Exclusion decisions are deterministic and recomputable, taken from path patterns, the
  index mode (`git ls-files -s`) or `.gitattributes` semantics, never from a per-run judgement by
  the model. The built-in tables are:
  - `GENERATED_PATTERNS`: `*.pb.go`, `*_pb2.py`, `*_pb2_grpc.py`, `*.generated.*`, `*.gen.*`,
    `*.designer.cs`, `*.g.cs`, `*.g.dart`, `generated/*`, `*/generated/*`,
    `__generated__/*`, `*/__generated__/*`;
  - `LOCKFILE_NAMES`: `package-lock.json`, `npm-shrinkwrap.json`, `yarn.lock`,
    `pnpm-lock.yaml`, `poetry.lock`, `Pipfile.lock`, `Cargo.lock`, `composer.lock`,
    `Gemfile.lock`, `go.sum`, `uv.lock`;
  - `VENDOR_PATTERNS`: `vendor/*`, `*/vendor/*`, `node_modules/*`, `*/node_modules/*`,
    `third_party/*`, `*/third_party/*`;
  - `MINIFIED_PATTERNS`: `*.min.js`, `*.min.css`, `*.min.mjs`, `*.min.*`;
  - `ADAPTER_INSTALL_PATTERNS`: `.claude/*`, `*/.claude/*`, `.codex/*`, `*/.codex/*`,
    `.opencode/*`, `*/.opencode/*`, `.trae/*`, `*/.trae/*`, `.agents/*`, `*/.agents/*`.
  Matching is case-insensitive and uses case-folding comparison, so the result does not depend
  on the host filesystem's case rules. Classification order is fixed:
  binary, sensitive, mode_change, submodule, adapter_install, generated, lockfile, vendor,
  minified, encoding-degraded. The two index-mode categories are read from the index itself
  (`git ls-files -s`) and are decided before any content or pattern category, so a `160000`
  gitlink is never handed to a text reader and an executable-bit change is never dropped for
  having equal bytes. `.gitattributes` remains a source only for the C34 rule; no pattern table
  is read from the worktree.
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
the normalised form of the result. V1-V13, V15 and V16 run at both stages; V14 is the only check
that belongs to the final stage alone, because the verdict file it reads does not exist yet at
coverage time.

- **V1 Manifest is trustworthy**: parseable, matching `schema_version`, matching
  `enumeration.version`, matching `work_order_id`, complete `baseline` and `head` fields,
  `units_total` equal to the number of `analyzable` hunks, `excluded_total` equal to the number
  of `analyzable=false` entries, `pre_existing_total` equal to the number of pre-existing
  hunks, contiguous `unit_index` from 1 with matching anchors, empty `hunks[]` on excluded
  paths, and `excluded=true` on every pre-existing hunk - a pre-existing hunk that claims
  `excluded=false` is a field defect and fails V1 there rather than surfacing later as a
  missing recomputation code block at V10. V1 has three tiers, and the second and third are
  what make the baseline identity a claim rather than a shape:
  1. **presence** - the fields above exist and have the declared types, including
     `baseline.worktree_snapshot` as a required object;
  2. **content** - `baseline.worktree_digest`, `baseline.algorithm` and `baseline.captured_at`
     are present and non-empty, and `baseline.algorithm` equals `DIGEST_ALGORITHM`, the C4
     algorithm id `sha256(path-nul-contenthash-lf/v1)`. An empty digest or a corrupted algorithm
     spelling is a field defect, not a provenance claim a later check may assume;
  3. **consistency** - a declared `available: false` has a matching entry in `degradations`,
     and a declared `available: true` names a directory that exists, is non-empty and is in the
     C4b `complete` state. The two statements are about the same fact and must agree.
- **V2 Coverage is complete**: every `analyzable=true` unit anchor exists in the HTML and is
  named by some `data-covers` set.
- **V3 Nothing out of scope**: the page contains no change section and no `data-covers` anchor
  outside the manifest.
- **V4 Analysis has substance**: all eight fields exist per unit section, are non-empty, meet
  the A13 threshold and carry no placeholder. V4 guarantees non-blank text only; it does not
  guarantee that the text is correct or even related to the code - V10 and V11 do that.
- **V5 Structure is compliant**: the ten sections exist in order, the change map has
  `units_total` body rows with seven columns and a non-empty code location, the exclusion table
  has `excluded_total + pre_existing_total` body rows with valid categories, no template
  placeholder survives in the page's own text (the rule is scoped with the same H37a
  element-interval exclusion V7 uses for URL text, so a placeholder-shaped literal a unit
  quotes inside a code block is content and not residue - the builder's own residual guard
  draws the same line by reading the template rather than the page), the `<meta>` declarations
  are present and the declared manifest hash matches, the report information section states
  the baseline commit, and the first round record has `refresh_reason=initial`.
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
  the worktree. At `validate-final` the failure is a refresh edge, not a node failure (C19a.6);
  at `validate-coverage` the same finding fails that node, because no refresh has been
  validated yet at that point and the node is not a latch publisher.
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
  The repair hint is bounded: every check message is capped at
  `MAX_CHECK_MESSAGE_CHARS = 400` characters, and a message that would exceed the cap is
  truncated with the visible marker ` ...[truncated: message capped at 400 characters]`. The
  head that survives carries the check id, the unit number and the reason, so a degenerate
  240 001-character single-line unit produces a usable diagnostic instead of a 120 144-character
  wall of text in stdout and `--json-out`. The cap is a diagnostic bound, not an acceptance
  threshold: it never turns a failure into a pass and it gates nothing in the receipt.
- **V12 Gate routing and the refresh latch**: the declared gate outcomes are exactly
  `accepted`, `revision-required`, `rejected`, `accepted-with-followup`; where the spec declares
  value-by-value routes, they correspond one to one with the declaration (no orphan value, no
  undeclared route); where it routes through the two derived booleans instead, both keys must
  be published; the rework group is driven by a single boolean gate key and never by the
  outcome string, so `accepted-with-followup` cannot enter it; both loops declare
  `max_iterations=3` and `on_limit=blocked` with their exact continue conditions and a main
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
- **V15 Baseline content is recomputed**: recompute C4's digest from the recorded worktree
  snapshot directory with the same `digest_from_hashes` construction the builder uses
  (`sha256(path-nul-contenthash-lf/v1)` over the tracked path list of `baseline.commit`, hashing
  each path's recorded snapshot bytes), and compare it with `baseline.worktree_digest`. A
  mismatch is a failure and names both digests and the directory. When the snapshot is in one of
  C4b's three unavailable states the check reports `not_recomputable` with the reason
  `baseline_worktree_snapshot_unavailable`, the state, and that state's degradation string,
  instead of failing - which preserves C4a's semantics: a degraded capture is legal, and a
  validator that refused it would leave a work order whose snapshot was lost with no repair
  route. A snapshot that claims `available: true` while its directory is missing fails V15
  rather than degrading. V15 runs at both stages.
- **V16 Enumeration is complete**: recompute the enumeration independently of the manifest's own
  numbers, with `git diff --no-renames --name-status -z <baseline_commit> --`, `git ls-files -s`
  and `git ls-files --others --exclude-standard -z`, and fail when a path a source reports as
  *changed* is absent from `files[]` and no recorded-path degradation names it. The comparison is
  scoped to the genuinely comparable relation - every path changed `O -> H`, plus every index
  entry whose mode is not `100644`/`100755` that the baseline commit does not already record at
  that same mode and object, plus every path the untracked enumeration reports that is not already
  the open state's own content - and the failure text names the dropped path and
  the command that reported it. All three sources are relations of *change*, and
  C7's `files[]` is the change set: an index entry the baseline commit already holds at that
  same mode and object is not a dropped path, because nothing about it changed, so it owes no
  unit and no exclusion row, and an untracked path whose bytes the recorded
  `baseline.untracked_snapshot` already holds is not a dropped path either, because it was already
  there when the work order opened and the work order did not touch it. Without the change test
  the index source demanded a `files[]` row for a path the work order never touched and reported a
  complete manifest as incomplete (measured: a repository whose baseline commit carries an
  untouched mode-`120000` entry and whose only change is one ordinary tracked file). The
  **third source** is what makes the relation cover the whole change set rather than the two
  index/commit relations alone: a path that reaches the enumeration as an untracked file may leave
  `files[]` only when the manifest records it under one of the recorded-path reasons - a
  degradation that names it, `path_unreadable:` or `untracked_snapshot_path_lost:` - because such
  a path has no bytes to analyse and the recorded reason is the only place its absence can be
  read. A path no such reason names, including a path named by a note about some other path, is
  still a silent drop and still fails: without the third source such a path could leave `files[]`
  with no row, no exclusion and no degradation, and the run still reported `coverage=complete`
  (the measured F1 shape). The entries the scope leaves out are counted
  in the check's detail object as `unchanged_index_modes`, never silently skipped, and the paths
  the untracked source added, excused or found unchanged are reported there as `untracked_paths`,
  `recorded_unreadable` and `unchanged_untracked`. V16 is what
  makes the coverage equation independent: V5 compares `excluded_total + pre_existing_total`
  against the report's own exclusion table, and both numbers come from the same manifest, so
  without V16 the check that reads like completeness evidence would only be a consistency check.
  V16 runs at both stages.

Failure behaviour is uniform: a failed check fails the node and is never downgraded to a
warning. The single exception is staleness routed at `validate-final`, which is an edge back to
the refresh entry point; the same finding at `validate-coverage` fails that node (C19a.6).

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
| The report is stale | V9 | declared and measured digests; routed to the refresh edge at `validate-final`; a node failure at `validate-coverage` |
| The baseline digest does not match the recorded snapshot | V15 | both digests and the snapshot directory |
| The recorded snapshot is unavailable, empty or incomplete | V15 plus the C4b degradation | the note `baseline_worktree_snapshot_unavailable` or the state's degradation string; never a silent pass |
| The baseline identity is empty or its algorithm is a corrupted spelling | V1 (content tier) | the field and the rejected value |
| A path one of the three independent git sources reports as *changed* is missing from `files[]` and no recorded-path degradation names it (`path_unreadable:` or `untracked_snapshot_path_lost:`); an index entry the baseline commit already records at that same mode and object is not a change and owes no row, and neither is an untracked path the recorded untracked snapshot already holds. The third source is the untracked enumeration `git ls-files --others --exclude-standard -z` | V16 | the dropped path and the command that reported it |
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

## Calibration record of the acceptance-gating constants

Every constant below gates acceptance, a tier selection or a unit boundary, and every value is a
**design-stage choice**: the repository holds no measured basis for any of them. This record is
the honest disposition acceptance condition 4 requires - each value with its retention reason,
the data classes that are missing, and the procedure a future calibration must follow. It is not
a claim that the values are calibrated.

| Constant | Declared value | Declared in | What it gates | Retention reason |
| --- | --- | --- | --- | --- |
| `MAX_WRONG` | `0` | `build_manifest.py` | V14's wrong-verdict ceiling and the review loop's stop condition | retained at the design value: no verdict corpus exists to justify a non-zero budget, and a wrong explanation is the failure mode the whole accuracy layer exists to catch |
| `MAX_MISLEADING` | `0` | `build_manifest.py` | V14's misleading-verdict ceiling and the review loop's stop condition | retained at the design value for the same reason; `misleading` and `wrong` share one rubric today, so no data separates them |
| `MAX_UNITS_MINIMAL` | `5` | `build_manifest.py` | the `minimal` strength tier's unit ceiling; exceeding it upgrades the tier to `standard` and writes `report.strength_upgrade_reason` | retained at the design value: the upgrade is a content-thickness decision, and no measured relation exists between unit count and the analysis a human needs |
| `MAX_ADDED_UNIT_LINES` | `400` | `build_manifest.py` | C31: the largest added or deleted file that stays one unit | retained at the design value; the window is a reading-size choice, not a measurement |
| `ADDED_UNIT_BLOCK_LINES` | `200` | `build_manifest.py` | C31: the block size a large added or deleted file is cut into | retained at the design value; the cut points are a built-in rule, so the number is a readability floor, not a model decision |
| `MAX_UNIT_LINES_SNIPPET` | `60` | `build_manifest.py` | H27: above this the unit uses the unified-diff presentation instead of the after-state snippet | retained at the design value; the alternative presentation is equally recomputable, so the constant trades page length against reading ease |
| `MIN_FIELD_CHARS` | `40` | `build_manifest.py` | A13: the minimum non-blank length of each of the eight analysis fields | retained at the design value; it prevents blanks and claims nothing about sufficiency |
| `PLACEHOLDER_TOKENS` | `9 tokens (todo, tbd, fixme, n/a, xxx, placeholder, lorem ipsum, 待补充, 待定)` | `build_manifest.py` | A13: a field made of, or containing, one of these standalone tokens fails | retained at the design value; the list covers the placeholder vocabulary observed in this repository, and the two Chinese entries keep the rule valid in a non-English document language |
| `SYMBOL_ONLY_RE` | `^[^\w]+$` | `build_manifest.py` | A13: a field with no word content fails | retained at the design value; it is the third floor of the same threshold |
| `VERDICTS` | `accurate, misleading, wrong` | `build_manifest.py` | V14's verdict vocabulary and the review worker's grade set | retained at the design value; three grades are the smallest set that separates "right" from "wrong" and "wrong in a way that misleads" |
| `report-pass-loop.loop.max_iterations` | `3` | `assets/change-report-flow.json` | C19a.4: the refresh pass bound, with `loop.on_limit = blocked` | retained at the design value; no round-count distribution has been measured, and exhaustion blocks the stage instead of looping. The terminal state was `failed` until a real work order was made un-completable by it: see C19a.4 |
| `report-review-loop.loop.max_iterations` | `3` | `assets/change-report-flow.json` | O5: the accuracy review bound, with `loop.on_limit = blocked` | retained at the design value for the same reason; this is the loop whose exhaustion produced that incident |
| `V12.loop_bound_literal` | `3` | `validate_report.py` | V12's independent expectation of both loop bounds | retained deliberately: the validator's copy is what makes a silent divergence between the spec, the generated template and the check impossible, so it is not derived from the artefact it validates |
| `MAX_CHECK_MESSAGE_CHARS` | `400` | `validate_report.py` | the diagnostic cap on any one check message (V11's repair hint included) | retained at the design value; it is a diagnostic bound and gates no acceptance, and 400 characters keep the check id, the unit number and the reason inside the surviving head |

**The comparison defect this record names.** V14's wrong-verdict gate was an **exact-equality**
test (`wrong != MAX_WRONG`) while `MAX_MISLEADING` was already a ceiling (`misleading >
MAX_MISLEADING`), so raising `MAX_WRONG` to 1 would have rejected an all-accurate verdict file.
The gate is now a ceiling (`wrong > MAX_WRONG`), which means any future calibration changes the
constant and not the comparison, and the two thresholds are read the same way. That correction
belongs to this record because it is a precondition of ever calibrating the value.

**The missing data classes.** The repository holds none of these, and their absence is the reason
every value above is retained rather than measured:

1. no corpus of real change reports - the only two report HTMLs in the repository come from
   fixtures whose baseline commits are not objects here;
2. exactly one data point that is real: this work order's own report and its verdict file. One
   report is a data point, never a base rate;
3. no independent adjudication corpus - no second, independent judgement of the same units that
   would let anyone measure how often a verdict is wrong;
4. no error budget - nobody has stated how many wrong explanations a delivery may contain;
5. no round-count distribution - nothing records how many refresh passes real reports need, so
   the loop bound of 3 has never been compared with an observed tail;
6. no rubric separating `wrong` from `misleading`, so the two thresholds cannot be calibrated
   independently even with a corpus.

**The procedure a future calibration must follow.** Collect a corpus of real reports with their
manifest and verdict files; have at least two independent adjudicators re-judge a sample of
units, blind to the original verdicts, and measure the disagreement rate as the labelling noise;
derive `MAX_WRONG` and `MAX_MISLEADING` from the adjudicated rates plus a stated error budget
rather than from the sample mean; measure the distribution of `units_total`, of unit line counts
and of refresh passes over the same corpus to retire or keep `MAX_UNITS_MINIMAL`, the three
window constants and the two loop bounds; record the corpus revision, the adjudication protocol
and the resulting rates next to this table; and change the constants and this record, the
corresponding entries in `references/change-report-contract.md`, and the boundary tests that pin
them **in one change**, so the value, its reason and its test never drift apart. Inventing a
number, or presenting an estimate as a calibrated result, does not satisfy this record - it is
explicitly excluded.

## Three failure states, all visible

1. **Generation failure**: the script errors; the node fails.
2. **Validation failure**: the node fails, and is never downgraded to a warning. The one
   exception is staleness, which is an edge back to the refresh entry point at `validate-final`
   (C19a.6); the edge itself is
   bounded by `max_iterations` and `on_limit`, and exhaustion blocks the loop instead of
   failing it (C19a.4).
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
  3. before entering the refresh round: publish `report.round` as the 1-based index of the pass
     being entered (1 on the first pass) and write it before `prepare-manifest` runs, so a pass
     never labels itself with the next pass's number and nothing pre-increments the key; when
     the round was caused by code rework (`refresh_reason in {rework_rejected,
     review_driven_repair}`) also increment `report.refresh_count`; write this round's
     `report.refresh_reason`. `report.gate_rework_required` is reset by `validate-final` on its
     success path, never by the recovery group and never by hand;
  4. the outer loop declares `max_iterations=3` and `on_limit=blocked`. Exhaustion blocks the
     stage - the runtime vocabulary for the loop's terminal state is `blocked`, and the
     reported reason is that three refresh passes did not pass validation - rather than
     retrying forever or quietly passing. The terminal state was `failed` until a real work
     order was made un-completable by it: that work order's accuracy review loop exhausted
     this same bound, the failure propagated through the subtree root and the report group as
     a declared `on_limit=failed` requires, and it blocked the result document and
     finalization, which the runtime offers no recovery for because `retry-failed` requires an
     executable leaf and never accepts a loop. A bounded quality loop that cannot converge is
     the case a human gate exists for, so both of this package's quality loops escalate with
     `blocked` - the repository's vocabulary for escalating rather than killing a run, and the
     value every other bounded quality loop already declares (`xc-document-evolution`'s
     `review-loop`);
  5. a rework-driven refresh carries its cause:
     `report.refresh_reason in {rework_rejected, rework_revision_required, stale_head,
     review_driven_repair}`, written into the round records;
  6. the staleness back-edge has exactly one publisher. `validate-final` publishes
     `report.gate_rework_required=true` on its stale path and `false` on its success path.
     `validate-coverage` runs the same V9 check, but it has no instruction to publish the
     refresh key and is not a declared latch publisher, so a stale report found there fails that
     node and the main session re-runs the refresh sequence before the pass continues. A pass
     therefore never closes with a stale report, and the protocol no longer implies that
     `validate-coverage` owns a back-edge it cannot publish.
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
     which work order and which project repository it belongs to. **That ignore entry is a
     bridge obligation, not an enumeration rule.** The enumeration (C29) is a function of
     `(repo, baseline, head)` alone and never of the workshop's topology, so this contract adds
     no workshop exclusion: the independence is what keeps the change set recomputable by a
     third party who cannot see the workbench. What makes this item true is the project bridge:
     a project that runs a mutation work order must ignore the `.xcoding/` path, and
     `xc-workshop-setup` writes that entry for the two independent topologies
     (`independent-link`, `independent-nested`) while `same-repo` and `no-git` do not get it.
     Under those two topologies the runtime tree and the node artifacts are untracked project
     paths, so the enumeration really does contain them - including
     `runtime/orchestration.xml`, which every Skill forbids an agent to read. That is a
     **stated boundary with a residual risk**, not a handled case: this mechanism does not
     repair it, the project bridge owner does, by writing the ignore entry or by accepting that
     the workshop is part of that project's change set. The three-topology probe recorded under
     the workbench `tmp/` directory is the evidence for the boundary, and a mutation work order
     on a non-worktree repository fails closed before its first mutating leaf instead of
     substituting an empty digest;
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
- **C25a** **The publish is two steps, and every report node with a completion check follows
  that shape.** The runtime resolves a node's declared completion facts **before** it applies the
  blackboard writes carried by the same mutation, so a node that publishes its receipt facts and
  completes in one call fails its own completion check: the facts are compared against the
  blackboard as it was before those writes landed. The required sequence is therefore:
  1. run the validator and keep its normalised receipt;
  2. publish every fact the check names - `report.units_total`, `report.units_covered`,
     `report.excluded_total`, `report.pre_existing_total`, `report.hash_bound`,
     `report.token_bound`, `report.coverage`, `report.self_contained`, `report.head_current`,
     `report.strength` and `report.round` - together with the other values of the step, in a
     mutation that does not carry the terminal check;
  3. pass **only** the `.receipt` sub-object of the validator's output to `--check-result-json`
     on the completing mutation.
  The values are strings (`"7"`, `"true"`) because the comparison is exact text. A single-call
  publish produces a set of `check_fact_mismatch` violations rather than a wrong result, so this
  rule costs nothing but its statement; what it prevents is a caller reading that violation set
  as evidence that the validation itself failed.
- **C26** The real strength of the proof is the recomputability of V1-V16: any third party can
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
  `max_iterations=3` and `on_limit=blocked`, the escalation terminal state a bounded quality
  loop uses when it cannot converge; the value was `failed` (the design's `on_limit=fail`)
  until an exhausted loop in a real work order made that whole work order un-completable.
  The refresh latch's publishers are **exactly** the rows the shipped
  specification declares in `metadata.rework_publishers`, and this table is their normative
  statement; a fifth terminating path, or a node that publishes the key without appearing here,
  is a contract violation:

  | terminates_round | node | publishes |
  |---|---|---|
  | `gate-rework` | `report-gate` | `true` |
  | `review-loop-exit` | `validate-final` | `true` |
  | `review-loop-exit` | `validate-final` | `false` |
  | `validate-final-stale` | `validate-final` | `true` |
  | `validate-final-stale` | `validate-final` | `false` |

  The `gate-rework` round deliberately ends with the key still `true`, because that `true` is
  the loop's continue edge and the pass that follows carries the reset; every other terminating
  path publishes the key once and resets it once. The review loop on exit is **not** a publisher:
  `validate-final` is the last node of every round and owns the reset. `report-gate-recovery-group`
  publishes no `report.*` key at all.
- **O1a** The **recovery selector** `report.gate_recovery_required` has exactly one publisher:
  `report-gate` publishes `true` for the two reworking outcomes and `false` for the two
  accepting ones, in the same pass, before `validate-final`'s guard is evaluated. Because the
  gate reopens in every pass, a `true` left behind by a reworking round is replaced before
  `validate-final` reads it, which is what keeps `validate-final` out of a round the gate already
  terminated. `report-gate-recovery-group` keeps the key untouched: it is a selector for the
  group itself and a reset inside the group would let the pass close before the reworked report
  was judged again.
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
- **O3** A code-rework segment routes the refresh sequence back through the pass that follows
  it. The shipped recovery group does **not** append `prepare-manifest`, `author-report` and
  `validate-coverage` itself: a rejected gate outcome appends the covered code's rework through
  the work order's existing implementation path, and then the next pass of `report-pass-loop`
  re-runs its whole body, which is the refresh sequence. The refresh C19a requires is therefore
  performed by the loop's own body, and a rework segment that ends without the pass re-entering
  is incomplete, because the covered paths changed and V9 will fail. Appending the refresh
  sequence a second time inside the recovery group was rejected: the group sits inside the same
  loop body, so the appended nodes would run twice per pass and give one pass two manifests.
- **O4** `report.round` is the **1-based index of the pass being entered** - 1 on the first pass,
  2 on the second - and it is published before `prepare-manifest` runs, so a pass never labels
  itself with the next pass's number and nothing pre-increments the key. `report.refresh_count`
  starts at 0 and counts code-driven refreshes; `report.refresh_reason` is written on entering
  each round. The refresh latch is reset by `validate-final` on its success path, never by the
  recovery group and never by hand.
- **O5** The inner `report-review-loop` (review, then revise while
  `report.accuracy_open_issues == true`) sits inside the outer loop body, so every refresh
  re-reviews the rewritten text. Both loops declare `max_iterations=3` and `on_limit=blocked`,
  so neither exhaustion is fatal: it escalates to a blocked stage that a human resolves.
- **O6** The gate sits inside the loop body, so it reopens on every round and the human always
  reads the refreshed report.
- **O7** Staleness is not a node failure: `validate-final` publishes the rework key and returns
  control to the next outer round. Its success path publishes the reset. Only a non-staleness
  validation failure fails the node; loop exhaustion blocks the loop rather than failing it.
- **O8** No configuration may skip `validate-coverage`, the review loop or `validate-final`.
  The gate may be closed; validation and the accuracy review may not. That distinction is the
  entire reason this stage can be trusted.
- **O9** **One ordering statement is normative, and this is it.** On the **full lifecycle** the
  report group is the last group before the result document: the host template mounts
  `implementation-group`, then `verification-group`, then `report-group`, then
  `result-document`, and that lifecycle mounts **no top-level review node** - a review that a
  bridge or an approved solution requires is extra work inside the implementation path, so it
  happens before the report and never between the report and the result document. On the
  **adaptive path** the order is main-session policy, and there the report node precedes an
  independent review leaf so that the reviewer reads the report. Both statements are one
  contract: a document that describes the report's position must state the order of the path it
  describes, and no document may claim that the full lifecycle mounts a review stage between the
  report and the result document.

## Lifecycle coverage disposition

- **C39** The report is a stage of **the lifecycles that mount it**, not a universal property of
  a code-changing work order. Sixteen lifecycle entry points are reachable in this checkout, and
  each one is dispositioned here; a public page may claim coverage only for the entries whose
  disposition is `produced-here`, `produced-by-embedder`, or `covering-root`. The dispositions
  are:

  | # | Entry point | Mutates project code | Disposition | Why |
  |---|---|---|---|---|
  | 1 | `xc-work operation=run` (full lifecycle) | yes | `produced-here` | `report-group` sits after `verification-group` and before `result-document`, guarded by the mode-derived commitment; `prepare-work-order` records that commitment and `finalize-work-order` consumes it, so the group is selected rather than optionally skipped. Both legal mount forms - the embedded `change-report-template.xml` subtree and the flat `role=report` node carrying the same contract - produce exactly one report |
  | 2 | `xc-work operation=adaptive-run` | yes | `produced-here` by contract | the planner emits the required `report` node, the adaptive template declares the report vocabulary, and the adaptive manifest validator enforces the declared source key `work_order.report_baseline` and the required artifact name; on this path the **flat `role=report` node is the only supported form**, because the plan declares that leaf and a subtree root cannot bind to it |
  | 3 | `jit-milestone` subtree | yes | `covering-root` | a milestone-only work order initialises the **work-order** template, so the enclosing work-order root's `report-group` covers the milestone subtree; mounted as a farm subtree, the embedding root owns the report. Neither reference defines `jit-milestone-flow.json` as an initialisation path for a shipped workflow, and no report node is added to the subtree. The one caller that points `init` straight at `jit-milestone-template.xml` is the harness `tests/test_xc_jit_milestone.py`, which exercises the subtree shape without an `embed-subtree` step, declares no report stage and drives no report commitment; it is a recorded test exception and not a second initialisation path |
  | 4 | `xc-new-feature` | yes | `produced-here` | the new-feature template mounts a `report-group` between its verification group and its result document, declares the caller's report keys and consumes the commitment in its finalizer |
  | 5 | `xc-feature-adoption` | no | `none-and-not-needed` | positively read-only: it changes no product behavior and routes any product change to a separate `xc-work` |
  | 6 | `xc-feature-reconciliation` | no (product code) | `produced-by-embedder` | it is mounted under the ordinary work order's reconciliation group and that lifecycle owns the report; under the `same-repo` topology its baseline writes are tracked paths and therefore contribute analysable units to the enclosing report (C24a.3) |
  | 7 | `xc-diagnosis` | transiently | `none-and-not-needed` while removal holds | in-node repair is forbidden; instrumentation is authorised only with a declared diff artifact and is removed before node completion, so the obligation replaced by removal is recorded as an exemption with that residual risk |
  | 8 | `xc-document-evolution` | no (project code) | `none-and-not-needed` | writes only `document.path` inside the workshop; where those writes are tracked (`same-repo`), the enclosing lifecycle's report covers them |
  | 9 | `xc-clarify` | no | `none-and-not-needed` | positively read-only, and it names its embedders as the owners of the rest of the lifecycle |
  | 10 | `xc-workshop-setup` | yes, outside any template | `bootstrap-exemption` | step 0 appends the project `.gitignore` before `xc-open-work-order` runs, so no work order, tree or workbench exists when the bytes land; recorded as a bootstrap write with its criterion (runs before the first work order of a project and is idempotent afterwards) and its residual risk |
  | 11 | `xc-change-report` subtree | no | `the mechanism itself` | by contract the report group never edits code; every writing role is `report-*` |
  | 12 | `xc-workflow-evolution` | yes, when routed | `produced-by-embedder` | it routes through `xc-work operation=run` with mode `change`/`maintenance`, which sets the commitment; its installer's copy into a consumer asset root is not owned by any node and is covered by the `adapter_install` exclusion (C15) |
  | 13 | `xc-implementation` | yes | `capability, not a lifecycle` | it is the authorising contract for entries 1-4 and owns no completion gate of its own |
  | 14 | `xc-analysis`, `xc-review`, `xc-knowledge`, `xc-orchestration-viewer` | no | `none-and-not-needed` | each states its read-only boundary positively in its own contract |
  | 15 | `xc-orchestration-author` | repository assets only | `produced-by-embedder` | it runs inside the evolution work order of entry 12, whose commitment applies, and it does not execute runtime nodes |
  | 16 | `xcoding setup` (CLI, not a Skill) | yes | `exclusion-covered` | it writes packaged Skill resources and host adapters under the project root with no work order in existence; those roots are the `adapter_install` category (C15/C17), so a later report states the write instead of listing it as an unexplained unit |

  Entry 3's disposition is a **recorded decision**, not an inference: `jit-milestone-flow.json` is
  not an initialisation path for a shipped workflow, no report node is added to it, and the
  enclosing root covers the subtree. The only caller that initialises the subtree template
  directly is the test harness named in that row, and it drives no report stage. Entries 10 and 16
  are the two closures that are records rather than mounts. Entries 5,
  7, 8, 9 and 14 are read-only or removal-obligated by their own contract text and need no report.
  The coverage claim in any public page is limited to the entries this table dispositions as
  covered, and the honest residual is entry 6 and entry 12 under topologies that track the
  workshop (C24a.3).
