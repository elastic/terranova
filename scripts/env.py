import sys

from sh import CommandNotFound, poetry


def configure() -> None:
    poetry("install", _out=sys.stdout, _err=sys.stderr)
    try:
        from sh import pre_commit

        pre_commit("install", _out=sys.stdout, _err=sys.stderr)
    except (CommandNotFound, ImportError):
        print("pre-commit isn't installed")
