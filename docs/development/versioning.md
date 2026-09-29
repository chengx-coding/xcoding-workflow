# Version Maintenance

**Language:** **English** | [简体中文](../zh-CN/development/versioning.md)

The current source version is <!-- xc:version -->0.2.0<!-- /xc:version -->. It identifies the source candidate; it does not claim that a public release or support evidence exists. The new shortcut exists only in builds containing its implementation; older installations can use `xcoding version --json`, and reinstalling the same historical wheel does not add the capability. Read the [installation contract](../getting-started/installation.md) for supported release boundaries.

## One Version Source

[`pyproject.toml`](../../pyproject.toml) `project.version` is the only editable product version source. Use a canonical stable `X.Y.Z` number with no leading zeros. Build metadata, wheel identity, Bundle manifests, and installed version reports must agree. Protocol schema versions, host adapter versions, and deliberately fixed test fixtures have their own meaning and are not product-version sources.

`xcoding --version` prints `xcoding <version>` for the validated installed package. It accepts no additional arguments. `xcoding version --json` retains the full machine-readable version and Bundle report; the existing bare `xcoding version` form still requires `--json` and reports `json-required` without it. The shortcut uses the same validation and does not hide installation errors. The installed package can legitimately differ from a development checkout; compare the correct artifact, not unrelated installations.

## Assess Every Iteration, Bump Only With Consent

Every XC iteration records a version assessment, including a justified `no-bump` outcome. Consider the whole set of unpublished changes since the last released version, not only the most recent commit. A commit or completed work order is not automatically a new release. Carry forward unresolved recommendations with references to their original decision artifacts and the released baseline. Keep those references in the work-order result so the next assessment can follow durable evidence instead of chat memory; if the earlier decision or release baseline is unavailable, record the gap and do not assume there are no pending changes.

| Disposition | When to recommend it |
| --- | --- |
| `no-bump` | No new release identity is needed yet, such as unreleased internal work or documentation/test maintenance with no changed public behavior; record why and what remains pending |
| `patch` | A release contains backward-compatible bug fixes or compatible maintenance without a new public capability |
| `minor` | A release adds backward-compatible public capabilities; while below `1.0.0`, also use the next minor version for a breaking public-contract change |
| `major` | At or above `1.0.0`, a release breaks a documented public contract |

These are SemVer classifications for this project, not compulsory numbering rules for consumer projects. A breaking `0.x` change advances `0.N.P` to `0.(N+1).0`; stable major changes reset the minor and patch numbers, and minor changes reset the patch number. Moving to `1.0.0` is a deliberate maturity and compatibility decision requiring explicit approval, never an automatic consequence of accumulating features. Public CLI behavior, installation or upgrade contracts, packaged Skills and agent contracts, and compatibility promises all contribute to the assessment. Changes to support claims require their own evidence even when the version number is approved.

Use the existing solution, result, or node artifact to retain one structured decision:

```yaml
version_disposition:
  current: <source-version>
  candidate: <proposed-version-or-null>
  classification: <no-bump|patch|minor|major>
  reason: <why-this-change-set-needs-or-does-not-need-a-bump>
  scope: <exact-changes-and-cumulative-unreleased-baseline>
  evidence: [<source-and-verification-references>]
  decision: <not-requested|pending|approved|rejected|deferred>
  actor: <requesting-agent-or-deciding-user>
  date: <ISO-8601-date>
  consent: <exact-user-decision-reference-or-null>
```

Before changing a version source, the Agent presents the candidate, reasons, scope, compatibility impact, and synchronization work through an existing main-session gate. Only explicit user consent to that concrete candidate and scope authorizes the bump. Approval to implement a feature, use automatic commits, or follow this policy is insufficient. Record a rejection or deferral, retain the version, and carry pending changes into the next assessment. If scope changes materially, reassess and obtain consent for the revised proposal. An approved bump still does not authorize publication, a release tag, or asset upload.

## Synchronize and Verify

After a concrete bump is approved, edit `pyproject.toml`, update explicitly marked current-version references, and rebuild derived artifacts. Do not hand-edit generated Bundle or wheel metadata. Keep historical release baselines, deliberate fixed fixtures, and independently versioned protocols intact.

Run `python scripts/check_version.py` during verification and CI. Current-reference markers use the `xc:version` HTML comment pair illustrated by this page's current-version statement. The checker validates those marked current references and applicable wheel filename examples against trusted project metadata; it does not interpret every historical number as current. The four current-reference pages are the root README pair and this version-policy pair. Their wheel filename examples must use the current version; historical wheel examples elsewhere are outside this check. Missing or malformed required markers must fail. Optional `--tag vX.Y.Z` and repeatable `--release-notes PATH` inputs verify a supplied tag and exact `## X.Y.Z` heading in supplied release notes; without those inputs, the checker does not claim to verify a release.

Candidate packaging checks must independently verify the expected distribution identity, wheel metadata, Bundle version, and installed CLI report. Release preparation additionally binds the candidate commit, immutable tag, wheel name and digest, Bundle digest, integrity/provenance assets, support-matrix evidence, and bilingual release notes. Re-run checks and review whenever these inputs change. Version approval, successful consistency checks, and publication approval remain distinct.

## Deferred Decisions

The earlier agent-definition rename was judged by the user to be compatible maintenance, while its numerical bump was deferred at `0.1.0`. That historical decision is retained in the [installation notes](../getting-started/installation.md); it is neither a standing exception nor permission to keep future changes unassessed. Preserve the original rationale and any unresolved public-contract interpretation in the next cumulative assessment. A later release decision may revisit it with evidence and explicit consent.

Return to [development guidance](../workflows/evolving.md) or the [documentation index](../index.md).
