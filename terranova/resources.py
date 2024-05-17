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
import pkgutil
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from re import Pattern

import yaml
from dataclasses_json import config, dataclass_json
from jsonschema.exceptions import ValidationError
from jsonschema.validators import validate
from sh import Command

from .exceptions import (
    InvalidManifestError,
    InvalidResourcesError,
    MissingManifestError,
    MissingRunbookEnvError,
    UnreadableManifestError,
    VersionManifestError,
)
from .utils import Constants, SharedContext


@dataclass_json
@dataclass(frozen=True)
class ResourcesMetadata:
    """Represents resources metadata"""

    name: str
    description: str
    url: str | None = None
    contact: str | None = None


@dataclass_json
@dataclass(frozen=True)
class ResourcesDependency:
    """Represents resources dependency"""

    source: str
    target: str


@dataclass_json
@dataclass(frozen=True)
class ResourcesRunbookEnv:
    """Represents resources runbook env."""

    name: str
    value: str | None = None


@dataclass_json
@dataclass(frozen=True)
class ResourcesRunbook:
    """
    Represents resources runbook

    Raises:
        ErrorReturnCode: if the runbook exit with non-zero code.
        MissingRunbookEnvError: if a forward env var is missing.
    """

    name: str
    entrypoint: str
    workdir: str | None = None
    args: list[str] | None = None
    env: list[ResourcesRunbookEnv] | None = None

    def exec(self, path: str, workdir: Path) -> None:
        """Try to execute the runbook."""
        env = {
            "TERRANOVA_PATH": path,
            "TERRANOVA_CONF_DIR": SharedContext.conf_dir().absolute().as_posix(),
            "TERRANOVA_RUNBOOK_NAME": self.name,
        }
        cmd_path = os.getenv("PATH")
        if cmd_path:
            env["PATH"] = cmd_path
        if self.env:
            for entry in self.env:
                if entry.value:
                    env[entry.name] = entry.value
                else:
                    maybe_env_var = os.getenv(entry.name)
                    if not maybe_env_var:
                        raise MissingRunbookEnvError(entry.name)
                    env[entry.name] = maybe_env_var
        if self.workdir:
            workdir = workdir.joinpath(self.workdir)
        entrypoint = Command(self.entrypoint)
        entrypoint(self.args, _env=env, _cwd=workdir, _in=sys.stdin, _out=sys.stdout, _err=sys.stderr)


@dataclass_json
@dataclass(frozen=True)
class ResourcesImport:
    """Represents resources import."""

    source: str = field(metadata=config(field_name="from"))
    resource: str = field(metadata=config(field_name="import"))
    target: str | None = field(default=None, metadata=config(field_name="as"))


@dataclass_json
@dataclass(frozen=True)
class ResourcesManifest:
    """Represents a resources manifest"""

    metadata: ResourcesMetadata
    dependencies: list[ResourcesDependency] | None = None
    runbooks: list[ResourcesRunbook] | None = None
    imports: list[ResourcesImport] | None = None

    @staticmethod
    def from_file(path: Path) -> "ResourcesManifest":
        """
        Read a resources manifest

        Args:
            path: path to manifest.
        Raises:
            MissingManifestError: if the manifest is missing.
            UnreadableManifestError: if the manifest can't be read.
            VersionManifestError: if the version manifest isn't supported.
            InvalidManifestError: if the manifest isn't invalid.
        """
        if not path.exists() or not path.is_file():
            raise MissingManifestError(path)
        if not os.access(path.as_posix(), os.R_OK):
            raise UnreadableManifestError(path)

        with path.open(Constants.FILE_MODE_READ, encoding=Constants.ENCODING_UTF_8) as file_descriptor:
            try:
                data = yaml.safe_load(file_descriptor)
            except yaml.YAMLError as err:
                raise InvalidManifestError(path) from err

            # Check version
            version = data.get("version", "1.0")

            # Get configuration schema
            try:
                schema = pkgutil.get_data(__name__, f"schemas/manifest_schema_v{version}.json")
            except FileNotFoundError as err:
                raise VersionManifestError(version) from err
            schema = json.loads(schema)

            # Validate manifest
            try:
                validate(instance=data, schema=schema)
            except ValidationError as err:
                raise InvalidManifestError(path) from err
            # noinspection PyUnresolvedReferences
            # pylint: disable=E1101
            return ResourcesManifest.from_dict(data)


@dataclass
class Resource:
    """Represents a resource."""

    name: str
    type: str
    attrs: dict[str, list[str]]


@dataclass
class Selector:
    """Represents a resource selector."""

    name: str
    value: str | None = None

    def match(self, resource: Resource) -> bool:
        """
        Returns:
            true if the selector matches the resource, otherwise false.
        """
        attr_value = resource.attrs.get(self.name)
        if self.value and attr_value and self.value not in attr_value:
            return False
        if not attr_value:
            return False
        return True


class ResourcesFinder:
    """Represents a resources finder able to find resources in files and directories."""

    # Resource patterns
    __RESOURCE_PATTERN: Pattern = re.compile(
        r"""(/\*(?P<comments>[@\S\s\n]*?)\*/\n)?resource \"(?P<resource_type>\w+)\" \"(?P<resource_name>[a-zA-Z0-9_-]+)\""""
    )
    __RESOURCE_ATTR_PATTERN: Pattern = re.compile(r"""@(?P<attr_name>\S+)\s+(?P<attr_value>.+)""")

    @staticmethod
    def find_in_dir(path: Path, selectors: list[Selector] | None = None) -> list[Resource]:
        """
        Find all resources in directory.

        Args:
            path: path to directory.
        Returns:
            list of resources in a file.
        Raises:
            InvalidResourcesError: if a resource doesn't have metadata.
        """
        resources = []
        for file in sorted(path.glob("*.tf")):
            resources += ResourcesFinder.find_in_file(file, selectors)
        return resources

    # pylint: disable=R0914
    @staticmethod
    def find_in_file(path: Path, selectors: list[Selector] | None = None) -> list[Resource]:
        """
        Find all resources in a file.

        Args:
            path: path to file.
            selectors: optional list of selectors.
        Returns:
            list of resources in a file.
        Raises:
            InvalidResourcesError: if a resource doesn't have metadata.
        """
        resources = []

        # Read file content
        content = path.read_text(Constants.ENCODING_UTF_8)

        # Detect all resources with metadata
        detected_resources = ResourcesFinder.__RESOURCE_PATTERN.findall(content)
        for resource_match in detected_resources:
            # Extract match groups
            if len(resource_match) < 4:
                _, resource_type, resource_name = resource_match
                raise InvalidResourcesError(
                    cause=f"The resource `{resource_type}:{resource_name}` at `{path.as_posix()}` isn't describe.",
                    resolution="Add metadata for the above resource.",
                )

            _, maybe_resource_attrs, resource_type, resource_name = resource_match
            maybe_resource_attrs = maybe_resource_attrs.strip()
            if not maybe_resource_attrs:
                raise InvalidResourcesError(
                    cause=f"The resource `{resource_type}:{resource_name}` at `{path.as_posix()}` isn't describe.",
                    resolution="Add metadata for the above resource.",
                )

            # Parse attributes
            attrs = defaultdict(list)
            for maybe_attr in maybe_resource_attrs.splitlines():
                attr_match = ResourcesFinder.__RESOURCE_ATTR_PATTERN.match(maybe_attr)
                if attr_match:
                    name, value = attr_match.groups()
                    attrs[name].append(value)
            resource = Resource(name=resource_name, type=resource_type, attrs=attrs)

            # Filter resource by selector
            match = True
            if selectors:
                for selector in selectors:
                    match = selector.match(resource)
                    if not match:
                        break
            if match:
                resources.append(resource)
        return resources
