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
import shutil
from pathlib import Path

import click
import mdformat
import sh
from click.exceptions import Exit
from jinja2 import Environment, PackageLoader
from rich.table import Table

from terranova.commands.helpers import (
    Selector,
    SelectorType,
    discover_resources,
    extract_output_var,
    mount_context,
    read_manifest,
    resource_dirs,
)
from terranova.exceptions import (
    AmbiguousRunbookError,
    InvalidResourcesError,
    MissingRunbookEnvError,
    MissingRunbookError,
)
from terranova.utils import Constants, Log, SharedContext


# pylint: disable=R0914
@click.command("init")
@click.argument("path", type=str, required=False)
@click.option("--migrate-state", help="Reconfigure a backend, and attempt to migrate any existing state.", is_flag=True)
@click.option(
    "--no-backend", help="Disable backend for this configuration and use what was previously instead.", is_flag=True
)
@click.option("--reconfigure", help="Reconfigure a backend, ignoring any saved configuration.", is_flag=True)
@click.option("--upgrade", help="Install the latest module and provider versions.", is_flag=True)
@click.option(
    "--fail-at-end",
    help="If specified, only fail afterwards; allow all non-impacted projects to continue.",
    default=False,
    is_flag=True,
)
# pylint: disable-next=R0913
def init(
    path: str | None, migrate_state: bool, no_backend: bool, reconfigure: bool, upgrade: bool, fail_at_end: bool
) -> None:
    # pylint: disable=R0912
    """Init resources manifest."""
    # Find all resources manifests
    paths = resource_dirs(path)

    # Store errors if fail_at_end
    errors = False

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
            if manifest.dependencies:
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
                Log.fatal(f"delete the directory at: {dir_path.as_posix()}")

        try:
            # Mount terraform context
            terraform = mount_context(full_path, manifest)
            terraform.init(
                backend_config={"key": os.path.relpath(full_path, SharedContext.resources_dir())},
                migrate_state=migrate_state,
                no_backend=no_backend,
                reconfigure=reconfigure,
                upgrade=upgrade,
            )
        except sh.ErrorReturnCode:
            errors = True
            if not fail_at_end:
                break

    # Report any errors if fail_at_end has been enabled
    if errors:
        raise Exit(code=1)


@click.command("get")
@click.argument("path", type=str, required=False)
@click.option("--selector", "selectors", type=SelectorType(), required=False, multiple=True)
def get(path: str | None, selectors: list[Selector] | None) -> None:
    """Display one or many resources."""
    # Find all resources manifests
    paths = resource_dirs(path)

    # Render resources table
    table = Table()
    table.add_column("Path", justify="left", style="cyan", no_wrap=True)
    table.add_column("Type", justify="left", style="green")
    table.add_column("Name", style="magenta")
    for full_path, rel_path in paths:
        resources = discover_resources(full_path, selectors)
        for resource in resources:
            table.add_row(rel_path, resource.type, resource.name)
    SharedContext.console().print(table)


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
@click.option(
    "--fail-at-end",
    help="If specified, only fail afterwards; allow all non-impacted projects to continue.",
    default=False,
    is_flag=True,
)
def validate(path: str | None, fail_at_end: bool) -> None:
    """Check whether the configuration is valid."""
    # Find all resources manifests
    paths = resource_dirs(path)

    # Store errors if fail_at_end
    errors = False

    # Format all paths
    for full_path, rel_path in paths:
        Log.action(f"Validating: {rel_path}")

        # Mount terraform context
        terraform = mount_context(full_path)
        discover_resources(full_path)

        message = f"validate resources at `{full_path.as_posix()}`."

        # Format resources files
        try:
            terraform.validate()
            Log.success(message)
        except InvalidResourcesError:
            errors = True
            Log.failure(message)
            if not fail_at_end:
                break

    # Report any errors if fail_at_end has been enabled
    if errors:
        Log.fatal("The syntax is probably incorrect in one of the projects. See above for errors.")


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


# pylint: disable=redefined-builtin
@click.command("plan")
@click.argument("path", type=str, required=False)
@click.option(
    "--compact-warnings",
    help="If Terraform produces any warnings that are not by errors, show them in a more compact that includes only the summary messages.",
    is_flag=True,
)
@click.option("--input/--no-input", help="Ask for input for variables if not directly set.", default=True)
@click.option("--no-color", help="If specified, output won't contain any color.", is_flag=True)
@click.option("--parallelism", help="Limit the number of parallel resource operations.", type=int, default=10)
@click.option(
    "--fail-at-end",
    help="If specified, only fail afterwards; allow all non-impacted projects to continue.",
    default=False,
    is_flag=True,
)
# pylint: disable-next=R0913
def plan(
    path: str | None, compact_warnings: bool, input: bool, no_color: bool, parallelism: int, fail_at_end: bool
) -> None:
    """Show changes required by the current configuration."""
    # Find all resources manifests
    paths = resource_dirs(path)

    # Store errors if fail_at_end
    errors = False

    # Format all paths
    for full_path, rel_path in paths:
        Log.action(f"Generating plan: {rel_path}")

        # Mount terraform context
        terraform = mount_context(full_path, import_vars=True)

        # Execute plan command
        try:
            terraform.plan(compact_warnings=compact_warnings, input=input, no_color=no_color, parallelism=parallelism)
        except sh.ErrorReturnCode:
            errors = True
            if not fail_at_end:
                break

    # Report any errors if fail_at_end has been enabled
    if errors:
        raise Exit(code=1)


@click.command("apply")
@click.argument("path", type=str, required=False)
@click.option("--auto-approve", help="Skip interactive approval of plan before applying.", is_flag=True)
@click.option("--target", help="Apply changes for specific target.", type=str)
@click.option(
    "--fail-at-end",
    help="If specified, only fail afterwards; allow all non-impacted projects to continue.",
    default=False,
    is_flag=True,
)
def apply(path: str | None, auto_approve: bool, target: str, fail_at_end: bool) -> None:
    """Create or update resources."""
    # Find all resources manifests
    paths = resource_dirs(path)

    # Store errors if fail_at_end
    errors = False

    # Format all paths
    for full_path, rel_path in paths:
        Log.action(f"Applying plan: {rel_path}")

        # Mount terraform context
        terraform = mount_context(full_path, import_vars=True)

        # Execute apply command
        try:
            terraform.apply(auto_approve, target)
        except sh.ErrorReturnCode:
            errors = True
            if not fail_at_end:
                break

    # Report any errors if fail_at_end has been enabled
    if errors:
        raise Exit(code=1)


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
    matching_runbooks = [rb for rb in manifest.runbooks if rb.name == name] if manifest.runbooks else []
    if not matching_runbooks:
        Log.fatal("execute runbook", MissingRunbookError(name))
    if len(matching_runbooks) > 1:
        Log.fatal("execute runbook", AmbiguousRunbookError(name))

    # Execute runbook
    executable_runbook = next(iter(matching_runbooks))
    try:
        executable_runbook.exec(path, full_path / "runbooks")
    except MissingRunbookEnvError as err:
        Log.fatal("find environment variable", err)
    except sh.ErrorReturnCode as err:
        raise Exit(code=err.exit_code) from err


@click.command("ls")
@click.argument("path", type=str, required=False)
def ls(path: str | None) -> None:
    """List resources."""
    # Find all resources manifests
    paths = resource_dirs(path)

    # Display resource paths
    for full_path, _ in paths:
        print(full_path)
