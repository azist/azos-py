# Azos-py AI Coding Agent Instructions

> This file contains general instructions for all agents: **Gemini, Claude Code, and Copilot**

> [!warning]
> You may NEVER EVER make any file system changes in any paths HIGHER than this project root,
> that is in any direct or indirect parent directory of this directory or file located in such directory.
> Project root is where this THIS VERY FILE is located and you may never change anything above it. You may only
> change files and directories which are logically on a CHILD path of THIS directory

## Project Overview
`azos-py` is a foundational library porting Azos framework concepts (.NET) to Python 3.11+. It provides specialized data
types, application chassis patterns, and structured logging for distributed/containerized environments.

## Build System & Workflow

Uses **uv** (not pip/poetry) for all package management:
```bash
# Setup - ONE command to initialize venv
uv .venv

# Install with extras (always use editable mode for dev)
uv pip install -e ".[apm,dev]"

# Build artifacts
uv build

# Run tests (pytest configured in pyproject.toml)
uv run pytest
```

**Critical**: Never use `python -m pip` or `poetry`. Always use `uv pip` or `uv run`.

## Core Architecture Patterns

### 1. Atoms - Efficient String-as-Int Type
Located in [src/azos/azatom.py](src/azos/azatom.py). Atoms encode 1-8 character strings (charset: `[0-9a-zA-Z_-]`) into
64-bit integers for performance.

**Usage Pattern**:

> [!important]
> The whole point of atoms is to NOT allocate/encode them all the time (e.g. in loops)
> but use system constants effectively getting rid of strings and using integers instead.

```python
from azos.azatom import Atom, encode, decode

# Prefer the Atom class wrapper
status = Atom("active")  # or Atom(1634560356)
if status == Atom("active"):  # Fast int comparison internally
    ...

# Direct encode/decode for one-off conversions
id_int = encode("abc-def")  # Returns: 28821928557109857
name = decode(id_int)        # Returns: "abc-def"
```

**Key Constraints**:
- Max 8 ASCII characters from `[0-9a-zA-Z_-]` charset
- Empty/None → 0 (Atom.ZERO)
- Invalid chars/length raise `AzosError`
- Internal caching in `decode()` - reuses strings

### 2. EntityId - Hierarchical Identity Vectors
Located in [src/azos/azentityid.py](src/azos/azentityid.py). Format: `type.schema@system::address`

**Parsing Examples**:
```python
from azos.azentityid import EntityId, tryparse

# Full format
sys, type, schema, addr = tryparse("car.vin@dealer::1A8987339HBz0909W874")

# System-only (type/schema optional)
sys, type, schema, addr = tryparse("dealer::I9973OD")
# type.is_zero == True, schema.is_zero == True

# Type without schema
sys, type, schema, addr = tryparse("car@dealer::ABC123")
# schema.is_zero == True
```

**Critical**: `address` part can contain JSON, URLs, or any string. System/type/schema are always Atoms.

### 3. Application Chassis Pattern
Located in [src/azos/application.py](src/azos/application.py). Singleton-like pattern for app lifecycle.

**Setup in main.py**:
```python
from azos.application import Application

app = Application(
    app_id="myapp",           # Short atom recommended
    ep_path=__file__,         # Entry point file path
    environment_name="prod"   # Or set SKY_ENVIRONMENT env var
)

# Access anywhere via singleton
current = Application.get_current_instance()
config = current.config  # ConfigParser loaded from {stem}-{env}.ini
```

**Config File Convention**: `main-dev.ini`, `main-prod.ini` co-located with entry point.

### 4. Structured Logging (APM)
Located in [src/azos/apm/log.py](src/azos/apm/log.py). Outputs newline-delimited JSON for K8s/log aggregators.

**Setup Pattern**:
```python
# Just import the module - tyhe stup is domne automatically based on app chassis
import  azos.apm.log
```

**Correlation IDs**:
```python
# Create correlation ID for request tracing
correlation_id = new_log_id()

# Add to logs via extra dict
logger.info("Processing request", extra={
    "sys_rel": correlation_id,      # Related/correlation ID
    "sys_channel": "oplog",          # Channel override
    "user_id": 123                   # Custom data fields
})
```

**Log Schema Fields** (output JSON):
- `id`: Unique event ID (auto-generated UUID)
- `rel`: Correlation/related ID for tracing
- `chn`: Channel (app/otel/oplog/sec/anl)
- `lvl`: Log level (DEBUG/INFO/ERROR...)
- `utc`: Unix timestamp in milliseconds
- `app`/`ain`: App ID and instance tag from Application chassis
- `msg`: Formatted message
- `d`: Dict of custom data fields from `extra` (excludes sys_* prefix)

### 5. OpenTelemetry Integration
Located in [src/azos/apm/otel.py](src/azos/apm/otel.py). Auto-enriches logs with trace context.

**Pattern**: Just import the module - it patches logging automatically:
```python
from azos.apm import otel  # Hooks into log enrichment

# Logs now include 'oti' (trace ID) and 'ots' (span ID)
```

## Exception Handling

Custom exception: `AzosError` from [src/azos/azexceptions.py](src/azos/azexceptions.py)

**Usage**:
```python
from azos.azexceptions import AzosError

raise AzosError(
    message="Invalid atom character",
    topic="atom",
    frm="encode(`bad value`)",  # Formatted as func(`args`)
    src=0                        # Error code (int)
)
```

## Testing Conventions

- Test files: `*_tests.py` or `test_*.py` in [tests/](tests/)
- Framework: pytest with unittest compatibility
- Run: `uv run pytest`

**Example Pattern** (see [tests/atom_tests.py](tests/atom_tests.py)):
```python
import pytest
from azos.azexceptions import AzosError

def test_feature_01():
    """Docstring describes what this specific case tests"""
    assert expected == actual

def test_error_case():
    """Use pytest.raises for exception validation"""
    with pytest.raises(AzosError) as exc_info:
        dangerous_operation()
    assert exc_info.value.frm == "expected_function(args)"
```

## Code Style & Conventions

1. **Imports**: Group standard lib → third-party → local, separated by blank lines
2. **Constants**: SCREAMING_SNAKE_CASE at module level (e.g., `MAX_ATOM_LENGTH`)
3. **Private Module Functions**: Prefix with `__` (e.g., `__validate_char`)
4. **Properties**: Use `@property` decorator for read-only attributes
5. **Type Hints**: Required for public APIs (use `|` for unions, not `Union`)
6. **Docstrings**: Triple-quoted on public functions/classes

## File System Boundary
**CRITICAL**: Never modify files above the project root, that is where `pyproject.toml` is located.

## Publishing
TestPyPI first, then PyPI. Uses `uv publish` with env vars:
- `UV_PUBLISH_TOKEN`: API token
- `UV_PUBLISH_URL`: Feed URL (defaults to pypi.org)

## Key Files Reference
- [pyproject.toml](pyproject.toml): Dependencies, build config, pytest settings
- [src/azos/azatom.py](src/azos/azatom.py): Atom encode/decode + class
- [src/azos/azentityid.py](src/azos/azentityid.py): EntityId parsing/class
- [src/azos/application.py](src/azos/application.py): Application chassis
- [src/azos/apm/log.py](src/azos/apm/log.py): Structured logging implementation
- [toys/](toys/): Example applications showing usage patterns
