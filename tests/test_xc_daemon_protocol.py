from __future__ import annotations

import json
import unittest
from http import HTTPStatus
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"

import sys

sys.path.insert(0, str(SOURCE_ROOT))

from xcoding.daemon import protocol


class DaemonProtocolTests(unittest.TestCase):
    def assert_protocol_error(
        self,
        code: str,
        function,
        *arguments,
    ) -> protocol.ProtocolError:
        with self.assertRaises(protocol.ProtocolError) as raised:
            function(*arguments)
        self.assertEqual(raised.exception.code, code)
        return raised.exception

    def test_success_and_error_envelopes_are_deterministic(self) -> None:
        success = protocol.success_payload(
            "request-id",
            {"value": 1},
        )
        failure = protocol.error_payload(
            "request-id",
            "bad_request",
            "invalid",
            {"field": "value"},
        )
        self.assertEqual(
            json.loads(protocol.json_bytes(success)),
            success,
        )
        self.assertEqual(
            json.loads(protocol.json_bytes(failure)),
            failure,
        )
        self.assertTrue(protocol.json_bytes(success).endswith(b"\n"))

    def test_json_parser_rejects_invalid_shapes_and_values(self) -> None:
        cases = (
            (b"[]", "invalid_json_root"),
            (b'{"a":1,"a":2}', "duplicate_json_key"),
            (b'{"value":NaN}', "invalid_json"),
            (b"\xff", "invalid_json"),
            (b"{", "invalid_json"),
        )
        for data, code in cases:
            with self.subTest(code=code):
                self.assert_protocol_error(
                    code,
                    protocol.parse_json_object,
                    data,
                )

    def test_json_parser_enforces_body_limit(self) -> None:
        error = self.assert_protocol_error(
            "request_too_large",
            protocol.parse_json_object,
            b"x" * (protocol.MAX_BODY_BYTES + 1),
        )
        self.assertEqual(
            error.status,
            HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
        )

    def test_query_envelope_requires_exact_fields_and_types(self) -> None:
        valid = {
            "tree_id": "tree-id",
            "command": "summary",
            "parameters": {"limit": 1},
        }
        self.assertEqual(
            protocol.parse_query_request(valid),
            ("tree-id", "summary", {"limit": 1}),
        )
        cases = (
            (
                {"tree_id": "id", "command": "summary"},
                "invalid_request_fields",
            ),
            (
                {**valid, "extra": True},
                "invalid_request_fields",
            ),
            (
                {**valid, "tree_id": ""},
                "invalid_tree_id",
            ),
            (
                {**valid, "tree_id": "bad\nid"},
                "invalid_tree_id",
            ),
            (
                {**valid, "tree_id": "x" * 129},
                "invalid_tree_id",
            ),
            (
                {**valid, "command": 1},
                "invalid_command",
            ),
            (
                {**valid, "parameters": []},
                "invalid_parameters",
            ),
        )
        for payload, code in cases:
            with self.subTest(code=code):
                self.assert_protocol_error(
                    code,
                    protocol.parse_query_request,
                    payload,
                )


if __name__ == "__main__":
    unittest.main()
