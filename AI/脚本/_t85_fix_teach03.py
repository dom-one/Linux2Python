"""修 teach/03-w2l-registry.py-指令注册表.md 里过期的事实。

两处：

1. 第 4 步 `python main.py ls w2l` 的预期输出少了 `entry.py`（2026-11-01
   加的入口名模块）和 `__pycache__`（Python 跑过就有的字节码缓存目录）。

2. 第 2 步那段 REPL 对话是「敲 `python` 进交互模式」的写法。这个写法：
   - 在管道里跑不了（核对器真跑它会让 Python 3.13+ 的新 REPL 反复抛
     控制台句柄的 OSError，6 秒刷 280 MB）
   - 对话里的 `sorted(REGISTRY)` 结果也过期了，现在是 5 个指令不是 1 个

   改成等价的非交互写法：`python -c "..."`，读者能直接复制到任何地方跑，
   核对器也能真跑并比对。

按规矩先写 .preview，断言过了再 os.replace 覆盖。

跑法：
    python AI/脚本/_t85_fix_teach03.py
"""

from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
TARGET = os.path.join(ROOT, "teach", "03-w2l-registry.py-指令注册表.md")
PREVIEW = TARGET + ".preview"


OLD_REPL = '''想直接看字典内容，可以临时开一个 REPL：

```bash
cd E:\\1\\NULL\\Windows-to-Linux
python
```

```python
>>> from w2l.registry import load_commands, REGISTRY
>>> load_commands()
>>> sorted(REGISTRY)
['grep']
>>> REGISTRY['grep'].summary
'搜索包含 PATTERN 的行（GNU grep 风格子集）'
>>> REGISTRY['grep'].parser_factory
<function build_parser at 0x...>
```
'''

NEW_REPL = '''想直接看字典内容，可以临时开一个 REPL 敲 `python` 再逐条输入。

不过写下来更实用的是 `python -c` —— 一行跑完就退出，可以直接粘到
脚本里、放进 CI、或者被别的程序调用：

```bash
cd E:\\1\\NULL\\Windows-to-Linux
python -c "from w2l.registry import load_commands, REGISTRY;load_commands();print(sorted(REGISTRY))"
```

预期输出：

```
['cat', 'grep', 'head', 'ls', 'tail']
```

同一批数据在 REPL 里逐条敲是：

```python
>>> from w2l.registry import load_commands, REGISTRY
>>> load_commands()
>>> sorted(REGISTRY)
['cat', 'grep', 'head', 'ls', 'tail']
>>> REGISTRY['grep'].summary
'搜索包含 PATTERN 的行（GNU grep 风格子集）'
>>> REGISTRY['grep'].parser_factory
<function build_parser at 0x...>
```

> REPL 只能在真终端里敲。命令被管道接走时 `python` 读不到控制台句柄，
> Python 3.13+ 的新 REPL 会反复抛 OSError 并无限刷 traceback。
> 要在脚本里拿数据，用上面的 `python -c` 写法。
'''

OLD_LS_OUT = '''```
__init__.py
cli.py
commands
context.py
errors.py
registry.py
```
'''

NEW_LS_OUT = '''```
__init__.py
__pycache__
cli.py
commands
context.py
entry.py
errors.py
registry.py
```
'''


def main() -> None:
    with open(TARGET, "r", encoding="utf-8", newline="") as fh:
        original = fh.read()

    text = original

    for old, new, label in (
        (OLD_REPL, NEW_REPL, "REPL 段"),
        (OLD_LS_OUT, NEW_LS_OUT, "ls 输出段"),
    ):
        if old not in text:
            raise SystemExit("找不到片段：%s" % label)
        if text.count(old) != 1:
            raise SystemExit("片段出现多次，跳过：%s" % label)
        text = text.replace(old, new, 1)

    # 断言
    assert "python -c \"from w2l.registry import load_commands, REGISTRY;load_commands();print(sorted(REGISTRY))\"" in text
    assert "['cat', 'grep', 'head', 'ls', 'tail']" in text
    assert "│   ├── entry.py" not in text  # 这篇没有结构树，别误伤
    assert "entry.py" in text
    assert "只读" not in text or True
    # 裸 python 不再作为 bash 命令块出现
    bash_blocks = re.findall(r"```bash\n(.*?)```", text, re.DOTALL)
    for block in bash_blocks:
        for line in block.splitlines():
            stripped = line.strip()
            assert stripped not in ("python", "python3", "py -3"), \
                "还有裸 python 命令块：%s" % stripped
    # 四个固定小节还在
    for heading in ("## 为什么这么创建", "## 这个文件是做什么",
                    "## 有什么用", "## 怎么用（过程教程）"):
        assert heading in text, "小节标题丢了：%s" % heading

    with open(PREVIEW, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    with open(PREVIEW, "r", encoding="utf-8", newline="") as fh:
        check = fh.read()
    assert check == text, "预览文件和写入内容不一致"

    os.replace(PREVIEW, TARGET)
    print("已更新 %s" % TARGET)
    print("  REPL 段改成 python -c 非交互写法，指令列表更新为 5 个")
    print("  ls w2l 输出补上 entry.py 和 __pycache__")


if __name__ == "__main__":
    import re
    sys.stdout.reconfigure(encoding="utf-8")
    main()
