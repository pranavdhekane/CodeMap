"""Input checks that run before any algorithm gets the data."""

import os

MAX_FILES = 5000
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__"}


class ValidationError(Exception):
    """Raised when the input is not acceptable."""


def validate_project_path(path: str) -> str:
    """Check the folder exists and is a sensible size. Returns the absolute path."""
    full_path = os.path.abspath(path)
    if not os.path.isdir(full_path):
        raise ValidationError(f"Project path is not a folder: {path}")

    py_files = 0
    for _root, dirs, files in os.walk(full_path):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            if name.endswith(".py"):
                py_files += 1
        if py_files > MAX_FILES:
            raise ValidationError(f"Project has more than {MAX_FILES} Python files")

    if py_files == 0:
        raise ValidationError("Project has no Python files")
    return full_path
