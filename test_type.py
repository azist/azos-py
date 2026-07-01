import contextlib
from typing import Any

def test_it(c: Any):
    if isinstance(c, contextlib.AbstractContextManager):
        c.__enter__()
