"""核对 teach/26 教程正文里的每一条事实断言。

断言分三类：
1. 源码事实：行数、选项数、函数名、代码片段位置
2. 实测行为：跑命令看真实输出
3. 与 GNU 的差异：边界值

每条断言打印 PASS / FAIL 与证据，全绿才算能落盘。

用法:
    python AI/脚本/_t908_verify_du_claims.py
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DATA = ROOT / "AI" / "数据" / "du_demo"
GNU_DU = Path(r"E:\software\Git\Git\usr\bin\du.exe")

PASS = 0
FAIL = 0
FAILURES: list[str] = []


def check(name: str, ok: bool, evidence: str = "") -> None:
    global PASS, FAIL
    if ok:
        PASS += 1
        print("  PASS  %-52s %s" % (name, evidence))
    else:
        FAIL += 1
        FAILURES.append("%s | %s" % (name, evidence))
        print("  FAIL  %-52s %s" % (name, evidence))


def run_ours(args: list[str], cwd: Path, timeout: int = 60) -> tuple[int, str, str]:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "main.py"), "du", *args],
        cwd=str(cwd), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=timeout)
    return proc.returncode, proc.stdout, proc.stderr


def run_gnu(args: list[str], cwd: Path) -> tuple[int, str, str]:
    proc = subprocess.run(
        [str(GNU_DU), *args], cwd=str(cwd), capture_output=True, text=True,
        encoding="utf-8", errors="replace")
    return proc.returncode, proc.stdout, proc.stderr


def main() -> None:
    src = (ROOT / "w2l" / "commands" / "du.py").read_text(encoding="utf-8")
    lines = src.splitlines()

    print("=" * 72)
    print("一、源码事实")
    print("=" * 72)
    check("du.py 总行数 590", len(lines) == 590, "实际 %d" % len(lines))

    # 选项数：统计 add_argument 的调用
    add_args = re.findall(r'add_argument\(\s*"([^"]+)"', src)
    check("add_argument 调用 22 次", len(add_args) == 22,
          "实际 %d 次" % len(add_args))
    # 去掉位置参数 paths 与 --help，剩下的才是选项
    real_opts = [a for a in add_args if a not in ("paths", "--help")]
    check("真实选项 20 个", len(real_opts) == 20,
          "实际 %d 个: %s" % (len(real_opts), real_opts))
    check("选项里含 --apparent-size", "--apparent-size" in add_args, "")

    # --help 里列出的选项数（去掉 [paths ...] 那行）
    code, help_out, _ = run_ours(["--help"], ROOT)
    opt_line = [ln for ln in help_out.splitlines() if ln.strip().startswith("usage:")]
    check("--help 输出一行 usage", len(opt_line) == 1, opt_line[0].strip() if opt_line else "")

    # 关键函数与行号
    for fname, expect in [
        ("def _format_human", 476),
        ("def _passes_threshold", 504),
        ("def _parse_size", 521),
        ("def _rewrite_argv", 133),
        ("def _claim", 304),
        ("def _list_children", 374),
        ("def _scan_dir", 331),
        ("def _count_file", 405),
        ("def _resolve_block_size", 568),
    ]:
        idx = next((i + 1 for i, ln in enumerate(lines) if ln.startswith(fname)), None)
        check("%s 在第 %d 行" % (fname, expect), idx == expect, "实际 %s" % idx)

    # _list_children 里用的是 os.stat 而不是 item.stat()
    check("_list_children 用 os.stat(item.path, ...)",
          "os.stat(item.path, follow_symlinks=follow)" in src, "")
    check("注释明确写了不能用 item.stat()",
          "不能用 item.stat()" in src, "")

    # 去重键
    check("去重键是 (st_dev, st_ino)", "key = (st.st_dev, st.st_ino)" in src, "")

    # 阈值跟字节比
    check("阈值判定用 size >= threshold",
          "return size >= threshold" in src and "return size <= -threshold" in src, "")

    # 测试用例数。pyproject.toml 的 addopts = "-q" 让 -q 变成两个，
    # 输出被压成 "tests/test_du.py: 30" 一行，按这个格式解析。
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_du.py", "--collect-only", "-q"],
        cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace")
    m = re.search(r"tests/test_du\.py:\s*(\d+)", proc.stdout)
    check("test_du.py 收集到 30 条用例", bool(m) and int(m.group(1)) == 30,
          "实际 %s" % (m.group(1) if m else "未匹配到"))

    print()
    print("=" * 72)
    print("二、实测行为")
    print("=" * 72)
    code, out, _ = run_ours(["-s", "tree"], DATA)
    check("-s tree 输出 7\\ttree", out == "7\ttree\n", repr(out))

    code, out, _ = run_ours(["-b", "-s", "tree"], DATA)
    check("-b -s tree 输出 6259\\ttree", out == "6259\ttree\n", repr(out))

    code, out, _ = run_ours(["-a", "tree"], DATA)
    rows = out.splitlines()
    check("-a tree 输出 10 行", len(rows) == 10, "实际 %d" % len(rows))
    check("-a tree 按名字排序（a.txt 在 b.txt 前）",
          rows[0].endswith("tree/a.txt") and rows[1].endswith("tree/b.txt"), rows[0])
    check("-a tree 末行是根目录 tree", rows[-1].endswith("\ttree"), rows[-1])

    code, out, _ = run_ours(["-d", "1", "tree"], DATA)
    check("-d 1 不打印 deeper", "deeper" not in out, repr(out))
    check("-d 1 仍打印 tree/sub", "tree/sub\n" in out, repr(out))

    code, out, _ = run_ours(["-t", "1024", "-a", "tree"], DATA)
    check("-t 1024 滤掉 a.txt", "a.txt" not in out, "")
    check("-t 1024 留下 b.txt", "b.txt" in out, "")

    code, out, _ = run_ours(["-t", "-1024", "-a", "tree"], DATA)
    check("-t -1024 留下 a.txt", "a.txt" in out, "")
    check("-t -1024 滤掉 b.txt", "b.txt" not in out, "")

    code, out, _ = run_ours(["-h", "-s", "tree"], DATA)
    check("-h -s tree 输出 6.2K", out == "6.2K\ttree\n", repr(out))
    code, out, _ = run_ours(["--si", "-s", "tree"], DATA)
    check("--si -s tree 输出 6.3k", out == "6.3k\ttree\n", repr(out))

    code, out, _ = run_ours(["-h", "--si", "-s", "tree"], DATA)
    check("-h --si（si 在后）用 1000 进制", out == "6.3k\ttree\n", repr(out))
    code, out, _ = run_ours(["--si", "-h", "-s", "tree"], DATA)
    check("--si -h（h 在后）用 1024 进制", out == "6.2K\ttree\n", repr(out))

    code, out, _ = run_ours(["-S", "-s", "tree"], DATA)
    check("-S -s tree 输出 3（不含子目录）", out == "3\ttree\n", repr(out))

    code, out, _ = run_ours(["tree", "tree"], DATA)
    check("同一棵树给两次只输出一次", out.count("tree") == 4, "实际 %d 行" % len(out.splitlines()))
    code, out, _ = run_ours(["-l", "tree", "tree"], DATA)
    check("-l 后两次都输出", out.count("\ttree\n") == 2, repr(out))

    code, out, _ = run_ours(["-s", "tree/empty"], DATA)
    check("空目录算 0", out == "0\ttree/empty\n", repr(out))

    code, out, err = run_ours(["nosuch"], DATA)
    check("操作数不存在退出码 2", code == 2, "实际 %d" % code)
    check("操作数不存在的文案是中文", "无法访问" in err, err.strip())
    code, out, err = run_ours(["nosuch", "tree"], DATA)
    check("有一个不存在时其余照常统计", "tree" in out and code == 2, "退出码 %d" % code)

    code, out, _ = run_ours(["-t", "1M", "tree"], DATA)
    check("全被滤掉退出码 1", code == 1, "实际 %d" % code)
    check("全被滤掉时 stdout 为空", out == "", repr(out))

    code, out, err = run_ours(["-s", "-a", "tree"], DATA)
    check("-s 与 -a 冲突退出码 2", code == 2, "实际 %d" % code)
    code, out, err = run_ours(["-s", "-d", "1", "tree"], DATA)
    check("-s 与 -d 1 冲突退出码 2", code == 2, "实际 %d" % code)
    code, out, err = run_ours(["-d", "-1", "tree"], DATA)
    check("-d 负数退出码 2", code == 2, "实际 %d" % code)
    code, out, err = run_ours(["-t", "bogus", "tree"], DATA)
    check("-t 非法值退出码 2", code == 2, "实际 %d" % code)
    code, out, err = run_ours(["-B", "0", "tree"], DATA)
    check("-B 0 退出码 2", code == 2, "实际 %d" % code)

    code, out, _ = run_ours(["-s", "tree/"], DATA)
    check("操作数带尾斜杠输出保留斜杠", out == "7\ttree/\n", repr(out))

    code, out, _ = run_ours(["-0", "-s", "tree"], DATA)
    check("-0 用 NUL 分隔", out == "7\ttree\x00", repr(out))

    print()
    print("=" * 72)
    print("三、与 GNU 的差异（实测边界）")
    print("=" * 72)
    one = DATA / "onefile"
    one.mkdir(exist_ok=True)
    target = one / "one.bin"

    def h_out(tool: str, size: int) -> str:
        target.write_bytes(b"\0" * size)
        if tool == "ours":
            _, o, _ = run_ours(["-h", "one.bin"], one)
        else:
            _, o, _ = run_gnu(["--apparent-size", "-h", "one.bin"], one)
        return o.strip().split("\t")[0]

    check("999K（1022976）两边都是 999K",
          h_out("ours", 999 * 1024) == "999K" and h_out("gnu", 999 * 1024) == "999K",
          "项目 %s / GNU %s" % (h_out("ours", 999 * 1024), h_out("gnu", 999 * 1024)))
    check("999K+1 项目是 1.0M、GNU 是 1000K",
          h_out("ours", 999 * 1024 + 1) == "1.0M" and h_out("gnu", 999 * 1024 + 1) == "1000K",
          "项目 %s / GNU %s" % (h_out("ours", 999 * 1024 + 1), h_out("gnu", 999 * 1024 + 1)))
    check("1023K 项目是 1.0M、GNU 是 1023K",
          h_out("ours", 1023 * 1024) == "1.0M" and h_out("gnu", 1023 * 1024) == "1023K",
          "项目 %s / GNU %s" % (h_out("ours", 1023 * 1024), h_out("gnu", 1023 * 1024)))
    check("1M-1（1048575）两边都是 1.0M",
          h_out("ours", 1024 * 1024 - 1) == "1.0M" and h_out("gnu", 1024 * 1024 - 1) == "1.0M",
          "项目 %s / GNU %s" % (h_out("ours", 1024 * 1024 - 1), h_out("gnu", 1024 * 1024 - 1)))
    check("10239 字节两边都是 10K",
          h_out("ours", 10239) == "10K" and h_out("gnu", 10239) == "10K",
          "项目 %s / GNU %s" % (h_out("ours", 10239), h_out("gnu", 10239)))

    # 目录联接
    jdir = DATA / "junc"
    jdir.mkdir(exist_ok=True)
    link = jdir / "to_tree"
    if link.exists():
        subprocess.run(["cmd", "/c", "rmdir", str(link)], capture_output=True)
    subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(DATA / "tree")],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
    if link.exists():
        lst = os.lstat(str(link))
        import stat as stat_mod
        check("联接 S_ISLNK=False、S_ISDIR=True",
              not stat_mod.S_ISLNK(lst.st_mode) and stat_mod.S_ISDIR(lst.st_mode),
              "S_ISLNK=%s S_ISDIR=%s" % (stat_mod.S_ISLNK(lst.st_mode),
                                         stat_mod.S_ISDIR(lst.st_mode)))
        code, out, _ = run_ours(["-a", "junc"], DATA)
        check("项目把联接当目录钻进去了", "junc/to_tree/a.txt" in out, "")
        code, out, _ = run_gnu(["--apparent-size", "-a", "junc"], DATA)
        check("GNU 把联接当符号链接（只报自己）",
              "junc/to_tree/a.txt" not in out and "junc/to_tree\n" in out, repr(out))

    # 自引用联接不无限递归
    selfdir = DATA / "selfref"
    selfdir.mkdir(exist_ok=True)
    selflink = selfdir / "loop"
    if selflink.exists():
        subprocess.run(["cmd", "/c", "rmdir", str(selflink)], capture_output=True)
    subprocess.run(["cmd", "/c", "mklink", "/J", str(selflink), str(selfdir)],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
    if selflink.exists():
        (selfdir / "f.txt").write_bytes(b"Q" * 100)
        code, out, _ = run_ours(["-a", "selfref"], DATA, timeout=60)
        check("自引用联接不会无限递归（3 行内结束）",
              code == 0 and len(out.splitlines()) <= 4,
              "退出码 %d，%d 行" % (code, len(out.splitlines())))

    # --time 取子树最新
    code, out, _ = run_ours(["--time", "-s", "tree"], DATA)
    check("--time 是三列（大小/时间/路径）",
          len(out.strip().split("\t")) == 3, repr(out))

    # -s -d 1 与 GNU 的差异
    code, out, err = run_ours(["-s", "-d", "1", "tree"], DATA)
    g_code, g_out, g_err = run_gnu(["--apparent-size", "-s", "-d", "1", "tree"], DATA)
    check("与 GNU 的差异：-s -d 1 本项目退 2、GNU 退 1",
          code == 2 and g_code == 1, "项目 %d / GNU %d" % (code, g_code))

    print()
    print("=" * 72)
    print("合计: PASS %d，FAIL %d" % (PASS, FAIL))
    print("=" * 72)
    if FAILURES:
        for item in FAILURES:
            print("  失败: %s" % item)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
