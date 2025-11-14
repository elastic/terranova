from __future__ import annotations

import asyncio
import os
import sys
from io import StringIO
from pathlib import Path
from queue import Queue

import pytest

from terranova.process import (
    Bind,
    Command,
    CommandNotFound,
    EnvCmd,
    ErrorReturnCode,
    PathCmd,
    TimeoutException,
)


class TestEnvCmd:
    def test_empty(self) -> None:
        env = EnvCmd.empty()
        assert env.build() == {}

    def test_inherit_copies_os_environ(self) -> None:
        env = EnvCmd.inherit()
        result = env.build()
        assert result == dict(os.environ)
        result["__SENTINEL__"] = "x"
        assert "__SENTINEL__" not in env.build()

    def test_inherit_with_predicate(self) -> None:
        os.environ["_TEST_VAR_KEEP"] = "yes"
        os.environ["_TEST_VAR_DROP"] = "no"
        try:
            env = EnvCmd.inherit(predicate=lambda k, _: k == "_TEST_VAR_KEEP")
            result = env.build()
            assert "_TEST_VAR_KEEP" in result
            assert "_TEST_VAR_DROP" not in result
        finally:
            del os.environ["_TEST_VAR_KEEP"]
            del os.environ["_TEST_VAR_DROP"]

    def test_add_updates_vars(self) -> None:
        env = EnvCmd.empty()
        returned = env.add({"FOO": "bar", "BAZ": "qux"})
        assert returned is env
        assert env.build() == {"FOO": "bar", "BAZ": "qux"}

    def test_add_chaining(self) -> None:
        env = EnvCmd.empty().add({"A": "1"}).add({"B": "2"})
        assert env.build() == {"A": "1", "B": "2"}

    def test_add_overwrites_existing(self) -> None:
        env = EnvCmd.empty().add({"KEY": "old"}).add({"KEY": "new"})
        assert env.build()["KEY"] == "new"


class TestPathCmd:
    def test_empty(self) -> None:
        path = PathCmd.empty()
        assert path.build() == ""

    def test_inherit(self) -> None:
        path = PathCmd.inherit()
        assert path.build() == os.environ.get("PATH", "")

    def test_add_prepends(self) -> None:
        path = PathCmd.empty().add("/usr/local/bin").add("/opt/bin")
        parts = path.build().split(os.pathsep)
        assert parts[0] == "/opt/bin"
        assert parts[1] == "/usr/local/bin"

    def test_add_returns_self(self) -> None:
        path = PathCmd.empty()
        returned = path.add("/bin")
        assert returned is path

    def test_inherit_then_prepend(self) -> None:
        path = PathCmd.inherit().add("/custom/bin")
        parts = path.build().split(os.pathsep)
        assert parts[0] == "/custom/bin"


class TestCommand:
    def test_not_found_raises(self) -> None:
        with pytest.raises(CommandNotFound) as exc_info:
            Command("__no_such_binary_exists__")
        assert exc_info.value.command == "__no_such_binary_exists__"
        assert "__no_such_binary_exists__" in str(exc_info.value)

    def test_binary_path(self) -> None:
        cmd = Command("echo")
        assert cmd.binary_path().is_absolute()
        assert cmd.binary_path().name == "echo"

    def test_args_getter_returns_empty_tuple_by_default(self) -> None:
        cmd = Command("echo")
        assert cmd.args() == ()

    def test_args_setter_and_getter(self) -> None:
        cmd = Command("echo")
        returned = cmd.args("hello", "world")
        assert returned is cmd
        assert cmd.args() == ("hello", "world")

    def test_env_getter_returns_empty_dict_by_default(self) -> None:
        cmd = Command("echo")
        assert cmd.env() == {}

    def test_env_setter_and_getter(self) -> None:
        cmd = Command("echo")
        returned = cmd.env({"FOO": "bar"})
        assert returned is cmd
        assert cmd.env() == {"FOO": "bar"}
        cmd.env()["EXTRA"] = "x"
        assert "EXTRA" not in cmd.env()

    def test_cwd_getter_returns_cwd(self) -> None:
        cmd = Command("echo")
        assert cmd.cwd() == Path.cwd()

    def test_cwd_setter_and_getter(self) -> None:
        cmd = Command("echo")
        new_cwd = Path("/tmp")
        returned = cmd.cwd(new_cwd)
        assert returned is cmd
        assert cmd.cwd() == new_cwd

    def test_stdin_getter_returns_none_by_default(self) -> None:
        cmd = Command("echo")
        assert cmd.stdin() is None

    def test_stdin_setter(self) -> None:
        cmd = Command("echo")
        returned = cmd.stdin("some input")
        assert returned is cmd
        assert cmd.stdin() == "some input"

    def test_stdout_getter_returns_none_by_default(self) -> None:
        cmd = Command("echo")
        assert cmd.stdout() is None

    def test_stdout_setter_callable(self) -> None:
        cmd = Command("echo")
        callback = lambda _: None  # noqa: E731
        cmd.stdout(callback)
        assert cmd.stdout() is callback

    def test_stdout_setter_path_is_absolutized(self) -> None:
        cmd = Command("echo")
        relative = Path("output.txt")
        cmd.stdout(relative)
        assert cmd.stdout() == relative.absolute()

    def test_stderr_getter_returns_none_by_default(self) -> None:
        cmd = Command("echo")
        assert cmd.stderr() is None

    def test_stderr_setter_path_is_absolutized(self) -> None:
        cmd = Command("echo")
        relative = Path("error.txt")
        cmd.stderr(relative)
        assert cmd.stderr() == relative.absolute()

    def test_inherit_sets_all_streams(self) -> None:
        cmd = Command("echo")
        returned = cmd.inherit()
        assert returned is cmd
        assert cmd.stdin() is sys.stdin
        assert cmd.stdout() is sys.stdout
        assert cmd.stderr() is sys.stderr

    def test_inherit_out_sets_stdout_stderr(self) -> None:
        cmd = Command("echo")
        returned = cmd.inherit_out()
        assert returned is cmd
        assert cmd.stdout() is sys.stdout
        assert cmd.stderr() is sys.stderr

    def test_timeout_setter(self) -> None:
        cmd = Command("echo")
        returned = cmd.timeout(30)
        assert returned is cmd

    def test_copy_from_another_command(self) -> None:
        src = Command("echo")
        src.args("hello").env({"X": "1"}).cwd(Path("/tmp")).timeout(10)
        dst = Command("echo")
        returned = dst.copy(src)
        assert returned is dst
        assert dst.args() == ("hello",)
        assert dst.env() == {"X": "1"}
        assert dst.cwd() == Path("/tmp")

    def test_exec_success(self) -> None:
        cmd = Command("echo").args("hello")
        process = cmd.exec()
        assert process.returncode == 0

    def test_exec_raises_error_return_code(self) -> None:
        cmd = Command("false")
        with pytest.raises(ErrorReturnCode) as exc_info:
            cmd.exec()
        assert exc_info.value.exit_code != 0
        assert "false" in exc_info.value.cmd

    def test_error_return_code_properties(self) -> None:
        err = ErrorReturnCode(cmd="mycmd", exit_code=42)
        assert err.cmd == "mycmd"
        assert err.exit_code == 42
        assert "mycmd" in str(err)
        assert "42" in str(err)

    def test_exec_raises_timeout_exception(self) -> None:
        cmd = Command("sleep").args("10").timeout(1)
        with pytest.raises(TimeoutException) as exc_info:
            cmd.exec()
        assert exc_info.value.timeout == 1
        assert "sleep" in exc_info.value.cmd

    def test_timeout_exception_properties(self) -> None:
        err = TimeoutException(cmd="mycmd", timeout=5.0)
        assert err.cmd == "mycmd"
        assert err.timeout == 5.0
        assert "mycmd" in str(err)
        assert "5.0" in str(err)

    def test_exec_no_wait_returns_running_process(self) -> None:
        cmd = Command("sleep").args("5")
        process = cmd.exec(wait_completion=False)
        assert process.returncode is None
        process.terminate()
        process.wait()

    def test_exec_stdout_to_callable(self) -> None:
        lines: list[str] = []
        cmd = Command("echo").args("hello world")
        cmd.stdout(lines.append)
        cmd.exec()
        assert any("hello world" in line for line in lines)

    def test_exec_stderr_to_callable(self) -> None:
        lines: list[str] = []
        cmd = Command("sh").args("-c", "echo error >&2")
        cmd.stderr(lines.append)
        cmd.exec()
        assert any("error" in line for line in lines)

    def test_exec_stdout_to_stringio(self) -> None:
        buf = StringIO()
        cmd = Command("echo").args("captured")
        cmd.stdout(buf)
        cmd.exec()
        assert "captured" in buf.getvalue()

    def test_exec_stdout_to_file(self, tmp_path: Path) -> None:
        out_file = tmp_path / "out.txt"
        cmd = Command("echo").args("file output")
        cmd.stdout(out_file)
        cmd.exec()
        assert "file output" in out_file.read_text()

    def test_exec_stderr_to_file(self, tmp_path: Path) -> None:
        err_file = tmp_path / "err.txt"
        cmd = Command("sh").args("-c", "echo err_content >&2")
        cmd.stderr(err_file)
        cmd.exec()
        assert "err_content" in err_file.read_text()

    def test_exec_stdin_from_string(self) -> None:
        lines: list[str] = []
        cmd = Command("cat")
        cmd.stdin("hello from stdin\n")
        cmd.stdout(lines.append)
        cmd.exec()
        assert any("hello from stdin" in line for line in lines)

    def test_exec_stdin_from_queue(self) -> None:
        lines: list[str] = []
        q: Queue = Queue()
        q.put("line1\n")
        q.put("line2\n")
        q.put(None)
        cmd = Command("cat")
        cmd.stdin(q)
        cmd.stdout(lines.append)
        cmd.exec()
        assert any("line1" in line for line in lines)
        assert any("line2" in line for line in lines)

    def test_exec_with_env(self) -> None:
        lines: list[str] = []
        env = EnvCmd.inherit().add({"MY_TEST_VAR": "my_value"}).build()
        cmd = Command("sh").args("-c", "echo $MY_TEST_VAR")
        cmd.env(env)
        cmd.stdout(lines.append)
        cmd.exec()
        assert any("my_value" in line for line in lines)

    def test_exec_with_cwd(self, tmp_path: Path) -> None:
        lines: list[str] = []
        cmd = Command("pwd")
        cmd.cwd(tmp_path)
        cmd.stdout(lines.append)
        cmd.exec()
        assert any(str(tmp_path) in line for line in lines)

    def test_exec_command_not_found_from_path(self) -> None:
        with pytest.raises(CommandNotFound):
            Command(Path("/no/such/binary")).exec()

    def test_aexec_success(self) -> None:
        async def run() -> None:
            cmd = Command("echo").args("async hello")
            process = await cmd.aexec()
            assert process.returncode == 0

        asyncio.run(run())

    def test_aexec_raises_error_return_code(self) -> None:
        async def run() -> None:
            cmd = Command("false")
            with pytest.raises(ErrorReturnCode):
                await cmd.aexec()

        asyncio.run(run())

    def test_aexec_raises_timeout_exception(self) -> None:
        async def run() -> None:
            cmd = Command("sleep").args("10").timeout(1)
            with pytest.raises(TimeoutException):
                await cmd.aexec()

        asyncio.run(run())

    def test_aexec_no_wait_returns_running_process(self) -> None:
        async def run() -> None:
            cmd = Command("sleep").args("5")
            process = await cmd.aexec(wait_completion=False)
            assert process.returncode is None
            process.terminate()
            await process.wait()

        asyncio.run(run())

    def test_aexec_stdout_to_callable(self) -> None:
        async def run() -> list[str]:
            lines: list[str] = []
            cmd = Command("echo").args("async output")
            cmd.stdout(lines.append)
            await cmd.aexec()
            return lines

        lines = asyncio.run(run())
        assert any("async output" in line for line in lines)

    def test_aexec_stderr_to_callable(self) -> None:
        async def run() -> list[str]:
            lines: list[str] = []
            cmd = Command("sh").args("-c", "echo async_err >&2")
            cmd.stderr(lines.append)
            await cmd.aexec()
            return lines

        lines = asyncio.run(run())
        assert any("async_err" in line for line in lines)

    def test_aexec_stdout_to_stringio(self) -> None:
        async def run() -> str:
            buf = StringIO()
            cmd = Command("echo").args("async captured")
            cmd.stdout(buf)
            await cmd.aexec()
            return buf.getvalue()

        result = asyncio.run(run())
        assert "async captured" in result

    def test_aexec_stdout_to_file(self, tmp_path: Path) -> None:
        async def run() -> None:
            out_file = tmp_path / "async_out.txt"
            cmd = Command("echo").args("async file output")
            cmd.stdout(out_file)
            await cmd.aexec()
            assert "async file output" in out_file.read_text()

        asyncio.run(run())

    def test_aexec_stdin_from_string(self) -> None:
        async def run() -> list[str]:
            lines: list[str] = []
            cmd = Command("cat")
            cmd.stdin("async stdin\n")
            cmd.stdout(lines.append)
            await cmd.aexec()
            return lines

        lines = asyncio.run(run())
        assert any("async stdin" in line for line in lines)

    def test_aexec_stdin_from_queue(self) -> None:
        async def run() -> list[str]:
            lines: list[str] = []
            q: Queue = Queue()
            q.put("async_line1\n")
            q.put("async_line2\n")
            q.put(None)
            cmd = Command("cat")
            cmd.stdin(q)
            cmd.stdout(lines.append)
            await cmd.aexec()
            return lines

        lines = asyncio.run(run())
        assert any("async_line1" in line for line in lines)
        assert any("async_line2" in line for line in lines)

    def test_aexec_with_env(self) -> None:
        async def run() -> list[str]:
            lines: list[str] = []
            env = EnvCmd.inherit().add({"ASYNC_VAR": "async_val"}).build()
            cmd = Command("sh").args("-c", "echo $ASYNC_VAR")
            cmd.env(env)
            cmd.stdout(lines.append)
            await cmd.aexec()
            return lines

        lines = asyncio.run(run())
        assert any("async_val" in line for line in lines)

    def test_aexec_with_cwd(self, tmp_path: Path) -> None:
        async def run() -> list[str]:
            lines: list[str] = []
            cmd = Command("pwd")
            cmd.cwd(tmp_path)
            cmd.stdout(lines.append)
            await cmd.aexec()
            return lines

        lines = asyncio.run(run())
        assert any(str(tmp_path) in line for line in lines)


class TestBind:
    def _make_bind(self) -> Bind:
        return Bind("echo")

    def test_command_not_found(self) -> None:
        with pytest.raises(CommandNotFound):
            Bind("__no_such_binary_exists__")

    def test_binary_path(self) -> None:
        b = self._make_bind()
        assert b.binary_path().name == "echo"

    def test_env_getter(self) -> None:
        b = self._make_bind()
        assert b.env() == {}

    def test_env_setter_chaining(self) -> None:
        b = self._make_bind()
        returned = b.env({"K": "V"})
        assert returned is b
        assert b.env() == {"K": "V"}

    def test_cwd_getter(self) -> None:
        b = self._make_bind()
        assert b.cwd() == Path.cwd()

    def test_cwd_setter_chaining(self) -> None:
        b = self._make_bind()
        returned = b.cwd(Path("/tmp"))
        assert returned is b
        assert b.cwd() == Path("/tmp")

    def test_stdin_chaining(self) -> None:
        b = self._make_bind()
        returned = b.stdin("data")
        assert returned is b

    def test_stdout_chaining(self) -> None:
        b = self._make_bind()
        returned = b.stdout(lambda _: None)
        assert returned is b

    def test_stderr_chaining(self) -> None:
        b = self._make_bind()
        returned = b.stderr(lambda _: None)
        assert returned is b

    def test_inherit_chaining(self) -> None:
        b = self._make_bind()
        returned = b.inherit()
        assert returned is b

    def test_inherit_out_chaining(self) -> None:
        b = self._make_bind()
        returned = b.inherit_out()
        assert returned is b

    def test_timeout_chaining(self) -> None:
        b = self._make_bind()
        returned = b.timeout(30)
        assert returned is b

    def test_copy_chaining(self) -> None:
        src_cmd = Command("echo")
        src_cmd.args("hi").env({"X": "1"})
        b = self._make_bind()
        returned = b.copy(src_cmd)
        assert returned is b

    def test_create_returns_command(self) -> None:
        b = self._make_bind()
        cmd = b.create("echo")
        assert isinstance(cmd, Command)