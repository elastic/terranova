#
# Copyright (c) 2024 Elastic.
#
# This file is part of terranova.
# See https://github.com/elastic/terranova for further info.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import os
import re
import sys
from pathlib import Path

from sh import ErrorReturnCode, gh, git

from scripts.utils import Constants, read_project_conf


def __set_version(version: str) -> None:
    # Update app version
    try:
        Constants.TERRANOVA_INIT_PATH.write_text(f"""__version__ = \"{version}\"\n""")
    except Exception as err:
        print(f"The `{Constants.TERRANOVA_INIT_PATH.as_posix()}` file can't be written", file=sys.stderr)
        raise err

    # Update project version
    try:
        data = Constants.PYPROJECT_PATH.read_text()
    except Exception as err:
        print(f"The `{Constants.PYPROJECT_PATH.as_posix()}` can't be read", file=sys.stderr)
        raise err

    data = re.sub(r"version = \"(.+)\"", f'version = "{version}"', data, count=1)
    try:
        Constants.PYPROJECT_PATH.write_text(data)
    except Exception as err:
        print(f"The `{Constants.PYPROJECT_PATH.as_posix()}` file can't be written", file=sys.stderr)
        raise err


def pre() -> None:
    # Ensure we have inputs
    release_version = os.getenv("RELEASE_VERSION")
    if not release_version:
        return print("You must define `RELEASE_VERSION` environment variable.", file=sys.stderr)
    if not re.match(r"(\d){1,2}\.(\d){1,2}\.(\d){1,2}", release_version):
        return print("The `RELEASE_VERSION` should match semver format.", file=sys.stderr)

    # Create a new branch
    branch_name = f"release/v{release_version}"
    git("checkout", "-b", branch_name, _out=sys.stdout, _err=sys.stderr)

    # Update all files
    __set_version(release_version)

    # Push release branch
    git("add", "--all", _out=sys.stdout, _err=sys.stderr)
    git("commit", "-m", f"release: terranova v{release_version}", "--no-verify", _out=sys.stdout, _err=sys.stderr)
    git("push", "origin", branch_name, _out=sys.stdout, _err=sys.stderr)

    # Create a PR
    gh(
        "pr",
        "create",
        "--fill",
        "--base=main",
        f"--head={branch_name}",
        _out=sys.stdout,
        _err=sys.stderr,
    )


def run() -> None:
    # Read project version
    conf = read_project_conf()
    release_version = conf.get("tool.poetry.version")

    # Create the release tag
    try:
        git("tag", release_version)
        git("push", "origin", release_version)
    except ErrorReturnCode:
        return print(f"The release `v{release_version}` already exists.", file=sys.stderr)

    # Create the release
    args = [
        "release",
        "create",
        "--generate-notes",
        "--latest",
        f"--title=terranova v{release_version}",
        release_version,
    ]
    binaries = [file.absolute().as_posix() for file in Path(".").glob("./terranova-*")]
    args.extend(binaries)
    gh(args, _out=sys.stdout, _err=sys.stderr)


def post() -> None:
    # Ensure we have inputs
    next_version = os.getenv("NEXT_VERSION")
    if not next_version:
        return print("You must define `NEXT_VERSION` environment variable", file=sys.stderr)
    if not re.match(r"(\d){1,2}\.(\d){1,2}\.(\d){1,2}-dev", next_version):
        return print("The `NEXT_VERSION` should match semver format.", file=sys.stderr)

    # Create a new branch
    branch_name = f"feat/post-release-v{next_version}"
    git("checkout", "-b", branch_name, _out=sys.stdout, _err=sys.stderr)

    # Update all files
    __set_version(next_version)

    # Push changes
    git("add", "--all", _out=sys.stdout, _err=sys.stderr)
    git(
        "commit",
        "-m",
        "chore: prepare for next iteration",
        "--no-verify",
        _out=sys.stdout,
        _err=sys.stderr,
    )
    git("push", "origin", branch_name, _out=sys.stdout, _err=sys.stderr)

    # Create a PR
    gh(
        "pr",
        "create",
        "--fill",
        "--base=main",
        f"--head={branch_name}",
        _out=sys.stdout,
        _err=sys.stderr,
    )
