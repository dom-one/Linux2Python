"""验证核对器的三个安全修复真的生效。

要验三件事：
1. 裸 `python` 命令块被跳过（不再进 REPL）
2. 输出超 4MB 的命令被杀掉并报错（模拟失控命令）
3. 超时命令能杀掉整棵进程树，不留孤儿

跑法：
    python AI/脚本/_t84_test_verifier_guard.py
"""

from __future__ import annotations

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "AI", "脚本"))

import _t12_verify_teach as V  # noqa: E402


def python_pids() -> list[str]:
    proc = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq python.exe", "/FO", "CSV", "/NH"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    pids = []
    for line in proc.stdout.splitlines():
        parts = line.split(",")
        if len(parts) > 1 and parts[0].strip('"').lower() == "python.exe":
            pids.append(parts[1].strip('"'))
    return pids


def main() -> None:
    print("=" * 60)
    print("1. 裸 python 命令块被判定为 risky")
    print("=" * 60)
    for payload in ("python", "python3", "py -3", "cd /tmp && python",
                    "python main.py", "python -c \"print(1)\"",
                    "python main.py grep TODO",
                    "cd E:/x && python && echo done"):
        risky = V.is_risky(payload)
        print("  %-28s -> risky=%s" % (repr(payload), risky))

    print("")
    print("=" * 60)
    print("2. 输出超限的命令被杀掉并报错")
    print("=" * 60)
    before = python_pids()
    # 用 python 造一个无限输出的命令（Windows 上没有 yes）
    # 写成脚本文件避开内联 -c 的转义麻烦
    spam = os.path.join(ROOT, "AI", "数据", "_t84_spam.py")
    os.makedirs(os.path.dirname(spam), exist_ok=True)
    with open(spam, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("import sys\nwhile True:\n    sys.stdout.write('x' * 100000)\n")
    code, out = V.run_in_shell(
        'python "%s"' % spam.replace("\\", "/"),
        timeout=30,
    )
    print("  返回码: %s" % code)
    print("  输出: %s" % out[:200])
    after = python_pids()
    orphans = [p for p in after if p not in before]
    print("  遗留 python 进程: %s" % orphans)
    if orphans:
        for pid in orphans:
            subprocess.run(["taskkill", "/F", "/T", "/PID", pid], capture_output=True)
    try:
        os.remove(spam)
    except OSError:
        pass

    print("")
    print("=" * 60)
    print("3. 超时命令不留孤儿")
    print("=" * 60)
    before = python_pids()
    code, out = V.run_in_shell("python -c \"import time;time.sleep(120)\"", timeout=5)
    print("  返回码: %s" % code)
    print("  输出: %s" % out[:200])
    after = python_pids()
    orphans = [p for p in after if p not in before]
    print("  遗留 python 进程: %s" % orphans)
    if orphans:
        for pid in orphans:
            subprocess.run(["taskkill", "/F", "/T", "/PID", pid], capture_output=True)

    print("")
    print("=" * 60)
    print("4. 正常命令照常工作")
    print("=" * 60)
    code, out = V.run_in_shell("python main.py --help")
    print("  返回码: %s" % code)
    print("  首行: %s" % out.splitlines()[0] if out else "(空)")

    print("")
    print("=" * 60)
    print("5. teach/03 的裸 python 块会被跳过")
    print("=" * 60)
    doc = os.path.join(ROOT, "teach", "03-w2l-registry.py-指令注册表.md")
    bash_count, checked, bad, skipped = V.check_doc(doc)
    print("  命令块 %d，有预期 %d，不匹配 %d" % (bash_count, checked, len(bad)))
    print("  跳过的块:")
    for idx, head in skipped:
        print("    #%d %s" % (idx, head))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
