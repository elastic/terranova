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
        process = None
        try:
            kwargs = {**kwargs, **{"_bg": True, "_bg_exc": False}}
            process = self.__cmd(*args, **kwargs)
            return process.wait()
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
            Log.failure("detect terraform binary", err, raise_exit=1)

        try:
            SharedContext.terraform_shared_plugin_cache_dir().mkdir(parents=True, exist_ok=True)
        except OSError as err:
            Log.failure("create terraform cache directory", err, raise_exit=1)

        self.__work_dir = work_dir
        self.__variables = variables

    @override
    def _exec(self, *args, **kwargs) -> RunningCommand:
        # Predicate for allowed env vars
        def is_allowed_env_var(env_var: str) -> bool:
            return (
                env_var.startswith("TF_")
                or env_var.startswith("INFRACTL_")
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

    def init(self, reconfigure=False, upgrade=False, backend_config: dict[str, str] = None) -> None:
        """Prepare your working directory for other commands."""
        args = ["init"]
        if reconfigure:
            args.append("-reconfigure")
        if upgrade:
            args.append("-upgrade")
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

    def plan(self) -> None:
        """Show changes required by the current configuration."""
        self._exec("plan", _inherit=True)

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
