"""
Loader for stock content files.

Stock files are text files that are stored in the package and can be loaded by name using
the `$(stock:filename)` syntax. This is useful for loading predefined templates, configurations, or other
resources that are bundled with the application.
"""

import importlib.resources


def load_text_content(stock_content_file: str) -> str | None:
    """
    Loads the content of a stock file as a string. Returns None if the file is not found.
    """
    try:
        ref = importlib.resources.files(__package__).joinpath("content", stock_content_file)
        return ref.read_text(encoding="utf-8")
    except (FileNotFoundError, TypeError):
        return None