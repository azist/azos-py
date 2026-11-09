import re

import pytest

from azos.db import naturaltextgenerator as ntg

ITERATIONS = 500


@pytest.fixture(autouse=True)
def seeded_random():
    """Makes the random data deterministic per test, then restores entropy seeding"""
    ntg.seed(12345)
    yield
    ntg.seed()


def test_constants_01():
    """Data tables are non-empty tuples of non-empty strings"""
    tables = (
        ntg.US_STATES,
        ntg.DOMAIN_NAMES,
        ntg.TLD_NAMES,
        ntg.POPULAR_FIRST_NAMES,
        ntg.POPULAR_LAST_NAMES,
        ntg.CITY_SUFFIXES,
        ntg.STREET_SUFFIXES,
        ntg.POPULAR_CITY_NAMES,
        ntg.LAST_NAME_SUFFIXES,
    )
    for t in tables:
        assert isinstance(t, tuple)
        assert len(t) > 0
        assert all(isinstance(s, str) and s for s in t)


def test_constants_02():
    """Known table sizes and content match the original"""
    assert len(ntg.US_STATES) == 51
    assert "CA" in ntg.US_STATES and "DC" in ntg.US_STATES
    assert all(len(s) == 2 and s.isupper() for s in ntg.US_STATES)
    assert all(t.startswith(".") for t in ntg.TLD_NAMES)
    assert "Winston-Salem" in ntg.POPULAR_CITY_NAMES
    assert all("\ufffd" not in s for t in (ntg.POPULAR_CITY_NAMES, ntg.POPULAR_LAST_NAMES) for s in t)


def test_text_resources_01():
    """Both embedded text resources load as package resources"""
    for name in ("JackLondon.txt", "ConanDoyle.txt"):
        text = ntg.__load_text(name)
        assert len(text) > 100000
        assert not text.startswith("\ufeff")


def test_generate_01():
    """Generate honors requested length and has no stray whitespace"""
    for _ in range(ITERATIONS):
        s = ntg.generate(60)
        assert len(s) <= 60
        assert s == s.strip()
        assert "  " not in s
        assert "\n" not in s and "\r" not in s


def test_generate_02():
    """Default length is 150 max"""
    for _ in range(ITERATIONS):
        assert len(ntg.generate()) <= 150


def test_generate_03():
    """Zero or negative length generates text of random size (max 150)"""
    lengths = set()
    for n in (0, -1, -100):
        for _ in range(ITERATIONS // 3):
            s = ntg.generate(n)
            assert len(s) <= 150
            lengths.add(len(s))
    assert len(lengths) > 10


def test_generate_04():
    """Lengths below 10 are clamped to 10"""
    for _ in range(ITERATIONS):
        assert len(ntg.generate(1)) <= 10


def test_generate_05():
    """Long text is close to the requested length"""
    lens = [len(ntg.generate(500)) for _ in range(100)]
    assert max(lens) <= 500
    assert min(lens) > 400


def test_generate_06():
    """Only letters/digits/apostrophe/hyphen/space are produced"""
    for _ in range(ITERATIONS):
        assert re.fullmatch(r"[\w'\- ]*", ntg.generate(200))


def test_generate_word_01():
    """Words obey min/max bounds and contain no spaces"""
    for _ in range(ITERATIONS):
        w = ntg.generate_word(5, 9)
        assert 5 <= len(w) <= 9
        assert " " not in w


def test_generate_word_02():
    """Min length is clamped to 4"""
    for _ in range(ITERATIONS):
        assert len(ntg.generate_word(1, 2)) >= 4


def test_generate_word_03():
    """Default bounds"""
    for _ in range(ITERATIONS):
        assert 4 <= len(ntg.generate_word()) <= 20


def test_generate_word_04():
    """Inverted bounds fall back to a valid range and do not hang"""
    for _ in range(ITERATIONS):
        assert 4 <= len(ntg.generate_word(5, 2)) <= 20


def test_generate_first_name():
    """First names are non-empty without whitespace"""
    for _ in range(ITERATIONS):
        s = ntg.generate_first_name()
        assert s and s == s.strip()


def test_generate_last_name():
    """Last names are non-empty with no apostrophe-free restriction on popular names"""
    for _ in range(ITERATIONS):
        s = ntg.generate_last_name()
        assert s and s == s.strip()


def test_generate_city_name():
    """City names are non-empty"""
    for _ in range(ITERATIONS):
        s = ntg.generate_city_name()
        assert s and s == s.strip()


def test_names_vary():
    """Generators produce varied data"""
    assert len({ntg.generate_first_name() for _ in range(ITERATIONS)}) > 50
    assert len({ntg.generate_last_name() for _ in range(ITERATIONS)}) > 50
    assert len({ntg.generate_city_name() for _ in range(ITERATIONS)}) > 50


def test_generate_us_city_state_zip():
    """City/state/zip format"""
    for _ in range(ITERATIONS):
        s = ntg.generate_us_city_state_zip()
        m = re.fullmatch(r"(.+), ([A-Z]{2}) (\d{5})", s)
        assert m
        assert m.group(2) in ntg.US_STATES


def test_generate_address_line():
    """Address starts with a street number between 1 and 10000"""
    for _ in range(ITERATIONS):
        m = re.match(r"^(\d+) \S", ntg.generate_address_line())
        assert m
        assert 1 <= int(m.group(1)) <= 10000


def test_generate_address_line_units():
    """Apartment/suite/room variants all occur"""
    lines = [ntg.generate_address_line() for _ in range(3000)]
    assert any(" apt #" in x for x in lines)
    assert any(" apt. " in x for x in lines)
    assert any(" suite " in x for x in lines)
    assert any(" room " in x for x in lines)


def test_generate_full_name_01():
    """Full name without middle has at least first and last parts"""
    for _ in range(ITERATIONS):
        assert len(ntg.generate_full_name().split(" ")) >= 2


def test_generate_full_name_02():
    """Middle name variant sometimes includes a middle name or initial"""
    names = [ntg.generate_full_name(True) for _ in range(ITERATIONS)]
    assert all(len(n.split(" ")) >= 2 for n in names)
    assert any(re.search(r" [A-Z] ", n) for n in names)


def test_generate_email():
    """Email has one @, no spaces/apostrophes and a lowercase domain"""
    for _ in range(ITERATIONS):
        e = ntg.generate_email()
        user, _, domain = e.partition("@")
        assert user and domain
        assert "@" not in domain
        assert " " not in e and "'" not in e
        assert domain == domain.lower()


def test_seed_01():
    """Same seed yields the same data, re-seeding with None yields different data"""
    ntg.seed(777)
    a = [ntg.generate_full_name(True), ntg.generate_address_line(), ntg.generate_email(), ntg.generate(80)]
    ntg.seed(777)
    b = [ntg.generate_full_name(True), ntg.generate_address_line(), ntg.generate_email(), ntg.generate(80)]
    assert a == b

    ntg.seed()
    c = [ntg.generate_full_name(True), ntg.generate_address_line(), ntg.generate_email(), ntg.generate(80)]
    assert a != c


def test_print_samples(capsys):
    """Writes sample data to the console (run pytest -s to see it live); different on every run"""
    ntg.seed()
    with capsys.disabled():
        print("\n--- NaturalTextGenerator samples ---")
        for _ in range(8):
            print(f"Name:    {ntg.generate_full_name(True)}")
            print(f"Address: {ntg.generate_address_line()}, {ntg.generate_us_city_state_zip()}")
            print(f"Email:   {ntg.generate_email()}")
            print(f"Text:    {ntg.generate(80)}")
            print()
