# azos-py
Provides Azos base types and services functionality for Python apps

**ver 0.2.1 20251227 DKh** <br>
ver 0.1.1 20251218 DKh <br>
ver 0.0.1 20230701 DKh

## Instructions

This project uses modern Python build management system `uv` which you get here:
https://docs.astral.sh/uv/guides/install-python/

### 1. Init Virtual environment
Virtual environment setup
```bash
uv .venv
```

### 2. Install package
Install your package (in editable mode for development): This is like referencing a project in a .NET solution.
Changes to code are reflected immediately without rebuilding.

```bash
uv pip install -e ".[apm,dev]"
```

### 3. Build wheel

Build the artifacts (Wheel and Tarball): This creates the `dist/` folder containing your `.whl` file
```bash
uv build
```

### 4. Publishing package
Only if you need to publish, this does not apply if you consume the pre-published package.
Assuming manual publish:

> Go to TestPyPi(https://test.pypi.org/account/register/) and register an account.
> Then go to Account Settings -> API Tokens and generate a token with "Entire Account" scope.
> Note: Do this for the real PyPI(https://pypi.org/) later when you are ready for production.

```bash
# 1. TestPyPI (test.pypi.org): The sandbox. Always deploy here first.
# 2. PyPI (pypi.org): The real production repository (analogous to nuget.org).

# UV Supports env Vars, set yours:
export UV_PUBLISH_TOKEN=....	# The API token (starts with pypi-).
export UV_PUBLISH_URL=....	# The URL of the feed (defaults to PyPI if omitted).

uv build
uv publish
```

If you use private artifactory (e.g. Azure):
```bash
uv publish \
  --publish-url https://pkgs.dev.azure.com/my-org/_packaging/my-feed/pypi/upload \
  --username "my-user" \
  --password "my-pat-token"
```


### 5. Consuming package
You install and consume `azos` package normally:

```python
# Importing from the main package
import azos

# Importing from the subpackage
from azos.apm.log import new_log_id

# Accessing the functionality
rel = new_log_id()
```
