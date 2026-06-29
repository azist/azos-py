"""
Tests for AppChassis lifecycle and static properties

Copyright (C) 2026 Azist, MIT License
"""

import pytest

from azos.chassis import ConfigError
from azos.descriptor import Descriptor



def test_basic_01():
    a = Descriptor({"a": 1, "b": True})
    b = Descriptor({"a": 7, "c": "hello"})

    a.override_by(b)

    assert len(a) == 3
    assert a["a"] == 7
    assert a["b"] is True
    assert a["c"] == "hello"

    print(a)


def test_basic_02():
    a = Descriptor({"a": 1, "b": True, "_override": "stop"})
    b = Descriptor({"a": 7, "c": "hello"})

    a.override_by(b)

    assert len(a) == 3
    assert a["a"] == 1
    assert a["b"] is True
    assert a["_override"] == "stop"
    print(a)


def test_basic_03():
    a = Descriptor({"a": 1, "b": True, "_override": "fail"})
    b = Descriptor({"a": 7, "c": "hello"})

    pytest.raises(ConfigError, lambda: a.override_by(b))


def test_basic_04():
    a = Descriptor({"a": 1, "b": {"a": -2}})
    b = Descriptor({"a": 7, "b": {"c": 90}})

    a.override_by(b)

    assert len(a) == 2
    assert a["a"] == 7
    assert a["b/a"] == -2
    assert a["b/c"] == 90
    print(a)


def test_basic_05():
    a = Descriptor({"a": 1, "b": [1,2,3]})
    b = Descriptor({"a": 7, "b": [40,52]})

    a.override_by(b)

    assert len(a) == 2
    assert a["a"] == 7
    assert a["b/#0"] == 1
    assert a["b/#1"] == 2
    assert a["b/#2"] == 3
    assert a["b/#3"] == 40
    assert a["b/#4"] == 52
    print(a)


def test_basic_06():
    a = Descriptor({"a": 1, "b": [{"name": "x", "val": 1}, {"name": "y", "val": 2}]})
    b = Descriptor({"a": 7, "b": [{"name": "y", "val": 40}, {"name": "z", "val": 52}]})

    a.override_by(b)

    assert len(a) == 2
    assert len(a["b"]) == 3 # type: ignore
    assert a["a"] == 7
    assert a["b/#0/name"] == "x"
    assert a["b/#0/val"] == 1
    assert a["b/#1/name"] == "y"
    assert a["b/#1/val"] == 40
    assert a["b/#2/name"] == "z"
    assert a["b/#2/val"] == 52
    print(repr(a.data))


def test_basic_07():
    a = Descriptor({"a": 1, "b": [{"id": "x", "val": 1}, {"id": "y", "val": 2}]})
    b = Descriptor({"a": 7, "b": [{"id": "y", "val": 40}, {"id": "z", "val": 52}]})

    a.override_by(b) # the resulting list will have 4 as "id" is not the default list_item_key ("name" is)

    assert len(a) == 2
    assert len(a["b"]) == 4 # type: ignore
    assert a["a"] == 7
    assert a["b/#0/id"] == "x"
    assert a["b/#0/val"] == 1
    assert a["b/#1/id"] == "y"
    assert a["b/#1/val"] == 2
    assert a["b/#2/id"] == "y"
    assert a["b/#2/val"] == 40
    assert a["b/#3/id"] == "z"
    assert a["b/#3/val"] == 52
    print(repr(a.data))


def test_basic_08():
    a = Descriptor({"a": 1, "b": [{"id": "x", "val": 1}, {"id": "y", "val": 2}]})
    b = Descriptor({"a": 7, "b": [{"id": "y", "val": 40}, {"id": "z", "val": 52}]})

    a.override_by(b, list_item_key="id") # the resulting list will have 3 because of "id" key matching

    assert len(a) == 2
    assert len(a["b"]) == 3 # type: ignore
    assert a["a"] == 7
    assert a["b/#0/id"] == "x"
    assert a["b/#0/val"] == 1
    assert a["b/#1/id"] == "y"
    assert a["b/#1/val"] == 40
    assert a["b/#2/id"] == "z"
    assert a["b/#2/val"] == 52
    print(repr(a.data))


def test_basic_09():
    a = Descriptor({"a": 1, "b": [1,2,3]})
    b = Descriptor({"a": 7, "b": {"x": 989} }) # overriding list with dict

    a.override_by(b)

    assert len(a) == 2
    assert a["a"] == 7
    assert isinstance(a["b"], dict)
    assert a["b/x"] == 989
    print(a)


def test_basic_10():
    a = Descriptor({"a": 7, "b": {"x": 989} }) # overriding dict with list
    b = Descriptor({"a": 1, "b": [1,2,3]})

    a.override_by(b)

    assert len(a) == 2
    assert a["a"] == 1
    assert isinstance(a["b"], list)
    assert a["b/#0"] == 1
    print(a)


def test_basic_11():
    a = Descriptor({"a": 1, "b": [1,2,3]})
    b = Descriptor({"a": 7, "b": [40, "_clear", 52]})

    a.override_by(b)

    print(a)
    assert len(a) == 2
    assert isinstance(a["b"], list)
    assert len(a["b"]) == 2 # type: ignore
    assert a["a"] == 7
    assert a["b/#0"] == 40
    assert a["b/#1"] == 52


def test_app_config():
    v1 = Descriptor({
        "app": {
            "id": "myapp",
            "version": "1.0",
            "description": "My Application first release"
        },
        "paths": [
            {"name": "root", "path": "/"},
            {"name": "data", "path": "~/data"},
        ],
        "log": {
            "daemon": "sync",
            "sinks": [
                {"name": "console", "type": "console"},
                {"name": "file", "type": "file", "path": "~/logs/app.log"}
            ]
        },
        "db": {
            "type": "postgresql",
            "host": "localhost",
            "port": 5432,
            "user": "appuser",
        }
    })

    v2 = Descriptor({
        "app": {
            "version": "1.1",
            "description": "My Application second release"
        },
        "paths": [
            {"name": "data", "path": "~/new_data"},
            {"name": "cache", "path": "~/cache"},
        ],
        "log": {
            "sinks": [
                {"name": "file", "_override": "stop", "type": "file", "path": "~/logs/app_v2.log"}
            ]
        },
        "db": {
            "_override": "stop",
            "port": 3306,
        }
    })

    current = v1.clone()
    assert current.data is not v1.data

    current.override_by(v2)
    assert current.data is not v1.data
    assert current.data is not v2.data


    print(repr(current.data))

    assert current["app/version"] == "1.1"
    assert current["app/description"] == "My Application second release"
    assert current["paths/$name=root/path"] == "/"
    assert current["paths/$name=data/path"] == "~/new_data"
    assert current["paths/$name=cache/path"] == "~/cache"

    assert current["log/daemon"] == "sync"
    assert current["log/sinks/$name=console/type"] == "console"
    assert current["log/sinks/$name=file/type"] == "file"

    assert v1["log/sinks/$name=file/path"] == "~/logs/app.log"
    assert v2["log/sinks/$name=file/path"] == "~/logs/app_v2.log"

    assert current["log/sinks/$name=file/path"] == "~/logs/app_v2.log"

    assert v1["db/port"] == 5432
    assert v2["db/port"] == 3306

    assert current["db/user"] == "appuser"
    assert current["db/port"] == 3306
