#
# Copyright Elasticsearch B.V. and/or licensed to Elasticsearch B.V. under one
# or more contributor license agreements. See the NOTICE file distributed with
# this work for additional information regarding copyright
# ownership. Elasticsearch B.V. licenses this file to you under
# the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# 	http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
#
import os
import sys
from pathlib import Path
from typing import Final, NoReturn

from sh import Command, CommandNotFound


class Constants:
    """All constants"""

    # pylint: disable=R0903
    ENCODING_UTF_8: Final[str] = "utf-8"
    PYPROJECT_PATH: Final[Path] = Path("pyproject.toml")
    PYRIGHTCONFIG_PATH: Final[Path] = Path("pyrightconfig.json")
    REGISTRY_URL: str = os.getenv("REGISTRY_URL", "local.dev")
    TERRANOVA_INIT_PATH: Final[Path] = Path("./terranova/__init__.py")


def fatal(msg: str, err: Exception | None = None) -> NoReturn:
    """Print error message on stderr and die."""
    print(msg, file=sys.stderr)
    if err:
        print(err, file=sys.stderr)
    sys.exit(1)


def detect_poetry() -> Command:
    """
    Try to detect poetry.

    Returns:
        a command if poetry is detected.
    """
    try:
        return Command("poetry")
    except CommandNotFound:
        fatal("`poetry` isn't detected")


def detect_git() -> Command:
    """
    Try to detect git.
    Returns:
        a command if git is detected.
    """
    try:
        return Command("git")
    except CommandNotFound:
        fatal("`git` isn't installed")


def detect_gh() -> Command:
    """
    Try to detect gh.
    Returns:
        a command if gh is detected.
    """
    try:
        return Command("gh")
    except CommandNotFound:
        fatal("`gh` isn't installed")


def detect_pylint() -> Command:
    """
    Try to detect pylint.
    Returns:
        a command if pylint is detected.
    """
    try:
        return Command("pylint")
    except CommandNotFound:
        fatal("`pylint` isn't installed")


def detect_pyinstaller() -> Command:
    """
    Try to detect pyinstaller.
    Returns:
        a command if pyinstaller is detected.
    """
    try:
        return Command("pyinstaller")
    except CommandNotFound:
        fatal("`pyinstaller` isn't installed")


def detect_pre_commit() -> Command | None:
    """
    Try to detect pre-commit.
    Returns:
        a command if pre-commit is detected.
    """
    try:
        return Command("pre-commit")
    except CommandNotFound:
        return None


def project_version() -> str:
    """
    Returns:
        current project version.
    """
    poetry = detect_poetry()
    version = poetry("version", "-s", _err=sys.stderr)
    return version.strip()


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
