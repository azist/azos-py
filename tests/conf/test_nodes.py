import os

from azos.atom import Atom
from azos.conf.configuration import Configuration
from azos.entityid import EntityId


def test_navigation_and_accessors():
    conf = Configuration().create("root")
    root = conf.root
    db = root.add_child_node("db")
    db.add_attribute_node("port", "5432")
    assert root.navigate("/db/$port").as_int() == 5432


def test_variable_interpolation_env(monkeypatch):
    conf = Configuration().create("root")
    root = conf.root
    monkeypatch.setenv("TEST_HOME", "/tmp")
    root.add_attribute_node("path", "home=$(~TEST_HOME)")
    assert root.attr_by_name("path").value == "home=/tmp"


def test_variable_interpolation_path():
    conf = Configuration().create("root")
    root = conf.root
    root.add_attribute_node("home", "/var")
    root.add_attribute_node("path", "$($home)/data")
    assert root.attr_by_name("path").value == "/var/data"


def test_special_types():
    conf = Configuration().create("root")
    root = conf.root
    root.add_attribute_node("status", "active")
    root.add_attribute_node("eid", "car@dealer::ABC123")
    assert root.attr_by_name("status").as_atom() == Atom("active")
    assert isinstance(root.attr_by_name("eid").as_entityid(), EntityId)
