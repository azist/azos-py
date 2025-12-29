# Azos Python (azos-py)

## Project Overview

`azos-py` provides foundational types and service functionality for Python applications, acting as a base library for the Azos ecosystem. It appears to port concepts from the Azos framework (likely .NET-based) to Python, facilitating interoperability and standardized patterns.

**Key Features:**
*   **Atoms:** A specialized data type for efficiently storing short strings (up to 8 characters) as 64-bit integers (`azatom`).
*   **Application Context:** A standardized application bootstrapping and configuration mechanism (`AzosApp`).
*   **Structured Logging:** A robust logging system designed for containerized environments, supporting JSON output, correlation IDs, and OpenTelemetry enrichment (`apm.log`).
*   **Exceptions:** A custom exception hierarchy (`AzosError`).

**Tech Stack:**
*   **Language:** Python 3.11+
*   **Build System:** `uv` (management) with `hatchling` (backend).
*   **Testing:** `unittest` (standard library), `pytest` (runner).
*   **Linting:** `ruff`.

## Architecture & Core Concepts

### 1. Atoms (`azatom.py`)
Atoms are a core primitive used to represent finite sets of values (like enums or IDs) efficiently.
*   **Encoding:** Strings (up to 8 chars, specific charset `[0-9a-zA-Z_-]`) are packed into a `uint64`.
*   **Efficiency:** Allows for integer-based comparisons and storage while retaining human-readable string representations via decoding.
*   **Usage:** Ideal for state flags, type IDs, or other low-cardinality tokens.

### 2. Application Context (`azapp.py`)
Provides a singleton-like entry point (`AzosApp`) for applications.
*   **Responsibilities:** Handles configuration parsing, instance identification (UUID), and lifecycle context.
*   **Bootstrapping:** Initializes the application state from a configuration dictionary.

### 3. Structured Logging (`apm/log.py`)
A specialized logging pipeline replacing the standard Python `logging` formatters.
*   **Schema:** Enforces a strict JSON schema with fields like `id` (event ID), `rel` (related/correlation ID), `chn` (channel), and `app` (application ID).
*   **Output:** `AzLogRecordJsonFormatter` produces newline-delimited JSON, suitable for K8s logging and log aggregators.
*   **Context:** `AzLogStrand` allows creating "strands" of logs that share correlation IDs (`rel`) for tracing conversations or transactions.

## Development Workflow

### Prerequisites
*   Python 3.11 or higher.
*   [uv](https://docs.astral.sh/uv/) installed.

### Setup
1.  Initialize virtual environment:
    ```bash
    uv .venv
    ```
2.  Install dependencies (including dev and APM extras):
    ```bash
    uv pip install -e ".[apm,dev]"
    ```

### Building
Create distribution artifacts (wheel and tarball) in `dist/`:
```bash
uv build
```

### Testing
Run the test suite using `pytest` (configured in `pyproject.toml`):
```bash
uv run pytest
```
Or using the standard library runner:
```bash
python -m unittest discover tests
```

### Linting
Run `ruff` to check code style:
```bash
uv run ruff check .
```

## Key Files

*   `pyproject.toml`: Build configuration, dependencies, and project metadata.
*   `src/azos/azatom.py`: Implementation of the Atom data type (encode/decode logic).
*   `src/azos/azapp.py`: `AzosApp` class definition.
*   `src/azos/apm/log.py`: Logging infrastructure, including `AzLogRecord` and formatters.
*   `src/azos/azexceptions.py`: Custom `AzosError` class.
*   `tests/atom_tests.py`: Unit tests for `azatom`.
