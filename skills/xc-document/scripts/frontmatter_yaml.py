#!/usr/bin/env python3
"""Bounded YAML subset codec for XC managed-document frontmatter."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from typing import Any


MAX_BYTES = 64 * 1024
MAX_LINES = 2048
MAX_DEPTH = 32
MAX_NODES = 4096
MAX_SCALAR_LENGTH = 16 * 1024
MAX_INTEGER_DIGITS = 4096

_INTEGER = re.compile(r"-?(?:0|[1-9][0-9]*)\Z")
_FLOAT = re.compile(
    r"-?(?:(?:0|[1-9][0-9]*)\.[0-9]+(?:[eE][+-]?[0-9]+)?|"
    r"(?:0|[1-9][0-9]*)[eE][+-]?[0-9]+)\Z"
)
_AMBIGUOUS_NUMERIC = re.compile(
    r"(?:"
    r"\+[0-9]+(?:\.[0-9]*)?(?:[eE][+-]?[0-9]+)?|"
    r"-?0[0-9]+|"
    r"-?(?:0|[1-9][0-9]*)\.|"
    r"-?\.[0-9]+(?:[eE][+-]?[0-9]+)?|"
    r"-?(?:0|[1-9][0-9]*)[eE][+-]?"
    r")\Z"
)
_PLAIN_STRING = re.compile(r"[A-Za-z0-9_./\\:@+-]+\Z")
_PLAIN_KEY = re.compile(r"[A-Za-z_][A-Za-z0-9_.-]*\Z")
_AMBIGUOUS_PLAIN = {
    "null",
    "true",
    "false",
    "~",
    "yes",
    "no",
    "on",
    "off",
    ".nan",
    "+.nan",
    "-.nan",
    ".inf",
    "-.inf",
    "+.inf",
}


class FrontmatterYamlError(ValueError):
    """A stable parse or serialization error with optional source location."""

    def __init__(self, message: str, line: int | None = None, column: int | None = None):
        self.message = message
        self.line = line
        self.column = column
        location = ""
        if line is not None:
            location = f" at line {line}"
            if column is not None:
                location += f", column {column}"
        super().__init__(message + location)


@dataclass(frozen=True)
class _Line:
    number: int
    indent: int
    content: str


def _strip_comment(value: str) -> str:
    single = False
    double = False
    index = 0
    while index < len(value):
        char = value[index]
        if single:
            if char == "'" and index + 1 < len(value) and value[index + 1] == "'":
                index += 2
                continue
            if char == "'":
                single = False
        elif double:
            if char == "\\":
                index += 2
                continue
            if char == '"':
                double = False
        elif char == "'":
            single = True
        elif char == '"':
            double = True
        elif char == "#" and (index == 0 or value[index - 1].isspace()):
            return value[:index]
        index += 1
    return value


def _mapping_split(value: str) -> tuple[str, str] | None:
    single = False
    double = False
    square = 0
    curly = 0
    index = 0
    while index < len(value):
        char = value[index]
        if single:
            if char == "'" and index + 1 < len(value) and value[index + 1] == "'":
                index += 2
                continue
            if char == "'":
                single = False
        elif double:
            if char == "\\":
                index += 2
                continue
            if char == '"':
                double = False
        elif char == "'":
            single = True
        elif char == '"':
            double = True
        elif char == "[":
            square += 1
        elif char == "]":
            square -= 1
        elif char == "{":
            curly += 1
        elif char == "}":
            curly -= 1
        elif (
            char == ":"
            and square == 0
            and curly == 0
            and (index + 1 == len(value) or value[index + 1].isspace())
        ):
            return value[:index], value[index + 1 :].lstrip()
        index += 1
    return None


class _Loader:
    def __init__(self, text: str):
        encoded_size = len(text.encode("utf-8"))
        if encoded_size > MAX_BYTES:
            raise FrontmatterYamlError(
                f"frontmatter exceeds {MAX_BYTES} UTF-8 bytes"
            )
        raw_lines = text.splitlines()
        if len(raw_lines) > MAX_LINES:
            raise FrontmatterYamlError(f"frontmatter exceeds {MAX_LINES} lines")
        self.lines: list[_Line] = []
        self.nodes = 0
        for number, raw in enumerate(raw_lines, start=1):
            prefix_length = len(raw) - len(raw.lstrip(" \t"))
            prefix = raw[:prefix_length]
            if "\t" in prefix:
                raise FrontmatterYamlError(
                    "tabs are not allowed for indentation", number, 1
                )
            indent = len(prefix)
            if indent % 2:
                raise FrontmatterYamlError(
                    "indentation must use multiples of two spaces", number, indent + 1
                )
            content = _strip_comment(raw[indent:]).rstrip()
            if not content:
                continue
            if content in {"---", "..."} or content.startswith("%"):
                raise FrontmatterYamlError(
                    "directives and multiple YAML documents are not supported",
                    number,
                    indent + 1,
                )
            self.lines.append(_Line(number, indent, content))

    def _error(self, message: str, line: _Line, offset: int = 0) -> FrontmatterYamlError:
        return FrontmatterYamlError(message, line.number, line.indent + offset + 1)

    def _count(self, line: _Line, scalar: str | None = None) -> None:
        self.nodes += 1
        if self.nodes > MAX_NODES:
            raise self._error(f"frontmatter exceeds {MAX_NODES} nodes", line)
        if scalar is not None and len(scalar) > MAX_SCALAR_LENGTH:
            raise self._error(
                f"scalar exceeds {MAX_SCALAR_LENGTH} characters", line
            )

    def load(self) -> Any:
        if not self.lines:
            return None
        if self.lines[0].indent != 0:
            raise self._error("root value must not be indented", self.lines[0])
        value, index = self._parse_block(0, 0, 0)
        if index != len(self.lines):
            raise self._error("unexpected trailing content", self.lines[index])
        return value

    def _parse_block(self, index: int, indent: int, depth: int) -> tuple[Any, int]:
        if depth > MAX_DEPTH:
            raise self._error(
                f"frontmatter exceeds nesting depth {MAX_DEPTH}", self.lines[index]
            )
        line = self.lines[index]
        if line.indent != indent:
            raise self._error("unexpected indentation", line)
        if line.content == "-" or line.content.startswith("- "):
            return self._parse_sequence(index, indent, depth)
        return self._parse_mapping(index, indent, depth)

    def _parse_mapping(
        self,
        index: int,
        indent: int,
        depth: int,
        first: tuple[_Line, str] | None = None,
    ) -> tuple[dict[str, Any], int]:
        result: dict[str, Any] = {}
        count_line = first[0] if first else self.lines[index]
        self._count(count_line)
        while first is not None or index < len(self.lines):
            if first is not None:
                line, content = first
                first = None
            else:
                line = self.lines[index]
                if line.indent < indent:
                    break
                if line.indent > indent:
                    raise self._error("unexpected indentation", line)
                if line.content == "-" or line.content.startswith("- "):
                    raise self._error("cannot mix mapping and sequence entries", line)
                content = line.content
                index += 1
            split = _mapping_split(content)
            if split is None:
                raise self._error("mapping entry must contain ': ' or end with ':'", line)
            raw_key, raw_value = split
            key = self._parse_key(raw_key.strip(), line)
            if key in result:
                raise self._error(f"duplicate mapping key: {key}", line)
            if raw_value:
                result[key] = self._parse_inline(raw_value, line, depth + 1)
            elif index < len(self.lines) and self.lines[index].indent > indent:
                child = self.lines[index]
                if child.indent != indent + 2:
                    raise self._error(
                        "nested value must be indented by exactly two spaces", child
                    )
                result[key], index = self._parse_block(index, indent + 2, depth + 1)
            else:
                self._count(line)
                result[key] = None
        return result, index

    def _parse_sequence(
        self, index: int, indent: int, depth: int
    ) -> tuple[list[Any], int]:
        result: list[Any] = []
        self._count(self.lines[index])
        while index < len(self.lines):
            line = self.lines[index]
            if line.indent < indent:
                break
            if line.indent > indent:
                raise self._error("unexpected indentation", line)
            if not (line.content == "-" or line.content.startswith("- ")):
                raise self._error("cannot mix sequence and mapping entries", line)
            rest = line.content[1:].lstrip()
            index += 1
            if not rest:
                if index < len(self.lines) and self.lines[index].indent > indent:
                    child = self.lines[index]
                    if child.indent != indent + 2:
                        raise self._error(
                            "nested value must be indented by exactly two spaces",
                            child,
                        )
                    value, index = self._parse_block(index, indent + 2, depth + 1)
                else:
                    self._count(line)
                    value = None
            elif _mapping_split(rest) is not None:
                value, index = self._parse_mapping(
                    index, indent + 2, depth + 1, first=(line, rest)
                )
            else:
                value = self._parse_inline(rest, line, depth + 1)
                if index < len(self.lines) and self.lines[index].indent > indent:
                    raise self._error(
                        "scalar sequence item cannot have nested content",
                        self.lines[index],
                    )
            result.append(value)
        return result, index

    def _parse_key(self, value: str, line: _Line) -> str:
        if not value:
            raise self._error("mapping key must not be empty", line)
        key = self._parse_inline(value, line, 0)
        if not isinstance(key, str):
            raise self._error("mapping keys must be strings", line)
        if key == "<<":
            raise self._error("YAML merge keys are not supported", line)
        return key

    def _parse_inline(self, value: str, line: _Line, depth: int) -> Any:
        if depth > MAX_DEPTH:
            raise self._error(f"frontmatter exceeds nesting depth {MAX_DEPTH}", line)
        if value.startswith(("[", "{", "'", '"')):
            parser = _FlowParser(self, value, line, depth)
            parsed = parser.parse_value()
            parser.skip_space()
            if not parser.finished:
                raise self._error("unexpected content after scalar", line, parser.index)
            return parsed
        return self._parse_plain(value, line)

    def _parse_plain(self, value: str, line: _Line) -> Any:
        value = value.strip()
        self._count(line, value)
        if not value:
            raise self._error("empty plain scalar is not supported", line)
        if value[0] in "!&*" or value.startswith("<<"):
            raise self._error("YAML tags, anchors, aliases, and merge keys are not supported", line)
        if value in {"|", ">"} or value.startswith(("|", ">")):
            raise self._error("block scalars are not supported", line)
        if value == "null":
            return None
        if value == "true":
            return True
        if value == "false":
            return False
        if value.lower() in {".inf", "+.inf", "-.inf", ".nan", "+.nan", "-.nan"}:
            raise self._error(f"unsupported or ambiguous numeric scalar: {value}", line)
        if _INTEGER.fullmatch(value):
            if len(value.lstrip("-")) > MAX_INTEGER_DIGITS:
                raise self._error(
                    f"integer exceeds {MAX_INTEGER_DIGITS} decimal digits", line
                )
            return int(value)
        if _FLOAT.fullmatch(value):
            number = float(value)
            if not math.isfinite(number):
                raise self._error("non-finite numbers are not supported", line)
            return number
        if _AMBIGUOUS_NUMERIC.fullmatch(value):
            raise self._error(f"unsupported or ambiguous numeric scalar: {value}", line)
        return value


class _FlowParser:
    def __init__(self, loader: _Loader, text: str, line: _Line, depth: int):
        self.loader = loader
        self.text = text
        self.line = line
        self.depth = depth
        self.index = 0

    @property
    def finished(self) -> bool:
        return self.index >= len(self.text)

    def error(self, message: str) -> FrontmatterYamlError:
        return self.loader._error(message, self.line, self.index)

    def skip_space(self) -> None:
        while not self.finished and self.text[self.index].isspace():
            self.index += 1

    def parse_value(self) -> Any:
        self.skip_space()
        if self.finished:
            raise self.error("expected a value")
        if self.depth > MAX_DEPTH:
            raise self.error(f"frontmatter exceeds nesting depth {MAX_DEPTH}")
        char = self.text[self.index]
        if char == "[":
            return self.parse_sequence()
        if char == "{":
            return self.parse_mapping()
        if char == "'":
            return self.parse_single_quoted()
        if char == '"':
            return self.parse_double_quoted()
        return self.parse_plain()

    def parse_sequence(self) -> list[Any]:
        self.loader._count(self.line)
        self.index += 1
        result: list[Any] = []
        self.skip_space()
        if not self.finished and self.text[self.index] == "]":
            self.index += 1
            return result
        while True:
            nested = _FlowParser(
                self.loader, self.text[self.index :], self.line, self.depth + 1
            )
            value = nested.parse_value()
            self.index += nested.index
            result.append(value)
            self.skip_space()
            if self.finished:
                raise self.error("unclosed flow sequence")
            char = self.text[self.index]
            self.index += 1
            if char == "]":
                return result
            if char != ",":
                raise self.error("flow sequence expects ',' or ']'")
            self.skip_space()

    def parse_mapping(self) -> dict[str, Any]:
        self.loader._count(self.line)
        self.index += 1
        result: dict[str, Any] = {}
        self.skip_space()
        if not self.finished and self.text[self.index] == "}":
            self.index += 1
            return result
        while True:
            key = self.parse_flow_key()
            if key in result:
                raise self.error(f"duplicate mapping key: {key}")
            self.skip_space()
            if self.finished or self.text[self.index] != ":":
                raise self.error("flow mapping expects ':' after key")
            self.index += 1
            nested = _FlowParser(
                self.loader, self.text[self.index :], self.line, self.depth + 1
            )
            value = nested.parse_value()
            self.index += nested.index
            result[key] = value
            self.skip_space()
            if self.finished:
                raise self.error("unclosed flow mapping")
            char = self.text[self.index]
            self.index += 1
            if char == "}":
                return result
            if char != ",":
                raise self.error("flow mapping expects ',' or '}'")
            self.skip_space()

    def parse_flow_key(self) -> str:
        self.skip_space()
        if self.finished:
            raise self.error("expected a mapping key")
        if self.text[self.index] in {"'", '"'}:
            value = (
                self.parse_single_quoted()
                if self.text[self.index] == "'"
                else self.parse_double_quoted()
            )
        else:
            start = self.index
            while not self.finished and self.text[self.index] != ":":
                if self.text[self.index] in "[]{},":
                    raise self.error("unsupported flow mapping key")
                self.index += 1
            raw = self.text[start : self.index].strip()
            value = self.loader._parse_plain(raw, self.line)
        if not isinstance(value, str):
            raise self.error("mapping keys must be strings")
        if value == "<<":
            raise self.error("YAML merge keys are not supported")
        return value

    def parse_plain(self) -> Any:
        start = self.index
        square = 0
        curly = 0
        while not self.finished:
            char = self.text[self.index]
            if square == 0 and curly == 0 and char in ",]}":
                break
            if char == "[":
                square += 1
            elif char == "{":
                curly += 1
            self.index += 1
        return self.loader._parse_plain(self.text[start : self.index].strip(), self.line)

    def parse_single_quoted(self) -> str:
        self.index += 1
        result: list[str] = []
        while not self.finished:
            char = self.text[self.index]
            self.index += 1
            if char != "'":
                result.append(char)
                continue
            if not self.finished and self.text[self.index] == "'":
                result.append("'")
                self.index += 1
                continue
            value = "".join(result)
            self.loader._count(self.line, value)
            return value
        raise self.error("unclosed single-quoted string")

    def parse_double_quoted(self) -> str:
        self.index += 1
        result: list[str] = []
        escapes = {
            "0": "\0",
            "a": "\a",
            "b": "\b",
            "t": "\t",
            "n": "\n",
            "v": "\v",
            "f": "\f",
            "r": "\r",
            "e": "\x1b",
            " ": " ",
            '"': '"',
            "/": "/",
            "\\": "\\",
            "N": "\u0085",
            "_": "\u00a0",
            "L": "\u2028",
            "P": "\u2029",
        }
        while not self.finished:
            char = self.text[self.index]
            self.index += 1
            if char == '"':
                value = "".join(result)
                self.loader._count(self.line, value)
                return value
            if char != "\\":
                if ord(char) < 0x20:
                    raise self.error("control character must be escaped")
                result.append(char)
                continue
            if self.finished:
                raise self.error("unfinished escape sequence")
            escape = self.text[self.index]
            self.index += 1
            if escape in escapes:
                result.append(escapes[escape])
                continue
            widths = {"x": 2, "u": 4, "U": 8}
            width = widths.get(escape)
            if width is None or self.index + width > len(self.text):
                raise self.error(f"unsupported escape sequence: \\{escape}")
            digits = self.text[self.index : self.index + width]
            if not re.fullmatch(r"[0-9A-Fa-f]+", digits):
                raise self.error("Unicode escape contains non-hexadecimal digits")
            self.index += width
            codepoint = int(digits, 16)
            if codepoint > 0x10FFFF or 0xD800 <= codepoint <= 0xDFFF:
                raise self.error("Unicode escape is outside the valid scalar range")
            result.append(chr(codepoint))
        raise self.error("unclosed double-quoted string")


def loads(text: str) -> Any:
    """Parse the supported YAML subset."""

    return _Loader(text).load()


class _Dumper:
    def __init__(self):
        self.nodes = 0

    def _count(self, scalar: str | None = None, depth: int = 0) -> None:
        if depth > MAX_DEPTH:
            raise FrontmatterYamlError(
                f"value exceeds nesting depth {MAX_DEPTH}"
            )
        self.nodes += 1
        if self.nodes > MAX_NODES:
            raise FrontmatterYamlError(f"value exceeds {MAX_NODES} nodes")
        if scalar is not None and len(scalar) > MAX_SCALAR_LENGTH:
            raise FrontmatterYamlError(
                f"scalar exceeds {MAX_SCALAR_LENGTH} characters"
            )

    def dump(self, value: Any) -> str:
        lines = self._dump_block(value, 0, 0)
        rendered = "\n".join(lines) + "\n"
        if len(rendered.encode("utf-8")) > MAX_BYTES:
            raise FrontmatterYamlError(
                f"serialized frontmatter exceeds {MAX_BYTES} UTF-8 bytes"
            )
        if len(lines) > MAX_LINES:
            raise FrontmatterYamlError(
                f"serialized frontmatter exceeds {MAX_LINES} lines"
            )
        return rendered

    def _dump_block(self, value: Any, indent: int, depth: int) -> list[str]:
        self._count(depth=depth)
        prefix = " " * indent
        if isinstance(value, dict):
            if not value:
                return [prefix + "{}"]
            lines: list[str] = []
            for key, item in value.items():
                if not isinstance(key, str):
                    raise FrontmatterYamlError("mapping keys must be strings")
                rendered_key = self._dump_key(key)
                if self._is_nonempty_collection(item):
                    lines.append(f"{prefix}{rendered_key}:")
                    lines.extend(self._dump_block(item, indent + 2, depth + 1))
                else:
                    lines.append(
                        f"{prefix}{rendered_key}: {self._dump_scalar_or_empty(item, depth + 1)}"
                    )
            return lines
        if isinstance(value, list):
            if not value:
                return [prefix + "[]"]
            lines = []
            for item in value:
                if self._is_nonempty_collection(item):
                    lines.append(prefix + "-")
                    lines.extend(self._dump_block(item, indent + 2, depth + 1))
                else:
                    lines.append(
                        prefix + "- " + self._dump_scalar_or_empty(item, depth + 1)
                    )
            return lines
        return [prefix + self._dump_scalar(value, depth)]

    @staticmethod
    def _is_nonempty_collection(value: Any) -> bool:
        return isinstance(value, (dict, list)) and bool(value)

    def _dump_scalar_or_empty(self, value: Any, depth: int) -> str:
        if value == {}:
            self._count(depth=depth)
            return "{}"
        if value == []:
            self._count(depth=depth)
            return "[]"
        return self._dump_scalar(value, depth)

    def _dump_key(self, value: str) -> str:
        self._count(value)
        if _PLAIN_KEY.fullmatch(value) and value != "<<":
            return value
        return json.dumps(value, ensure_ascii=True)

    def _dump_scalar(self, value: Any, depth: int) -> str:
        if value is None:
            self._count(depth=depth)
            return "null"
        if isinstance(value, bool):
            self._count(depth=depth)
            return "true" if value else "false"
        if isinstance(value, int):
            self._count(depth=depth)
            if value.bit_length() > 13608:
                raise FrontmatterYamlError(
                    f"integer exceeds {MAX_INTEGER_DIGITS} decimal digits"
                )
            rendered = str(value)
            if len(rendered.lstrip("-")) > MAX_INTEGER_DIGITS:
                raise FrontmatterYamlError(
                    f"integer exceeds {MAX_INTEGER_DIGITS} decimal digits"
                )
            return rendered
        if isinstance(value, float):
            self._count(depth=depth)
            if not math.isfinite(value):
                raise FrontmatterYamlError("non-finite numbers are not supported")
            return repr(value)
        if not isinstance(value, str):
            raise FrontmatterYamlError(
                f"unsupported value type: {type(value).__name__}"
            )
        self._count(value, depth)
        lowered = value.lower()
        if (
            value
            and value == value.strip()
            and _PLAIN_STRING.fullmatch(value)
            and lowered not in _AMBIGUOUS_PLAIN
            and not _INTEGER.fullmatch(value)
            and not _FLOAT.fullmatch(value)
            and not _AMBIGUOUS_NUMERIC.fullmatch(value)
        ):
            return value
        return json.dumps(value, ensure_ascii=True)


def dumps(value: Any) -> str:
    """Serialize a value using the canonical supported YAML subset."""

    return _Dumper().dump(value)
