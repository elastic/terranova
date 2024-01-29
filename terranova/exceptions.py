from pathlib import Path


class ExplainedError(Exception):
    """
    Represents an explained error.
    The error should contain the cause and a possible resolution.
    """

    def __init__(self, cause: str, resolution: str | None = None) -> None:
        """Init explained error."""
        self.__cause = cause
        self.__resolution = resolution

    @property
    def cause(self) -> str:
        """
        Returns:
            cause of the error.
        """
        return self.__cause

    @property
    def resolution(self) -> str | None:
        """
        Returns:
            possible resolution of the error.
        """
        return self.__resolution


class ManifestError(ExplainedError):
    """Represents an invalid manifest."""


class InvalidManifestError(ManifestError):
    """Represents an invalid manifest error."""

    def __init__(self, path: Path) -> None:
        """Init invalid manifest error."""
        super().__init__(
            cause=f"Invalid `manifest.yml` file at `{path.as_posix()}`",
            resolution="Check the syntax or the version of the manifest.",
        )


class VersionManifestError(ManifestError):
    """Represents an version manifest error."""

    def __init__(self, version: str) -> None:
        """Init version manifest error."""
        super().__init__(
            cause=f"Manifest version `v{version}` isn't supported",
            resolution="Upgrade `terranova` version or downgrade manifest version.",
        )


class MissingManifestError(ManifestError):
    """Represents a missing manifest error."""

    def __init__(self, path: Path) -> None:
        """Init missing manifest error."""
        super().__init__(
            cause=f"Missing `manifest.yml` file at `{path.as_posix()}`",
            resolution="Create a manifest or use another location.",
        )


class UnreadableManifestError(ManifestError):
    """Represents an unreadable manifest error"""

    def __init__(self, path: Path) -> None:
        """Init missing manifest error."""
        super().__init__(
            cause=f"Unreadable `manifest.yml` file at `{path.as_posix()}`",
            resolution="Use the right user or change permissions.",
        )


class InvalidResourcesError(ExplainedError):
    """Represents an invalid resources configuration."""


class RunbookError(ExplainedError):
    """Represents a runbook error."""


class AmbiguousRunbookError(RunbookError):
    """Represents an ambiguous runbook error."""

    def __init__(self, name: str) -> None:
        """Init ambiguous runbook error."""
        super().__init__(
            cause=f"The runbook name `{name}` is ambiguous`",
            resolution="Ensure the runbook name is unique.",
        )


class MissingRunbookError(RunbookError):
    """Represents a missing runbook error."""

    def __init__(self, name: str) -> None:
        """Init missing runbook error."""
        super().__init__(
            cause=f"The runbook `{name}` isn't defined`",
            resolution="Ensure the runbook is defined.",
        )
