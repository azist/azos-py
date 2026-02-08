# Conf Implementation Plan

> This plan follows `AGENTS.md` constraints. All code goes under `src/azos/conf`. Tests go under `tests/conf`.

## 1) Nodes (`nodes.py`)

- [ ] Review C# `ConfigNode.cs` to mirror semantics, naming, and behaviors
- [ ] Define `ConfigNode` base class
  - [ ] Public properties: `name`, `value`, `parent`, `root`, `path`
  - [ ] Identity helpers: `is_root`, `is_section`, `is_attribute`
  - [ ] Navigation: `find_by_path(path)`, `get_child(name)`, `children` iterator
  - [ ] Value accessors with conversion (see section 2)
  - [ ] Variable interpolation pipeline hook (see section 3)
- [ ] Define `ConfigSectionNode`
  - [ ] Child management: `add_child(node)`, `remove_child(node)`, `clear_children()`
  - [ ] Ordered iteration and name-based lookup
  - [ ] Path resolution for sections
- [ ] Define `ConfigAttributeNode`
  - [ ] Leaf-only enforcement (no children)
  - [ ] Attribute-specific accessors and value semantics
- [ ] Ensure public APIs have type hints and docstrings

## 2) Value Accessors & Conversions

- [ ] Implement typed accessors aligned with C#:
  - [ ] `as_str`, `as_int`, `as_float`, `as_bool`, `as_datetime` (or `as_date`)
  - [ ] `as_atom` (use `azos.atom.Atom`)
  - [ ] `as_entityid` (use `azos.entityid.EntityId`)
- [ ] Define conversion rules for empty/null values and errors
- [ ] Add conversion helpers in `nodes.py` (private `__` functions)

## 3) Variable Interpolation

- [ ] Identify canonical syntax from C# (`$(var)`, `$(~env_var)`, verbatim rules)
- [ ] Implement interpolation helper (shared by nodes)
  - [ ] Resolution order (local node → parent → root)
  - [ ] Verbatim escape handling
  - [ ] Cyclic reference detection
- [ ] Add tests for interpolation rules and verbatim cases

## 4) Configuration Root (`configuration.py`)

- [ ] Implement `Configuration` class
  - [ ] `root` property exposes root `ConfigSectionNode`
  - [ ] Convenience accessors: `get(path)`, `exists(path)`
- [ ] Keep storage format decoupled from the tree (no parsing here)

## 5) Laconic Lexer (`laconfig_lexer.py`)

- [ ] Read `LACONFIG_LANGUAGE.md` token definitions
- [ ] Implement lexer:
  - [ ] Token types, values, and source span tracking
  - [ ] Whitespace/comment handling
  - [ ] String/identifier/number parsing
- [ ] Unit tests for lexer tokenization edge cases

## 6) Laconic Parser (`laconfig_parser.py`)

- [ ] Mirror C# `LaconfigParser.cs` FSM
- [ ] Build configuration tree using lexer stream
  - [ ] Section nodes, attribute nodes, nesting rules
  - [ ] Error handling with meaningful messages/positions
- [ ] Roundtrip parse/serialize tests (start with parse-only if no writer)

## 7) Tests (`tests/conf/...`)

- [ ] Create `tests/conf` package
- [ ] Port cases from:
  - [ ] `LaconicRoundtripTests.cs`
  - [ ] `LaconicTests.cs`
- [ ] Add new tests for Python-only behaviors (type conversion, interpolation)

## 8) Validation & Tooling

- [ ] Run focused pytest: `uv run pytest tests/conf`
- [ ] Address failures without touching unrelated modules
