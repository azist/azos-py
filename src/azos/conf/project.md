# Conf Project Defintion

We will build Azos configuration support in Python. We will base Python code on the same canonical standard
which is implemented in Azos C# library.

> The canonical implementation is C# code base, and can be access here:
>   https://github.com/azist/azos/tree/master/src/Azos/Conf

## Architecture

1. In Azos Configuration is an in-memory tree of nodes
2. There are two type of nodes:  `ConfigSectionNode` and `ConfigAttributeNode` both inherit from `ConfigNode`
   Pay Attention to features like:
   - Node path navigation
   - Variable interpolation/verbatim vars
   - Value accessors with type conversion. In Python not all types available so we need to create Python -types like float, int, string, bool, date. Special types `Atom` and `EntityId` are already ported `atom.py` and `entityid.py`

3. The sections can have children, attribute node can not have children
4. See https://github.com/azist/azos/blob/master/src/Azos/Conf/ConfigNode.cs  C# file for details. We will need to port most of the logic
5. The abstract base `ConfigNode` has main properties: `name` and `value`
6. Pay attention to value accessors `asInt`, `asBool` etc. we already ported `atom.py` and `entityid.py`
7. The configuration storage format is a separate concept from the configuration tree
8. `Configuration` object is the root of the `ConfigSectionNode` root node of the tree
9. Configuration format reader/writer would be separate from configuration object
10. Laconic format is used in C# `LaconicConfiguration` which is based on `LACONFIG LANGUAGE` lexer described here: https://github.com/azist/azos/blob/master/src/Azos/CodeAnalysis/Laconfig/LACONFIG_LANGUAGE.md
11. The Laconic parser uses LACONFIG lexer to build a configuration tree out of Laconfig content (such as a string)
12. In Future we would be able to add other configurations (e.g. JSON or XML) which will populate the same `Configuration` structures.

## High Level Tasks

> All Python code will adhere to AGENTS.md instructions in the root here. All generated code will go under `/conf` subdirectory. Only unit tests will go under `/tests/conf...`

Plan the following artifacts, step by step and create individual sub tasks in the adjacent file called "tasks.md":

1. [ ] Create `nodes.py` with `ConfigNode`, `ConfigSectionNode`, `COnfigAttributeNode` mimicking C# design
2. [ ] Create `configuration.py` with `Configuration` class that contains the root node exposed via `root` property
3. [ ] Create `laconfig_lexer.py` with the Lexer driven by "LACONFIG_LANGUAGE.md" from github link above
4. [ ] Create `laconfig_parser.py` with the finite state machine see "https://github.com/azist/azos/blob/master/src/Azos/CodeAnalysis/Laconfig/LaconfigParser.cs" which will build the `Configuration` object
5. [ ] Create a unit test suite under `/test/conf` to mimic C# tests found here:
    - [ ] https://github.com/azist/azos/blob/master/src/testing/Azos.Tests.Nub/Configuration/LaconicRoundtripTests.cs
    - [ ] https://github.com/azist/azos/blob/master/src/testing/Azos.Tests.Nub/Configuration/LaconicTests.cs



