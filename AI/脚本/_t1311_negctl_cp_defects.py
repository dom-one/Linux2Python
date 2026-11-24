"""负控制：把 HEAD 的旧 cp 拿回来跑同一批用例，确认它们真能挑出差异。

判据：新用例集在旧实现上必须报出**多于 0 条**不一致。
如果旧实现也是全绿，说明这批用例根本没在检查东西（假绿）。
"""

from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = ROOT / "AI" / "数据" / "cp_defect_probe"
OLD_COPY = DATA / "old_cp_head.py"

sys.path.insert(0, str(ROOT))


def _load_t410():
    spec = importlib.util.spec_from_file_location("_t410_diff_cp", HERE / "_t410_diff_cp.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_t1310():
    spec = importlib.util.spec_from_file_location("_t1310_diff_cp_defects", HERE / "_t1310_diff_cp_defects.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


T410 = _load_t410()
T1310 = _load_t1310()
CASES = T1310.CASES

from w2l.context import RunContext  # noqa: E402


def dump_old_cp() -> None:
    """把 HEAD 版本的 cp.py 落到 AI/数据/ 下（脚本内写盘，不走 shell）。

    落盘时去掉 @command(...) 那行装饰器：重新注册同名指令会抛
    「指令重复注册」，而装饰器本身只是登记，功能函数原样返回。
    """
    DATA.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        ["git", "show", "HEAD:w2l/commands/cp.py"],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        raise SystemExit("取 HEAD 的 cp.py 失败: " + proc.stderr.decode("utf-8", "replace"))
    source = proc.stdout.decode("utf-8")
    kept = [line for line in source.splitlines() if not line.startswith("@command(")]
    OLD_COPY.write_text("\n".join(kept) + "\n", encoding="utf-8")


def load_old_cp():
    """把旧 cp.py 当成 w2l.commands 的一个成员加载，相对导入才解析得了。"""
    import w2l.commands  # noqa: F401  确保包已注册

    spec = importlib.util.spec_from_file_location("w2l.commands.cp_old", OLD_COPY)
    module = importlib.util.module_from_spec(spec)
    sys.modules["w2l.commands.cp_old"] = module
    spec.loader.exec_module(module)
    return module


def run_old(argv: list[str], cwd: Path, stdin_text: str | None) -> dict:
    old = load_old_cp()
    out, err = io.StringIO(), io.StringIO()
    try:
        namespace = old.build_parser().parse_args(list(argv))
    except SystemExit as exc:
        return {"rc": int(exc.code or 0), "out": "", "err": f"argparse 退出 {exc.code}\n"}
    ctx = RunContext(
        cwd=cwd,
        stdout=out,
        stderr=err,
        stdin=io.StringIO(stdin_text) if stdin_text is not None else io.StringIO(""),
    )
    code = old.cp(namespace, ctx)
    return {"rc": code, "out": out.getvalue(), "err": err.getvalue()}


def main() -> int:
    dump_old_cp()
    sandbox_root = Path(tempfile.mkdtemp(prefix="cpnegctl_", dir=str(DATA)))

    report: list[dict] = []
    mismatches = 0

    for index, (name, argv, stdin_text, check_mtime) in enumerate(CASES):
        base = sandbox_root / f"case{index:03d}"
        base.mkdir(parents=True)
        gnu_dir = base / "gnu"
        old_dir = base / "old"
        for target in (gnu_dir, old_dir):
            target.mkdir()
            T410.build_fixture(target)
            (target / "emptydir").mkdir()

        gnu = T410.run_gnu(argv, gnu_dir, stdin_text)
        old = run_old(argv, old_dir, stdin_text)

        problems: list[str] = []
        if (gnu["rc"] == 0) != (old["rc"] == 0):
            problems.append(f"成功与否不同: GNU rc={gnu['rc']} 旧实现 rc={old['rc']}")
        if bool(gnu["err"].strip()) != bool(old["err"].strip()):
            problems.append("有无报错不同")
        gnu_tree = T410.tree_state(gnu_dir)
        old_tree = T410.tree_state(old_dir)
        if gnu_tree != old_tree:
            problems.append("目录树不同")
        if sorted(T410.PAIR_RE.findall(gnu["out"])) != sorted(T410.PAIR_RE.findall(old["out"])):
            problems.append("verbose 不同")
        if check_mtime:
            if T410.mtime_state(gnu_dir) != T410.mtime_state(old_dir):
                problems.append("mtime 不同")

        if problems:
            mismatches += 1
            report.append({"name": name, "argv": argv, "problems": problems})

    out_path = DATA / "negctl_cp_defects.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"负控制：{len(CASES)} 组用例在旧实现上不一致 {mismatches} 组")
    for item in report:
        print(f"  - {item['name']}: {'; '.join(item['problems'])}")
    print("详细结果:", out_path)

    if mismatches == 0:
        print("负控制失败：这批用例连旧实现都挑不出差异 => 判据没在检查东西")
        return 1
    print("负控制通过：用例能区分旧实现与 GNU")
    return 0


if __name__ == "__main__":
    sys.exit(main())
