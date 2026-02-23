# Codebase Audit Report

**Date:** 2026-02-22
**Project:** azos-py

This report outlines the findings of a 3-agent inspection team focusing on Security, Python Idioms, and Software Architecture.

---

## 1. Security Specialist Report

### 1.1 Path Traversal Vulnerability
*   **File:** `src/azos/chassis.py`
*   **Function:** `process_includes`
*   **Issue:** The function processes `#include<filename>` directives by joining the filename with a `root_path`. It does not explicitly sanitize the filename or prevent directory traversal sequences (`../`).
*   **Risk:** A malicious configuration file could reference files outside the intended directory (e.g., `#include<../../../../etc/passwd>`), leading to arbitrary file read vulnerabilities.
*   **Recommendation:** Validate that the resolved path starts with the `root_path` before reading.

### 1.2 Recursive Variable Expansion
*   **File:** `src/azos/chassis.py`
*   **Function:** `expand_var_expressions`
*   **Issue:** The system supports recursive variable expansion (`$(var1)` -> `$(var2)`). While limited to a depth of 10 (`INCLUDE_MAX_DEPTH`), complex recursive logic in configuration parsing is a common source of Denial of Service (DoS) or unexpected behavior.
*   **Recommendation:** Ensure strictly bounded recursion and consider disabling recursive expansion if not strictly necessary.

### 1.3 Broad Exception Handling
*   **General Observation:** The `process_includes` function (and others) may implicitly trust file operations. Error handling logic in `DIContainer` and `Atom` is custom (`AzosError`), but care must be taken to ensure standard Python exceptions (like `MemoryError` or `SystemExit`) are not inadvertently suppressed or mishandled in higher-level blocks (though none were explicitly flagged in the inspected snippets).

---

## 2. Python Idiom Expert Report

### 2.1 Non-Idiomatic Type Checking
*   **File:** `src/azos/atom.py`
*   **Location:** `Atom.__init__`
*   **Issue:** Usage of `type(val) == str` prevents inheritance compatibility.
*   **Correction:** Use `isinstance(val, str)`.

### 2.2 Inefficient String Concatenation
*   **File:** `src/azos/atom.py`
*   **Location:** `decode` function
*   **Issue:** Strings are concatenated in a loop: `result = result + chr(c)`. This creates a new string object for every iteration, resulting in quadratic time complexity `O(N^2)`.
*   **Correction:** Collect characters in a list and join them at the end: `"".join(chars)`.

### 2.3 Naming Conventions (PEP 8 Violations)
*   **File:** `src/azos/chassis.py`, `src/azos/atom.py`
*   **Issue:**
    *   Argument names use camelCase (e.g., `tDep`, `astr`) instead of snake_case (`dep_type`, `atom_str`).
    *   Method names like `try_get` are Pythonic, but the overall style mimics statically typed languages (Java/C#).
*   **Recommendation:** Rename arguments to `snake_case` to align with standard Python conventions.

### 2.4 "Getter/Setter" Patterns
*   **General Observation:** The codebase heavily utilizes `get_current_instance()` and `set_...` style methods rather than relying on Python's properties or context managers where appropriate. While properties are used in `AppChassis`, the static accessor pattern is very un-Pythonic.

---

## 3. Software Architect Report

### 3.1 Aggressive Side-Effects on Import
*   **File:** `src/azos/apm/log.py`
*   **Issue:** The module executes `_activate_az_logging()` at the global scope (end of file). This function:
    1.  Calls `root.handlers.clear()` removing *all* existing log handlers.
    2.  Sets the root logger level to DEBUG.
    3.  Installs its own handler.
*   **Impact:** Merely importing this library hijacks the entire application's logging configuration. This is unacceptable behavior for a library, as it overrides the host application's intent and configuration.
*   **Recommendation:** Move activation logic to an explicit `configure()` or `init()` function that the user must call.

### 3.2 Singleton & Service Locator Anti-Patterns
*   **File:** `src/azos/chassis.py`
*   **Issue:** `AppChassis` relies on global static variables (`__s_current`, `__s_default`) to maintain state. `DIContainer` is used as a Service Locator (`AppChassis.deps`).
*   **Impact:**
    *   **Testing:** It is difficult to run tests in parallel or isolation because the "current app" is a global mutable state.
    *   **Coupling:** Components are tightly coupled to the `AppChassis` global, making them hard to reuse without the entire framework.
*   **Recommendation:** Pass the `AppChassis` or explicit dependencies via constructors (Dependency Injection) rather than having components fetch them from a global static accessor.

### 3.3 Circular Dependencies & Coupling
*   **Observation:** The `log.py` module imports `AppChassis`, and `AppChassis` relies on config parsing which may need logging. The `__app_chassis_load` callback mechanism is an attempt to mitigate this, but it results in a fragile initialization order.

### 3.4 Professionalism
*   **TODOs and Dead Code:**
    *   `src/azos/apm/log.py`: `#todo: implement terse formatter`
    *   `src/azos/atom.py`: Commented out `print` statements (`#print(f"Atom {id}...`) suggest debugging code was left in source.
*   **Magic Strings:** Usage of specific strings like "SKY_ENVIRONMENT" suggests legacy coupling or lack of generalization.
