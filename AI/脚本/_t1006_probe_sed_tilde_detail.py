#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""核对脚本：把 `~` 范围终点的实际输出逐条钉死。

上一轮探针里 `3,~2p` 本实现只给 2 行，与从源码推出来的「offset % step == 0 时结束」
对不上。这个脚本把每个用例的实际输出逐条打出来，并对源码里的判定函数
做一次直接调用，看两边说的是不是同一件事。

用法：python AI/脚本/_t1006_probe_sed_tilde_detail.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))

from w2l.commands.sed import run_sed  # noqa: E402

LINES = [f"L{i}" + ("X" if i in (2, 4, 6) else "") for i in range(1, 9)]
DATA = ("\n".join(LINES) + "\n").encode("utf-8")


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="sedtilde2_"))
    (tmp / "u.txt").write_bytes(DATA)

    print("语料 u.txt 每行: " + " ".join(LINES))
    print()

    print("--- 本实现：N,~M 的实际覆盖行 ---")
    for start in (1, 2, 3):
        for step in (1, 2, 3, 4):
            script = f"{start},~{step}p"
            code, out, err = run_sed(["-n", script, "u.txt"], cwd=tmp)
            print(f"  {script:<10} -> {out.split()}  exit={code} err={err!r}")
    print()

    print("--- 本实现：/X/,~M 的实际覆盖行 ---")
    for step in (0, 1, 2, 3, 4):
        script = f"/X/,~{step}p"
        code, out, err = run_sed(["-n", script, "u.txt"], cwd=tmp)
        print(f"  {script:<12} -> {out.split()}  exit={code} err={err!r}")
    print()

    print("--- 本实现：,/X 相对范围 ---")
    for script in ("1,/X/p", "2,/X/p", "/X/,+2p"):
        code, out, err = run_sed(["-n", script, "u.txt"], cwd=tmp)
        print(f"  {script:<12} -> {out.split()}  exit={code} err={err!r}")
    print()

    print("--- 本实现：N,+M 相对范围 ---")
    for script in ("1,+2p", "1,+0p", "2,+3p"):
        code, out, err = run_sed(["-n", script, "u.txt"], cwd=tmp)
        print(f"  {script:<12} -> {out.split()}  exit={code} err={err!r}")
    print()

    # 直接问源码里的判定函数：这个范围在每一行上「结束了吗」
    print("--- 直接问 _tilde_reached：/X/,~2 在每一行上的判定 ---")
    from w2l.commands.sed import _Address, _Command, _Engine, _LineSource  # noqa: E402
    import re  # noqa: E402

    cmd = _Command(name="p")
    cmd.addr1 = _Address("regex", regex=re.compile("X"))
    cmd.addr2 = _Address("tilde", step=2)
    engine = _Engine([cmd], {}, True)
    source = _LineSource([ln + "\n" for ln in LINES])
    for _ in range(len(LINES)):
        source.next_line()
        engine.pattern = source.next_line() if False else engine.pattern
        # 直接喂当前行
        line = source._buffer if False else None
        # 用引擎自己的循环不方便，这里手动推进
        break
    # 改用最直接的办法：逐行走引擎，钩住 _tilde_reached
    calls: list[tuple[int, str, bool]] = []
    original = _Engine._tilde_reached

    def spy(self, command, end, src):
        result = original(self, command, end, src)
        calls.append((src.number, self.pattern.strip(), result))
        return result

    _Engine._tilde_reached = spy
    try:
        cmd2 = _Command(name="p")
        cmd2.addr1 = _Address("regex", regex=re.compile("X"))
        cmd2.addr2 = _Address("tilde", step=2)
        eng = _Engine([cmd2], {}, True)
        eng.run(_LineSource([ln + "\n" for ln in LINES]), _SpyWriter())
    finally:
        _Engine._tilde_reached = original

    print("  (行号, 该行内容, _tilde_reached 返回值)")
    for num, content, result in calls:
        print(f"    {num} {content:<6} -> {result}")
    return 0


class _SpyWriter:
    def write(self, text, newline=True):
        pass

    def close(self):
        pass


if __name__ == "__main__":
    sys.exit(main())
