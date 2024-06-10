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
from pathlib import Path

from overrides import override
from sh import Command, CommandNotFound, ErrorReturnCode, RunningCommand

from .exceptions import InvalidResourcesError
from .utils import Constants, Log, SharedContext


# pylint: disable=R0903
class Bind:
    """Represents an abstract external bind."""

    def __init__(self, cmd: Command) -> None:
        """Init bind."""
        self.__cmd = cmd

    def _exec(self, *args, **kwargs) -> RunningCommand:
        """Run the command and handle lifecycle in case we kill the parent process."""
        process: RunningCommand | None = None
        try:
            kwargs = {**kwargs, **{"_bg": True, "_bg_exc": False}}
            running_process = self.__cmd(*args, **kwargs)
            if isinstance(running_process, RunningCommand):
                return running_process.wait()
            raise ValueError
        finally:
            if process is not None and process.is_alive():
                process.kill()


class Terraform(Bind):
    """Represents a bind to terraform command."""

    def __init__(self, work_dir: Path, variables: dict[str, str] | None = None) -> None:
        """Init terraform bind."""
        try:
            super().__init__(cmd=Command("terraform"))
        except CommandNotFound as err:
            Log.fatal("detect terraform binary", err)

        try:
            SharedContext.terraform_shared_plugin_cache_dir().mkdir(parents=True, exist_ok=True)
        except OSError as err:
            Log.fatal("create terraform cache directory", err)

        self.__work_dir = work_dir
        self.__variables = variables

    @override
    def _exec(self, *args, **kwargs) -> RunningCommand:
        # Predicate for allowed env vars
        def is_allowed_env_var(env_var: str) -> bool:
            return (
                env_var.startswith("TF_")
                or env_var.startswith("TERRANOVA_")
                # Implicit credentials for s3 backend
                or env_var.startswith("AWS_")
                or env_var in ["HOME", "PATH"]
            )

        # Copy allowed env vars
        env = {key: value for key, value in os.environ.items() if is_allowed_env_var(key)}

        # Bind variables
        if self.__variables:
            for key, value in self.__variables.items():
                env[f"TF_VAR_{key}"] = value

        # Bind plugin cache dir
        env["TF_PLUGIN_CACHE_DIR"] = SharedContext.terraform_shared_plugin_cache_dir().absolute().as_posix()

        # Enable debug
        if SharedContext.is_verbose_enabled():
            env["TF_LOG"] = "DEBUG"

        # Set all
        kwargs["_env"] = env
        if kwargs.get("_inherit"):
            del kwargs["_inherit"]
            kwargs["_in"] = sys.stdin
            kwargs["_out"] = sys.stdout
            kwargs["_err"] = sys.stderr
        kwargs["_cwd"] = self.__work_dir
        return super()._exec(*args, **kwargs)

    # pylint: disable=too-many-arguments
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
        self._exec(*args, _inherit=True)

    def validate(self) -> None:
        """
        Check whether the configuration is valid.

        Raises:
            InvalidResourcesError: if the resources configuration is invalid.
        """
        try:
            self._exec("validate", _inherit=True)
        except ErrorReturnCode as err:
            raise InvalidResourcesError(
                cause="the syntax is probably incorrect.",
                resolution="https://developer.hashicorp.com/terraform/language/syntax/configuration",
            ) from err

    def fmt(self) -> None:
        """Reformat your configuration in the standard style."""
        self._exec("fmt", _inherit=True)

    # pylint: disable=redefined-builtin
    def plan(self, compact_warnings: bool, input: bool, no_color: bool, parallelism: int) -> None:
        """Show changes required by the current configuration."""
        args = ["plan"]
        if compact_warnings:
            args.append("-compact-warnings")
        args.append("-input=true" if input else "-input=false")
        if no_color:
            args.append("-no-color")
        if parallelism and parallelism != 10:  # Default value is 10
            args.append(f"-parallelism={parallelism}")
        self._exec(*args, _inherit=True)

    def apply(self, auto_approve: bool = False, target: str | None = None) -> None:
        """Create or update infrastructure."""
        args = ["apply"]
        if auto_approve:
            args.append("-auto-approve")
        if target:
            args.append(f"-target={target}")
        self._exec(*args, _inherit=True)

    def graph(self) -> None:
        """Generate a Graphviz graph of the steps in an operation."""
        self._exec("graph", _inherit=True)

    def taint(self, address: str) -> None:
        """Mark a resource as not fully functional."""
        self._exec("taint", address, _inherit=True)

    def untaint(self, address: str) -> None:
        """Remove the 'tainted' state from a resource instance."""
        self._exec("untaint", address, _inherit=True)

    def output(self, name: str) -> str:
        """Show output values from your root module."""
        result = self._exec("output", "-raw", name, _in=sys.stdin, _err=sys.stderr)
        return result.stdout.decode(Constants.ENCODING_UTF_8)

    def define(self, address: str, identifier: str) -> None:
        """Associate existing infrastructure with a Terraform resource."""
        self._exec("import", address, identifier, _inherit=True)

    def destroy(self) -> None:
        """Destroy previously-created infrastructure."""
        self._exec("destroy", _inherit=True)
