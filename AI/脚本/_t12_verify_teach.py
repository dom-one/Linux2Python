"""核对 teach/ 教程里的命令是不是真能跑，输出是不是和文档写的一致。

用法:
    python AI/脚本/_t12_verify_teach.py                      # 核对全部教程
    python AI/脚本/_t12_verify_teach.py teach/18-xxx.md      # 只核对一篇

做法:
1. 解析 markdown 里的 ```bash 围栏块
2. 去掉块里的 cd 行，其余行用 && 串成一条命令
3. 在 cmd.exe 里跑，输出重定向到临时文件（绕开控制台 GBK 编码）
4. 和紧随其后的第一个围栏块（文档写的预期输出）逐行比对

为什么用 Git Bash 跑命令:
教程里的命令是 bash 风格（ls、wc、rm --），cmd.exe 里没有这些命令。
用 bash 跑才对得上读者看到的写法。找不到 Git Bash 时退回 cmd.exe。

为什么输出重定向到文件再读:
Windows 控制台输出是 GBK，直接解码会报错。读到字节后按 UTF-8/GBK 依次试。

为什么用字符串形式调 bash:
subprocess 传 list 时 Python 的 list2cmdline 会把引号转义成 \"，
cmd 解析不了，整条命令直接失败。传字符串才是 cmd 认的形式。

安全约束（重要）:
教程里有些命令是「示例」，真跑会改工作区：取锁放锁、删文件、提交代码、
往进度文件追加记录。这个脚本只做「只读核对」：
- 默认跳过命中危险模式的命令块，只报告跳过，不执行
- 用 --allow-risky 显式放行才会真跑
"""

import argparse
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TEACH_DIR = os.path.join(ROOT, "teach")
WORKDIR = ROOT

# Git Bash 位置。PATH 里的 bash 可能是 WSL 的桩程序（跑什么都报
# ERROR_PATH_NOT_FOUND），所以按常见安装路径找真的那个。
BASH_CANDIDATES = [
    r"E:\software\Git\Git\bin\bash.exe",
    r"C:\Program Files\Git\bin\bash.exe",
    r"C:\Program Files (x86)\Git\bin\bash.exe",
]
BASH_BIN = next((p for p in BASH_CANDIDATES if os.path.isfile(p)), None)

# 会改工作区或改仓库状态的命令模式。只做只读核对时一律跳过，不执行。
#
# git 一律按危险处理。教程里的 git 示例覆盖了 add/commit/push/checkout/
# switch/branch/tag/remote 等多种写法，逐个枚举容易漏（漏了 git switch 就
# 会真的把工作区切到别的分支）。宁可多跳过，不要误改仓库。
RISKY_PATTERNS = [
    re.compile(p) for p in (
        r"_t10_lock\.py\s+acquire",
        r"_t10_lock\.py\s+release",
        r"_t11_progress\.py",
        # 核对器自己：teach/15 里有它的用法示例，跑起来会递归调用自己
        r"_t12_verify_teach\.py",
        r"\bgit\b",
        r"\brm\s+--",
        r"\brmdir\b",
        r"\bdel\s+",
        r"\bmd\b\s+\S",
        r"\bmove\b",
        r"\bcopy\b",
        r"\bmkdir\b",
        r"pip\s+(install|uninstall)",
        r"pip\s+wheel",
        r"\bpython\s+-m\s+pip\b",
        r">\s*\S+\.(md|txt|py|toml|cfg|ini)\b",
        r"\btee\b",
    )
]


def is_risky(payload: str) -> bool:
    """命令是否会改工作区。"""
    return any(pattern.search(payload) for pattern in RISKY_PATTERNS)


def decode(raw: bytes) -> str:
    """控制台输出可能是 GBK，按多种编码依次尝试。"""
    for enc in ("utf-8", "gbk", "cp936"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


# pytest 的耗时每次跑都不一样，比对前先抹平
TIMING_RE = re.compile(r"\bin \d+\.\d+s\b")


def normalize(text: str) -> str:
    """把不稳定的部分归一化：pytest 耗时。"""
    return TIMING_RE.sub("in <T>s", text)


def _run_outer(command: str, outpath: str, shell_cmd: str, timeout: int):
    """按给定命令模板执行一次。"""
    with open(os.devnull, "rb") as devnull:
        return subprocess.run(shell_cmd, capture_output=True, stdin=devnull, timeout=timeout)


def run_in_shell(command: str, timeout: int = 60):
    """跑一条命令，返回 (退出码, 输出文本)。

    优先用 Git Bash：教程里的命令是 bash 风格（ls、wc、rm --），
    cmd.exe 里没有这些命令。用 bash 跑才对得上读者看到的写法。

    找不到 Git Bash 时退回 cmd.exe：读者在 cmd 里敲也要能跑通。
    """
    handle, outpath = tempfile.mkstemp(suffix=".txt")
    os.close(handle)
    try:
        if BASH_BIN and os.path.isfile(BASH_BIN):
            # bash 里 stdout 重定向直接写文件，编码由 Python 端按 GBK/UTF-8 兜底
            full = 'cd "%s" && { %s ; } > "%s" 2>&1' % (WORKDIR, command, outpath)
            try:
                _run_outer(command, outpath, [BASH_BIN, "-c", full], timeout)
            except subprocess.TimeoutExpired:
                return -1, "(超时 %ds，命令没退出)" % timeout
        else:
            full = 'cd /d "%s" && %s > "%s" 2>&1' % (WORKDIR, command, outpath)
            try:
                _run_outer(command, outpath, "cmd.exe /c " + full, timeout)
            except subprocess.TimeoutExpired:
                return -1, "(超时 %ds，命令没退出)" % timeout
        with open(outpath, "rb") as fh:
            return 0, decode(fh.read()).strip()
    finally:
        try:
            os.remove(outpath)
        except OSError:
            pass


def check_doc(path: str, allow_risky: bool = False):
    """核对一篇教程，返回 (命令块数, 有预期数的块数, 不匹配列表, 跳过列表)。"""
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()

    fence = re.compile(r"```([A-Za-z]*)\n(.*?)```", re.DOTALL)
    blocks = [(m.group(1), m.group(2), m.start(), m.end()) for m in fence.finditer(text)]

    mismatches = []
    skipped = []
    checked = 0
    bash_count = 0

    for i, (lang, content, start, end) in enumerate(blocks):
        if lang.lower() != "bash":
            continue
        bash_count += 1

        # 紧跟其后的说明文字（到下一个围栏开头）里带「预期」，才认后面的块是预期输出
        next_start = blocks[i + 1][2] if i + 1 < len(blocks) else len(text)
        interstitial = text[end:next_start]

        expected_blocks = []
        if "预期" in interstitial and i + 1 < len(blocks):
            # 收集紧跟着的一串「无语言标记」的围栏块：一条命令可能对应多段输出
            j = i + 1
            while j < len(blocks) and not blocks[j][0]:
                expected_blocks.append(blocks[j][1].strip())
                if j + 1 < len(blocks):
                    gap = text[blocks[j][3]:blocks[j + 1][2]]
                    if gap.strip():
                        break
                j += 1

        cmd_lines = [ln for ln in content.strip().splitlines()
                     if not ln.strip().lower().startswith("cd ")]
        if not cmd_lines:
            continue

        payloads = [" && ".join(ln.strip() for ln in cmd_lines)]
        if len(expected_blocks) == len(cmd_lines) and len(cmd_lines) > 1:
            # 一条命令对应一段输出：逐条跑，逐段比对
            payloads = [ln.strip() for ln in cmd_lines]

        if not allow_risky and any(is_risky(p) for p in payloads):
            skipped.append((bash_count, cmd_lines[0].strip()[:66]))
            continue

        actual_list = []
        for payload in payloads:
            _, actual = run_in_shell(payload)
            actual_list.append(actual)

        if not expected_blocks:
            continue

        checked += 1
        exp_groups = []
        if len(expected_blocks) == len(payloads):
            exp_groups = [[normalize(ln.strip()) for ln in e.splitlines() if ln.strip()]
                          for e in expected_blocks]
        else:
            merged = "\n".join(expected_blocks)
            exp_groups = [[normalize(ln.strip()) for ln in merged.splitlines() if ln.strip()]]

        act_groups = [[normalize(ln.strip()) for ln in a.splitlines() if ln.strip()]
                      for a in actual_list]

        ok = len(exp_groups) == len(act_groups)
        if ok:
            for exp_lines, act_lines in zip(exp_groups, act_groups):
                if len(exp_lines) != len(act_lines):
                    ok = False
                    break
                for exp_line, act_line in zip(exp_lines, act_lines):
                    if exp_line == act_line:
                        continue
                    # 临时目录路径含随机串，只比对公共前缀
                    prefix = exp_line.split("tmp")[0]
                    if prefix and act_line.startswith(prefix):
                        continue
                    ok = False
                    break
                if not ok:
                    break
        if not ok:
            mismatches.append((bash_count, cmd_lines[0].strip()[:66],
                               [g for g in exp_groups], [g for g in act_groups], 0))

    return bash_count, checked, mismatches, skipped


def main():
    parser = argparse.ArgumentParser(description="核对 teach/ 教程里的命令")
    parser.add_argument("doc", nargs="*", help="要核对的教程文件，默认全部")
    parser.add_argument("--allow-risky", action="store_true",
                        help="连会改工作区的命令也真跑（默认只做只读核对）")
    args = parser.parse_args()

    if args.doc:
        paths = [os.path.join(ROOT, p) if not os.path.isabs(p) else p for p in args.doc]
    else:
        paths = sorted(
            os.path.join(TEACH_DIR, name) for name in os.listdir(TEACH_DIR)
            if name.endswith(".md")
        )

    total_bash = 0
    total_checked = 0
    total_skipped = 0
    all_bad = []

    for path in paths:
        bash_count, checked, bad, skipped = check_doc(path, args.allow_risky)
        total_bash += bash_count
        total_checked += checked
        total_skipped += len(skipped)
        name = os.path.basename(path)
        note = "，跳过 %d（会改工作区）" % len(skipped) if skipped else ""
        if bad:
            all_bad.extend((name,) + item for item in bad)
            print("%s: 命令块 %d，有预期 %d，不匹配 %d%s"
                  % (name, bash_count, checked, len(bad), note))
        else:
            print("%s: 命令块 %d，有预期 %d，全部一致%s"
                  % (name, bash_count, checked, note))

    print("---")
    print("合计: 命令块 %d，有预期 %d，跳过 %d，不匹配 %d"
          % (total_bash, total_checked, total_skipped, len(all_bad)))

    for name, idx, head, exp, act, rc in all_bad:
        print("")
        print("[%s 块 #%d] 退出码 %d | %s" % (name, idx, rc, head))
        print("  预期: %r" % (exp,))
        print("  实际: %r" % (act,))

    return 1 if all_bad else 0


if __name__ == "__main__":
    sys.exit(main())
