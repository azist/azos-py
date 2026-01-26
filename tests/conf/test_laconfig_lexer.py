from azos.conf.laconfig_lexer import LaconfigLexer, LaconfigTokenType


def test_lexer_basic_tokens():
    source = "root{ a=1 b=\"x\" }"
    tokens = [t.token_type for t in LaconfigLexer(source).tokenize()]
    assert tokens[0] == LaconfigTokenType.BOF
    assert tokens[-1] == LaconfigTokenType.EOF
    assert LaconfigTokenType.LBRACE in tokens
    assert LaconfigTokenType.RBRACE in tokens


def test_lexer_comments_and_strings():
    source = "root{ //comment\n path=$\"c:\\\\logs\" name='it\\'s' }"
    tokens = LaconfigLexer(source).tokenize()
    texts = [t.text for t in tokens if t.token_type == LaconfigTokenType.STRING]
    assert "c:\\\\logs" in texts
    assert "it's" in texts


def test_lexer_verbatim_string():
    source = "root{ script=$\"line1\nline2\" }"
    tokens = LaconfigLexer(source).tokenize()
    strings = [t.text for t in tokens if t.token_type == LaconfigTokenType.STRING]
    assert "line1\nline2" in strings
