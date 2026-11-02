"""核对 head 在 Windows 上的三件关键事。

1. GBK 文件解出来是中文，不是乱码
2. 二进制文件逐字节原样转交（与源文件做校验和对比）
3. 管道输出按原样保留 LF，不被翻译成 CRLF
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
PYTHON = sys.executable


def run(args: list[str], cwd: Path, stdin: bytes = b"") -> subprocess.CompletedProcess:
    return subprocess.run(
        [PYTHON, str(ROOT / "main.py"), "head", *args],
        cwd=str(cwd),
        input=stdin,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    root = Path(tempfile.mkdtemp(prefix="check_head_"))
    failures = 0

    try:
        # 1. GBK 文件
        gbk_text = "第一行中文\n第二行中文\n".encode("gb18030")
        (root / "gbk.txt").write_bytes(gbk_text)
        proc = run(["-n", "2", str(root / "gbk.txt")], root)
        out = proc.stdout.decode("utf-8", "replace")
        print("--- GBK 文件")
        print(f"    输出: {out!r}")
        if "第一行中文" in out and "第二行中文" in out:
            print("    结果: 中文正常显示")
        else:
            print("    结果: 失败，中文没解出来")
            failures += 1

        # 2. 二进制文件逐字节转交
        payload = bytes(range(256)) * 4
        (root / "bin.dat").write_bytes(payload)
        proc = run([str(root / "bin.dat")], root)
        got = proc.stdout
        print("--- 二进制文件")
        print(f"    源文件 sha256   : {hashlib.sha256(payload).hexdigest()}")
        print(f"    输出   sha256   : {hashlib.sha256(got).hexdigest()}")
        if got == payload:
            print("    结果: 逐字节一致")
        else:
            print(f"    结果: 失败，输出 {len(got)} 字节，源文件 {len(payload)} 字节")
            failures += 1

        # 3. 管道输出保留 LF
        lf = b"a\nb\nc\n"
        (root / "lf.txt").write_bytes(lf)
        proc = run([str(root / "lf.txt")], root)
        print("--- 管道输出")
        print(f"    输出: {proc.stdout!r}")
        if proc.stdout == lf:
            print("    结果: LF 原样保留，没被翻译成 CRLF")
        else:
            print("    结果: 失败，换行被翻译了")
            failures += 1

        # 4. 标题与错误的先后
        (root / "sub").mkdir()
        proc = run([str(root / "sub")], root)
        print("--- 目录当文件")
        print(f"    stdout: {proc.stdout!r}")
        print(f"    stderr: {proc.stderr.decode('utf-8', 'replace')!r}")
        print(f"    退出码: {proc.returncode}")
        if proc.returncode == 2 and "是一个目录" in proc.stderr.decode("utf-8", "replace"):
            print("    结果: 退出码 2 且报了目录错误")
        else:
            print("    结果: 失败")
            failures += 1

        # 5. 打不开的文件不打标题
        proc = run(["-v", str(root / "nope.txt")], root)
        print("--- 不存在的文件")
        print(f"    stdout: {proc.stdout!r}")
        print(f"    stderr: {proc.stderr.decode('utf-8', 'replace')!r}")
        print(f"    退出码: {proc.returncode}")
        if proc.returncode == 2 and proc.stdout == b"":
            print("    结果: 退出码 2 且没打标题")
        else:
            print("    结果: 失败")
            failures += 1

        print()
        print(f"检查项 5 个，失败 {failures} 个")
        return 1 if failures else 0
    finally:
        import shutil

        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
