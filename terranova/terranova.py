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
from pathlib import Path

import click

from . import __version__
from .commands import (
    apply,
    define,
    destroy,
    docs,
    fmt,
    get,
    graph,
    init,
    output,
    plan,
    runbook,
    taint,
    validate,
)
from .utils import SharedContext


@click.group("terranova")
@click.option("--debug", help="Enable debug mode.", is_flag=True, default=False)
@click.option(
    "-v",
    "--verbose",
    help="Make the operation more talkative.",
    is_flag=True,
    default=False,
)
@click.option(
    "--conf-dir",
    help="Conf directory path.",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    envvar="TERRANOVA_CONF_DIR",
    default="./conf",
)
@click.version_option(__version__)
def main(debug: bool, verbose: bool, conf_dir: Path) -> None:
    """Terranova is a thin wrapper for Terraform that provides extra tools and logic to handle Terraform configurations at scale."""
    SharedContext.init(debug, verbose, conf_dir)


# Register commands
main.add_command(apply)
main.add_command(define)
main.add_command(destroy)
main.add_command(docs)
main.add_command(fmt)
main.add_command(get)
main.add_command(graph)
main.add_command(init)
main.add_command(output)
main.add_command(plan)
main.add_command(runbook)
main.add_command(taint)
main.add_command(validate)
