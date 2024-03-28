import os
from pathlib import Path
from typing import Final

PROJECT_ROOT_DIR: Final[Path] = Path(__file__).parent.parent.absolute().resolve()
PROJECT_TESTS_FIXTURES_DIR: Final[Path] = PROJECT_ROOT_DIR / "tests" / "fixtures"


def env_vars_are_undefined(*env_vars: str) -> bool:
    for env_var in env_vars:
        value = os.environ.get(env_var)
        if not value or value.strip() == "":
            return True
    return False
