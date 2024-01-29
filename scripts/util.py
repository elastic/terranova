import sys
from pathlib import Path
from typing import Any

import toml
from dotty_dict import dotty
from toml import TomlDecodeError


def read_project_conf() -> dict[str, Any]:
    """
    Read project configuration and returns a dict configuration.
    Returns:
        dict configuration.
    Raises:
        TomlDecodeError: if the `pyproject.toml` isn't valid.
    """
    try:
        return dotty(toml.load(Path("pyproject.toml").absolute().as_posix()))
    except TomlDecodeError as err:
        print("The `pyproject.toml` file isn't valid", file=sys.stderr)
        raise err
