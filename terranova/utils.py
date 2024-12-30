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
from pathlib import Path
from threading import Lock
from typing import Any, Final, NoReturn

from click.exceptions import Exit
from rich.console import Console

from .exceptions import ExplainedError


class Constants:
    """All constants"""

    CTX_CONF_DIR: Final[str] = "ctx_conf_dir"
    CTX_CONSOLE: Final[str] = "ctx_console"
    CTX_DEBUG: Final[str] = "ctx_debug"
    CTX_ERR_CONSOLE: Final[str] = "ctx_err_console"
    CTX_VERBOSE: Final[str] = "ctx_verbose"
    ENCODING_UTF_8: Final[str] = "utf-8"
    FILE_MODE_READ: Final[str] = "r"
    MANIFEST_FILE_NAME: Final[str] = "manifest.yml"


class SharedContext:
    """Utility class to share context globally."""

    # Shard context
    __UNDERLYING: dict[str, Any] = {}
    __LOCK: Lock = Lock()

    @staticmethod
    def init(debug: bool, verbose: bool, conf_dir: Path) -> None:
        """Init global shared context."""
        with SharedContext.__LOCK:
            SharedContext.__UNDERLYING[Constants.CTX_CONSOLE] = Console()
            SharedContext.__UNDERLYING[Constants.CTX_ERR_CONSOLE] = Console(stderr=True)
            SharedContext.__UNDERLYING[Constants.CTX_DEBUG] = debug
            SharedContext.__UNDERLYING[Constants.CTX_VERBOSE] = verbose
            SharedContext.__UNDERLYING[Constants.CTX_CONF_DIR] = conf_dir

    @staticmethod
    def console() -> Console:
        """Retrieve console from context."""
        with SharedContext.__LOCK:
            return SharedContext.__UNDERLYING[Constants.CTX_CONSOLE]

    @staticmethod
    def err_console() -> Console:
        """Retrieve err console from context."""
        with SharedContext.__LOCK:
            return SharedContext.__UNDERLYING[Constants.CTX_ERR_CONSOLE]

    @staticmethod
    def is_debug_enabled() -> bool:
        """Returns true if debug is enabled."""
        with SharedContext.__LOCK:
            return SharedContext.__UNDERLYING[Constants.CTX_DEBUG]

    @staticmethod
    def is_verbose_enabled() -> bool:
        """Returns true if verbose is enabled."""
        with SharedContext.__LOCK:
            return SharedContext.__UNDERLYING[Constants.CTX_VERBOSE]

    @staticmethod
    def conf_dir() -> Path:
        """Returns conf directory path."""
        with SharedContext.__LOCK:
            return SharedContext.__UNDERLYING[Constants.CTX_CONF_DIR]

    @staticmethod
    def resources_dir() -> Path:
        """Returns specs directory path."""
        return SharedContext.conf_dir() / "resources"

    @staticmethod
    def shared_dir() -> Path:
        """Returns shared directory path."""
        return SharedContext.conf_dir() / "shared"

    @staticmethod
    def terraform_shared_dir() -> Path:
        """Returns terraform shared directory path."""
        return SharedContext.conf_dir() / ".terraform"

    @staticmethod
    def terraform_shared_states_dir() -> Path:
        """Returns terraform shared states directory path."""
        return SharedContext.terraform_shared_dir() / "states"

    @staticmethod
    def terraform_shared_plugin_cache_dir() -> Path:
        """Returns terraform shared plugin cache directory path."""
        return SharedContext.terraform_shared_dir() / "plugin-cache"


class Log:
    """Utility class to log message or error using common pattern."""

    @classmethod
    def action(cls, msg) -> None:
        """Log an action."""
        SharedContext.console().print(f"[yellow]⇒[/yellow] {str(msg)}")

    @classmethod
    def success(cls, msg) -> None:
        """Log a success."""
        SharedContext.console().print(f"[green]✓[/green] Succeeded to {str(msg)}")

    @classmethod
    def failure(cls, msgs: str | list[str], err: Exception | None = None) -> None:
        """Log a failure."""
        err_console = SharedContext.err_console()
        if SharedContext.is_debug_enabled() and err:
            err_console.print_exception()
            err_console.print(err)
        if not isinstance(msgs, list):
            msgs = [msgs]
        err_console.print(f"[red]x[/red] Failed to {str(msgs[0])}")
        for msg in msgs[1:]:
            err_console.print(f"  {str(msg)}")

        # Render explained error
        if err:
            if isinstance(err, ExplainedError):
                err_console.print(f"  Cause: {err.cause}")
                if err.resolution:
                    err_console.print(f"  Resolution: {err.resolution}")
            else:
                err_console.print(f"  Details: {err}")

    @classmethod
    def fatal(
        cls, msgs: str | list[str], err: Exception | None = None, raise_exit: int = 1
    ) -> NoReturn:
        """Log a failure and exit."""
        Log.failure(msgs, err)
        raise Exit(code=raise_exit)
