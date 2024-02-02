import os
import shutil
from pathlib import Path

import click
import mdformat
import sh
from click.exceptions import Exit
from jinja2 import Environment, PackageLoader

from .binds import Terraform
from .exceptions import (
    AmbiguousRunbookError,
    InvalidResourcesError,
    ManifestError,
    MissingRunbookError,
)
from .resources import Resource, ResourcesFinder, ResourcesManifest
from .utils import Constants, Log, SharedContext


# pylint: disable=R1710
def read_manifest(path: Path) -> "ResourcesManifest":
    """
    Read the resources manifest if possible.
    This function handle errors by logging and exiting.

    Args:
        path: path to manifest directory.

    Returns:
        the manifest.
    """
    try:
        return ResourcesManifest.from_file(path / Constants.MANIFEST_FILE_NAME)
    except ManifestError as err:
        Log.failure("read manifest", err, raise_exit=1)


# pylint: disable=R1710
def discover_resources(path: Path) -> list[Resource]:
    """
    Discover resources in every terraform configuration files.
    This function handle errors by logging and exiting.

    Args:
        path: path to resources directory.

    Returns:
        list of resources.
    """
    try:
        return ResourcesFinder.find_in_dir(path)
    except InvalidResourcesError as err:
        Log.failure(
            f"discover resources at `{path.as_posix()}`",
            err,
            raise_exit=1,
        )


def find_all_resource_dirs() -> list[(Path, str)]:
    """
    Find all path where there is a resource manifest.

    Returns:
        list of all path.
    """
    paths = []
    resources_dir = SharedContext.resources_dir().as_posix()
    resources_dir_prefix_len = len(resources_dir) + 1
    for path, _, files in os.walk(resources_dir):
        for file in files:
            if os.path.basename(file) == Constants.MANIFEST_FILE_NAME:
                paths.append((Path(path), path[resources_dir_prefix_len:]))
    return paths


def resource_dirs(path: str | None) -> list[(Path, str)]:
    """
    List of all resource dirs to interact with.

    Args:
        path: use a specific path.

    Returns:
        list of all resource dirs.
    """
    if path:
        # Construct resources path
        return [(SharedContext.resources_dir().joinpath(path), path)]
    # Find all resources manifests
    return find_all_resource_dirs()


def mount_context(full_path: Path, manifest: ResourcesManifest | None = None, import_vars: bool = False) -> Terraform:
    """Mount the terraform context by importing variables if needed."""
    # Ensure manifest exists and can be read
    if not manifest:
        manifest = read_manifest(full_path)

    # Import variables
    if manifest.imports and import_vars:
        variables = {}
        for importer in manifest.imports:
            target = importer.target if importer.target else importer.resource
            variables[target] = extract_output_var(importer.source, importer.resource)
    else:
        variables = None

    return Terraform(full_path, variables)


def extract_output_var(path: str, name: str) -> str:
    """Show output values from your root module."""
    # Construct resources path
    full_path = SharedContext.resources_dir().joinpath(path)

    # Mount terraform context
    terraform = mount_context(full_path)

    # Execute output command
    try:
        return terraform.output(name)
    except sh.ErrorReturnCode as err:
        raise Exit(code=err.exit_code) from err


@click.command("init")
@click.argument("path", type=str, required=False)
def init(path: str | None) -> None:
    """Init resources manifest."""
    # Find all resources manifests
    paths = resource_dirs(path)

    # Init all paths
    for full_path, rel_path in paths:
        Log.action(f"Initializing: {rel_path}")

        # Ensure manifest exists and can be read
        manifest = read_manifest(full_path)

        # Remove all symbolic links
        symbolic_links = [file for file in full_path.iterdir() if file.is_symlink()]
        for link in symbolic_links:
            os.unlink(link.as_posix())

        # Save workdir
        cwd = os.getcwd()
        try:
            # Switch to resources dir
            os.chdir(full_path.as_posix())

            # Create new symbolic links
            for dependency in manifest.dependencies:
                try:
                    target_dirname = os.path.dirname(dependency.target)
                    os.symlink(
                        os.path.relpath(
                            SharedContext.shared_dir().joinpath(dependency.source).as_posix(),
                            full_path.joinpath(target_dirname).as_posix(),
                        ),
                        dependency.target,
                    )
                except FileExistsError:
                    # The symlink already exists and it's probably fine
                    pass
        finally:
            os.chdir(cwd)

        # Cleanup various directories
        for dirname in ["outputs", "templates", "runbooks"]:
            dir_path = full_path / dirname
            try:
                if dir_path.exists() and dir_path.is_dir():
                    # Is it empty
                    if not any(dir_path.iterdir()):
                        dir_path.rmdir()
            except OSError:
                Log.failure(f"delete the directory at: {dir_path.as_posix()}", raise_exit=1)

        try:
            already_init = (full_path / ".terraform").exists()
            # Mount terraform context
            terraform = mount_context(full_path, manifest)
            terraform.init(
                reconfigure=already_init,
                upgrade=already_init,
                backend_config={"key": os.path.relpath(full_path, SharedContext.resources_dir())},
            )
        except sh.ErrorReturnCode as err:
            raise Exit(code=err.exit_code) from err


@click.command("get")
@click.argument("path", type=str)
def get(path: str) -> None:
    """Display one or many resources."""
    # Construct resources path
    full_path = SharedContext.resources_dir().joinpath(path)

    # Ensure manifest exists and can be read
    read_manifest(full_path)

    resources = ResourcesFinder.find_in_dir(full_path)
    print(resources)


@click.command("fmt")
@click.argument("path", type=str, required=False)
def fmt(path: str) -> None:
    """Reformat your configuration in the standard style."""
    # Find all resources manifests
    paths = resource_dirs(path)

    # Format all paths
    for full_path, rel_path in paths:
        Log.action(f"Formatting: {rel_path}")

        # Mount terraform context
        terraform = mount_context(full_path)

        # Format resources files
        try:
            terraform.fmt()
        except sh.ErrorReturnCode as err:
            raise Exit(code=err.exit_code) from err


@click.command("validate")
@click.argument("path", type=str, required=False)
def validate(path: str | None) -> None:
    """Check whether the configuration is valid."""
    # Find all resources manifests
    paths = resource_dirs(path)

    # Format all paths
    for full_path, rel_path in paths:
        Log.action(f"Validating: {rel_path}")

        # Mount terraform context
        terraform = mount_context(full_path)
        discover_resources(full_path)

        # Format resources files
        try:
            terraform.validate()
            Log.success(f"validate resources at `{full_path.as_posix()}`.")
        except InvalidResourcesError as err:
            Log.failure(
                f"validate resources at `{full_path.as_posix()}`.",
                err,
                raise_exit=1,
            )


@click.command("docs")
@click.option(
    "--docs-dir",
    help="Docs directory path.",
    type=click.Path(path_type=Path),
    required=True,
    default="./docs",
)
def docs(docs_dir: Path) -> None:
    """Generate documentation for all resources."""
    # Find all resources manifests
    jobs = []
    for path, _, files in os.walk(SharedContext.resources_dir().as_posix()):
        for file in files:
            if os.path.basename(file) == Constants.MANIFEST_FILE_NAME:
                jobs.append(
                    (Path(path), docs_dir.joinpath(os.path.relpath(path, SharedContext.resources_dir().as_posix())))
                )

    # Clean docs dir
    if docs_dir.exists():
        shutil.rmtree(docs_dir.as_posix())

    # Generate docs
    env = Environment(loader=PackageLoader("terranova", "templates"))
    tmpl = env.get_template("resources.md")
    for resources_path, target_path in jobs:
        target_path.parent.mkdir(parents=True, exist_ok=True)

        # Read resources manifest and find all resources
        manifest = read_manifest(resources_path)
        resources = discover_resources(resources_path)

        # Write documentation file
        rendering = tmpl.render({"manifest": manifest, "resources": resources})
        formatted = mdformat.text(rendering)
        target_path.with_suffix(".md").write_text(data=formatted, encoding=Constants.ENCODING_UTF_8)


@click.command("plan")
@click.argument("path", type=str, required=False)
def plan(path: str | None) -> None:
    """Show changes required by the current configuration."""
    # Find all resources manifests
    paths = resource_dirs(path)

    # Format all paths
    for full_path, rel_path in paths:
        Log.action(f"Generating plan: {rel_path}")

        # Mount terraform context
        terraform = mount_context(full_path, import_vars=True)

        # Execute plan command
        try:
            terraform.plan()
        except sh.ErrorReturnCode as err:
            raise Exit(code=err.exit_code) from err


@click.command("apply")
@click.argument("path", type=str, required=False)
@click.option("--auto-approve", help="Skip interactive approval of plan before applying.", is_flag=True)
@click.option("--target", help="Apply changes for specific target.", type=str)
def apply(path: str | None, auto_approve: bool, target: str) -> None:
    """Create or update resources."""
    # Find all resources manifests
    paths = resource_dirs(path)

    # Format all paths
    for full_path, rel_path in paths:
        Log.action(f"Applying plan: {rel_path}")

        # Mount terraform context
        terraform = mount_context(full_path, import_vars=True)

        # Execute apply command
        try:
            terraform.apply(auto_approve, target)
        except sh.ErrorReturnCode as err:
            raise Exit(code=err.exit_code) from err


@click.command("destroy")
@click.argument("path", type=str, required=False)
def destroy(path: str | None) -> None:
    """Destroy previously-created resources."""
    # Find all resources manifests
    paths = resource_dirs(path)

    # Format all paths
    for full_path, rel_path in paths:
        Log.action(f"Destroying resources: {rel_path}")

        # Mount terraform context
        terraform = mount_context(full_path, import_vars=True)

        # Execute destroy command
        try:
            terraform.destroy()
        except sh.ErrorReturnCode as err:
            raise Exit(code=err.exit_code) from err


@click.command("graph")
@click.argument("path", type=str)
def graph(path: str) -> None:
    """Generate a Graphviz graph of the steps in an operation."""
    # Construct resources path
    full_path = SharedContext.resources_dir().joinpath(path)

    # Mount terraform context
    terraform = mount_context(full_path)

    # Execute destroy command
    try:
        terraform.graph()
    except sh.ErrorReturnCode as err:
        raise Exit(code=err.exit_code) from err


@click.command("taint")
@click.argument("path", type=str)
@click.argument("address", type=str)
def taint(path: str, address: str) -> None:
    """Mark a resource as not fully functional."""
    # Construct resources path
    full_path = SharedContext.resources_dir().joinpath(path)

    # Mount terraform context
    terraform = mount_context(full_path, import_vars=True)

    # Execute taint command
    try:
        terraform.taint(address)
    except sh.ErrorReturnCode as err:
        raise Exit(code=err.exit_code) from err


@click.command("import")
@click.argument("path", type=str)
@click.argument("address", type=str)
@click.argument("identifier", type=str)
def define(path: str, address: str, identifier: str) -> None:
    """Associate existing infrastructure with a Terraform resource."""
    # Construct resources path
    full_path = SharedContext.resources_dir().joinpath(path)

    # Mount terraform context
    terraform = mount_context(full_path, import_vars=True)

    # Execute import command
    try:
        terraform.define(address, identifier)
    except sh.ErrorReturnCode as err:
        raise Exit(code=err.exit_code) from err


@click.command("output")
@click.argument("path", type=str)
@click.argument("name", type=str)
def output(path: str, name: str) -> None:
    """Show output values from your root module."""
    print(extract_output_var(path, name), end="", flush=True)


@click.command("runbook")
@click.argument("path", type=str)
@click.argument("name", type=str)
def runbook(path: str, name: str) -> None:
    """Execute a runbook."""
    # Construct resources path
    full_path = SharedContext.resources_dir().joinpath(path)

    # Ensure manifest exists and can be read
    manifest = read_manifest(full_path)

    # Extract runbook
    matching_runbooks = [rb for rb in manifest.runbooks if rb.name == name]
    if not matching_runbooks:
        Log.failure("execute runbook", MissingRunbookError(name), raise_exit=1)
    if len(matching_runbooks) > 1:
        Log.failure("execute runbook", AmbiguousRunbookError(name), raise_exit=1)

    # Execute runbook
    executable_runbook = next(iter(matching_runbooks))
    try:
        executable_runbook.exec(path, full_path / "runbooks")
    except sh.ErrorReturnCode as err:
        raise Exit(code=err.exit_code) from err
