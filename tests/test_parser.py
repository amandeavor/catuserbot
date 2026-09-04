# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# Aetheris V5 #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2026 Aetheris Intelligence Project
# Licensed under the GNU Affero General Public License v3.0
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

import pytest
from userbot.core.parser import CommandLexer, CommandParserV5, ParsedCommand


def test_command_lexer_basic():
    text = '.echo "hello world" --times=3 -v'
    lexer = CommandLexer(text)
    tokens = lexer.tokenize()
    assert tokens == [".echo", "hello world", "--times=3", "-v"]


def test_command_lexer_code_blocks():
    text = ".run ```python\nprint('hello')\n``` --lang=py"
    lexer = CommandLexer(text)
    tokens = lexer.tokenize()
    assert tokens[0] == ".run"
    assert tokens[1] == "```python\nprint('hello')\n```"
    assert tokens[2] == "--lang=py"


def test_parser_positional_and_flags():
    parser = CommandParserV5()
    cmd = parser.parse(".deploy web-service production --replicas 5 -f --dry-run")
    assert cmd.name == "deploy"
    assert cmd.prefix == "."
    assert cmd.positional == ["web-service", "production"]
    assert cmd.flags.get("replicas") == "5"
    assert cmd.flags.get("f") is True
    assert cmd.flags.get("dry-run") is True


def test_parser_grouped_short_flags():
    parser = CommandParserV5()
    cmd = parser.parse(".clean -rfv target_dir")
    assert cmd.name == "clean"
    assert cmd.flags.get("r") is True
    assert cmd.flags.get("f") is True
    assert cmd.flags.get("v") is True
    assert cmd.positional == ["target_dir"]


def test_parser_schema_binding():
    parser = CommandParserV5()
    cmd = parser.parse(".scale api --count 8 --rate 2.5 --strict")
    bound = cmd.bind({
        "count": int,
        "rate": float,
        "strict": bool,
    })
    assert bound["count"] == 8
    assert bound["rate"] == 2.5
    assert bound["strict"] is True


def test_parser_empty_or_whitespace():
    parser = CommandParserV5()
    cmd = parser.parse("    ")
    assert cmd.name == ""
    assert cmd.positional == []
    assert cmd.flags == {}
