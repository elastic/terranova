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

from scripts.utils import detect_pyinstaller


def run() -> None:
    args = ["-n", "terranova", "--onefile", "--noconfirm", "--optimize=2"]
    exclude_modules = ()
    for exclude_module in exclude_modules:
        args.extend(["--exclude-module", exclude_module])

    hidden_imports = ()
    for hidden_import in hidden_imports:
        args.extend(["--hidden-import", hidden_import])

    args.extend(
        [
            "--add-data",
            "terranova/schemas/:terranova/schemas/",
            "--add-data",
            "terranova/templates/:terranova/templates/",
            "./bin/terranova",
        ]
    )
    pyinstaller = detect_pyinstaller()
    pyinstaller(args, _out=sys.stdout, _err=sys.stderr)
