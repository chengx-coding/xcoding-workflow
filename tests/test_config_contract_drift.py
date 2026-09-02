from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
AUTHOR_CORE = (
    REPOSITORY_ROOT
    / "skills"
    / "xc-orchestration-author"
    / "scripts"
    / "author_core.py"
)

sys.path.insert(0, str(SOURCE_ROOT))

from xcoding.runtime import core


def load_author_core():
    """Load author_core.py as a standalone script via file location.

    author_core.py is deliberately not a package import, so we load it by path
    with a unique module name rather than registering it in the package tree.
    """
    spec = importlib.util.spec_from_file_location(
        "xc_author_core_config_contract_test",
        AUTHOR_CORE,
    )
    if spec is None or spec.loader is None:
        raise AssertionError("cannot load author_core.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ConfigContractDriftTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.author = load_author_core()

    def _load(self, module, config_path: Path) -> tuple[bool, dict[str, Any] | None]:
        try:
            config = module.load_config(config_path=config_path)
        except getattr(module, "ConfigError"):
            return False, None
        return True, config

    def _write(self, temp: str, content: dict[str, Any]) -> Path:
        context = Path(temp) / ".xcoding"
        context.mkdir(parents=True, exist_ok=True)
        config_path = context / "xc-orchestration-runtime.json"
        config_path.write_text(json.dumps(content) + "\n", encoding="utf-8")
        return config_path

    def test_defaults_agree(self) -> None:
        self.assertEqual(
            core.DEFAULT_CONFIG["workshop"]["topology"],
            self.author.DEFAULT_CONFIG["workshop"]["topology"],
        )
        self.assertEqual(core.WORKSHOP_TOPOLOGY_DEFAULT, "independent-link")
        self.assertEqual(self.author.WORKSHOP_TOPOLOGY_DEFAULT, "independent-link")
        self.assertEqual(
            core.ALLOWED_WORKSHOP_TOPOLOGIES,
            self.author.ALLOWED_WORKSHOP_TOPOLOGIES,
        )

    def test_unknown_topology_rejected_by_both(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            config_path = self._write(temp, {"workshop": {"topology": "weird"}})
            core_ok, _ = self._load(core, config_path)
            author_ok, _ = self._load(self.author, config_path)
            self.assertFalse(core_ok)
            self.assertFalse(author_ok)

    def test_same_repo_without_explicit_auto_commit_rejected_by_both(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            config_path = self._write(temp, {"workshop": {"topology": "same-repo"}})
            core_ok, _ = self._load(core, config_path)
            author_ok, _ = self._load(self.author, config_path)
            self.assertFalse(core_ok)
            self.assertFalse(author_ok)

    def test_independent_nested_accepted_by_both(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            config_path = self._write(
                temp,
                {"workshop": {"topology": "independent-nested"}},
            )
            core_ok, core_config = self._load(core, config_path)
            author_ok, author_config = self._load(self.author, config_path)
            self.assertTrue(core_ok)
            self.assertTrue(author_ok)
            assert core_config is not None
            assert author_config is not None
            self.assertEqual(
                core_config["workshop"]["topology"],
                "independent-nested",
            )
            self.assertEqual(
                author_config["workshop"]["topology"],
                "independent-nested",
            )


if __name__ == "__main__":
    unittest.main()
