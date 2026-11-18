"""探针二：把 GNU chmod 在本机的行为基线钉死。

上一轮探针发现 MSYS 的 chmod 似乎只存「只读属性」：
chmod 755 之后 stat 显示 644。本轮逐条验证：
- 只读属性是不是唯一的可存状态
- 目录的权限位是不是恒为 755
- -v 的「changed / unchanged」文案格式
- 符号模式在只存只读属性的前提下会怎样降级

结果写进 AI/数据/chmod_probe2_report.txt。
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
AI_DIR = HERE.parent
DATA = AI_DIR / "数据" / "chmod_probe2"
REPORT = AI_DIR / "数据" / "chmod_probe2_report.txt"

lines: list[str] = []


def say(text: str = "") -> None:
    lines.append(text)


def run(cmd: list[str], cwd: Path | None = None) -> tuple[int, str, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, proc.stdout, proc.stderr


def force_rmtree(path: Path) -> None:
    if not path.exists():
        return
    for item in path.rglob("*"):
        try:
            os.chmod(item, stat.S_IREAD | stat.S_IWRITE)
        except OSError:
            pass
    shutil.rmtree(path, ignore_errors=True)


def gnu_mode(name: str) -> str:
    code, out, err = run(["stat", "-c", "%a %A", name], cwd=DATA)
    return out.strip() or f"<rc={code} err={err.strip()}>"


def py_mode(name: str) -> str:
    path = DATA / name
    try:
        st = os.stat(path)
    except OSError as exc:
        return f"<stat 失败: {exc}>"
    return f"{stat.S_IMODE(st.st_mode):04o}"


def writable(name: str) -> str:
    """Python 视角：这个文件还能不能写（等价于只读属性有没有被设上）。"""
    path = DATA / name
    try:
        with open(path, "a", encoding="utf-8"):
            pass
        return "可写"
    except OSError:
        return "只读"


def scenario(label: str, setup: list[str], chmod_cmd: list[str], target: str) -> None:
    """重置夹具 -> 跑 setup -> 记 before -> 跑 chmod -> 记 after。"""
    force_rmtree(DATA)
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "f.txt").write_text("hello\n", encoding="utf-8")
    (DATA / "g.txt").write_text("hello\n", encoding="utf-8")
    sub = DATA / "sub"
    sub.mkdir()
    (sub / "inner.txt").write_text("inner\n", encoding="utf-8")
    (sub / "deep").mkdir()
    (sub / "deep" / "leaf.txt").write_text("leaf\n", encoding="utf-8")

    for cmd in setup:
        run(cmd, cwd=DATA)

    before_gnu = gnu_mode(target)
    before_py = py_mode(target)
    before_write = writable(target)

    code, out, err = run(chmod_cmd, cwd=DATA)

    say(f"--- {label}")
    say(f"    命令: {' '.join(chmod_cmd)}")
    say(f"    前: GNU={before_gnu} | Python={before_py} | {before_write}")
    say(f"    rc={code}")
    if out:
        say("    stdout: " + out.replace("\n", "\n      ").rstrip())
    if err:
        say("    stderr: " + err.replace("\n", "\n      ").rstrip())
    say(f"    后: GNU={gnu_mode(target)} | Python={py_mode(target)} | {writable(target)}")
    say("")


def main() -> int:
    say("=== GNU chmod 在本机的可存状态 ===")
    say("")

    # 文件：各种目标模式落到 stat 上是什么样
    for mode in ("000", "400", "444", "600", "640", "644", "700", "755", "777"):
        scenario(
            f"chmod {mode} f.txt",
            [],
            ["chmod", mode, "f.txt"],
            "f.txt",
        )

    # 只读之后再改：会不会被清掉
    scenario("先 444 再 644", [["chmod", "444", "f.txt"]], ["chmod", "644", "f.txt"], "f.txt")
    scenario("先 444 再 600", [["chmod", "444", "f.txt"]], ["chmod", "600", "f.txt"], "f.txt")
    scenario("先 444 再 u+x", [["chmod", "444", "f.txt"]], ["chmod", "u+x", "f.txt"], "f.txt")
    scenario("先 444 再 g+w", [["chmod", "444", "f.txt"]], ["chmod", "g+w", "f.txt"], "f.txt")
    scenario("先 644 再 u-w", [], ["chmod", "u-w", "f.txt"], "f.txt")
    scenario("先 644 再 a-w", [], ["chmod", "a-w", "f.txt"], "f.txt")
    scenario("先 444 再 a+w", [["chmod", "444", "f.txt"]], ["chmod", "a+w", "f.txt"], "f.txt")

    # -v / -c 的文案
    scenario(
        "-v 改可写文件成 644（本来就可写）",
        [],
        ["chmod", "-v", "644", "f.txt"],
        "f.txt",
    )
    scenario(
        "-v 改只读文件成 644",
        [["chmod", "444", "f.txt"]],
        ["chmod", "-v", "644", "f.txt"],
        "f.txt",
    )
    scenario(
        "-v 改只读文件成 444（已经是 444）",
        [["chmod", "444", "f.txt"]],
        ["chmod", "-v", "444", "f.txt"],
        "f.txt",
    )
    scenario(
        "-v 改可写文件成 600",
        [],
        ["chmod", "-v", "600", "f.txt"],
        "f.txt",
    )
    scenario(
        "-c 改只读文件成 644",
        [["chmod", "444", "f.txt"]],
        ["chmod", "-c", "644", "f.txt"],
        "f.txt",
    )
    scenario(
        "-c 改可写文件成 644（没变化）",
        [],
        ["chmod", "-c", "644", "f.txt"],
        "f.txt",
    )

    # 目录
    scenario("chmod 755 sub", [], ["chmod", "755", "sub"], "sub")
    scenario("chmod 700 sub", [], ["chmod", "700", "sub"], "sub")
    scenario("chmod 555 sub", [], ["chmod", "555", "sub"], "sub")
    scenario("chmod 444 sub", [], ["chmod", "444", "sub"], "sub")
    scenario("chmod -R 700 sub", [], ["chmod", "-R", "700", "sub"], "sub")
    scenario(
        "-R 700 sub（看子文件）",
        [],
        ["chmod", "-R", "700", "sub"],
        "sub/inner.txt",
    )
    scenario(
        "-R 444 sub（看子文件）",
        [],
        ["chmod", "-R", "444", "sub"],
        "sub/inner.txt",
    )

    # 组合模式与逗号
    scenario("chmod u+w,g-w f", [], ["chmod", "u+w,g-w", "f.txt"], "f.txt")
    scenario("chmod a=rwx f", [], ["chmod", "a=rwx", "f.txt"], "f.txt")
    scenario("chmod 644,755 f（逗号多模式）", [], ["chmod", "644,755", "f.txt"], "f.txt")
    scenario("chmod 0644 f", [], ["chmod", "0644", "f.txt"], "f.txt")
    scenario("chmod --reference=g.txt f", [], ["chmod", "--reference=g.txt", "f.txt"], "f.txt")

    # 错误路径
    say("=== 错误路径 ===")
    for cmd in (
        ["chmod", "644", "missing.txt"],
        ["chmod", "-f", "644", "missing.txt"],
        ["chmod", "-v", "644", "missing.txt"],
        ["chmod", "7777", "f.txt"],
        ["chmod", "8", "f.txt"],
        ["chmod", "+x", "f.txt"],
        ["chmod", "u+", "f.txt"],
        ["chmod", "a+rwx", "f.txt", "extra1", "extra2"],
        ["chmod", "--reference=missing.txt", "f.txt"],
        ["chmod", "--badoption", "f.txt"],
    ):
        force_rmtree(DATA)
        DATA.mkdir(parents=True, exist_ok=True)
        (DATA / "f.txt").write_text("hello\n", encoding="utf-8")
        code, out, err = run(cmd, cwd=DATA)
        say(f"  $ {' '.join(cmd)}")
        say(f"    rc={code}")
        if out:
            say("    stdout: " + out.replace("\n", "\n      ").rstrip())
        if err:
            say("    stderr: " + err.replace("\n", "\n      ").rstrip())
    say("")

    say("=== 根目录 / 保留根 ===")
    for cmd in (["chmod", "-R", "755", "/"], ["chmod", "--preserve-root", "-R", "755", "/"]):
        code, out, err = run(cmd, cwd=DATA)
        say(f"  $ {' '.join(cmd)}")
        say(f"    rc={code}")
        if out:
            say("    stdout: " + out.replace("\n", "\n      ").rstrip())
        if err:
            say("    stderr: " + err.replace("\n", "\n      ").rstrip())
    say("")

    force_rmtree(DATA)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"报告已写入 {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
