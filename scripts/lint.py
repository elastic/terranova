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
import sys
from io import StringIO

from terranova.process import ErrorReturnCode

from scripts.utils import detect_git, detect_ruff, detect_uv, fatal


def git_branch_delete(branch_name: str) -> None:
    """Delete a git branch if exists."""
    try:
        git = detect_git()
        git.args("branch", "-D", branch_name).inherit_out().exec()
    except ErrorReturnCode:
        pass


def check_ruff() -> None:
    print("Checking codebase")
    try:
        ruff = detect_ruff()
        ruff.args("check", "terranova").inherit_out().exec()
    except ErrorReturnCode as err:
        # Forward exit code without traceback
        sys.exit(err.exit_code)


def check_license_headers() -> None:
    print("Checking license headers")
    git = detect_git()

    capture_stdout = StringIO()
    git.args("rev-parse", "HEAD").stdout(capture_stdout).stderr(sys.stderr).exec()
    head_commit_hash = capture_stdout.getvalue().strip()

    capture_stdout = StringIO()
    git.args("rev-parse", "--abbrev-ref", "HEAD").stdout(capture_stdout).exec()
    current_branch_name = capture_stdout.getvalue().strip()

    branch_name = f"automation/lint-{head_commit_hash}"
    try:
        # Prepare the branch
        git_branch_delete(branch_name)
        git.args("checkout", "-b", branch_name).inherit().exec()

        # Apply headers licence
        uv = detect_uv()
        uv.args("run", "poe", "project:license").inherit().exec()

        # Validate
        capture_stdout = StringIO()
        git.args("status", "-s").stdout(capture_stdout).stderr(sys.stderr).exec()
        changes = capture_stdout.getvalue().strip()
        if changes:
            fatal(f"Apply headers license to:\n{changes}")
    finally:
        git.args("checkout", current_branch_name).exec()
        git_branch_delete(branch_name)


def run() -> None:
    check_ruff()
    check_license_headers()
