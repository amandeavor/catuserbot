# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# Aetheris V5 #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2026 Aetheris Intelligence Project
# Licensed under the GNU Affero General Public License v3.0
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

import enum
import re
from dataclasses import dataclass, field, is_dataclass
from typing import Any, Dict, List, Optional, Tuple, Type, get_type_hints


class TokenType(enum.Enum):
    WORD = "WORD"
    QUOTED = "QUOTED"
    LONG_FLAG = "LONG_FLAG"       # --limit or --limit=50
    SHORT_FLAG = "SHORT_FLAG"     # -f or -rf
    SEPARATOR = "SEPARATOR"       # --
    NEWLINE = "NEWLINE"


@dataclass
class Token:
    type: TokenType
    value: str
    key: Optional[str] = None
    raw: str = ""

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, str):
            return self.value == other or self.raw == other
        if isinstance(other, Token):
            return self.type == other.type and self.value == other.value and self.raw == other.raw
        return False

    def __str__(self) -> str:
        return self.raw if self.raw else self.value


class CommandLexer:
    """
    Production lexical scanner for Telegram command lines.
    Preserves Telegram Markdown, code blocks, multiline text, and escaped quotes.
    """

    def __init__(self, text: str):
        self.text = text or ""
        self.pos = 0
        self.length = len(self.text)

    def tokenize(self) -> List[Token]:
        tokens: List[Token] = []
        in_code_block = False

        while self.pos < self.length:
            char = self.text[self.pos]

            # Code block detection (```...```)
            if self.text[self.pos:self.pos + 3] == "```":
                # Preserve entire code block as a single quoted/literal token
                end_pos = self.text.find("```", self.pos + 3)
                if end_pos == -1:
                    code_content = self.text[self.pos + 3:]
                    self.pos = self.length
                else:
                    code_content = self.text[self.pos + 3:end_pos]
                    self.pos = end_pos + 3
                tokens.append(Token(TokenType.QUOTED, code_content, raw=f"```{code_content}```"))
                continue

            # Whitespace
            if char in " \t\r":
                self.pos += 1
                continue

            # Literal separator '--'
            if self.text[self.pos:self.pos + 2] == "--" and (self.pos + 2 == self.length or self.text[self.pos + 2] in " \t\n"):
                tokens.append(Token(TokenType.SEPARATOR, "--", raw="--"))
                self.pos += 2
                continue

            # Quoted string ("..." or '...')
            if char in "\"'":
                quote_char = char
                self.pos += 1
                start_pos = self.pos
                value_chars = []
                while self.pos < self.length:
                    c = self.text[self.pos]
                    if c == "\\" and self.pos + 1 < self.length and self.text[self.pos + 1] == quote_char:
                        value_chars.append(quote_char)
                        self.pos += 2
                    elif c == quote_char:
                        self.pos += 1
                        break
                    else:
                        value_chars.append(c)
                        self.pos += 1
                val = "".join(value_chars)
                tokens.append(Token(TokenType.QUOTED, val, raw=f"{quote_char}{val}{quote_char}"))
                continue

            # Long flag: --name or --name=value
            if self.text[self.pos:self.pos + 2] == "--":
                start_pos = self.pos
                self.pos += 2
                flag_text_chars = []
                while self.pos < self.length and self.text[self.pos] not in " \t\r\n":
                    flag_text_chars.append(self.text[self.pos])
                    self.pos += 1
                full_flag = "".join(flag_text_chars)
                if "=" in full_flag:
                    k, v = full_flag.split("=", 1)
                    tokens.append(Token(TokenType.LONG_FLAG, v, key=k, raw=f"--{full_flag}"))
                else:
                    tokens.append(Token(TokenType.LONG_FLAG, "true", key=full_flag, raw=f"--{full_flag}"))
                continue

            # Short flag: -f or -rf
            if char == "-" and self.pos + 1 < self.length and not self.text[self.pos + 1].isdigit() and self.text[self.pos + 1] not in " \t\r\n":
                start_pos = self.pos
                self.pos += 1
                flag_chars = []
                while self.pos < self.length and self.text[self.pos] not in " \t\r\n":
                    flag_chars.append(self.text[self.pos])
                    self.pos += 1
                short_flags = "".join(flag_chars)
                tokens.append(Token(TokenType.SHORT_FLAG, short_flags, key=short_flags, raw=f"-{short_flags}"))
                continue

            # Standard word or remaining text
            start_pos = self.pos
            word_chars = []
            while self.pos < self.length and self.text[self.pos] not in " \t\r\n":
                word_chars.append(self.text[self.pos])
                self.pos += 1
            word = "".join(word_chars)
            tokens.append(Token(TokenType.WORD, word, raw=word))

        return tokens


@dataclass
class ParsedCommand:
    """Represents a fully structured command line with flags, positional args, and raw text."""
    command: str
    flags: Dict[str, Any] = field(default_factory=dict)
    args: List[str] = field(default_factory=list)
    raw_query: str = ""
    raw_text: str = ""

    def get_flag(self, name: str, default: Any = None) -> Any:
        return self.flags.get(name, default)

    def has_flag(self, name: str) -> bool:
        return name in self.flags

    def bind_schema(self, schema_cls: Type[Any]) -> Any:
        """Binds and validates parsed flags and arguments into a typed schema dataclass."""
        hints = get_type_hints(schema_cls)
        kwargs = {}

        # 1. Map flags
        for field_name, field_type in hints.items():
            val = None
            if field_name in self.flags:
                val = self.flags[field_name]
            elif len(field_name) == 1 and field_name in self.flags:
                val = self.flags[field_name]

            if val is not None:
                if field_type is bool:
                    kwargs[field_name] = str(val).lower() in {"true", "1", "yes"}
                elif field_type is int:
                    try:
                        kwargs[field_name] = int(val)
                    except ValueError:
                        raise ValueError(f"Flag '{field_name}' must be an integer, got: {val}")
                elif field_type is float:
                    try:
                        kwargs[field_name] = float(val)
                    except ValueError:
                        raise ValueError(f"Flag '{field_name}' must be a float, got: {val}")
                else:
                    kwargs[field_name] = str(val)

        # 2. Map remaining positional args to first string field if needed
        return schema_cls(**kwargs)

    @property
    def name(self) -> str:
        if self.command and self.command[0] in {".", "!", "/", "?"}:
            return self.command[1:]
        return self.command

    @property
    def prefix(self) -> str:
        if self.command and self.command[0] in {".", "!", "/", "?"}:
            return self.command[0]
        return ""

    @property
    def positional(self) -> List[str]:
        return self.args

    @property
    def raw_args(self) -> str:
        return self.raw_query

    def bind(self, schema_dict_or_cls: Any) -> Any:
        if isinstance(schema_dict_or_cls, dict):
            bound = {}
            for k, typ in schema_dict_or_cls.items():
                if k in self.flags:
                    raw_v = self.flags[k]
                    if typ is bool:
                        bound[k] = bool(raw_v) and str(raw_v).lower() not in {"false", "0"}
                    elif typ is int:
                        bound[k] = int(raw_v)
                    elif typ is float:
                        bound[k] = float(raw_v)
                    else:
                        bound[k] = str(raw_v)
            return bound
        return self.bind_schema(schema_dict_or_cls)


class CommandParserV5:
    """Production GNU/POSIX command parser for Aetheris V5."""

    @staticmethod
    def parse(raw_text: str) -> ParsedCommand:
        if not raw_text or not raw_text.strip():
            return ParsedCommand(command="")

        # Extract command prefix and name
        parts = raw_text.strip().split(None, 1)
        command_word = parts[0]
        args_text = parts[1] if len(parts) > 1 else ""

        lexer = CommandLexer(args_text)
        tokens = lexer.tokenize()

        flags: Dict[str, Any] = {}
        args: List[str] = []
        is_literal = False
        i = 0

        while i < len(tokens):
            token = tokens[i]

            if is_literal:
                args.append(token.value)
                i += 1
                continue

            if token.type == TokenType.SEPARATOR:
                is_literal = True
                i += 1
                continue

            if token.type == TokenType.LONG_FLAG:
                key = token.key or ""
                val = token.value
                if val == "true":
                    if i + 1 < len(tokens) and tokens[i + 1].type in {TokenType.WORD, TokenType.QUOTED} and not tokens[i + 1].value.startswith("-"):
                        val = tokens[i + 1].value
                        i += 1
                    else:
                        val = True
                flags[key] = val
                # Also store normalized underscore variant
                flags[key.replace("-", "_")] = val
            elif token.type == TokenType.SHORT_FLAG:
                keys = token.key or ""
                if len(keys) == 1 and i + 1 < len(tokens) and tokens[i + 1].type in {TokenType.WORD, TokenType.QUOTED} and not tokens[i + 1].value.startswith("-"):
                    flags[keys] = tokens[i + 1].value
                    i += 1
                else:
                    # Combined boolean short flags (e.g. -rf -> r: True, f: True)
                    for k in keys:
                        flags[k] = True
            elif token.type in {TokenType.WORD, TokenType.QUOTED}:
                args.append(token.value)

            i += 1

        raw_query = " ".join(args)
        return ParsedCommand(
            command=command_word,
            flags=flags,
            args=args,
            raw_query=raw_query,
            raw_text=raw_text,
        )


parser_v5 = CommandParserV5()
command_parser = parser_v5

__all__ = [
    "TokenType",
    "Token",
    "CommandLexer",
    "ParsedCommand",
    "CommandParserV5",
    "parser_v5",
    "command_parser",
]
