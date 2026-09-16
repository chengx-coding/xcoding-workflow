from __future__ import annotations

import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]

WORKSHOP_SETUP_SKILL = REPOSITORY_ROOT / "skills" / "xc-workshop-setup" / "SKILL.md"
DIAGNOSIS_SKILL = REPOSITORY_ROOT / "skills" / "xc-diagnosis" / "SKILL.md"
RECONCILIATION_SKILL = REPOSITORY_ROOT / "skills" / "xc-feature-reconciliation" / "SKILL.md"
JIT_MILESTONE_PROTOCOL = (
    REPOSITORY_ROOT / "skills" / "xc-work" / "references" / "jit-milestone-protocol.md"
)
FEATURE_FARMS = REPOSITORY_ROOT / "skills" / "xc-work" / "references" / "feature-farms.md"
COVERAGE_PROTOCOL = (
    REPOSITORY_ROOT / "skills" / "xc-change-report" / "references" / "coverage-protocol.md"
)


def read_flat(path: Path) -> str:
    """Read a Markdown page with whitespace flattened, so assertions survive re-wrapping."""
    return " ".join(path.read_text(encoding="utf-8").split())


class XcLifecycleDispositionTests(unittest.TestCase):
    """G-11 ... G-15 and G-49: every uncovered lifecycle entry carries a recorded disposition.

    Each record must name the lifecycle, the reason, and the evidence that bounds the residual.
    A missing record is an inference, which is what these gaps measured.
    """

    def test_milestone_is_a_subtree_under_the_work_order_root(self) -> None:
        protocol = read_flat(JIT_MILESTONE_PROTOCOL)
        farms = read_flat(FEATURE_FARMS)

        # The decision: a milestone-only work order initialises the work-order template,
        # and the enclosing root's report covers the milestone subtree.
        self.assertIn("## Report Coverage", protocol)
        self.assertIn("subtree, not a work-order root", protocol)
        self.assertIn("A milestone-only work order initialises `work-order-template.xml` through `xc-work`", protocol)
        self.assertIn("enclosing work-order root's report covers the milestone subtree's change set", protocol)
        # The consequence: no report node is added, and the flow spec is not a root path.
        self.assertIn("no report node is added to `jit-milestone-template.xml` or to `jit-milestone-flow.json`", protocol)
        self.assertIn("not an initialisation path", protocol)
        self.assertIn("A milestone subtree is never embedded under a root without a report stage", protocol)

        # The same decision where farm subtrees are defined.
        self.assertIn("## Report Coverage", farms)
        self.assertIn("A farm's subtrees are subtrees, never roots", farms)
        self.assertIn("The enclosing root's report covers the farm's whole change set once", farms)
        self.assertIn("not `jit-milestone-flow.json`", farms)

        # The frozen disposition table the records must agree with.
        coverage = read_flat(COVERAGE_PROTOCOL)
        self.assertIn("| `jit-milestone` subtree |", coverage)
        self.assertIn("`covering-root`", coverage)

    def test_workshop_setup_bootstrap_write_is_recorded_as_an_exemption(self) -> None:
        skill = read_flat(WORKSHOP_SETUP_SKILL)

        self.assertIn("### Bootstrap write exemption (step 0.4)", skill)
        self.assertIn("recorded as an exemption from the report", skill)

        # Reason: no work order exists when the bytes land, and moving the write is circular.
        self.assertIn("**Reason.**", skill)
        self.assertIn("No work order, runtime tree, workbench or artifact exists when the bytes land", skill)
        self.assertIn("Moving the write into a template is circular", skill)

        # Criterion: the exact conditions under which the exemption may be claimed.
        self.assertIn("**Criterion.**", skill)
        self.assertIn("The exemption covers exactly this write, and only while all of it holds", skill)
        self.assertIn("runs before that project's first work order and is idempotent afterwards", skill)
        self.assertIn("`not-applicable`", skill)
        self.assertIn("`skipped-conflict`", skill)
        self.assertIn("It needs no exclusion category", skill)

        # Residual risk: the exposure that remains, named rather than implied.
        self.assertIn("**Residual risk.**", skill)
        self.assertIn("unguarded and unreported", skill)
        self.assertIn("bounded to that one bootstrap line", skill)

        # The installer writes are a different disposition, not a second exemption.
        self.assertIn("They are not exempt", skill)
        self.assertIn("`adapter_install` category", skill)

    def test_diagnosis_exemption_is_recorded_with_its_residual_risk(self) -> None:
        skill = read_flat(DIAGNOSIS_SKILL)

        self.assertIn("### Report exemption for the transient mutation", skill)
        self.assertIn("recorded as an exemption from the work order's change report", skill)
        self.assertIn("the removal obligation is what replaces the report obligation", skill)

        self.assertIn("**Reason.**", skill)
        self.assertIn("The mutation is evidence gathering, not a deliverable", skill)

        self.assertIn("**Criterion.**", skill)
        self.assertIn("The exemption holds only while every one of these holds", skill)
        self.assertIn("the node verifies removal before it completes", skill)
        self.assertIn("it blocks the node instead", skill)

        self.assertIn("**Residual risk.**", skill)
        self.assertIn("A mutation that survives unverified removal", skill)
        self.assertIn("`xc-review` reports a workspace change the reviewed scope created outside the workbench", skill)

    def test_reconciliation_states_the_same_repo_topology_consequence(self) -> None:
        setup = read_flat(WORKSHOP_SETUP_SKILL)
        reconciliation = read_flat(RECONCILIATION_SKILL)

        # Where the topology is chosen.
        self.assertIn("### Topology and the change report", setup)
        self.assertIn(
            "Under `same-repo` the feature baselines that `xc-feature-reconciliation` writes are tracked paths, "
            "so they become analysable units the enclosing work order's report must explain",
            setup,
        )
        # Where the baselines are written.
        self.assertIn("### Where a baseline write lands", reconciliation)
        self.assertIn(
            "Under `same-repo` the baseline is a tracked product path, so the write becomes an analysable change unit "
            "that the enclosing work order's report must explain like any other change",
            reconciliation,
        )
        self.assertIn(
            "Under `independent-link` and `independent-nested` the project repository ignores `.xcoding/`, "
            "so the write stays outside the change set the enclosing report enumerates",
            reconciliation,
        )
        self.assertIn("The topology was fixed by `xc-workshop-setup` before this work order opened", reconciliation)

    def test_topology_boundary_is_stated(self) -> None:
        skill = read_flat(WORKSHOP_SETUP_SKILL)
        coverage = read_flat(COVERAGE_PROTOCOL)

        # The boundary: which topologies get the ignore entry and which do not.
        self.assertIn("The ignore entry is written for the two independent topologies only", skill)
        self.assertIn(
            "Under `independent-link` and `independent-nested` the product repository ignores `.xcoding/`, "
            "so the runtime tree and the node artifacts stay out of the change set a work order enumerates",
            skill,
        )
        self.assertIn(
            "Under `same-repo` and `no-git` the runtime tree and the node artifacts are untracked product paths, "
            "so the enumeration does contain them",
            skill,
        )
        # The honest disposition: recorded, with the mechanism unchanged.
        self.assertIn("stated boundary with a residual risk, not a handled case", skill)
        self.assertIn("this Skill adds no workshop exclusion", skill)
        self.assertIn("the `no-git` topology may run read-only modes only", skill)

        # The obligation is the bridge's, and the contract says it is not handled in code.
        self.assertIn("That ignore entry is a bridge obligation, not an enumeration rule", coverage)
        self.assertIn("does not repair it, the project bridge owner does", coverage)
        self.assertIn("runtime/orchestration.xml", skill)
        self.assertIn("runtime/orchestration.xml", coverage)


if __name__ == "__main__":
    unittest.main()
