#!/usr/bin/env python3
"""Deterministic lightweight lexical colouring for `xc-change-report` code blocks.

The colourer is a pure function: the same text and the same language label always
produce byte-identical output. It never changes the code text itself -- it only wraps
runs of characters in `<span class="tok-*">` elements and escapes HTML entities.

H29-H32 of the change report contract: no third-party highlighting library, no network
lookup of language definitions, unknown extensions degrade to escaped monospace text,
and "coloured" is explicitly not "syntactically correct".

Standard library only.
"""

from __future__ import annotations

import argparse
import html
import json
import sys
import tokenize
from io import StringIO
from pathlib import Path

# A deliberately small, generic keyword set. It is shared by every supported language
# instead of shipping a grammar per language: the colourer is cosmetic (H32), so an
# imperfect split between "keyword" and "identifier" is an accepted, documented cost.
GENERIC_KEYWORDS = frozenset(
    """
    abstract and as assert async await base begin break case catch class const continue
    crate def default defer del delete do done elif else elseif elsif end enum event
    except exec export extends external false final finally fn for foreach from func
    function get global go goto if impl implements import in include instanceof
    interface internal is lambda let lock loop match module mut namespace new nil none
    not null object of or override package parallel params pass private protected
    protocol public raise readonly record ref regex repeat require reset return sealed
    select set sizeof static struct sub super switch synchronized then this throw
    throws trait transient true try type typeof union unless until use using val var
    virtual void volatile when where while with yield
    """.split()
)

LANGUAGE_BY_EXTENSION = {
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".jsx": "javascript",
    ".ts": "javascript",
    ".tsx": "javascript",
    ".java": "c",
    ".c": "c",
    ".h": "c",
    ".hpp": "c",
    ".cc": "c",
    ".cpp": "c",
    ".cs": "c",
    ".go": "c",
    ".rs": "c",
    ".kt": "c",
    ".swift": "c",
    ".php": "c",
    ".rb": "shell",
    ".sh": "shell",
    ".bash": "shell",
    ".zsh": "shell",
    ".ps1": "shell",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".ini": "toml",
    ".cfg": "toml",
    ".sql": "sql",
    ".html": "markup",
    ".htm": "markup",
    ".xml": "markup",
    ".svg": "markup",
    ".css": "css",
    ".scss": "css",
    ".md": "markdown",
    ".markdown": "markdown",
    ".txt": "text",
}

LANGUAGE_SETTINGS = {
    "python": {"line_comment": "#", "block": (("'''", "'''"), ('"""', '"""')), "quotes": "\"'"},
    "javascript": {"line_comment": "//", "block": (("/*", "*/"),), "quotes": "\"'`"},
    "c": {"line_comment": "//", "block": (("/*", "*/"),), "quotes": "\"'"},
    "shell": {"line_comment": "#", "block": (), "quotes": "\"'"},
    "json": {"line_comment": "", "block": (), "quotes": '"'},
    "yaml": {"line_comment": "#", "block": (), "quotes": "\"'"},
    "toml": {"line_comment": "#", "block": (), "quotes": "\"'"},
    "sql": {"line_comment": "--", "block": (("/*", "*/"),), "quotes": "'\""},
    "markup": {"line_comment": "", "block": (("<!--", "-->"),), "quotes": "\"'"},
    "css": {"line_comment": "", "block": (("/*", "*/"),), "quotes": "\"'"},
    "markdown": {"line_comment": "", "block": (), "quotes": ""},
    "text": {"line_comment": "", "block": (), "quotes": ""},
}


def detect_language(path: str) -> str:
    """Map a file extension to a language label; unknown extensions become plain text (H31)."""
    suffix = Path(path).suffix.lower()
    return LANGUAGE_BY_EXTENSION.get(suffix, "text")


def supported_languages() -> list[str]:
    return sorted(LANGUAGE_SETTINGS)


def _escape(text: str) -> str:
    return html.escape(text, quote=False)


def _wrap(kind: str, text: str) -> str:
    return f'<span class="tok-{kind}">{_escape(text)}</span>'


def _number_end(text: str, index: int) -> int:
    cursor = index
    while cursor < len(text) and (text[cursor].isalnum() or text[cursor] in "._"):
        cursor += 1
    return cursor


def _identifier_end(text: str, index: int) -> int:
    cursor = index
    while cursor < len(text) and (text[cursor].isalnum() or text[cursor] == "_"):
        cursor += 1
    return cursor


def highlight(text: str, language: str) -> str:
    """Return HTML for `text` with `tok-*` spans. Pure function (H32)."""
    settings = LANGUAGE_SETTINGS.get(language, LANGUAGE_SETTINGS["text"])
    line_comment = settings["line_comment"]
    blocks = settings["block"]
    quotes = settings["quotes"]

    output: list[str] = []
    index = 0
    length = len(text)
    while index < length:
        character = text[index]

        if line_comment and text.startswith(line_comment, index):
            end = text.find("\n", index)
            end = length if end == -1 else end
            output.append(_wrap("comment", text[index:end]))
            index = end
            continue

        matched_block = None
        for opener, closer in blocks:
            if text.startswith(opener, index):
                matched_block = (opener, closer)
                break
        if matched_block:
            opener, closer = matched_block
            end = text.find(closer, index + len(opener))
            end = length if end == -1 else end + len(closer)
            output.append(_wrap("comment", text[index:end]))
            index = end
            continue

        if character in quotes:
            cursor = index + 1
            while cursor < length:
                if text[cursor] == "\\" and cursor + 1 < length:
                    cursor += 2
                    continue
                if text[cursor] == character:
                    cursor += 1
                    break
                cursor += 1
            output.append(_wrap("string", text[index:cursor]))
            index = cursor
            continue

        if character.isdigit():
            end = _number_end(text, index)
            output.append(_wrap("number", text[index:end]))
            index = end
            continue

        if character.isalpha() or character == "_":
            end = _identifier_end(text, index)
            word = text[index:end]
            if word.lower() in GENERIC_KEYWORDS:
                output.append(_wrap("keyword", word))
            else:
                output.append(_escape(word))
            index = end
            continue

        output.append(_escape(character))
        index += 1
    return "".join(output)


def looks_like_python(text: str) -> bool:
    """Best-effort hint used only when a snippet has no path context."""
    try:
        for _ in tokenize.generate_tokens(StringIO(text).readline):
            pass
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return False
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Colour a code snippet for the change report.")
    parser.add_argument("--file", default="")
    parser.add_argument("--language", default="")
    parser.add_argument("--text", default="")
    parser.add_argument("--out", default="")
    args = parser.parse_args(argv)

    if args.file:
        source = Path(args.file).read_text(encoding="utf-8", errors="replace")
        language = args.language or detect_language(args.file)
    else:
        source = args.text
        language = args.language or "text"

    if language not in LANGUAGE_SETTINGS:
        print(json.dumps({"ok": False, "error": f"unsupported language: {language}"}, indent=2))
        return 1

    payload = highlight(source, language)
    if args.out:
        Path(args.out).write_text(payload, encoding="utf-8", newline="\n")
    print(
        json.dumps(
            {
                "ok": True,
                "language": language,
                "characters": len(source),
                "html": payload if not args.out else "",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
