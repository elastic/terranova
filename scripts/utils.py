import os
import sys
from pathlib import Path
from typing import Any, Final

import toml
from dotty_dict import dotty
from sh import Command, CommandNotFound
from toml import TomlDecodeError


class Constants:
    """All constants"""

    # pylint: disable=R0903
    ENCODING_UTF_8: Final[str] = "utf-8"
    PYPROJECT_PATH: Final[Path] = Path("pyproject.toml")
    TERRANOVA_INIT_PATH: Final[Path] = Path("./terranova/__init__.py")
    REGISTRY_URL: str = os.getenv("REGISTRY_URL", "local.dev")


def read_project_conf() -> dict[str, Any]:
    """
    Read project configuration and returns a dict configuration.
    Returns:
        dict configuration.
    Raises:
        TomlDecodeError: if the `pyproject.toml` isn't valid.
    """
    try:
        return dotty(toml.load(Constants.PYPROJECT_PATH.absolute().as_posix()))
    except TomlDecodeError as err:
        print("The `pyproject.toml` file isn't valid", file=sys.stderr)
        raise err


def container_backend() -> tuple[Command, dict[str, str]]:
    """
    Try to detect a container backend.
    Either podman or docker.

    Returns:
        a command if a backend is detected.
    Raises:
        CommandNotFound: if a suitable backend can't be found.
    """
    cmd = None
    env = os.environ.copy()
    for backend in ["docker", "podman"]:
        try:
            cmd = Command(backend)
        except CommandNotFound:
            continue
        if "podman" == backend:
            env["BUILDAH_FORMAT"] = "docker"
        break

    if not cmd:
        raise CommandNotFound("Unable to find a suitable backend: docker or podman")
    return cmd, env
