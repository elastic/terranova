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
import os
import sys
from asyncio import Queue
from io import StringIO, TextIOBase
from pathlib import Path
from typing import Callable, Self, TextIO

from overrides import override
from sh import (
    Command,
    CommandNotFound,
    ErrorReturnCode,
    RunningCommand,
    TimeoutException,
)

from .exceptions import InvalidResourcesError
from .utils import Log, SharedContext

# Redirect bind types
type RedirectIn = Queue | str | TextIO
type RedirectOut = Path | TextIOBase | Callable[[str], None]
type RedirectErr = Path | TextIOBase | Callable[[str], None]


class EnvBind:
    """Convenient environment variables builder for bind."""

    def __init__(self) -> None:
        """Init env bind."""
        self.__build = {}

    @staticmethod
    def empty() -> "EnvBind":
        """Create an empty env bind."""
        return EnvBind()

    @staticmethod
    def inherit(predicate: Callable[[str, str], bool] | None = None) -> "EnvBind":
        """Create an env bind that inherit environment variables from the current process."""
        env = EnvBind()
        if predicate:
            env.__build = {
                key: value for key, value in os.environ.items() if predicate(key, value)
            }
        else:
            env.__build = os.environ.copy()
        return env

    def add(self, env_vars: dict[str, str]) -> Self:
        """Add environment variables to the env bind."""
        self.__build.update(env_vars)
        return self

    def build(self) -> dict[str, str]:
        """
        Returns:
            environment variables built using the env bind.
        """
        return self.__build.copy()


class PathBind:
    """Convenient path builder for bind."""

    def __init__(self) -> None:
        """Init path bind."""
        self.__build = []

    @staticmethod
    def empty() -> "PathBind":
        """Create an empty path bind."""
        return PathBind()

    @staticmethod
    def inherit() -> "PathBind":
        """Create a path bind that inherit the PATH environment variable from the current process."""
        path = PathBind()
        path.__build = os.environ.get("PATH", "").split(os.pathsep)
        return path

    def add(self, value: Command | str) -> Self:
        """Add a command or binary directory path to the program PATH."""
        if isinstance(value, str):
            self.__build.insert(0, value)
        else:
            self.__build.insert(0, value._path)
        return self

    def build(self) -> str:
        """
        Returns:
            computed PATH environment variable.
        """
        return os.pathsep.join(self.__build)


class Bind:
    """Convenient wrapper around sh library."""

    def __init__(self, cmd: Command) -> None:
        """
        Init bind.

        Args:
            cmd (Command): command.
        """
        self.__cmd = cmd
        self.__cwd = Path.cwd()
        self.__env: dict[str, str] = {}
        self.__args: tuple[str, ...] = ()
        self.__in: RedirectIn | None = None
        self.__out: RedirectOut | None = None
        self.__err: RedirectErr | None = None
        self.__timeout: int | None = None
        self.__start_handler: Callable[[RunningCommand], None] | None = None
        self.__completion_handler: (
            Callable[[RunningCommand, bool, int], None] | None
        ) = None

    def args(self, *value: str) -> tuple[str, ...] | Self:
        """
        Returns current arguments if no value is provided, otherwise set arguments.

        Args:
            *value: arguments to set.
        Returns:
            current arguments if no value is provided or self for chaining.
        """
        if not value:
            return self.__args

        self.__args = value
        return self

    def env(self, value: dict[str, str] | None = None) -> dict[str, str] | Self:
        """
        Returns current env vars if no value is provided, otherwise set env vars.

        Args:
            value: env vars to set.
        Returns:
            current env vars if no value is provided or self for chaining.
        """
        if value is None:
            return self.__env.copy()

        self.__env = value
        return self

    def cwd(self, value: Path | None = None) -> Path | Self:
        """
        Returns current cwd if no value is provided, otherwise set env vars.

        Args:
            value: env vars to set.
        Returns:
            current env vars if no value is provided or self for chaining.
        """
        if value is None:
            return self.__cwd

        self.__cwd = value
        return self

    def stdin(self, value: RedirectIn | None = None) -> RedirectIn | Self:
        """
        Returns current stdin if no value is provided, otherwise set stdin.

        Args:
            value: stdin to set.
        Returns:
            current stdin if no value is provided or self for chaining.
        """
        if value is None:
            return self.__in

        self.__in = value
        return self

    def stdout(self, value: RedirectOut | None = None) -> RedirectOut | Self:
        """
        Returns current stdout if no value is provided, otherwise set stdout.

        Args:
            value: stdout to set.
        Returns:
            current stdout if no value is provided or self for chaining.
        """
        if value is None:
            return self.__out
        elif isinstance(value, TextIOBase):
            self.__out = value
        elif isinstance(value, Path):
            self.__out = value.absolute().as_posix()
        else:
            self.__out = value
        return self

    def stderr(self, value: RedirectErr | None = None) -> RedirectErr | Self:
        """
        Returns current stderr if no value is provided, otherwise set stderr.

        Args:
            value: stderr to set.
        Returns:
            current stderr if no value is provided or self for chaining.
        """
        if value is None:
            return self.__err
        elif isinstance(value, TextIOBase):
            self.__err = value
        elif isinstance(value, Path):
            self.__err = value.absolute().as_posix()
        else:
            self.__err = value
        return self

    def inherit(self) -> Self:
        """
        Inherit stdin, stdout and stderr from current process.

        Returns:
            self for chaining.
        """
        self.__in = sys.stdin
        self.inherit_out()
        return self

    def inherit_out(self) -> Self:
        """
        Inherit stdout and stderr from current process.

        Returns:
            self for chaining.
        """
        self.__out = sys.stdout
        self.__err = sys.stderr
        return self

    def timeout(self, timeout: int) -> Self:
        """Set a timeout for process to spawn."""
        self.__timeout = timeout
        return self

    def binary_path(self) -> Path:
        """
        Returns:
            path where binary is installed.
        """
        return Path(self.__cmd._path)

    def start_handler(
        self, value: Callable[[RunningCommand], None] | None = None
    ) -> Callable[[RunningCommand], None] | None | Self:
        """
        Register a handler that will be called when the command is started.

        Args:
            value: the handler that will be called when the command is started.
        """
        if value is None:
            return self.__start_handler

        self.__start_handler = value
        return self

    def completion_handler(
        self, value: Callable[[RunningCommand, bool, int], None] | None = None
    ) -> Callable[[RunningCommand, bool, int], None] | None | Self:
        """
        Register a handler that will be called when the command is completed.

        Args:
            value: the handler that will be called when the command is completed.
        """
        if value is None:
            return self.__completion_handler

        self.__completion_handler = value
        return self

    def copy(self, bind: "Bind") -> Self:
        """Copy all parameters from the another bind."""
        self.__env = bind.__env.copy()
        self.__cwd = bind.__cwd
        self.__in = bind.__in
        self.__out = bind.__out
        self.__err = bind.__err
        self.__start_handler = bind.__start_handler
        self.__completion_handler = bind.__completion_handler
        return self

    def exec(self, wait_completion=True) -> RunningCommand:
        """
        Run the command and handle lifecycle in case we kill the parent process.

        Args:
            wait_completion: wait for completion.
        Returns:
            process execution context.
        """
        process: RunningCommand | None = None

        try:
            process = self.__cmd(
                *self.__args,
                _bg=True,
                _bg_exc=False,
                _truncate_exc=False,
                _env=self.__env if self.__env else None,
                _cwd=self.__cwd.as_posix(),
                _in=self.__in,
                _out=self.__out,
                _err=self.__err,
                _return_cmd=True,
                _done=self.__completion_handler,
            )
            if self.__start_handler is not None:
                self.__start_handler(process)
            return process.wait() if wait_completion else process
        finally:
            # It could happen if command arguments are wrong
            if wait_completion and process is not None and process.is_alive():
                process.terminate()
                try:
                    process.wait(timeout=10)
                except TimeoutException:
                    process.kill()


class BindMixin:
    """Mixin to create bind tied to real command."""

    def __init__(self, cmd: Command) -> None:
        """
        Init bind mixin.

        Args:
            cmd: command location.
        """
        self._bind = self.create_bind(cmd)

    def create_bind(self, cmd: Command) -> Bind:
        """
        Create bind tied to real command.

        Args:
            cmd: command location.
        Returns:
            bind.
        """
        return Bind(cmd)

    def env(self, value: dict[str, str] | None = None) -> dict[str, str] | Self:
        """
        Returns current env vars if no value is provided, otherwise set env vars.

        Args:
            value: env vars to set.
        Returns:
            current env vars if no value is provided or self for chaining.
        """
        if value is None:
            return self._bind.env()
        self._bind.env(value)
        return self

    def cwd(self, value: Path | None = None) -> Path | Self:
        """
        Returns current cwd if no value is provided, otherwise set env vars.

        Args:
            value: env vars to set.
        Returns:
            current env vars if no value is provided or self for chaining.
        """
        if value is None:
            return self._bind.cwd()
        self._bind.cwd(value)
        return self

    def stdin(self, value: RedirectIn) -> Self:
        """
        Returns current stdin if no value is provided, otherwise set stdin.

        Args:
            value: stdin to set.
        Returns:
            current stdin if no value is provided or self for chaining.
        """
        self._bind.stdin(value)
        return self

    def stdout(self, value: RedirectOut) -> Self:
        """
        Returns current stdout if no value is provided, otherwise set stdout.

        Args:
            value: stdout to set.
        Returns:
            current stdout if no value is provided or self for chaining.
        """
        self._bind.stdout(value)
        return self

    def stderr(self, value: RedirectErr) -> Self:
        """
        Returns current stderr if no value is provided, otherwise set stderr.

        Args:
            value: stderr to set.
        Returns:
            current stderr if no value is provided or self for chaining.
        """
        self._bind.stderr(value)
        return self

    def inherit(self) -> Self:
        """
        Inherit stdin, stdout and stderr from current process.

        Returns:
            self for chaining.
        """
        self._bind.inherit()
        return self

    def inherit_out(self) -> Self:
        """
        Inherit stdout and stderr from current process.

        Returns:
            self for chaining.
        """
        self._bind.inherit_out()
        return self

    def timeout(self, timeout: int) -> Self:
        """Set a timeout for process to spawn."""
        self._bind.timeout(timeout)
        return self

    def binary_path(self) -> Path:
        """
        Returns:
            path where binary is installed.
        """
        return self._bind.binary_path()

    def start_handler(self, handler: Callable[[RunningCommand], None]) -> Self:
        """
        Register a handler that will be called when the command is started.

        Args:
            handler: the handler that will be called when the command is started.
        """
        self._bind.start_handler(handler)
        return self

    def completion_handler(
        self, handler: Callable[[RunningCommand, bool, int], None]
    ) -> Self:
        """
        Register a handler that will be called when the command is completed.

        Args:
            handler: the handler that will be called when the command is completed.
        """
        self._bind.completion_handler(handler)
        return self

    def copy(self, bind: Bind) -> Self:
        """Copy all parameters from the another bind."""
        self._bind.copy(bind)
        return self


class Terraform(BindMixin):
    """Represents a bind to terraform command."""

    def __init__(self, work_dir: Path, variables: dict[str, str] | None = None) -> None:
        """Init terraform bind."""
        try:
            super().__init__(cmd=Command("terraform"))
        except CommandNotFound as err:
            Log.fatal("detect terraform binary", err)

        try:
            SharedContext.terraform_shared_plugin_cache_dir().mkdir(
                parents=True, exist_ok=True
            )
        except OSError as err:
            Log.fatal("create terraform cache directory", err)

        self.__work_dir = work_dir
        self.__variables = variables

    @override
    def create_bind(self, cmd: Command) -> Bind:
        inherit_env_vars = (
            "CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE",
            "CLOUDSDK_CORE_PROJECT",
            "CLOUDSDK_PROJECT",
            "GCLOUD_PROJECT",
            "GCP_PROJECT",
            "GOOGLE_APPLICATION_CREDENTIALS",
            "GOOGLE_CLOUD_PROJECT",
            "GOOGLE_GHA_CREDS_PATH",
            "HOME",
            "PATH",
        )

        # Predicate for allowed env vars
        def is_allowed_env_var(env_var: str) -> bool:
            return (
                env_var in inherit_env_vars
                # Inherit terraform env vars
                or env_var.startswith("TF_")
                # Inherit terranova env vars
                or env_var.startswith("TERRANOVA_")
                # Implicit credentials for s3 backend
                or env_var.startswith("AWS_")
                # Forward asdf for shims support
                or env_var.startswith("ASDF_")
            )

        env = EnvBind.inherit(lambda k, _: is_allowed_env_var(k))

        # Bind variables
        additional_env_vars = {}
        if self.__variables:
            for key, value in self.__variables.items():
                additional_env_vars[f"TF_VAR_{key}"] = value

        # Bind plugin cache dir
        additional_env_vars["TF_PLUGIN_CACHE_DIR"] = (
            SharedContext.terraform_shared_plugin_cache_dir().absolute().as_posix()
        )

        # Enable debug
        if SharedContext.is_verbose_enabled():
            additional_env_vars["TF_LOG"] = "DEBUG"

        return (
            Bind(cmd)
            .env(env.add(additional_env_vars).build())
            .inherit()
            .cwd(self.__work_dir)
        )

    def init(
        self,
        backend_config: dict[str, str] | None = None,
        migrate_state: bool = False,
        no_backend: bool = False,
        reconfigure: bool = False,
        upgrade: bool = False,
    ) -> None:
        """Prepare your working directory for other commands."""
        args = ["init"]
        if reconfigure:
            args.append("-reconfigure")
        if upgrade:
            args.append("-upgrade")
        if migrate_state:
            args.append("-migrate-state")
        if no_backend:
            args.append("-backend=false")
        if backend_config:
            for key, value in backend_config.items():
                args.append(f"-backend-config={key}={value}")
        self._bind.args(*args).exec()

    def validate(self) -> None:
        """
        Check whether the configuration is valid.

        Raises:
            InvalidResourcesError: if the resources configuration is invalid.
        """
        try:
            self._bind.args("validate").exec()
        except ErrorReturnCode as err:
            raise InvalidResourcesError(
                cause="the syntax is probably incorrect.",
                resolution="https://developer.hashicorp.com/terraform/language/syntax/configuration",
            ) from err

    def fmt(self) -> None:
        """Reformat your configuration in the standard style."""
        self._bind.args("fmt").exec()

    def plan(
        self,
        compact_warnings: bool,
        input: bool,
        no_color: bool,
        parallelism: int | None,
        detailed_exitcode: bool,
        out: Path | None = None,
    ) -> None:
        """Show changes required by the current configuration."""
        args = ["plan"]
        if compact_warnings:
            args.append("-compact-warnings")
        args.append("-input=true" if input else "-input=false")
        if no_color:
            args.append("-no-color")
        if parallelism and parallelism != 10:  # Default value is 10
            args.append(f"-parallelism={parallelism}")
        if detailed_exitcode:
            args.append("-detailed-exitcode")
        if out:
            args.append(f"-out={out.as_posix()}")
        self._bind.args(*args).exec()

    def apply(
        self,
        plan: str | None = None,
        auto_approve: bool = False,
        target: str | None = None,
    ) -> None:
        """Create or update infrastructure."""
        args = ["apply"]
        if plan:
            args.append(plan)
        if auto_approve:
            args.append("-auto-approve")
        if target:
            args.append(f"-target={target}")
        self._bind.args(*args).exec()

    def graph(self) -> None:
        """Generate a Graphviz graph of the steps in an operation."""
        self._bind.args("graph").exec()

    def taint(self, address: str) -> None:
        """Mark a resource as not fully functional."""
        self._bind.args("taint", address).exec()

    def untaint(self, address: str) -> None:
        """Remove the 'tainted' state from a resource instance."""
        self._bind.args("untaint", address).exec()

    def output(self, name: str) -> str:
        """Show output values from your root module."""
        capture = StringIO()
        self._bind.args("output", "-raw", name).stdout(capture).exec()
        return capture.getvalue()

    def define(self, address: str, identifier: str) -> None:
        """Associate existing infrastructure with a Terraform resource."""
        self._bind.args("import", address, identifier).exec()

    def destroy(self) -> None:
        """Destroy previously-created infrastructure."""
        self._bind.args("destroy").exec()
