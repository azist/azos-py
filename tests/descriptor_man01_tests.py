"""
Tests for AppChassis lifecycle and static properties

Copyright (C) 2026 Azist, MIT License
"""

from typing import override

from azos.oop import free
from azos.descriptor import Descriptor


def test_basic_01():
    d = Descriptor({
        "a": 1,
        "b": True,
        "c": "$(a)-$(b)",
        "d": "08/05/1980",
        "d2": "08/05/1980 2:30:00 pm",
        "e": "-123.09",
        "f": {
            "a": -400,
            "b": "ok"
        },
        "arr": [1, None, True, {"x": -56.891, "y": "123.023"}],
        "g": None
    })

    assert d["a"] == 1
    assert d["b"] is True
    assert d["c"] == "$(a)-$(b)"
    assert d["d"] == "08/05/1980"
    assert d["e"] == "-123.09"
    assert d["f"]["a"] == -400 # type: ignore
    assert d["f"]["b"] == "ok" # type: ignore
    assert d["f/a"] == -400
    assert d["f/b"] == "ok"
    assert d["g"] is None



    assert "a" in d
    assert "MISSING" not in d

    assert d.as_str("a") == "1"
    assert d.as_int("a") == 1
    assert d.as_float("a") == 1.0
    assert d.as_bool("a")

    assert d.as_str("c") == "1-True"
    assert d.as_str("c",verbatim=True) == "$(a)-$(b)"

    assert d.as_str("g") is None
    assert d.as_str("g", default="Hello") == "Hello"
    assert d.as_int("g", default=-305) == -305

    assert d.as_datetime("d").year == 1980 # type: ignore
    assert d.as_datetime("d2").hour == 14 # type: ignore
    assert d.as_datetime("d2").minute == 30 # type: ignore

    assert d.as_float("arr/#3/x") == -56.891
    assert d.as_float("arr/#3/y") == 123.023
