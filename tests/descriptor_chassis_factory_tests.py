"""
Tests for FileChassisDescriptorFactory: bootloading AppChassis descriptors from a tree of JSON files
located under `tests/cfg-data` covering `required` flag, `$(env)` macro and `#include<...>` pragmas.

All entry points are (non-existing) `tests/cfg-data/{stem}.py` files, so the default root file is
`tests/cfg-data/{stem}.$(env).json` and all relative includes resolve against `tests/cfg-data`.

Copyright (C) 2026 Azist, MIT License
"""

import json
import os
from configparser import ConfigParser
from contextlib import contextmanager
from typing import Any, Iterator

import pytest

from azos.chassis import AppChassis, ConfigError
from azos.descriptor import (CONFIG_FILE_DESCRIPTOR_PATH_ATTR, MAX_INCLUDES, Descriptor,
                             FileChassisDescriptorFactory)
from azos.exceptions import AzosError


CFG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cfg-data")
APP_ID = "tapp"

COMMON = {"company": "Azist", "region": "us-east"}
TIMEOUTS = {"connect": 3000, "command": 15000}


def ep(stem: str) -> str:
    """Returns a (non-existing) entry point path co-located with the config tree"""
    return os.path.join(CFG_DIR, f"{stem}.py")


def make_config(path: str | None = None, app_id: str = APP_ID) -> ConfigParser:
    """Makes chassis config, optionally specifying descriptor file path for the app section"""
    config = ConfigParser()
    if path is not None:
        config.read_dict({app_id: {CONFIG_FILE_DESCRIPTOR_PATH_ATTR: path}})
    return config


@contextmanager
def chassis(stem: str,
            env: str | None,
            factory: FileChassisDescriptorFactory | None = None,
            config: ConfigParser | None = None,
            app_id: str = APP_ID) -> Iterator[AppChassis]:
    """Allocates a chassis using FileChassisDescriptorFactory, disposing it at the end"""
    app = AppChassis(app_id,
                     ep(stem),
                     env,
                     config if config is not None else make_config(app_id=app_id),
                     factory if factory is not None else FileChassisDescriptorFactory())
    try:
        yield app
    finally:
        app.dispose()


def bootload_error(stem: str,
                   env: str | None,
                   factory: FileChassisDescriptorFactory | None = None,
                   config: ConfigParser | None = None,
                   cause: type[BaseException] | None = None,
                   app_id: str = APP_ID) -> AzosError:
    """Asserts that chassis allocation fails with a bootload AzosError and returns it"""
    with pytest.raises(AzosError) as exc_info:
        with chassis(stem, env, factory, config, app_id):
            pass

    error = exc_info.value
    assert error.topic == "chassis-bootload"
    assert f"app_id=`{app_id}`" in error.frm
    if cause is not None:
        assert isinstance(error.__cause__, cause)

    # A failed allocation must not leave the chassis allocated
    assert AppChassis.get_current_instance().is_default
    return error


@pytest.fixture(autouse=True)
def _no_sky_env(monkeypatch: pytest.MonkeyPatch):
    """Isolates the tests from the OS environment name var"""
    monkeypatch.delenv("SKY_ENVIRONMENT", raising=False)
    monkeypatch.delenv("sky_environment", raising=False)


# ----------------------------------------------------------------------------------------------------------------------
# Default root file `{stem}.$(env).json`, no includes
# ----------------------------------------------------------------------------------------------------------------------

def test_plain_dev():
    """Default root file name is derived from the entry point stem and the `$(env)` macro"""
    with chassis("plain", "dev") as app:
        d = app.descriptor
        assert isinstance(d, Descriptor)
        assert d.chassis is app
        assert d.data == {"name": "plain", "env": "dev", "num": 1, "nested": {"flag": True, "list": [1, 2, 3]}}
        assert d.as_int("num") == 1
        assert d.as_bool("nested/flag") is True
        assert d["nested/list/#2"] == 3


def test_plain_prod():
    """A different environment selects a different root file"""
    with chassis("plain", "prod") as app:
        d = app.descriptor
        assert d.as_str("env") == "prod"
        assert d.as_int("num") == 2
        assert d.as_bool("nested/flag") is False
        assert d.as_list("nested/list") == [4, 5]


def test_plain_env_name_is_case_insensitive():
    """Chassis lowercases the environment name, so `PROD` resolves `plain.prod.json`"""
    with chassis("plain", "PROD") as app:
        assert app.environment == "prod"
        assert app.descriptor.as_str("env") == "prod"


def test_plain_env_from_os_var(monkeypatch: pytest.MonkeyPatch):
    """When the environment is not passed explicitly it is taken from `SKY_ENVIRONMENT`"""
    monkeypatch.setenv("SKY_ENVIRONMENT", "Prod")
    with chassis("plain", None) as app:
        assert app.environment == "prod"
        assert app.descriptor.as_int("num") == 2


def test_plain_factory_default_is_required():
    """The factory is `required` by default"""
    bootload_error("plain", "test", FileChassisDescriptorFactory(), cause=FileNotFoundError)


# ----------------------------------------------------------------------------------------------------------------------
# Required / not required
# ----------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("required", [True, False])
def test_required_root_exists(required: bool):
    """An existing root file is loaded regardless of the `required` flag"""
    with chassis("plain", "dev", FileChassisDescriptorFactory(required=required)) as app:
        assert app.descriptor.as_str("name") == "plain"
        assert app.descriptor.chassis is app


def test_required_root_missing_env_file():
    """Required: missing root file for the environment fails the chassis bootload"""
    error = bootload_error("plain", "test", FileChassisDescriptorFactory(required=True), cause=FileNotFoundError)
    assert "plain.test.json" in error.message
    assert "env=`test`" in error.frm


def test_required_root_missing_stem():
    """Required: missing root file for unknown entry point stem fails"""
    bootload_error("nothing", "dev", FileChassisDescriptorFactory(required=True), cause=FileNotFoundError)


def test_not_required_root_missing_env_file():
    """Not required: missing root file yields an empty descriptor bound to the chassis"""
    with chassis("plain", "test", FileChassisDescriptorFactory(required=False)) as app:
        d = app.descriptor
        assert isinstance(d, Descriptor)
        assert len(d) == 0
        assert d.data == {}
        assert d.chassis is app
        assert d.as_str("name") is None


def test_not_required_root_missing_custom_path():
    """Not required: missing root file specified in config yields an empty descriptor"""
    config = make_config("custom/nope.$(env).json")
    with chassis("plain", "dev", FileChassisDescriptorFactory(required=False), config) as app:
        assert len(app.descriptor) == 0


def test_required_root_missing_custom_path():
    """Required: missing root file specified in config fails"""
    config = make_config("custom/nope.$(env).json")
    error = bootload_error("plain", "dev", FileChassisDescriptorFactory(required=True), config, cause=FileNotFoundError)
    assert "nope.dev.json" in error.message


@pytest.mark.parametrize("required", [True, False])
def test_missing_include_always_fails(required: bool):
    """A missing included file is an error even when the root file is not required"""
    error = bootload_error("missing-incl", "dev", FileChassisDescriptorFactory(required=required),
                           cause=FileNotFoundError)
    assert "does-not-exist.json" in error.message


@pytest.mark.parametrize("required", [True, False])
def test_missing_env_include_fails_only_for_that_env(required: bool):
    """An `$(env)` include may exist for one environment and be missing for another"""
    factory = FileChassisDescriptorFactory(required=required)
    with chassis("partial", "dev", factory) as app:
        assert app.descriptor.data == {"feature": {"enabled": True}}

    error = bootload_error("partial", "prod", factory, cause=FileNotFoundError)
    assert "feature.prod.json" in error.message


@pytest.mark.parametrize("required", [True, False])
def test_invalid_existing_root_always_fails(required: bool):
    """Not required only relaxes a missing root file, an invalid existing one still fails"""
    factory = FileChassisDescriptorFactory(required=required)
    bootload_error("root-list", "dev", factory, cause=ConfigError)
    bootload_error("bad-json", "dev", factory, cause=json.JSONDecodeError)


def test_factory_instance_is_reusable():
    """The same factory instance can bootload multiple chassis sequentially"""
    factory = FileChassisDescriptorFactory()
    for env, num in (("dev", 1), ("prod", 2), ("dev", 1)):
        with chassis("plain", env, factory) as app:
            assert app.descriptor.as_int("num") == num


# ----------------------------------------------------------------------------------------------------------------------
# Custom root path via config `[{app_id}] fs-chassis-descriptor-path`
# ----------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("env", ["dev", "prod"])
def test_custom_path_with_env(env: str):
    """Relative custom path with `$(env)` macro resolves against the entry point dir"""
    config = make_config("custom/chassis.$(env).json")
    with chassis("plain", env, config=config) as app:
        d = app.descriptor
        assert d.data == {"name": "custom-env", "env": env, "shared": COMMON}


@pytest.mark.parametrize("env", ["dev", "prod"])
def test_custom_path_upper_case_env_macro(env: str):
    """The `$(ENV)` macro name is case-insensitive"""
    config = make_config("custom/chassis.$(ENV).json")
    with chassis("plain", env, config=config) as app:
        assert app.descriptor.as_str("env") == env


def test_custom_path_whitespace_is_trimmed():
    """The configured path value is trimmed"""
    config = make_config("   custom/chassis.$(env).json   ")
    with chassis("plain", "dev", config=config) as app:
        assert app.descriptor.as_str("name") == "custom-env"


def test_custom_path_blank_uses_default():
    """A blank configured path falls back to the default `{stem}.$(env).json`"""
    config = make_config("   ")
    with chassis("plain", "dev", config=config) as app:
        assert app.descriptor.as_str("name") == "plain"


def test_custom_path_other_app_section_is_ignored():
    """The path is read only from the section named after the app id"""
    config = make_config("custom/chassis.$(env).json", app_id="otherapp")
    with chassis("plain", "dev", config=config) as app:
        assert app.descriptor.as_str("name") == "plain"


@pytest.mark.parametrize("env, server", [("dev", "localhost"), ("prod", "db.prod.azist")])
def test_custom_path_without_env_with_env_includes(env: str, server: str):
    """A root path without `$(env)` is the same file for all envs, but its `$(env)` includes still vary"""
    config = make_config("custom/chassis.json")
    with chassis("plain", env, config=config) as app:
        d = app.descriptor
        assert d.as_str("name") == "custom-noenv"
        assert d.as_dict("shared") == COMMON
        assert d.as_str("db/server") == server
        assert d.as_dict("db/timeouts") == TIMEOUTS


@pytest.mark.parametrize("env", ["dev", "prod"])
def test_custom_path_absolute(env: str):
    """An absolute configured path with `$(env)` is used as-is"""
    config = make_config(os.path.join(CFG_DIR, "custom", "chassis.$(env).json"))
    with chassis("plain", env, config=config) as app:
        assert app.descriptor.as_str("env") == env


def test_custom_path_unsupported_extension():
    """Only JSON files are supported"""
    config = make_config("custom/chassis.yaml")
    error = bootload_error("plain", "dev", config=config, cause=ValueError)
    assert "Unsupported config file format" in error.message


def test_custom_path_unknown_macro_fails():
    """Only `$(env)` is supported at bootload; an unresolvable macro fails"""
    config = make_config("custom/chassis.$(azos_no_such_bootload_macro).json")
    bootload_error("plain", "dev", config=config, cause=ConfigError)


@pytest.mark.parametrize("env, expected", [("dev", "custom-env"), ("prod", "custom-noenv")])
def test_custom_path_from_colocated_ini(env: str, expected: str):
    """Path is read from co-located `{stem}-{env}.ini` when the chassis loads its own config"""
    app = AppChassis("iniapp", ep("ini"), env, None, FileChassisDescriptorFactory())
    try:
        assert app.config.get("iniapp", CONFIG_FILE_DESCRIPTOR_PATH_ATTR).endswith(".json")
        assert app.descriptor.as_str("name") == expected
        assert app.descriptor.as_dict("shared") == COMMON
    finally:
        app.dispose()


# ----------------------------------------------------------------------------------------------------------------------
# Includes: with and without `$(env)`, nested, mixed
# ----------------------------------------------------------------------------------------------------------------------

def test_includes_dev():
    """All include combinations for `dev`"""
    with chassis("incl", "dev") as app:
        assert app.descriptor.data == {
            "name": "incl",
            "env": "dev",
            "common": COMMON,
            "db": {"server": "localhost", "pool": 5, "timeouts": TIMEOUTS},
            "servers": [{"host": "a.azist", "weight": 1}, {"host": "b.azist", "weight": 2}, "literal"],
            "tags": ["alpha", "beta"],
            "port": 8080,
            "logging": {"level": "info", "sinks": [{"type": "console"}]},
        }


def test_includes_prod():
    """All include combinations for `prod`"""
    with chassis("incl", "prod") as app:
        assert app.descriptor.data == {
            "name": "incl",
            "env": "prod",
            "common": COMMON,
            "db": {"server": "db.prod.azist", "pool": 50, "timeouts": TIMEOUTS},
            "servers": [{"host": "a.azist", "weight": 1}, {"host": "b.azist", "weight": 2}, "literal"],
            "tags": ["alpha", "beta"],
            "port": 8080,
            "logging": {
                "level": "info",
                "sinks": [{"type": "file", "path": "/var/log/app.log"}, {"type": "otel"}],
            },
        }


@pytest.mark.parametrize("env", ["dev", "prod"])
def test_include_without_env_is_same_for_all_envs(env: str):
    """Includes without `$(env)` resolve to the same files for every environment"""
    with chassis("incl", env) as app:
        d = app.descriptor
        assert d.as_dict("common") == COMMON
        assert d.as_list("tags") == ["alpha", "beta"]
        assert d.as_int("port") == 8080
        assert d.as_str("servers/#0/host") == "a.azist"
        assert d.as_int("servers/#1/weight") == 2
        assert d.as_str("servers/#2") == "literal"


@pytest.mark.parametrize("env, pool", [("dev", 5), ("prod", 50)])
def test_env_include_with_nested_include_without_env(env: str, pool: int):
    """An `$(env)`-specific include may in turn include an environment-agnostic file"""
    with chassis("incl", env) as app:
        d = app.descriptor
        assert d.as_int("db/pool") == pool
        assert d.as_int("db/timeouts/connect") == 3000
        assert d.as_int("db/timeouts/command") == 15000


@pytest.mark.parametrize("env, sink_types", [("dev", ["console"]), ("prod", ["file", "otel"])])
def test_include_without_env_with_nested_env_include(env: str, sink_types: list[str]):
    """An environment-agnostic include may in turn include an `$(env)`-specific file"""
    with chassis("incl", env) as app:
        d = app.descriptor
        assert d.as_str("logging/level") == "info"
        assert [s["type"] for s in d.as_list("logging/sinks")] == sink_types # pyright: ignore[reportOptionalIterable, reportGeneralTypeIssues]


def test_nested_includes_resolve_against_entry_point_dir():
    """`parts/logging.json` includes `parts/sinks...` which must resolve against the entry point dir,
    not the including file dir (that would be `parts/parts/sinks...` which does not exist)"""
    assert not os.path.exists(os.path.join(CFG_DIR, "parts", "parts"))
    with chassis("incl", "dev") as app:
        assert app.descriptor.as_str("logging/sinks/#0/type") == "console"


def test_include_root_pragma():
    """The root itself may be an include pragma which resolves to a map"""
    with chassis("root-incl", "dev") as app:
        assert app.descriptor.data == {"name": "plain", "env": "dev", "num": 1,
                                       "nested": {"flag": True, "list": [1, 2, 3]}}


def test_include_root_pragma_to_list_fails():
    """The root include must resolve to a map"""
    error = bootload_error("root-incl-list", "dev", cause=ConfigError)
    assert "must be a JSON map object" in error.message


def test_include_pragma_syntax():
    """Only whole-string pragmas are processed; surrounding/inner whitespace is allowed"""
    with chassis("pragma", "dev") as app:
        d = app.descriptor
        assert d.as_dict("spaced") == COMMON
        assert d.as_str("upper/server") == "localhost"
        assert d.as_str("inline", verbatim=True) == "see #include<parts/common.json>"
        assert d.as_str("trailing", verbatim=True) == "#include<parts/common.json> extra"
        assert d.as_str("no-brackets", verbatim=True) == "#include parts/common.json"
        assert d.as_str("plain") == "just text"
        assert d.as_int("deep/list/#0/x") == 8080


def test_custom_root_path_to_include_tree():
    """A custom root path (different from the entry point stem) may point to a file with includes"""
    with chassis("custom", "prod", config=make_config("incl.$(env).json")) as app:
        d = app.descriptor
        assert d.as_str("name") == "incl"
        assert d.as_str("db/server") == "db.prod.azist"
        assert d.as_dict("db/timeouts") == TIMEOUTS


@pytest.mark.parametrize("env", ["dev", "prod"])
def test_absolute_root_with_relative_and_absolute_includes(env: str, tmp_path):
    """Absolute root outside the tree: relative includes still resolve against the entry point dir,
    absolute includes (with and without `$(env)`) are used as-is"""
    root = tmp_path / f"root.{env}.json"
    root.write_text(json.dumps({
        "relative": "#include<parts/common.json>",
        "relative_env": "#include<parts/sinks.$(env).json>",
        "absolute": f"#include<{os.path.join(CFG_DIR, 'parts', 'tags.json')}>",
        "absolute_env": f"#include<{os.path.join(CFG_DIR, 'parts', 'db.$(env).json')}>",
    }), encoding="utf-8")

    config = make_config(str(tmp_path / "root.$(env).json"))
    with chassis("plain", env, config=config) as app:
        d = app.descriptor
        assert d.as_dict("relative") == COMMON
        assert len(d.as_list("relative_env")) == (1 if env == "dev" else 2) # type: ignore
        assert d.as_list("absolute") == ["alpha", "beta"]
        assert d.as_int("absolute_env/pool") == (5 if env == "dev" else 50)
        assert d.as_dict("absolute_env/timeouts") == TIMEOUTS


# ----------------------------------------------------------------------------------------------------------------------
# Include errors: depth, circular, bad content
# ----------------------------------------------------------------------------------------------------------------------

def test_include_max_depth_ok():
    """A chain of exactly `MAX_INCLUDES` nested includes is allowed"""
    assert MAX_INCLUDES == 10
    with chassis("deep10", "dev") as app:
        node = app.descriptor.data["chain"]
        levels = []
        while "next" in node:
            levels.append(node["level"])
            node = node["next"]
        levels.append(node["level"])
        assert levels == list(range(2, 12))
        assert node["leaf"] is True


def test_include_max_depth_exceeded():
    """A chain of `MAX_INCLUDES + 1` nested includes fails"""
    error = bootload_error("deep11", "dev", cause=ConfigError)
    assert "maximum depth" in error.message


def test_include_circular():
    """Circular includes are stopped by the depth limit"""
    error = bootload_error("circular", "dev", cause=ConfigError)
    assert "circular" in error.message


def test_include_self_with_env():
    """A root including itself via `$(env)` is circular"""
    bootload_error("selfref", "dev", cause=ConfigError)


def test_include_unsupported_extension():
    """Included files must be JSON as well"""
    bootload_error("badext-incl", "dev", cause=ValueError)


def test_include_malformed_json():
    """Malformed included JSON fails"""
    bootload_error("bad-json-incl", "dev", cause=json.JSONDecodeError)


def test_root_malformed_json():
    """Malformed root JSON fails"""
    bootload_error("bad-json", "dev", cause=json.JSONDecodeError)


def test_root_list_fails():
    """Root must be a JSON map"""
    error = bootload_error("root-list", "dev", cause=ConfigError)
    assert "must be a JSON map object" in error.message


# ----------------------------------------------------------------------------------------------------------------------
# Static helpers
# ----------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("path, expected", [
    ("main.$(env).json", os.path.join(CFG_DIR, "main.qa.json")),
    ("main.$(ENV).json", os.path.join(CFG_DIR, "main.qa.json")),
    ("a/$(env)/b.$(env).json", os.path.join(CFG_DIR, "a", "qa", "b.qa.json")),
    ("main.json", os.path.join(CFG_DIR, "main.json")),
    (os.path.join(os.sep, "abs", "x.$(env).json"), os.path.join(os.sep, "abs", "x.qa.json")),
])
def test_resolve_path(path: str, expected: str):
    assert FileChassisDescriptorFactory.resolve_path(path, CFG_DIR, "qa") == expected


def test_process_includes_no_pragmas_is_identity():
    data = {"a": 1, "b": [1, "x", {"c": None}]}
    assert FileChassisDescriptorFactory.process_includes(data, CFG_DIR, "dev") == {"a": 1, "b": [1, "x", {"c": None}]}


def test_process_includes_scalars_and_lists():
    data = ["#include<parts/port.json>", "#include<parts/tags.json>", "#include<parts/db.$(env).json>"]
    result = FileChassisDescriptorFactory.process_includes(data, CFG_DIR, "prod")
    assert result == [8080, ["alpha", "beta"], {"server": "db.prod.azist", "pool": 50, "timeouts": TIMEOUTS}]


def test_process_includes_same_file_instances_are_independent():
    """Every include of the same file produces its own data instance"""
    data = {"x": "#include<parts/common.json>", "y": "#include<parts/common.json>"}
    result = FileChassisDescriptorFactory.process_includes(data, CFG_DIR, "dev")
    assert result["x"] == result["y"] == COMMON
    assert result["x"] is not result["y"]


def test_load_data_from_file_missing():
    with pytest.raises(FileNotFoundError):
        FileChassisDescriptorFactory.load_data_from_file(os.path.join(CFG_DIR, "nope.json"))


# ----------------------------------------------------------------------------------------------------------------------
# JSONC comments
# ----------------------------------------------------------------------------------------------------------------------

COMMENTS_LIST = ["alpha", "/* beta */", "// gamma", "'//' \"/*\" \"\"\"*/\"\"\""]


def test_comments_root_and_includes():
    """Both `//` and `/* */` comments are stripped from the root and (nested) included files,
    while comment markers inside string literals are kept"""
    with chassis("comments", "dev") as app:
        d = app.descriptor
        assert d.as_str("name") == "comments"
        assert d.as_str("env") == "dev"
        assert d.as_str("url", verbatim=True) == "https://azist.com/path//double//slash"
        assert d.as_str("dq", verbatim=True) == "a // not a comment /* not a block */ b"
        assert d.as_str("sq", verbatim=True) == "'// single quoted line' and '/* single quoted block */'"
        assert d.as_str("tq", verbatim=True) == '""" // triple quoted line /* triple quoted block */ """'
        assert d.as_str("escaped", verbatim=True) == 'say "// hi" and \\'
        assert d.as_str("path", verbatim=True) == "c:\\dir\\"
        assert d.as_str("only_slashes", verbatim=True) == "//"
        assert d.as_str("only_block", verbatim=True) == "/**/"
        assert d.as_list("nums") == [1, 2, 3]
        assert d.as_list("list") == COMMENTS_LIST

        assert d.as_dict("part") == {
            "company": "Azist",
            "motto": "it's /* not */ a comment, // really",
            "quote": '"""/* triple */""" and \'// single\'',
            "nested": COMMENTS_LIST,
        }


def test_comments_only_expected_keys():
    """Commented-out keys never make it into the data"""
    with chassis("comments", "dev") as app:
        data = app.descriptor.data
        assert set(data.keys()) == {"name", "env", "url", "dq", "sq", "tq", "escaped", "path",
                                    "only_slashes", "only_block", "nums", "part", "list"}
        assert "commented_out" not in data["part"]
        assert "also_commented_out" not in data["part"]
        assert "skipped" not in data["list"]


def test_comments_load_data_from_file_list():
    """An included list file with comments loads standalone"""
    assert FileChassisDescriptorFactory.load_data_from_file(os.path.join(CFG_DIR, "parts", "comments-b.json")) == COMMENTS_LIST


@pytest.mark.parametrize("src, expected", [
    ('{"a": 1} // tail', {"a": 1}),
    ('{"a": /* x */ 1}', {"a": 1}),
    ('{"a": "// x"}', {"a": "// x"}),
    ('{"a": "/* x */"}', {"a": "/* x */"}),
    ('{"a": "\'// x\'"}', {"a": "'// x'"}),
    ('{"a": "\'/* x */\'"}', {"a": "'/* x */'"}),
    ('{"a": "\\"\\"\\" // x \\"\\"\\""}', {"a": '""" // x """'}),
    ('{"a": "\\"\\"\\" /* x */ \\"\\"\\""}', {"a": '""" /* x */ """'}),
    ('{"a": "\\\\"} // "b"', {"a": "\\"}),
    ('{"a": "x"} /* it\'s "open */', {"a": "x"}),
    ('{"a": 1, /* "b": 2, */ "c": 3}', {"a": 1, "c": 3}),
    ('{"a": 1,\n// "b": 2,\n"c": 3}', {"a": 1, "c": 3}),
])
def test_comments_in_file(tmp_path, src: str, expected: Any):
    """Comments in a file are stripped, comment-like content of string literals is preserved"""
    fn = tmp_path / "c.json"
    fn.write_text(src, encoding="utf-8")
    assert FileChassisDescriptorFactory.load_data_from_file(str(fn)) == expected


def test_comments_block_keeps_line_numbers(tmp_path):
    """Multi-line block comments keep their line breaks, so JSON errors report original line numbers"""
    fn = tmp_path / "c.json"
    fn.write_text('{\n/*\n\n\n*/\n"a": oops\n}', encoding="utf-8")
    with pytest.raises(json.JSONDecodeError) as exc_info:
        FileChassisDescriptorFactory.load_data_from_file(str(fn))
    assert exc_info.value.lineno == 6
