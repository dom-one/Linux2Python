"""探针：ls --json 的三层校验 + 负控制。

第一层 自洽：同一棵树上，文本模式列出的条目序列 == JSON 的条目序列（顺序也一致），
    两种模式的退出码也必须一致。
第二层 字段：JSON 的 size / mtime / type / mode / permissions 与 os.lstat 直接取值一致。
第三层 外部：JSON 的 size 与 GNU ls -l 的 size 列一致（这是真正的外部基准，
    判据写在探针自己这边，不复刻实现的取值逻辑）。

负控制：故意改坏一条记录（size +1、name 改字），检查判据确实会报出来。
    判据不响 = 「全部一致」是假绿。

用法：python AI/脚本/_t1601_probe_ls_json.py
报告落盘到 AI/脚本/_t1601_ls_json_report.txt（stdout 只打 ASCII 摘要）。
"""

from __future__ import annotations

import io
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from w2l.commands.ls import build_parser as build_ls_parser  # noqa: E402
from w2l.commands.ls import ls  # noqa: E402
from w2l.context import RunContext  # noqa: E402
from w2l.perms import canonical_mode, format_perms  # noqa: E402

REPORT = Path(__file__).with_name("_t1601_ls_json_report.txt")

GNU_LS_CANDIDATES = (
    r"E:\software\Git\Git\usr\bin\ls.exe",
    r"C:\Program Files\Git\usr\bin\ls.exe",
    r"C:\Program Files (x86)\Git\usr\bin\ls.exe",
)

# GNU ls -l 的一行：权限位、链接数、属主、属组、字节数、日期、名字
# 日期有两种写法："Nov 26 02:05"（半年以内）与 "Nov 26  2025"（更早），
# 两种都是三个字段，所以名字要等日期吃干净了再取。
GNU_LONG_RE = re.compile(
    r"^([-dlpsbc])([rwxsStT-]{9})\s+\d+\s+\S+\s+\S+\s+(\d+)\s+"
    r"\w{3}\s+\d{1,2}\s+(?:\d{2}:\d{2}|\d{4})\s+(.*)$"
)

# -F 追加的类型标记
_CLASSIFY_MARKS = "/*@|="


def find_gnu_ls() -> str | None:
    for candidate in GNU_LS_CANDIDATES:
        if os.path.isfile(candidate):
            return candidate
    return None


def run_ls(argv: list[str], cwd: Path) -> tuple[int, str, str]:
    namespace = build_ls_parser().parse_args(list(argv))
    out, err = io.StringIO(), io.StringIO()
    ctx = RunContext(cwd=cwd, stdout=out, stderr=err, stdin=io.StringIO(""))
    code = ls(namespace, ctx)
    return code, out.getvalue(), err.getvalue()


def build_fixture(root: Path) -> None:
    """造一棵测试树。文件用 write_bytes 写，保证是真正的 LF（Windows 文本模式会翻 CRLF）。

    名字里不带空格、不带冒号：探针要靠「行首是块标题、行尾是名字」来切文本输出，
    带这些字符的��字会让切分判据失效。
    """
    (root / "alpha.txt").write_bytes(b"hello\n")
    (root / "Beta.txt").write_bytes(b"B\n")
    (root / "gamma.log").write_bytes(b"x" * 2048)
    (root / "big.bin").write_bytes(b"\x00" * 5000)
    (root / ".hidden").write_bytes(b"h\n")
    (root / "empty").mkdir()
    sub = root / "sub"
    sub.mkdir()
    (sub / "deep.txt").write_bytes(b"deep\n")
    (sub / "nested").mkdir()
    (sub / "nested" / "leaf.txt").write_bytes(b"leaf\n")


# ---------- 判据 ----------


def text_entry_names(text: str, long: bool, classify: bool) -> list[str]:
    """从文本输出里取出条目名序列。

    文本输出有两种行：块标题（「标签:」）和条目行。条目行在长格式下是
    「权限 大小 日期 名字」，名字是最后一个字段。
    """
    names = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.endswith(":") and " " not in stripped:
            # 块标题：整行就是「标签:」，标签本身不带空格
            continue
        if long:
            name = stripped.split()[-1]
        else:
            name = stripped
        if classify and name[-1:] in _CLASSIFY_MARKS:
            name = name[:-1]
        # JSON 的 name 恒为路径的最后一段，所以文本这边也要取 basename 才可比
        names.append(_basename(name))
    return names


def _basename(path: str) -> str:
    normalized = path.replace("\\", "/").rstrip("/")
    if not normalized:
        return path
    return normalized.rsplit("/", 1)[-1]


def check_sequence(text_out: str, payload: dict, long: bool, classify: bool) -> list[str]:
    """第一层：文本模式的条目序列必须与 JSON 的条目序列逐项相同。"""
    problems = []
    text_names = text_entry_names(text_out, long, classify)
    json_names = [record["name"] for record in payload["entries"]]
    if text_names != json_names:
        problems.append(f"条目序列不一致：文本 {text_names!r} != JSON {json_names!r}")
    return problems


def check_records(records: list[dict], cwd: Path) -> list[str]:
    """第二层：每条记录的字段必须与 os.lstat 直接取值一致。"""
    problems = []
    for record in records:
        path = record["path"]
        target = Path(os.path.normpath(str(cwd / path)))
        try:
            st = os.lstat(target)
        except OSError as exc:
            problems.append(f"{path}: 无法 stat（{exc.strerror or exc}）")
            continue
        if record["size"] != st.st_size:
            problems.append(f"{path}: size {record['size']} != {st.st_size}")
        if abs(record["mtime"] - st.st_mtime) > 1e-6:
            problems.append(f"{path}: mtime {record['mtime']} != {st.st_mtime}")
        if record["type"] == "directory":
            if not os.path.isdir(target):
                problems.append(f"{path}: type 说成目录，实际不是")
        elif record["type"] == "file":
            if not os.path.isfile(target) or os.path.islink(target):
                problems.append(f"{path}: type 说成普通文件，实际不是")
        want_mode = f"{canonical_mode(st.st_mode) & 0o7777:04o}"
        if record["mode"] != want_mode:
            problems.append(f"{path}: mode {record['mode']} != {want_mode}")
        if record["permissions"] != format_perms(st.st_mode):
            problems.append(
                f"{path}: permissions {record['permissions']} != {format_perms(st.st_mode)}"
            )
    return problems


def check_paths(records: list[dict], operands: list[str], cwd: Path) -> list[str]:
    """每条记录的路径必须落在给定的操作数之下（解析成绝对路径再比，不比字符串前缀）。"""
    problems = []
    roots = [os.path.normpath(str(cwd / operand)) for operand in operands]
    for record in records:
        if record["name"] in (".", ".."):
            # 这两条按定义就指向所在目录与它的上一级，不做归属判断
            continue
        resolved = os.path.normpath(str(cwd / record["path"]))
        inside = any(
            resolved == root or resolved.startswith(root + os.sep) for root in roots
        )
        if not inside:
            problems.append(f"{record['path']}: 不在任何操作数之下（{roots}）")
    return problems


def parse_gnu_long(text: str) -> dict[str, tuple[str, int]]:
    """解析 GNU ls -l 的输出，取 (名字 -> (权限位, 字节数))。"""
    table: dict[str, tuple[str, int]] = {}
    for line in text.splitlines():
        if line.startswith("total "):
            continue
        match = GNU_LONG_RE.match(line)
        if not match:
            continue
        perm = match.group(1) + match.group(2)
        table[match.group(4)] = (perm, int(match.group(3)))
    return table


def check_against_gnu(records: list[dict], gnu_text: str) -> list[str]:
    """第三层：JSON 的 size 必须与 GNU ls -l 的 size 列一致（只比普通文件）。"""
    problems = []
    table = parse_gnu_long(gnu_text)
    if not table:
        return ["GNU ls -l 没有解析出任何条目"]
    for record in records:
        if record["type"] != "file":
            # 目录大小在 Windows 上不稳定（空目录 0、条目一多就 4096），不参与比对
            continue
        name = record["name"]
        if name not in table:
            problems.append(f"{name}: GNU ls -l 里没有这一项（解析到 {sorted(table)}）")
            continue
        _perm, size = table[name]
        if size != record["size"]:
            problems.append(f"{name}: size JSON {record['size']} != GNU {size}")
    return problems


# ---------- 主流程 ----------

COMBOS: list[tuple[list[str], list[str]]] = [
    ([], ["."]),
    (["-a"], ["."]),
    (["-A"], ["."]),
    (["-l"], ["."]),
    (["-lh"], ["."]),
    (["-F"], ["."]),
    (["-t"], ["."]),
    (["-S"], ["."]),
    (["-r"], ["."]),
    (["-R"], ["."]),
    (["-a", "-l"], ["."]),
    (["-R", "-a"], ["."]),
    (["-t", "-r"], ["."]),
    (["-d"], ["sub"]),
    ([], ["alpha.txt"]),
    ([], ["alpha.txt", "sub"]),
    ([], ["nope", "sub"]),
    ([], []),
]


def main() -> int:
    lines: list[str] = []
    gnu_ls = find_gnu_ls()
    lines.append(f"GNU ls: {gnu_ls or '（没找到，外部对拍跳过）'}")
    lines.append("")

    with tempfile.TemporaryDirectory(prefix="w2l_json_") as tmp:
        root = Path(tmp)
        build_fixture(root)

        total_problems: list[str] = []
        for flags, operands in COMBOS:
            argv = flags + operands
            # 短选项可以合并写（-lh 等价于 -l -h），所以用 startswith 判
            long = any(f.startswith("-l") for f in flags)
            classify = any(f.startswith("-F") for f in flags)
            text_code, text_out, _ = run_ls(argv, root)
            json_code, json_out, _ = run_ls(argv + ["--json"], root)
            problems: list[str] = []
            if text_code != json_code:
                problems.append(f"退出码不一致：文本 {text_code} != JSON {json_code}")
            try:
                payload = json.loads(json_out)
            except json.JSONDecodeError as exc:
                problems.append(f"stdout 不是合法 JSON：{exc}")
                payload = {"entries": []}
            else:
                if payload.get("command") != "ls":
                    problems.append(f"command 字段是 {payload.get('command')!r}，应为 'ls'")
                problems.extend(check_sequence(text_out, payload, long, classify))
                problems.extend(check_records(payload["entries"], root))
                problems.extend(check_paths(payload["entries"], operands or ["."], root))
            tag = " ".join(argv) if argv else "(无参数)"
            if problems:
                total_problems.extend(f"[{tag}] {p}" for p in problems)
                lines.append(f"FAIL [{tag}]")
                lines.extend(f"    - {p}" for p in problems)
            else:
                lines.append(f"ok   [{tag}]  条目 {len(payload.get('entries', []))} 个")

        lines.append("")

        # ---------- 外部对拍 ----------
        if gnu_ls:
            _code, json_out, _ = run_ls(["--json", "."], root)
            payload = json.loads(json_out)
            proc = subprocess.run(
                [gnu_ls, "-l", "."],
                cwd=str(root),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            lines.append("GNU ls -l 原始输出：")
            lines.extend("    " + line for line in proc.stdout.splitlines())
            lines.append("")
            gnu_problems = check_against_gnu(payload["entries"], proc.stdout)
            if gnu_problems:
                lines.append("FAIL [外部对拍 GNU ls -l]")
                lines.extend(f"    - {p}" for p in gnu_problems)
                total_problems.extend(f"[外部对拍] {p}" for p in gnu_problems)
            else:
                lines.append("ok   [外部对拍 GNU ls -l]  size 与 GNU 一致")
        else:
            lines.append("SKIP [外部对拍 GNU ls -l]  没找到 GNU ls")

        lines.append("")

        # ---------- 负控制 ----------
        _code, json_out, _ = run_ls(["--json", "."], root)
        payload = json.loads(json_out)
        text_out = run_ls(["."], root)[1]
        baseline_records = check_records(payload["entries"], root)
        baseline_sequence = check_sequence(text_out, payload, False, False)

        size_mutated = [dict(r) for r in payload["entries"]]
        victim = next(r for r in size_mutated if r["type"] == "file")
        victim["size"] = victim["size"] + 1
        size_problems = check_records(size_mutated, root)

        name_mutated = [dict(r) for r in payload["entries"]]
        name_mutated[0]["name"] = name_mutated[0]["name"] + "-MUTATED"
        name_problems = check_sequence(
            text_out, {"entries": name_mutated}, False, False
        )

        neg_lines = [
            f"基线：字段问题 {len(baseline_records)} 条，序列问题 {len(baseline_sequence)} 条",
            f"变异 size+1 后：字段问题 {len(size_problems)} 条（应 > 0）",
            f"变异 name 后：序列问题 {len(name_problems)} 条（应 > 0）",
        ]
        neg_ok = (
            not baseline_records
            and not baseline_sequence
            and len(size_problems) > 0
            and len(name_problems) > 0
        )
        lines.append("负控制：" + ("ok" if neg_ok else "FAIL"))
        lines.extend(f"    - {line}" for line in neg_lines)
        if not neg_ok:
            total_problems.append("[负控制] 判据没被变异触发，判据本身失效")

    lines.append("")
    if total_problems:
        lines.append(f"合计问题 {len(total_problems)} 条")
    else:
        lines.append("全部检查通过")

    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    summary = "PASS" if not total_problems else f"FAIL({len(total_problems)})"
    print(f"[probe_ls_json] {summary}  report={REPORT}")
    return 0 if not total_problems else 1


if __name__ == "__main__":
    sys.exit(main())
