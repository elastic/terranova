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
import sys

from sh import ErrorReturnCode, git, poetry, pylint

from scripts.utils import fatal


def git_branch_delete(branch_name: str) -> None:
    """Delete a git branch if exists."""
    try:
        git("branch", "-D", branch_name)
    except ErrorReturnCode:
        pass


def check_pylint() -> None:
    print("Checking codebase")
    try:
        pylint("terranova", _out=sys.stdout, _err=sys.stderr)
    except ErrorReturnCode as err:
        # Forward exit code without traceback
        sys.exit(err.exit_code)


def check_license_headers() -> None:
    print("Checking license headers")
    head_commit_hash = git("rev-parse", "HEAD", _err=sys.stderr).strip()
    current_branch_name = git("rev-parse", "--abbrev-ref", "HEAD").strip()
    branch_name = f"automation/lint-{head_commit_hash}"
    try:
        # Prepare the branch
        git_branch_delete(branch_name)
        git("checkout", "-b", branch_name, _in=sys.stdin, _out=sys.stdout, _err=sys.stderr)

        # Apply headers licence
        poetry("poe", "project:license", _in=sys.stdin, _out=sys.stdout, _err=sys.stderr)

        # Validate
        changes = git("status", "-s", _err=sys.stderr).strip()
        if changes:
            fatal(f"Apply headers license to:\n{changes}")
    finally:
        git("checkout", current_branch_name)
        git_branch_delete(branch_name)


def run() -> None:
    check_pylint()
    check_license_headers()
