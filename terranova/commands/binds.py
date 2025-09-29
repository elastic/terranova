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
import json
import os
import shutil
from base64 import b64decode, b64encode
from pathlib import Path
from tempfile import NamedTemporaryFile

import click
import mdformat
from click.exceptions import Exit
from jinja2 import Environment, PackageLoader
from rich.table import Table
from sh import ErrorReturnCode

from terranova.commands.helpers import (
    Selector,
    SelectorType,
    discover_resources,
    extract_import_vars,
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


@click.command("init")
@click.argument("path", type=str, required=False)
@click.option(
    "--migrate-state",
    help="Reconfigure a backend, and attempt to migrate any existing state.",
    is_flag=True,
)
@click.option(
    "--no-backend",
    help="Disable backend for this configuration and use what was previously instead.",
    is_flag=True,
)
@click.option(
    "--reconfigure",
    help="Reconfigure a backend, ignoring any saved configuration.",
    is_flag=True,
)
@click.option(
    "--upgrade", help="Install the latest module and provider versions.", is_flag=True
)
@click.option(
    "--fail-at-end",
    help="If specified, only fail afterwards; allow all non-impacted projects to continue.",
    default=False,
    is_flag=True,
)
def init(
    path: str | None,
    migrate_state: bool,
    no_backend: bool,
    reconfigure: bool,
    upgrade: bool,
    fail_at_end: bool,
) -> None:
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
                                SharedContext.shared_dir()
                                .joinpath(dependency.source)
                                .as_posix(),
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
                backend_config={
                    "key": os.path.relpath(full_path, SharedContext.resources_dir())
                },
                migrate_state=migrate_state,
                no_backend=no_backend,
                reconfigure=reconfigure,
                upgrade=upgrade,
            )
        except ErrorReturnCode:
            errors = True
            if not fail_at_end:
                break

    # Report any errors if fail_at_end has been enabled
    if errors:
        raise Exit(code=1)


@click.command("get")
@click.argument("path", type=str, required=False)
@click.option(
    "--selector", "selectors", type=SelectorType(), required=False, multiple=True
)
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
        except ErrorReturnCode as err:
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
        Log.fatal(
            "The syntax is probably incorrect in one of the projects. See above for errors."
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
                    (
                        Path(path),
                        docs_dir.joinpath(
                            os.path.relpath(
                                path, SharedContext.resources_dir().as_posix()
                            )
                        ),
                    )
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
        target_path.with_suffix(".md").write_text(
            data=formatted, encoding=Constants.ENCODING_UTF_8
        )


@click.command("plan")
@click.argument("path", type=str, required=False)
@click.option(
    "--compact-warnings",
    help="If Terraform produces any warnings that are not by errors, show them in a more compact that includes only the summary messages.",
    is_flag=True,
)
@click.option(
    "--input/--no-input",
    help="Ask for input for variables if not directly set.",
    default=True,
)
@click.option(
    "--no-color", help="If specified, output won't contain any color.", is_flag=True
)
@click.option(
    "--parallelism",
    help="Limit the number of parallel resource operations.",
    type=int,
    default=10,
)
@click.option(
    "--fail-at-end",
    help="If specified, only fail afterwards; allow all non-impacted projects to continue.",
    default=False,
    is_flag=True,
)
@click.option(
    "--detailed-exitcode",
    help="""
    \b
    Return detailed exit codes when the command exits.
    This will change the meaning of exit codes to:
    0 - Succeeded, diff is empty (no changes)
    1 - Errored
    2 - Succeeded, there is a diff
    """,
    is_flag=True,
)
@click.option(
    "--out",
    help="Write a plan file to the given path",
    type=click.Path(path_type=Path, dir_okay=False, writable=True),
    required=False,
)
def plan(
    path: str | None,
    compact_warnings: bool,
    input: bool,
    no_color: bool,
    parallelism: int,
    fail_at_end: bool,
    detailed_exitcode: bool,
    out: Path | None,
) -> None:
    """Show changes required by the current configuration."""
    # Find all resources manifests
    paths = resource_dirs(path)

    # Store errors if fail_at_end
    errors = False
    error_exit_codes = []

    # Execution plan
    execution_plan = {}

    # Generate all plans
    for full_path, rel_path in paths:
        Log.action(f"Generating plan: {rel_path}")

        # Mount terraform context
        terraform = mount_context(full_path, import_vars=True)

        # Execute plan command
        try:
            args = {
                "compact_warnings": compact_warnings,
                "input": input,
                "no_color": no_color,
                "parallelism": parallelism,
                "detailed_exitcode": detailed_exitcode,
            }

            if out:
                with NamedTemporaryFile(prefix="terranova-") as file_descriptor:
                    path = Path(file_descriptor.name)
                    args["out"] = path
                    try:
                        terraform.plan(**args)
                        execution_plan[rel_path] = b64encode(path.read_bytes()).decode(
                            Constants.ENCODING_UTF_8
                        )
                    except ErrorReturnCode as plan_err:
                        if plan_err.exit_code == 2:
                            execution_plan[rel_path] = b64encode(
                                path.read_bytes()
                            ).decode(Constants.ENCODING_UTF_8)
                        raise plan_err
            else:
                terraform.plan(**args)
        except ErrorReturnCode as err:
            errors = True
            error_exit_codes.append(err.exit_code)
            if not fail_at_end:
                break

    def write_plan():
        out.write_text(json.dumps(execution_plan))
        Log.action(
            f"Saved terranova plan to: {out}\n\n"
            f"To perform exactly these actions with terranova, run the following command to apply:\n"
            f'    terranova apply "{out}"'
        )

    # Report any errors if fail_at_end has been enabled
    if errors:
        # The error_exit_codes list contains the numbers 1, 2, or both if detailed-exitcode is enabled.
        # See https://developer.hashicorp.com/terraform/cli/commands/plan#detailed-exitcode fur further details.
        # If 1 is present, the plan failed for at least one path, hence we should return 1.
        # If all exit codes are 2, the plan succeeded for all paths, but there are changes, hence we should return 2.
        exit_code = 1 if 1 in error_exit_codes else 2
        # Exit code 2 is a success, but there are changes. Hence, we should write the plan to the given path.
        if exit_code == 2 and out:
            write_plan()
        raise Exit(code=exit_code)

    # Generate terranova plan
    if out:
        write_plan()


@click.command("apply")
@click.argument("path_or_plan", type=str, required=False)
@click.option(
    "--auto-approve",
    help="Skip interactive approval of plan before applying.",
    is_flag=True,
)
@click.option("--target", help="Apply changes for specific target.", type=str)
@click.option(
    "--fail-at-end",
    help="If specified, only fail afterwards; allow all non-impacted projects to continue.",
    default=False,
    is_flag=True,
)
def apply(
    path_or_plan: str | None, auto_approve: bool, target: str, fail_at_end: bool
) -> None:
    """Create or update resources."""
    # Check if there is a plan to apply
    if path_or_plan.endswith("tnplan"):
        execution_plan = json.loads(
            Path(path_or_plan).read_text(Constants.ENCODING_UTF_8)
        )
        paths = []
        for rel_path in execution_plan.keys():
            paths.append((SharedContext.resources_dir().joinpath(rel_path), rel_path))
    else:
        execution_plan = None

        # Find all resources manifests
        paths = resource_dirs(path_or_plan)

    # Store errors if fail_at_end
    errors = False

    # Apply each independent plan
    for full_path, rel_path in paths:
        Log.action(f"Applying plan: {rel_path}")

        # Mount terraform context
        terraform = mount_context(full_path, import_vars=True)

        # Execute apply command
        try:
            if execution_plan:
                with NamedTemporaryFile(prefix="terranova-") as file_descriptor:
                    path = Path(file_descriptor.name)
                    path.write_bytes(b64decode(execution_plan[rel_path]))
                    terraform.apply(
                        plan=file_descriptor.name,
                        auto_approve=auto_approve,
                        target=target,
                    )
            else:
                terraform.apply(auto_approve=auto_approve, target=target)
        except ErrorReturnCode:
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
        except ErrorReturnCode as err:
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
    except ErrorReturnCode as err:
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
    except ErrorReturnCode as err:
        raise Exit(code=err.exit_code) from err


@click.command("untaint")
@click.argument("path", type=str)
@click.argument("address", type=str)
def untaint(path: str, address: str) -> None:
    """Remove the 'tainted' state from a resource instance."""
    # Construct resources path
    full_path = SharedContext.resources_dir().joinpath(path)

    # Mount terraform context
    terraform = mount_context(full_path, import_vars=True)

    # Execute untaint command
    try:
        terraform.untaint(address)
    except ErrorReturnCode as err:
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
    except ErrorReturnCode as err:
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
    matching_runbooks = (
        [rb for rb in manifest.runbooks if rb.name == name] if manifest.runbooks else []
    )
    if not matching_runbooks:
        Log.fatal("execute runbook", MissingRunbookError(name))
    if len(matching_runbooks) > 1:
        Log.fatal("execute runbook", AmbiguousRunbookError(name))

    # Import vars
    import_vars = extract_import_vars(manifest)

    # Execute runbook
    executable_runbook = next(iter(matching_runbooks))
    try:
        executable_runbook.exec(path, full_path / "runbooks", import_vars)
    except MissingRunbookEnvError as err:
        Log.fatal("find environment variable", err)
    except ErrorReturnCode as err:
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
