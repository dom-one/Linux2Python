"""排查：串内运算符的符号模式为什么算错了。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from w2l.commands.chmod import _parse_clauses, _ModeSpec  # noqa: E402

for text in ("a+x-r", "a+rw-x", "a+x", "u+rw,go-w", "a+rw+x"):
    clauses = _parse_clauses(text)
    print(f"{text!r}:")
    for clause in clauses:
        print(
            f"    who={clause.who:04o} op={clause.op!r} perms={clause.perms!r} "
            f"copy_from={clause.copy_from}"
        )
    spec = _ModeSpec(None, clauses)
    print(f"    0644 -> {spec.target(0o644, False):04o}")
    print()
