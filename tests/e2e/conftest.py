import pytest
from click.testing import CliRunner, Result


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def assert_result(result: Result) -> tuple[str, str]:
    stdout = result.stdout
    stderr = result.stderr if result.stderr_bytes else None

    if result.exit_code > 0:
        print(f"stdout: {stdout}")
        print(f"stderr: {stderr}")
        assert result.exit_code == 0
    for pattern in ["Failed", "Error"]:
        assert pattern not in [stdout, stderr]
    return stdout, stderr
