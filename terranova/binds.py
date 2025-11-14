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
from io import StringIO
from pathlib import Path
from typing import override

from terranova.exceptions import InvalidResourcesError
from terranova.process import Bind, EnvCmd, CommandNotFound, Command, ErrorReturnCode
from terranova.utils import Log, SharedContext


class Terraform(Bind):
    """Represents a bind to terraform command."""

    def __init__(self, work_dir: Path, variables: dict[str, str] | None = None) -> None:
        """Init terraform bind."""
        try:
            super().__init__("terraform")
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
    def create(self, cmd_path: str | Path) -> Command:
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

        env = EnvCmd.inherit(lambda k, _: is_allowed_env_var(k))

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
            Command(cmd_path)
            .env(env.add(additional_env_vars).build())
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
        self._cmd.args(*args).inherit().exec()

    def validate(self) -> None:
        """
        Check whether the configuration is valid.

        Raises:
            InvalidResourcesError: if the resources configuration is invalid.
        """
        try:
            self._cmd.args("validate").inherit().exec()
        except ErrorReturnCode as err:
            raise InvalidResourcesError(
                cause="the syntax is probably incorrect.",
                resolution="https://developer.hashicorp.com/terraform/language/syntax/configuration",
            ) from err

    def fmt(self) -> None:
        """Reformat your configuration in the standard style."""
        self._cmd.args("fmt").inherit().exec()

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
        self._cmd.args(*args).inherit().exec()

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
        self._cmd.args(*args).inherit().exec()

    def graph(self) -> None:
        """Generate a Graphviz graph of the steps in an operation."""
        self._cmd.args("graph").inherit().exec()

    def taint(self, address: str) -> None:
        """Mark a resource as not fully functional."""
        self._cmd.args("taint", address).inherit().exec()

    def untaint(self, address: str) -> None:
        """Remove the 'tainted' state from a resource instance."""
        self._cmd.args("untaint", address).inherit().exec()

    def output(self, name: str) -> str:
        """Show output values from your root module."""
        capture = StringIO()
        self._cmd.args("output", "-raw", name).inherit().stdout(capture).exec()
        return capture.getvalue()

    def define(self, address: str, identifier: str) -> None:
        """Associate existing infrastructure with a Terraform resource."""
        self._cmd.args("import", address, identifier).inherit().exec()

    def destroy(self) -> None:
        """Destroy previously-created infrastructure."""
        self._cmd.args("destroy").inherit().exec()
