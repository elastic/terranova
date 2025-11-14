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
import platform
import sys
from io import StringIO
from pathlib import Path
from time import time

from scripts.utils import (
    Constants,
    container_backend,
    detect_git,
    detect_pyinstaller,
    project_version,
)


def run() -> None:
    git = detect_git()
    capture_stdout = StringIO()
    git.args("rev-parse", "--short", "HEAD").stdout(capture_stdout).exec()
    commit_hash_short = capture_stdout.getvalue().strip()
    current_time_epoch = int(time())
    version = project_version()
    python_version = platform.python_version()

    image_id = f"{version}-{current_time_epoch}-{commit_hash_short}"

    # Create dist dir
    local_dist_path = Path("dist")
    local_dist_path.mkdir(parents=True, exist_ok=False)
    local_dist_path = local_dist_path.absolute()

    system = platform.system().lower()
    if system == "darwin":
        pyinstaller = detect_pyinstaller().inherit_out()
        pyinstaller.args("terranova.spec").exec()
        arch = platform.machine()
        arch = "amd64" if arch == "x86_64" else arch
        Path("./dist/terranova").replace(
            Path(f"./dist/terranova-{version}-{system}-{arch}")
        )
    elif system == "linux":
        # Use cross-build to build both amd64 and arm64 versions.
        cmd = container_backend()
        for arch in ["amd64", "arm64"]:
            platform_arch = f"linux/{arch}"
            cmd.args(
                "buildx",
                "build",
                "--load",
                "--platform",
                platform_arch,
                "--build-arg",
                f"base_image_version={python_version}",
                "-t",
                f"{Constants.REGISTRY_URL}/terranova:{image_id}",
                "-f",
                "Containerfile",
                ".",
            ).inherit_out().exec()
            capture_stdout = StringIO()
            cmd.args(
                "run",
                "-d",
                "--platform",
                platform_arch,
                "--entrypoint=cat",
                f"{Constants.REGISTRY_URL}/terranova:{image_id}",
            ).stdout(capture_stdout).exec()
            container_id = capture_stdout.getvalue().strip()
            cmd.args(
                "cp",
                f"{container_id}:/opt/terranova/dist/terranova",
                (local_dist_path / f"terranova-{version}-linux-{arch}").as_posix(),
            ).inherit_out().exec()
            cmd.args(
                "rm",
                "-f",
                container_id,
            ).exec()
    else:
        print(f"Unsupported system: {system}", file=sys.stderr)
