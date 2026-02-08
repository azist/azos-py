"""Provides a Laconic configuration lexer"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ..exceptions import AzosError


class LaconfigTokenType(str, Enum):
    """Token types for Laconfig"""

    BOF = "BOF"
    EOF = "EOF"
    IDENTIFIER = "Identifier"
    STRING = "String"
    NULL = "Null"
    LBRACE = "LBrace"
    RBRACE = "RBrace"
    EQUALS = "Equals"


@dataclass(frozen=True)
class SourcePosition:
    """Source position within a text file"""

    line: int
    column: int
    index: int


@dataclass(frozen=True)
class LaconfigToken:
    """Represents a Laconfig token"""

    token_type: LaconfigTokenType
    text: str
    start: SourcePosition
    end: SourcePosition


class LaconfigLexer:
    """Lexes Laconfig source into a stream of tokens"""

    def __init__(self, source: str) -> None:
        self._source = source or ""

    def tokenize(self) -> list[LaconfigToken]:
        """Returns a list of tokens"""
        return list(self.iter_tokens())

    def iter_tokens(self):
        """Generates tokens lazily"""
        source = self._source
        length = len(source)
        index = 0
        line = 1
        column = 1
        fresh_line = True

        def position() -> SourcePosition:
            return SourcePosition(line, column, index)

        def advance(count: int = 1) -> None:
            nonlocal index, line, column, fresh_line
            for _ in range(count):
                if index >= length:
                    return
                ch = source[index]
                index += 1
                if ch == "\r":
                    if index < length and source[index] == "\n":
                        index += 1
                    line += 1
                    column = 1
                    fresh_line = True
                    continue
                if ch == "\n":
                    line += 1
                    column = 1
                    fresh_line = True
                    continue
                column += 1
                fresh_line = False

        def peek(offset: int = 0) -> str:
            pos = index + offset
            if pos >= length:
                return ""
            return source[pos]

        yield LaconfigToken(LaconfigTokenType.BOF, "", position(), position())

        while index < length:
            ch = peek()
            nxt = peek(1)

            if ch in {" ", "\t"}:
                advance()
                continue

            if ch == "\r" or ch == "\n":
                advance()
                continue

            if fresh_line and ch == "#":
                while index < length and peek() not in {"\r", "\n"}:
                    advance()
                continue

            if ch == "/" and nxt == "/":
                advance(2)
                while index < length and peek() not in {"\r", "\n"}:
                    advance()
                continue

            if (ch == "/" and nxt == "*") or (ch == "|" and nxt == "*"):
                terminator = "*/" if ch == "/" else "*|"
                advance(2)
                while index < length:
                    if peek() == terminator[0] and peek(1) == terminator[1]:
                        advance(2)
                        break
                    advance()
                else:
                    raise AzosError("Unterminated comment block", "conf", "laconfig_lexer")
                continue

            if ch == "$" and nxt in {"\"", "'"}:
                start = position()
                quote = nxt
                advance(2)
                text = ""
                while index < length:
                    cur = peek()
                    if cur == quote:
                        if peek(1) == quote:
                            text += quote
                            advance(2)
                            continue
                        end = position()
                        advance()
                        yield LaconfigToken(LaconfigTokenType.STRING, text, start, end)
                        break
                    text += cur
                    advance()
                else:
                    raise AzosError("Unterminated verbatim string", "conf", "laconfig_lexer")
                continue

            if ch in {"\"", "'"}:
                start = position()
                quote = ch
                advance()
                text = ""
                while index < length:
                    cur = peek()
                    if cur in {"\r", "\n"}:
                        raise AzosError("Unterminated string", "conf", "laconfig_lexer")
                    if cur == quote:
                        end = position()
                        advance()
                        text = self.__unescape_string(text)
                        yield LaconfigToken(LaconfigTokenType.STRING, text, start, end)
                        break
                    if cur == "\\":
                        text += cur
                        advance()
                        if index < length:
                            text += peek()
                            advance()
                        continue
                    text += cur
                    advance()
                else:
                    raise AzosError("Unterminated string", "conf", "laconfig_lexer")
                continue

            if ch in {"{", "}", "="}:
                start = position()
                advance()
                end = position()
                token_type = {
                    "{": LaconfigTokenType.LBRACE,
                    "}": LaconfigTokenType.RBRACE,
                    "=": LaconfigTokenType.EQUALS,
                }[ch]
                yield LaconfigToken(token_type, ch, start, end)
                continue

            start = position()
            text = ""
            while index < length:
                cur = peek()
                nxt = peek(1)
                if cur in {" ", "\t", "\r", "\n", "{", "}", "="}:
                    break
                if (cur == "/" and nxt in {"/", "*"}) or (cur == "|" and nxt == "*"):
                    break
                if cur in {"\"", "'"}:
                    break
                if cur == "$" and nxt in {"\"", "'"}:
                    break
                text += cur
                advance()
            end = position()
            if text == "":
                raise AzosError("Unexpected character", "conf", "laconfig_lexer")
            token_type = LaconfigTokenType.NULL if text == "null" else LaconfigTokenType.IDENTIFIER
            yield LaconfigToken(token_type, text, start, end)

        pos = position()
        yield LaconfigToken(LaconfigTokenType.EOF, "", pos, pos)

    def __unescape_string(self, text: str) -> str:
        result = ""
        idx = 0
        while idx < len(text):
            ch = text[idx]
            if ch != "\\":
                result += ch
                idx += 1
                continue
            idx += 1
            if idx >= len(text):
                raise AzosError("Invalid escape sequence", "conf", "laconfig_lexer")
            esc = text[idx]
            idx += 1
            mapping = {
                "\"": "\"",
                "'": "'",
                "\\": "\\",
                "0": "\0",
                "a": "\a",
                "b": "\b",
                "f": "\f",
                "n": "\n",
                "r": "\r",
                "t": "\t",
                "v": "\v",
            }
            if esc in mapping:
                result += mapping[esc]
                continue
            if esc == "u":
                hex_part = text[idx:idx + 4]
                if len(hex_part) != 4 or any(c not in "0123456789abcdefABCDEF" for c in hex_part):
                    raise AzosError("Invalid unicode escape", "conf", "laconfig_lexer")
                result += chr(int(hex_part, 16))
                idx += 4
                continue
            if esc == "x":
                hex_digits = ""
                while idx < len(text) and text[idx] in "0123456789abcdefABCDEF" and len(hex_digits) < 4:
                    hex_digits += text[idx]
                    idx += 1
                if hex_digits == "":
                    raise AzosError("Invalid hex escape", "conf", "laconfig_lexer")
                result += chr(int(hex_digits, 16))
                continue
            raise AzosError("Invalid escape sequence", "conf", "laconfig_lexer")
        return result
