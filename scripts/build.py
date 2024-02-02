import platform
import sys
from pathlib import Path
from time import time

from sh import git, pyinstaller

from scripts.utils import Constants, container_backend, read_project_conf


def run() -> None:
    conf = read_project_conf()
    commit_hash_short = git("rev-parse", "--short", "HEAD").strip()
    current_time_epoch = int(time())
    version = conf.get("tool.poetry.version")
    python_version = platform.python_version()

    image_id = f"{version}-{current_time_epoch}-{commit_hash_short}"

    # Create dist dir
    local_dist_path = Path("dist")
    local_dist_path.mkdir(parents=True, exist_ok=False)
    local_dist_path = local_dist_path.absolute().as_posix()

    system = platform.system().lower()
    if system == "darwin":
        pyinstaller("terranova.spec", _out=sys.stdout, _err=sys.stderr)
        Path("./dist/terranova").replace(Path(f"./dist/terranova-{system}-{platform.machine()}"))
    elif system == "linux":
        # Use cross-build to build both amd64 and arm64 versions.
        cmd, env = container_backend()
        for platform_arch in ["linux/amd64", "linux/arm64"]:
            platform_arch_slug = platform_arch.replace("/", "-")
            cmd(
                "buildx",
                "build",
                "--load",
                "--platform",
                platform_arch,
                "--build-arg",
                f"base_image_version={python_version}",
                "--build-arg",
                f"platform_arch={platform_arch_slug}",
                "--build-arg",
                f"app_version={version}",
                "-t",
                f"{Constants.REGISTRY_URL}/terranova:{image_id}",
                "-f",
                "Containerfile",
                ".",
                _out=sys.stdout,
                _err=sys.stderr,
                _env=env,
            )
            container_id = cmd(
                "run",
                "-d",
                "--entrypoint=cat",
                f"{Constants.REGISTRY_URL}/terranova:{image_id}",
                _err=sys.stderr,
                _env=env,
            ).strip()
            cmd(
                "cp",
                f"{container_id}:/opt/terranova/dist",
                local_dist_path,
                _out=sys.stdout,
                _err=sys.stderr,
                _env=env,
            )
            cmd(
                "rm",
                "-f",
                container_id,
                _out=sys.stdout,
                _err=sys.stderr,
                _env=env,
            )
    else:
        print(f"Unsupported system: {system}", file=sys.stderr)
