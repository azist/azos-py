import pytest
from azos import atom
from azos.exceptions import AzosError


def test_decode_01():
    num = 478560413032 #hello
    assert atom.decode(num) == "hello"


def test_decode_02():
    num = 7956003944985229683 #syslogin
    assert atom.decode(num) == "syslogin"


def test_decode_03():
    num = 97 #a
    assert atom.decode(num) == "a"


def test_decode_04():
    num = 98 #b
    assert atom.decode(num) == "b"


def test_decode_05():
    num = 0 #zero
    assert atom.decode(num) == ""


def test_decode_06():
    num = 4123376657429507385
    assert atom.decode(num) == "9-9-9-99"


def test_decode_07():
    num = 28821929395970657
    assert atom.decode(num) == "abc_def"


def test_decode_08():
    num = 28821928557109857
    assert atom.decode(num) == "abc-def"


def test_decode_09():
    with pytest.raises(AzosError) as exc_info:
        atom.decode(937) #invalid azatom value
    assert exc_info.value.frm == "decode(937)" # error frm field should contain method(arg) name


def test_decode_10():
    with pytest.raises(AzosError) as exc_info:
        atom.decode(18446744073709551619) #invalid azatom value 2^64 = 18446744073709551616
    assert exc_info.value.frm == "decode(18446744073709551619)"


def test_encode_01():
    assert atom.encode("abc-def") == 28821928557109857


def test_encode_02():
    assert atom.encode(None) == 0
    assert atom.encode("") == 0


def test_encode_03():
    with pytest.raises(AzosError) as exc_info:
        atom.encode("too long of a string")
    assert exc_info.value.frm == "encode(`too long of a string`)"


def test_encode_04():
    with pytest.raises(AzosError) as exc_info:
        atom.encode("^ba d")
    assert exc_info.value.frm == "encode(`^ba d`)"


def test_class_01():
    a = atom.Atom("a")
    assert a.id == 97
    assert str(a) == "a"
    assert repr(a) == "Atom(#97, `a`)"


def test_class_02():
    a = atom.Atom(97)
    assert a.id == 97
    assert str(a) == "a"
    assert repr(a) == "Atom(#97, `a`)"


def test_class_03():
    a = atom.Atom("a")
    b = atom.Atom("a")
    assert a is not b
    assert a == b
    assert hash(a) == hash(b)


def test_class_04():
    a = atom.Atom("a")
    b = a
    assert a is b
    assert a == b
    assert hash(a) == hash(b)


def test_class_05():
    a = atom.Atom("a")
    b = atom.Atom("b")
    assert a is not b
    assert a != b
    assert hash(a) != hash(b)


def test_class_06():
    a = atom.Atom(8825501086245354106)
    assert a.valid


def test_class_07():
    a = atom.Atom(8825501086245354109)
    assert not a.valid


def test_class_08():
    a = atom.Atom(0)
    assert a.id == 0
    assert a.valid
    assert a.is_zero
    assert str(a) == ""
    assert repr(a) == "Atom.ZERO"


def test_is_valid_06():
    a = 8825501086245354106
    assert atom.is_valid(a)


def test_is_valid_07():
    a = 8825501086245354109
    assert not atom.is_valid(a)
