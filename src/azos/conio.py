"""
Azos Console I/O Module
Copyright (C) 2026 Azist, MIT License
"""

# ANSI Escape Codes Class
class ANSIColors:
    """Provides ANSI coloring codes"""

    # Control
    RESET = "\033[0m"

    # Foreground Colors - Low Intensity
    FG_BLACK = "\033[30m"
    FG_RED = "\033[31m"
    FG_GREEN = "\033[32m"
    FG_YELLOW = "\033[33m"
    FG_BLUE = "\033[34m"
    FG_MAGENTA = "\033[35m"
    FG_CYAN = "\033[36m"
    FG_WHITE = "\033[37m"

    # Foreground Colors - High Intensity (Bright)
    FG_BRIGHT_BLACK = "\033[90m"
    FG_BRIGHT_RED = "\033[91m"
    FG_BRIGHT_GREEN = "\033[92m"
    FG_BRIGHT_YELLOW = "\033[93m"
    FG_BRIGHT_BLUE = "\033[94m"
    FG_BRIGHT_MAGENTA = "\033[95m"
    FG_BRIGHT_CYAN = "\033[96m"
    FG_BRIGHT_WHITE = "\033[97m"

    # Background Colors - Low Intensity
    BG_BLACK = "\033[40m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"
    BG_WHITE = "\033[47m"

    # Background Colors - High Intensity (Bright)
    BG_BRIGHT_BLACK = "\033[100m"
    BG_BRIGHT_RED = "\033[101m"
    BG_BRIGHT_GREEN = "\033[102m"
    BG_BRIGHT_YELLOW = "\033[103m"
    BG_BRIGHT_BLUE = "\033[104m"
    BG_BRIGHT_MAGENTA = "\033[105m"
    BG_BRIGHT_CYAN = "\033[106m"
    BG_BRIGHT_WHITE = "\033[107m"


def bright_fg(color: str) -> str:
    """Return bright foreground ANSI code for color name."""
    return get_color_code(color, bright=True, fg=True)


def bright_bg(color: str) -> str:
    """Return bright background ANSI code for color name."""
    return get_color_code(color, bright=True, fg=False)


def dark_fg(color: str) -> str:
    """Return dark/normal foreground ANSI code for color name."""
    return get_color_code(color, bright=False, fg=True)


def dark_bg(color: str) -> str:
    """Return dark/normal background ANSI code for color name."""
    return get_color_code(color, bright=False, fg=False)


def get_color_code(color: str, bright: bool = False, fg: bool = True) -> str:
    """Returns an ANSI console escape code using ANSIColors constants."""
    color_key = color.upper()
    if color_key == "RESET":
        return ANSIColors.RESET

    key = f"{'FG' if fg else 'BG'}{'_BRIGHT' if bright else ''}_{color_key}"
    fallback = (ANSIColors.FG_BRIGHT_WHITE if bright else ANSIColors.FG_WHITE) if fg else ANSIColors.BG_BLACK
    return getattr(ANSIColors, key, fallback)
