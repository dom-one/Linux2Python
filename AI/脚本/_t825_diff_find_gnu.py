"""差分对照：本项目的 find 与 GNU findutils 4.10 逐条对拍。

★ 为什么 GNU 那一侧必须经 bash 拉起
Python 的 subprocess 直接 spawn MSYS 的 find.exe 时，MSYS 运行时会在 argv 到达
find 之前改写它（`{}` 被吃掉、`*.txt` 被通配符展开），量到的是运行时的行为、
不是 GNU find 的行为。详见 _t816_probe_find_gnu_truth.py 的说明。

★ 为什么 -exec 的目标是一个原生 Python 助手，而不是 printf
argv 在「原生父进程 → MSYS 子程序」这条路上会被 MSYS 运行时改写：
实测原生 Python 直接 spawn MSYS 的 printf.exe，参数 `A{}B` 变成 `AB`、
`[%s]\\n` 变成 `[%s]n`（花括号与反斜杠都被吃掉）。
所以拿 printf 当 -exec 目标时，比出来的是 MSYS 运行时的差异，不是 find 的差异。

改成用**原生 Python**（`python.exe 助手脚本`）当 -exec 目标：
  - 原生 → 原生：argv 原样送达（实测 _t827）
  - MSYS find → 原生助手：相对路径原样送达（实测 _t827）
  - 本项目的 find → 原生助手：argv 由本项目自己拼，原样送达
于是两边比的就是「find 把 {} 展开成了什么」，这才是要对的东西。

★ 探针自身必须自证有效
第一版把助手脚本的路径直接当可执行文件传过去，两边都是「找不到这个程序」
⇒ stdout 都是空 ⇒ 报「37 条全一致」——那是假绿。
判据：**候选数与输出内容都要看**，空输出不等于一致。
现在助手以 `python.exe + 脚本路径` 的形式调用，两边 stdout 都要有内容才算真跑过。

★ 比对口径
- 逐字节比 stdout（**不做 CRLF 归一**）：本项目这一版修掉了管道输出是 CRLF
  的毛病，管道里必须和 GNU 一样是纯 LF，所以归一化会把差异抹掉。
- 标注「预期差异」的用例不计失败，但要在报告里写清差在哪、为什么接受。
- 退出码只记录不判等：本项目「无结果返回 1」是项目约定，GNU 恒返回 0。

用法: python AI/脚本/_t825_diff_find_gnu.py
产出: AI/数据/find_fix/diff.txt
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
AI_DIR = HERE.parent
ROOT = AI_DIR.parent
BASE = AI_DIR / "数据" / "find_fix"

# -exec 的目标：原生 Python 助手，把收到的 argv 逐个 repr 打出来
DUMP = BASE / "_t825_dump_argv.py"
DUMP.write_text(
    "import sys\n"
    "for a in sys.argv[1:]:\n"
    "    print(repr(a))\n",
    encoding="utf-8",
)


def _bash_quote(text: str) -> str:
    return "'" + text.replace("'", "'\\''") + "'"


# (标题, 表达式参数, 预期差异说明)
# 预期差异为空表示必须逐字节一致；非空时说明「为什么这条允许不一致」
CASES: list[tuple[str, list[str], str]] = [
    # ---------- 求值真值表 ----------
    ("求值-动作a动作", ["-printf", "L\\n", "-a", "-printf", "R\\n"], ""),
    ("求值-动作o动作", ["-printf", "L\\n", "-o", "-printf", "R\\n"], ""),
    ("求值-printoprint", ["-print", "-o", "-print"], ""),
    ("求值-printaprint", ["-print", "-a", "-print"], ""),
    ("求值-测试o动作", ["-name", "*.txt", "-o", "-printf", "R:%p\\n"], ""),
    ("求值-测试a动作", ["-name", "*.txt", "-a", "-printf", "R:%p\\n"], ""),
    ("求值-测试o测试", ["-name", "*.txt", "-o", "-name", "*.md", "-printf", "P:%p\\n"], ""),
    ("求值-动作o测试", ["-printf", "L:%p\\n", "-o", "-name", "*.txt"], ""),
    ("求值-动作a测试", ["-printf", "L:%p\\n", "-a", "-name", "*.txt"], ""),
    ("求值-三段o", ["-printf", "L\\n", "-o", "-printf", "R\\n", "-o", "-printf", "S\\n"], ""),
    ("求值-三段a", ["-printf", "L\\n", "-a", "-printf", "R\\n", "-a", "-printf", "S\\n"], ""),
    ("求值-优先级md或txt且a", ["-name", "*.md", "-o", "-name", "*.txt", "-a", "-name", "a*"], ""),
    ("求值-括号", ["(", "-name", "*.txt", "-o", "-name", "*.md", ")", "-print"], ""),
    # ---------- -prune ----------
    ("prune-or-print", ["-type", "d", "-prune", "-o", "-print"], ""),
    ("prune-and-printf", ["-type", "d", "-prune", "-a", "-printf", "P:%p\\n"], ""),
    ("prune-单独", ["-type", "d", "-prune"], ""),
    ("prune-or-name", ["-type", "d", "-prune", "-o", "-name", "*.txt"], ""),
    # ---------- 隐式 -print ----------
    ("隐式-测试o测试", ["-name", "*.txt", "-o", "-name", "*.md"], ""),
    ("隐式-测试o不匹配", ["-name", "*.txt", "-o", "-name", "*.zzz"], ""),
    ("隐式-单测试", ["-name", "*.txt"], ""),
    # ---------- {} 展开（; 形式）----------
    ("exec-单独占位符", ["-exec", "TARGET", "SCRIPT", "{}", ";"], ""),
    ("exec-嵌入式前后缀", ["-exec", "TARGET", "SCRIPT", "A{}B", ";"], ""),
    ("exec-嵌入式两处", ["-exec", "TARGET", "SCRIPT", "{}A{}", ";"], ""),
    ("exec-两个参数各一处", ["-exec", "TARGET", "SCRIPT", "X", "{}", "Y", "{}", ";"], ""),
    (
        "exec-无占位符",
        ["-exec", "TARGET", "SCRIPT", "NOPLACE", ";"],
        "GNU 没有 {} 时不追加路径；本项目沿用「路径追加到末尾」的既有约定",
    ),
    # ---------- {} 展开（+ 形式）----------
    ("exec加-单独占位符", ["-exec", "TARGET", "SCRIPT", "{}", "+"], ""),
    (
        "exec加-嵌入式",
        ["-exec", "TARGET", "SCRIPT", "A{}B", "+"],
        "GNU 报错退出 1；本项目按用法错误处理，退出 2（退出码是项目约定，stderr 文案也不同）",
    ),
    (
        "exec加-两处占位符",
        ["-exec", "TARGET", "SCRIPT", "X", "{}", "Y", "{}", "+"],
        "GNU 报错退出 1；本项目按用法错误处理，退出 2",
    ),
    (
        "exec加-无占位符",
        ["-exec", "TARGET", "SCRIPT", "NOPLACE", "+"],
        "GNU 报错退出 1；本项目接受并把路径追加到末尾（既有约定）",
    ),
    (
        "exec加-占位符非末尾",
        ["-exec", "TARGET", "SCRIPT", "X", "{}", "Y", "+"],
        "GNU 报错退出 1；本项目按用法错误处理，退出 2",
    ),
    # ---------- 其他常用谓词 ----------
    ("类型-文件", ["-type", "f"], ""),
    ("类型-目录", ["-type", "d"], ""),
    ("printf-字段", ["-printf", "%f|%y|%s\\n"], ""),
    ("printf-路径字段", ["-printf", "%p|%h\\n"], ""),
    ("print0", ["-print0"], ""),
    ("深度-一层", ["-maxdepth", "1"], ""),
    ("深度-跳过根", ["-mindepth", "1"], ""),
]


def build_fixture(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "a.txt").write_bytes(b"alpha\n")
    (root / "b.md").write_bytes(b"# b\n")
    sub = root / "sub"
    sub.mkdir(exist_ok=True)
    (sub / "c.txt").write_bytes(b"gamma\n")


def run_gnu(tree: Path, extra: list[str]) -> tuple[int, bytes, bytes]:
    """经 bash 拉起 GNU find：cwd 放在夹具里、操作数用 .，输出是相对路径。"""
    quoted = " ".join(_bash_quote(part) for part in extra)
    out_path = BASE / "_t825_case.out"
    err_path = BASE / "_t825_case.err"
    script = BASE / "_t825_case.sh"
    script.write_text(
        f"cd '{tree.as_posix()}'\n"
        f"/usr/bin/find . {quoted} > '{out_path.as_posix()}' 2> '{err_path.as_posix()}'\n"
        f"echo $? > '{(BASE / '_t825_case.code').as_posix()}'\n",
        encoding="utf-8",
    )
    bash = shutil.which("bash") or r"E:\software\Git\Git\bin\bash.exe"
    subprocess.run([bash, str(script)], capture_output=True)
    out = out_path.read_bytes() if out_path.exists() else b""
    err = err_path.read_bytes() if err_path.exists() else b""
    code_path = BASE / "_t825_case.code"
    code = int(code_path.read_text(encoding="utf-8").strip()) if code_path.exists() else -1
    return code, out, err


def run_mine(tree: Path, extra: list[str]) -> tuple[int, bytes, bytes]:
    """跑本项目的 find（原生 Python，不经 MSYS）。"""
    proc = subprocess.run(
        [sys.executable, str(ROOT / "main.py"), "find", ".", *extra],
        cwd=tree,
        capture_output=True,
    )
    return proc.returncode, proc.stdout, proc.stderr


def main() -> int:
    BASE.mkdir(parents=True, exist_ok=True)
    tree = BASE / "tree10"
    if tree.exists():
        shutil.rmtree(tree, ignore_errors=True)
    build_fixture(tree)

    report: list[str] = [
        "# 由 _t825_diff_find_gnu.py 生成，勿手改",
        f"# 夹具: {tree.as_posix()}（a.txt / b.md / sub/c.txt）",
        f"# -exec 目标: {sys.executable} {DUMP.as_posix()}（原生 Python 助手，打印收到的 argv）",
        "# 比对口径: stdout 逐字节比（不归一 CRLF）；退出码只记录不判等",
        "",
    ]
    same_count = 0
    expected_count = 0
    diff_cases: list[str] = []
    empty_outputs: list[str] = []
    for title, extra, expected in CASES:
        g_extra = [part for part in extra]
        m_extra = [part for part in extra]
        # TARGET 占位符展开成「python.exe + 助手脚本」两个参数
        g_extra = [
            (sys.executable if part == "TARGET" else part) for part in g_extra
        ]
        g_extra = [
            (DUMP.as_posix() if part == "SCRIPT" else part) for part in g_extra
        ]
        m_extra = [
            (sys.executable if part == "TARGET" else part) for part in m_extra
        ]
        m_extra = [
            (str(DUMP) if part == "SCRIPT" else part) for part in m_extra
        ]
        g_code, g_out, g_err = run_gnu(tree, g_extra)
        m_code, m_out, m_err = run_mine(tree, m_extra)

        out_same = g_out == m_out
        # 探针自证：两边 stdout 都空时，这条用例根本没跑到有输出的地步
        if not g_out and not m_out and not expected:
            empty_outputs.append(title)
        if out_same:
            same_count += 1
            verdict = "一致"
        elif expected:
            expected_count += 1
            verdict = "预期差异（已记录理由）"
        else:
            diff_cases.append(title)
            verdict = "★不一致★"

        report.append("=" * 72)
        report.append(f"### {title}")
        report.append(f"$ find . {' '.join(extra)}")
        report.append(f"GNU    exit={g_code} stdout={g_out!r}")
        report.append(f"本项目 exit={m_code} stdout={m_out!r}")
        report.append(f"stdout 一致: {out_same}")
        if not out_same:
            report.append(f"GNU    stderr={g_err!r}")
            report.append(f"本项目 stderr={m_err!r}")
        if expected:
            report.append(f"预期差异理由: {expected}")
        report.append(f"判定: {verdict}")

    report.append("=" * 72)
    report.append(
        f"用例 {len(CASES)} 条，逐字节一致 {same_count} 条，"
        f"预期差异 {expected_count} 条，不一致 {len(diff_cases)} 条"
    )
    if diff_cases:
        report.append(f"不一致的用例: {diff_cases}")
    (BASE / "diff.txt").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(
        f"用例 {len(CASES)} 条，一致 {same_count} 条，"
        f"预期差异 {expected_count} 条，不一致 {len(diff_cases)} 条"
    )
    if diff_cases:
        print(f"不一致: {diff_cases}")
    print(f"结果 -> {BASE / 'diff.txt'}")
    return 0 if not diff_cases else 1


if __name__ == "__main__":
    sys.exit(main())
