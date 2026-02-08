"""Provides a Laconic configuration parser"""

from __future__ import annotations

from ..exceptions import AzosError
from .configuration import Configuration
from .laconfig_lexer import LaconfigLexer, LaconfigToken, LaconfigTokenType
from .nodes import ConfigSectionNode


class LaconfigParser:
    """Parses Laconfig text into a Configuration instance"""

    def __init__(self, source: str) -> None:
        self._source = source
        self._tokens: list[LaconfigToken] = []
        self._index = 0

    def parse(self) -> Configuration:
        """Parses the source string into a Configuration"""
        lexer = LaconfigLexer(self._source)
        self._tokens = lexer.tokenize()
        self._index = 0
        self._expect(LaconfigTokenType.BOF)
        root_name = self._read_name()
        root_value = None
        if self._peek_type() == LaconfigTokenType.EQUALS:
            self._advance()
            root_value = self._read_value()
        self._expect(LaconfigTokenType.LBRACE)
        config = Configuration().create(root_name, root_value)
        self._parse_content(config.root)
        self._expect(LaconfigTokenType.RBRACE)
        self._expect(LaconfigTokenType.EOF)
        config.root.reset_modified()
        return config

    def _parse_content(self, parent: ConfigSectionNode) -> None:
        while True:
            token_type = self._peek_type()
            if token_type == LaconfigTokenType.RBRACE:
                return
            if token_type in {LaconfigTokenType.EOF, None}:
                raise AzosError("Unexpected end of file", "conf", "laconfig_parser")
            name = self._read_name()
            value = None
            if self._peek_type() == LaconfigTokenType.EQUALS:
                self._advance()
                value = self._read_value()
            if self._peek_type() == LaconfigTokenType.LBRACE:
                self._advance()
                section = parent.add_child_node(name, value)
                self._parse_content(section)
                self._expect(LaconfigTokenType.RBRACE)
                continue
            if value is not None:
                parent.add_attribute_node(name, value)
                continue
            raise AzosError("Invalid entry without value or section body", "conf", "laconfig_parser")

    def _read_name(self) -> str:
        token = self._advance()
        if token.token_type in {LaconfigTokenType.IDENTIFIER, LaconfigTokenType.STRING}:
            return token.text
        raise AzosError("Expected name", "conf", "laconfig_parser")

    def _read_value(self) -> str | None:
        token = self._advance()
        if token.token_type == LaconfigTokenType.NULL:
            return None
        if token.token_type in {LaconfigTokenType.IDENTIFIER, LaconfigTokenType.STRING}:
            return token.text
        raise AzosError("Expected value", "conf", "laconfig_parser")

    def _advance(self) -> LaconfigToken:
        token = self._tokens[self._index]
        self._index += 1
        return token

    def _expect(self, token_type: LaconfigTokenType) -> None:
        token = self._advance()
        if token.token_type != token_type:
            raise AzosError(f"Expected {token_type} but got {token.token_type}", "conf", "laconfig_parser")

    def _peek_type(self) -> LaconfigTokenType | None:
        if self._index >= len(self._tokens):
            return None
        return self._tokens[self._index].token_type
