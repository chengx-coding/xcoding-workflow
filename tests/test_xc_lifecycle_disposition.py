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
    """Every lifecycle entry the change report does not cover states why.

    These tests pin the *decisions*, not their presentation. An earlier revision asserted the
    exact heading text and the `Reason. / Criterion. / Residual risk.` scaffolding of each
    record, which froze the change report's prominence into the test suite: the prose could not
    be shortened without a test failing, whatever it said. The change report is an ordinary
    lifecycle stage, so what must survive is the substance of each disposition - which lifecycle,
    what the consequence is, and which topology or condition triggers it - and not the number of
    paragraphs used to say it.
    """

    def test_milestone_is_a_subtree_under_the_work_order_root(self) -> None:
        protocol = read_flat(JIT_MILESTONE_PROTOCOL)
        farms = read_flat(FEATURE_FARMS)

        # The decision: a milestone-only work order initialises the work-order template, and the
        # enclosing root's report covers the milestone subtree.
        self.assertIn("## Report Coverage", protocol)
        self.assertIn("subtree, not a work-order root", protocol)
        self.assertIn(
            "A milestone-only work order initialises `work-order-template.xml` through `xc-work`",
            protocol,
        )
        self.assertIn(
            "report covers the milestone subtree's change set",
            protocol,
        )
        # The consequence: the flow spec is not an initialisation path for a shipped workflow.
        self.assertIn("not an initialisation path", protocol)

        # The same decision where farm subtrees are defined.
        self.assertIn("## Report Coverage", farms)
        self.assertIn(
            "The enclosing root's report covers the farm's whole change set once",
            farms,
        )
        self.assertIn("no report per subtree", farms)

        # The frozen disposition table the records must agree with.
        coverage = read_flat(COVERAGE_PROTOCOL)
        self.assertIn("| `jit-milestone` subtree |", coverage)
        self.assertIn("`covering-root`", coverage)

    def test_workshop_setup_bootstrap_write_disposition_is_stated(self) -> None:
        skill = read_flat(WORKSHOP_SETUP_SKILL)

        # The fact: the bootstrap `.gitignore` append precedes any work order, so no report can
        # cover it, and the bounds that make that acceptable.
        self.assertIn("before the project's first work order exists", skill)
        self.assertIn("idempotent", skill)
        self.assertIn("/.xcoding/", skill)
        self.assertIn("never rewrites an existing user line", skill)
        self.assertIn("writes nothing for `same-repo` or `no-git`", skill)
        self.assertIn("A later work order enumerates the resulting file normally", skill)

    def test_diagnosis_transient_mutation_disposition_is_stated(self) -> None:
        skill = read_flat(DIAGNOSIS_SKILL)

        # The controlling obligation is removal before completion; the report disposition follows
        # from it rather than standing as a separate regime.
        self.assertIn("removal before node completion", skill)
        self.assertIn("block the node and escalate", skill)
        self.assertIn("not part of any change set the enclosing work order reports", skill)
        self.assertIn("the removal obligation is what covers it", skill)

    def test_reconciliation_states_the_same_repo_topology_consequence(self) -> None:
        reconciliation = read_flat(RECONCILIATION_SKILL)

        self.assertIn("### Where a baseline write lands", reconciliation)
        self.assertIn(
            "Under the `same-repo` topology a feature baseline is a tracked product path",
            reconciliation,
        )
        self.assertIn("analysable change unit", reconciliation)
        self.assertIn(
            "including when the reconciliation concluded that no product behavior changed",
            reconciliation,
        )
        # Ownership: this Skill states the consequence but does not choose the topology.
        self.assertIn("does not choose the topology", reconciliation)
        self.assertIn("`xc-workshop-setup` fixed it", reconciliation)

    def test_topology_boundary_is_stated(self) -> None:
        skill = read_flat(WORKSHOP_SETUP_SKILL)
        coverage = read_flat(COVERAGE_PROTOCOL)

        # Which topologies keep the workshop out of the product's change set, and which do not.
        self.assertIn("### Topology and the change report", skill)
        self.assertIn(
            "Under `independent-link` and `independent-nested` the product repository ignores "
            "`.xcoding/`",
            skill,
        )
        self.assertIn("stay outside the enumeration", skill)
        self.assertIn("Under `same-repo` and `no-git`", skill)
        self.assertIn("the enumeration does contain them", skill)

        # The honest disposition: the mechanism is unchanged and the obligation is the project's.
        self.assertIn("This Skill adds no workshop exclusion", skill)
        self.assertIn("the `no-git` topology may run read-only modes only", skill)

        # The obligation is the bridge's, and the contract says it is not handled in code.
        self.assertIn("That ignore entry is a bridge obligation, not an enumeration rule", coverage)
        self.assertIn("does not repair it, the project bridge owner does", coverage)
        self.assertIn("runtime/orchestration.xml", skill)
        self.assertIn("runtime/orchestration.xml", coverage)


if __name__ == "__main__":
    unittest.main()
