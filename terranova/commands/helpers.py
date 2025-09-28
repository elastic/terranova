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
from pathlib import Path

import click
from click import Parameter
from click.exceptions import Exit
from overrides import override
from sh import ErrorReturnCode

from terranova.binds import Terraform
from terranova.exceptions import InvalidResourcesError, ManifestError
from terranova.resources import Resource, ResourcesFinder, ResourcesManifest, Selector
from terranova.utils import Constants, Log, SharedContext


class SelectorType(click.ParamType):
    """Selector param typing for click."""

    name = "selector"

    @override
    def convert(
        self, value, param: Parameter | None, ctx: click.Context | None
    ) -> Selector:
        if not isinstance(value, str):
            self.fail(f"{value!r} isn't a valid selector", param, ctx)

        data = value.split("=", maxsplit=1)
        return Selector(name=data[0], value=None if len(data) == 1 else data[1])


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
        Log.fatal("read manifest", err)


def discover_resources(
    path: Path, selectors: list[Selector] | None = None
) -> list[Resource]:
    """
    Discover resources in every terraform configuration files.
    This function handle errors by logging and exiting.

    Args:
        path: path to resources directory.
        selectors: list of selectors.

    Returns:
        list of resources.
    """
    try:
        return ResourcesFinder.find_in_dir(path, selectors)
    except InvalidResourcesError as err:
        Log.fatal(
            f"discover resources at `{path.as_posix()}`",
            err,
        )


def find_all_resource_dirs(resources_dir: Path) -> list[tuple[Path, str]]:
    """
    Find all path where there is a resource manifest.

    Returns:
        list of all path.
    """
    paths: list[tuple[Path, str]] = []
    resources_dir_path = SharedContext.resources_dir().as_posix()
    resources_dir_prefix_len = len(resources_dir_path) + 1
    for path, _, files in os.walk(resources_dir):
        for file in files:
            if os.path.basename(file) == Constants.MANIFEST_FILE_NAME:
                paths.append((Path(path), path[resources_dir_prefix_len:]))
    return paths


def resource_dirs(path: str | None) -> list[tuple[Path, str]]:
    """
    List of all resource dirs to interact with.

    Args:
        path: use a specific path.

    Returns:
        list of all resource dirs.
    """
    resources_dir = SharedContext.resources_dir()
    if path:
        resources_dir = resources_dir.joinpath(path)
    return find_all_resource_dirs(resources_dir)


def mount_context(
    full_path: Path,
    manifest: ResourcesManifest | None = None,
    import_vars: bool = False,
) -> Terraform:
    """Mount the terraform context by importing variables if needed."""
    # Ensure manifest exists and can be read
    if not manifest:
        manifest = read_manifest(full_path)

    # Import variables
    variables = extract_import_vars(manifest) if import_vars else None
    return Terraform(full_path, variables)


def extract_import_vars(manifest: ResourcesManifest) -> dict[str, str]:
    """Extract import variables from manifest."""
    variables: dict[str, str] = {}
    if manifest.imports:
        for importer in manifest.imports:
            target = importer.target if importer.target else importer.resource
            variables[target] = extract_output_var(importer.source, importer.resource)
    return variables


def extract_output_var(path: str, name: str) -> str:
    """Show output values from your root module."""
    # Construct resources path
    full_path = SharedContext.resources_dir().joinpath(path)

    # Mount terraform context
    terraform = mount_context(full_path)

    # Execute output command
    try:
        return terraform.output(name)
    except ErrorReturnCode as err:
        raise Exit(code=err.exit_code) from err
