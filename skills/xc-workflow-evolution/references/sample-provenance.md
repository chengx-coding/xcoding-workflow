# Sample provenance gate (generic)

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
--out <report.json>`. Exit 1 means overlap; exit 0 means no overlap.
