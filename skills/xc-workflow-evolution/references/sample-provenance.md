# Sample provenance gate (generic)

**Scope:** universal sample regression. **Applies when:** any sample result is scored or promoted.
**Does not apply:** no prior artifact exists; record `--no-prior` explicitly. **Evidence surface:**
provenance report JSON plus the seed/project/prior manifests. **Generality evidence:** a derived
artifact is rejected; a clean seed run is accepted (recorded in private evaluation, not in this
reference). **Force:** convention + checker (exit 0 clean, 1 derived, 2 input error).

A sample result is valid only when its provenance is clean. The gate applies to every sample, not a
particular product or prompt.

## Required record

- seed source and seed manifest hash;
- clean project path and the work order that ran it;
- project file manifest (paths + SHA-256, excluding `.git` and `.xcoding`);
- prior-artifact manifests compared;
- overlap report: files present in the project that are byte-identical to a prior artifact and not
  identical to the seed.

## Rule

If a non-seed project file is byte-identical to a prior sample artifact, the run is **derived** unless
the overlap is explained by the seed itself. A derived run may be kept as an experiment, but it cannot
be scored as a clean-seed version, promoted, or used to claim a clean-seed best.

The provenance record is written before scoring and promotion. A missing record is a gap, not a pass.

## Check

Use `scripts/check_sample_provenance.py --seed <seed> --project <project> --prior <prior-artifact>
--out <report.json>`, or `--no-prior` for the first sample. Exit 0 clean, 1 derived overlap,
2 input error. A missing or error record is a gap, not a pass.
