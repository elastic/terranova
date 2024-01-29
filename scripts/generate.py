import sys

from sh import pyinstaller


def run() -> None:
    args = ["-n", "terranova", "--onefile", "--noconfirm"]
    args.extend(
        [
            "--add-data",
            "terranova/schemas/:terranova/schemas/",
            "--add-data",
            "terranova/templates/:terranova/templates/",
            "./bin/terranova",
        ]
    )
    pyinstaller(args, _out=sys.stdout, _err=sys.stderr)
