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
