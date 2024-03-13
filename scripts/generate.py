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

from sh import pyinstaller


def run() -> None:
    args = ["-n", "terranova", "--onefile", "--noconfirm"]
    args.extend(
        [
            "--add-data",
            "terranova/schemas/:terranova/schemas/",
            "--add-data",
            "terranova/templates/:terranova/templates/",
            "./bin/terranova",
        ]
    )
    pyinstaller(args, _out=sys.stdout, _err=sys.stderr)
