from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DOCUMENT_SKILL = REPOSITORY_ROOT / "skills" / "xc-document"
DOCUMENT_SCRIPTS = DOCUMENT_SKILL / "scripts"
TEMPLATES = DOCUMENT_SKILL / "assets" / "templates"

sys.path.insert(0, str(DOCUMENT_SCRIPTS))
from frontmatter_yaml import (
    MAX_BYTES,
    MAX_DEPTH,
    MAX_INTEGER_DIGITS,
    MAX_LINES,
    MAX_NODES,
    MAX_SCALAR_LENGTH,
    FrontmatterYamlError,
    dumps,
    loads,
)


class FrontmatterYamlTests(unittest.TestCase):
    def assert_rejected(self, content: str, expected: str) -> None:
        with self.assertRaises(FrontmatterYamlError) as raised:
            loads(content)
        self.assertIn(expected, str(raised.exception))

    def test_loads_nested_block_collections(self) -> None:
        content = """schema_version: 1
feature_ids:
  - payment-refund
  - ledger
orchestration:
  initialized_by:
    work_order_id: test-order
    tree_ref: C:\\dev\\xc\\runtime\\orchestration.xml
items:
  - name: first
    flags: [true, false, null]
  -
    nested: value
"""

        parsed = loads(content)

        self.assertEqual(parsed["schema_version"], 1)
        self.assertEqual(parsed["feature_ids"], ["payment-refund", "ledger"])
        self.assertEqual(
            parsed["orchestration"]["initialized_by"]["tree_ref"],
            r"C:\dev\xc\runtime\orchestration.xml",
        )
        self.assertEqual(
            parsed["items"],
            [
                {"name": "first", "flags": [True, False, None]},
                {"nested": "value"},
            ],
        )

    def test_loads_flow_values_quotes_escapes_and_comments(self) -> None:
        content = r"""root: {items: [1, -2, 3.5, 6e2, false, null], text: "line\n\u4E2D", note: 'it''s # data'} # comment
plain_hash: value#part
quoted_hash: "value # part"
yaml_11_words: [yes, no, on, off, ~, 2026-08-02]
"""

        parsed = loads(content)

        self.assertEqual(parsed["root"]["items"], [1, -2, 3.5, 600.0, False, None])
        self.assertEqual(parsed["root"]["text"], "line\n\u4e2d")
        self.assertEqual(parsed["root"]["note"], "it's # data")
        self.assertEqual(parsed["plain_hash"], "value#part")
        self.assertEqual(parsed["quoted_hash"], "value # part")
        self.assertEqual(
            parsed["yaml_11_words"],
            ["yes", "no", "on", "off", "~", "2026-08-02"],
        )

    def test_round_trips_finite_json_values_deterministically(self) -> None:
        value = {
            "schema_version": 1,
            "document_kind": "node-artifact",
            "feature_ids": ["alpha", "beta"],
            "data": {
                "empty_object": {},
                "empty_array": [],
                "boolean": True,
                "nothing": None,
                "integer": -7,
                "float": 1.25,
                "unicode": "\u8bed\u8a00",
                "ambiguous": "yes",
                "numeric_strings": ["+1", "01", ".5", "1.", "1e", "+.nan", "-.nan"],
                "windows_path": r"C:\dev\xc\runtime.xml",
            },
        }

        rendered = dumps(value)

        self.assertTrue(rendered.endswith("\n"))
        self.assertEqual(loads(rendered), value)
        self.assertEqual(dumps(loads(rendered)), rendered)
        self.assertIn('unicode: "\\u8bed\\u8a00"', rendered)
        self.assertIn('ambiguous: "yes"', rendered)

    def test_all_managed_document_templates_use_supported_yaml(self) -> None:
        templates = sorted(TEMPLATES.glob("*.md"))
        self.assertEqual(len(templates), 10)
        for template in templates:
            with self.subTest(template=template.name):
                text = template.read_text(encoding="utf-8")
                frontmatter = text.split("---", 2)[1]
                parsed = loads(frontmatter)
                self.assertIsInstance(parsed, dict)
                self.assertEqual(parsed["schema_version"], 1)

    def test_rejects_duplicate_keys_and_structure_errors(self) -> None:
        cases = (
            ("key: one\nkey: two\n", "duplicate mapping key"),
            ("root: {key: one, key: two}\n", "duplicate mapping key"),
            (" key: value\n", "multiples of two spaces"),
            ("key:\n    nested: value\n", "exactly two spaces"),
            ("items:\n  - one\n  key: value\n", "cannot mix"),
            ("\tkey: value\n", "tabs are not allowed"),
            ("key value\n", "mapping entry must contain"),
            ("root: [one, two\n", "unclosed flow sequence"),
        )
        for content, expected in cases:
            with self.subTest(expected=expected):
                self.assert_rejected(content, expected)

    def test_rejects_unsupported_yaml_features(self) -> None:
        cases = (
            ("value: !python/object value\n", "tags, anchors, aliases"),
            ("value: &anchor text\n", "tags, anchors, aliases"),
            ("value: *anchor\n", "tags, anchors, aliases"),
            ("<<: {name: value}\n", "merge keys"),
            ("value: |\n  text\n", "block scalars"),
            ("%YAML 1.2\nvalue: text\n", "directives"),
            ("---\nvalue: text\n", "multiple YAML documents"),
            ("? [complex, key]\n: value\n", "mapping entry must contain"),
            ("value: .inf\n", "ambiguous numeric"),
            ("value: 01\n", "ambiguous numeric"),
        )
        for content, expected in cases:
            with self.subTest(expected=expected):
                self.assert_rejected(content, expected)

    def test_enforces_load_resource_limits(self) -> None:
        cases = (
            ("key: " + ("x" * MAX_BYTES), f"exceeds {MAX_BYTES} UTF-8 bytes"),
            (
                "\n".join(f"k{index}: value" for index in range(MAX_LINES + 1)),
                f"exceeds {MAX_LINES} lines",
            ),
            (
                "\n".join(
                    ("  " * index) + f"k{index}:"
                    for index in range(MAX_DEPTH + 2)
                ),
                f"nesting depth {MAX_DEPTH}",
            ),
            (
                "items: [" + ",".join("0" for _ in range(MAX_NODES + 1)) + "]",
                f"exceeds {MAX_NODES} nodes",
            ),
            (
                'key: "' + ("x" * (MAX_SCALAR_LENGTH + 1)) + '"',
                f"scalar exceeds {MAX_SCALAR_LENGTH}",
            ),
            (
                "key: " + ("9" * (MAX_INTEGER_DIGITS + 1)),
                f"integer exceeds {MAX_INTEGER_DIGITS}",
            ),
        )
        for content, expected in cases:
            with self.subTest(expected=expected):
                self.assert_rejected(content, expected)

    def test_dump_rejects_unsupported_or_unbounded_values(self) -> None:
        with self.assertRaisesRegex(FrontmatterYamlError, "non-finite"):
            dumps({"value": math.inf})
        with self.assertRaisesRegex(FrontmatterYamlError, "mapping keys"):
            dumps({1: "value"})
        with self.assertRaisesRegex(FrontmatterYamlError, "unsupported value type"):
            dumps({"value": object()})
        with self.assertRaisesRegex(FrontmatterYamlError, "scalar exceeds"):
            dumps({"value": "x" * (MAX_SCALAR_LENGTH + 1)})
        with self.assertRaisesRegex(FrontmatterYamlError, "integer exceeds"):
            dumps({"value": 10 ** MAX_INTEGER_DIGITS})


if __name__ == "__main__":
    unittest.main()
