"""bin/ 启动器测试：验证 dmlinux 在任意目录下都能正常工作。

覆盖三种调用方式：
  - cmd.exe / PowerShell 走 dmlinux.cmd（PATHEXT 命中）
  - Unix shell / git-bash 走无扩展名的 dmlinux（精确同名命中）
  - 退出码透传：0 命中 / 1 无命中 / 2 用法错误
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / "bin"

pytestmark = pytest.mark.skipif(
    os.name != "nt",
    reason="dmlinux.cmd 是 Windows 启动器，非 Windows 平台不适用",
)


def _env_with_bin() -> dict[str, str]:
    env = dict(os.environ)
    env["PATH"] = f"{BIN}{os.pathsep}{env.get('PATH', '')}"
    return env


def _run_in_cmd(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    """在 cmd.exe 里通过 PATH 查找 dmlinux，模拟用户的真实用法。"""
    cmdline = "dmlinux " + subprocess.list2cmdline(args)
    return subprocess.run(
        ["cmd.exe", "/d", "/c", cmdline],
        cwd=str(cwd),
        env=_env_with_bin(),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _run_in_bash(args: list[str], cwd: Path, bash: str) -> subprocess.CompletedProcess:
    """在 bash 里通过 PATH 查找 dmlinux（命中无扩展名的那份）。

    bash 会把反斜杠当转义符，所以 Windows 路径要先转成 C:/... 形式。
    """
    posix_args = [a.replace("\\", "/") for a in args]
    cmdline = "dmlinux " + subprocess.list2cmdline(posix_args)
    return subprocess.run(
        [bash, "-c", cmdline],
        cwd=str(cwd),
        env=_env_with_bin(),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


@pytest.fixture
def sample_file(tmp_path: Path) -> Path:
    target = tmp_path / "app.log"
    target.write_text("INFO start\nERROR failed\nwarn retry\n", encoding="utf-8")
    return target


def test_launcher_files_exist():
    assert (BIN / "dmlinux.cmd").is_file()
    assert (BIN / "dmlinux").is_file()


def test_cmd_launcher_finds_match_from_any_cwd(sample_file: Path, tmp_path: Path):
    other = tmp_path / "elsewhere"
    other.mkdir()
    result = _run_in_cmd(["grep", "-n", "ERROR", str(sample_file)], cwd=other)
    assert result.returncode == 0
    assert "2:ERROR failed" in result.stdout


def test_cmd_launcher_exit_code_no_match(sample_file: Path, tmp_path: Path):
    result = _run_in_cmd(["grep", "nothing-here", str(sample_file)], cwd=tmp_path)
    assert result.returncode == 1


def test_cmd_launcher_exit_code_unknown_command(tmp_path: Path):
    result = _run_in_cmd(["no-such-command"], cwd=tmp_path)
    assert result.returncode == 2


def test_cmd_launcher_help(tmp_path: Path):
    result = _run_in_cmd(["--help"], cwd=tmp_path)
    assert result.returncode == 0
    assert "grep" in result.stdout


def test_cmd_launcher_help_uses_dmlinux_name(tmp_path: Path):
    """通过启动器调用时，帮助文案应显示 dmlinux，而不是 python main.py。"""
    result = _run_in_cmd(["--help"], cwd=tmp_path)
    assert "dmlinux <指令>" in result.stdout
    assert "python main.py" not in result.stdout


def test_cmd_launcher_grep_help_uses_dmlinux_name(tmp_path: Path):
    result = _run_in_cmd(["grep", "--help"], cwd=tmp_path)
    assert result.returncode == 0
    assert "dmlinux grep" in result.stdout


def test_direct_entry_keeps_python_main_py_name(tmp_path: Path):
    """直接跑 main.py 时帮助文案保持原样，避免回归。"""
    proc = subprocess.run(
        [sys.executable, str(ROOT / "main.py"), "--help"],
        cwd=str(tmp_path),
        env={k: v for k, v in os.environ.items() if k != "DMLINUX"},
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert proc.returncode == 0
    assert "python main.py <指令>" in proc.stdout
    assert "dmlinux" not in proc.stdout


def test_entry_name_follows_env_flag(monkeypatch):
    from w2l.entry import command_prog, entry_name

    monkeypatch.delenv("DMLINUX", raising=False)
    assert entry_name() == "python main.py"
    monkeypatch.setenv("DMLINUX", "1")
    assert entry_name() == "dmlinux"
    assert command_prog("grep") == "dmlinux grep"


def test_sh_launcher_finds_match_from_any_cwd(sample_file: Path, tmp_path: Path):
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("PATH 中没有 bash，跳过 shell 启动器测试")
    other = tmp_path / "elsewhere"
    other.mkdir()
    result = _run_in_bash(["grep", "-n", "ERROR", str(sample_file)], cwd=other, bash=bash)
    assert result.returncode == 0
    assert "2:ERROR failed" in result.stdout
