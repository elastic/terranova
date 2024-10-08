from click.testing import CliRunner

from terranova import cli
from terranova.cli import main
from tests.e2e.conftest import assert_result


def test_version(runner: CliRunner) -> None:
    result = runner.invoke(main, args=["--version"])
    stdout, _ = assert_result(result)
    assert f"terranova, version {cli.__version__}" in stdout


def test_with_no_command(runner: CliRunner) -> None:
    result = runner.invoke(main, args=[])
    stdout, _ = assert_result(result)
    assert f"Commands" in stdout
