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
import json
import os
import sys
from pathlib import Path

from sh import RunningCommand

from scripts.utils import Constants, detect_poetry, detect_pre_commit


def configure() -> None:
    poetry = detect_poetry()
    poetry("install", "--sync", _out=sys.stdout, _err=sys.stderr)

    # Generate pyright config for Zed
    if os.getenv("ZED_TERM", "false") == "true":
        process: RunningCommand = poetry(
            "env", "info", "-p", _err=sys.stderr, _return_cmd=True
        )  # type: ignore[no-untyped-def]
        project_venv_path = Path(process.stdout.decode(Constants.ENCODING_UTF_8).strip())
        project_venv_name = project_venv_path.name
        venv_path = project_venv_path.parents[0].as_posix()
        if not Constants.PYRIGHTCONFIG_PATH.exists():
            Constants.PYRIGHTCONFIG_PATH.write_text(json.dumps({"venv": project_venv_name, "venvPath": venv_path}))

    # Skip pre-commit if not present
    pre_commit = detect_pre_commit()
    if pre_commit:
        pre_commit("install", _out=sys.stdout, _err=sys.stderr)
    else:
        print("pre-commit isn't installed")
