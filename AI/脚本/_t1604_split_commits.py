"""把本轮的改动拆成两个提交：一个修缺陷，一个加特性。

本轮实际做了两件事：
1. 修掉 `ls -Ra` 撞上 `.` 与 `..` 的无限递归（探针撞出来的旧缺陷）
2. 给 `ls` 加 `--json` 结构化输出（阶段三的路线项）

两件事落在同一个文件 w2l/commands/ls.py 上，git add -p 是交互式的用不了，
所以这里用「从 HEAD 的 blob 重建中间态」的办法拆：

- `--prep`   ：把 ls.py / test_ls.py / README.md 还原成「只有修复」的状态，
               并跑一遍 pytest 确认这个中间态自己就是绿的（提交信息说
               「不提交没跑过测试的代码」，中间态也得站得住）
- `--restore`：把完整版写回来（完整版从 --prep 存下的备份里取）

写文件一律用 newline=""，Windows 上默认会把 \\n 翻成 \\r\\n，
一翻整份文件就变成一次全文件改动。

用法：
    python AI/脚本/_t1604_split_commits.py --prep
    python AI/脚本/_t1604_split_commits.py --restore
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKUP_DIR = ROOT / "AI" / "脚本"

LS_PY = "w2l/commands/ls.py"
TEST_LS = "tests/test_ls.py"
README = "README.md"

# 修复要插入的守卫：. 与 .. 只列出来，不往里递归
GUARD = (
    "        # -a 会把 . 与 .. 也列进条目里，但它们不是子目录：\n"
    "        # . 递归回自己、.. 递归到上一级，两条都停不下来（GNU 也不往里递归）\n"
    '        if entry.name in (".", ".."):\n'
    "            continue\n"
)

LS_ANCHOR = (
    '        _list_tree(root / entry.name, f"{label}/{entry.name}", args, ctx, out, '
    "show_all, almost_all)\n"
)

# 只含修复的回归测试（不含 --json 那一批）
REGRESSION_TEST = '''

def test_recursive_with_all_does_not_recurse_into_dot_entries(ls_tree):
    """-a 会把 . 与 .. 列进条目里，但它们不是子目录。

    以前这里是无限递归（. 递归回自己、.. 递归到上一级），撞上 RecursionError。
    GNU ls -Ra 只把 . 与 .. 列出来，不往里递归。
    """
    code, out, err = run_ls(["-Ra", str(ls_tree)])
    assert code == 0
    assert err == ""
    # 每一级目录都只出现一次，不会出现 ./sub/sub
    assert f"{ls_tree}/sub/sub" not in out
    assert f"{ls_tree}/sub:" in out
'''

README_ANCHOR = (
    "- **文件操作数按原样打印**：`python main.py ls w2l/cli.py` 输出完整路径，"
    "跟 GNU 一样不回退成文件名。\n"
)

README_BULLET = (
    "- **`-R` 与 `-a` 同开时，`.` 与 `..` 只列出来不递归进去**：GNU 同样如此。"
    "（以前这里是无限递归，`.` 递归回自己、`..` 递归到上一级。）\n"
)


def git_blob(rel: str) -> bytes:
    proc = subprocess.run(
        ["git", "show", f"HEAD:{rel}"],
        cwd=str(ROOT),
        capture_output=True,
        check=True,
    )
    return proc.stdout


def write_text(rel: str, text: str) -> None:
    """按字节写出，newline="" 保住 LF，不让 Windows 翻成 CRLF。"""
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(text)


def backup_path(rel: str) -> Path:
    flat = rel.replace("/", "__")
    return BACKUP_DIR / f"_t1604_full_{flat}.txt"


def run_pytest() -> int:
    out = BACKUP_DIR / "_t1604_pytest_mid.txt"
    with out.open("wb") as handle:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "-q"],
            cwd=str(ROOT),
            stdout=handle,
            stderr=subprocess.STDOUT,
        )
    print(f"  pytest 退出码 {proc.returncode}（输出见 {out}）")
    return proc.returncode


def prep() -> int:
    print("[prep] 备份完整版")
    for rel in (LS_PY, TEST_LS, README):
        src = ROOT / rel
        dst = backup_path(rel)
        dst.write_bytes(src.read_bytes())
        print(f"  {rel} -> {dst.name}")

    print("[prep] 从 HEAD 重建「只有修复」的版本")
    ls_text = git_blob(LS_PY).decode("utf-8")
    if ls_text.count(LS_ANCHOR) != 1:
        print(f"[prep] 失败：ls.py 的锚点命中 {ls_text.count(LS_ANCHOR)} 次（应为 1）")
        return 1
    write_text(LS_PY, ls_text.replace(LS_ANCHOR, GUARD + LS_ANCHOR))

    test_text = git_blob(TEST_LS).decode("utf-8")
    write_text(TEST_LS, test_text.rstrip("\n") + "\n" + REGRESSION_TEST)

    readme_text = git_blob(README).decode("utf-8")
    if readme_text.count(README_ANCHOR) != 1:
        print(f"[prep] 失败：README 的锚点命中 {readme_text.count(README_ANCHOR)} 次（应为 1）")
        return 1
    write_text(README, readme_text.replace(README_ANCHOR, README_ANCHOR + README_BULLET))

    print("[prep] 校验中间态")
    mid = (ROOT / LS_PY).read_text(encoding="utf-8")
    if mid.count('if entry.name in (".", ".."):') != 1:
        print("[prep] 失败：守卫没落进中间态")
        return 1
    if "--json" in mid:
        print("[prep] 失败：中间态里还留着 --json 的痕迹")
        return 1
    if "--json" in (ROOT / TEST_LS).read_text(encoding="utf-8"):
        print("[prep] 失败：中间态的测试里还留着 --json 的用例")
        return 1

    code = run_pytest()
    if code != 0:
        print("[prep] 失败：中间态的 pytest 不是绿的，先别提交")
        return 1
    print("[prep] 中间态就绪，可以提交")
    return 0


def restore() -> int:
    print("[restore] 取回完整版")
    for rel in (LS_PY, TEST_LS, README):
        src = backup_path(rel)
        if not src.exists():
            print(f"[restore] 失败：备份不存在 {src}")
            return 1
        (ROOT / rel).write_bytes(src.read_bytes())
        print(f"  {rel} 已还原")

    code = run_pytest()
    if code != 0:
        print("[restore] 失败：还原后 pytest 不是绿的")
        return 1
    print("[restore] 完整版就绪，可以提交")
    return 0


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in ("--prep", "--restore"):
        print(__doc__)
        return 2
    if sys.argv[1] == "--prep":
        return prep()
    return restore()


if __name__ == "__main__":
    sys.exit(main())
