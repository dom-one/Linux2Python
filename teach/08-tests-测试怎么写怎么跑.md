# tests/ — 测试怎么写怎么跑

`tests/` 目录只有两个文件：`conftest.py`（测试脚手架）和 `test_grep.py`（36 个用例）。用的是 pytest。

## 为什么这么创建

**为什么用 pytest 而不是 unittest。** 这个项目的测试要反复做一件事：造一批临时文件 → 跑一条指令 → 断言输出。pytest 的 `tmp_path` fixture 直接给每个用例一个独立的临时目录，省掉 `tempfile` 的手工清理；`pytest.raises` 让异常断言只有一行；`-k` 表达式让按名字筛用例变成一条命令。unittest 里这些都要自己搭。

**为什么要有 `conftest.py`。** 三个原因：

1. **让项目根目录进 `sys.path`**。`tests/conftest.py` 里有：

   ```python
   ROOT = Path(__file__).resolve().parents[1]
   if str(ROOT) not in sys.path:
       sys.path.insert(0, str(ROOT))
   ```

   有了它，`import w2l...` 在任何工作目录下都能用，不需要 `pip install -e .`。

2. **复用跑指令的样板**。每个用例都要「解析参数 → 造上下文 → 调处理函数 → 拿退出码和输出」，这段写在 `run_grep()` 里：

   ```python
   def run_grep(argv, cwd=None, stdin_text=""):
       namespace = build_parser().parse_args(list(argv))
       out, err = io.StringIO(), io.StringIO()
       ctx = RunContext(cwd=Path(cwd or ROOT), stdout=out, stderr=err, stdin=io.StringIO(stdin_text))
       code = grep(namespace, ctx)
       return code, out.getvalue(), err.getvalue()
   ```

   用例里就只剩一行 `code, out, err = run_grep([...])`。

3. **复用测试数据**。`sample_tree` fixture 造出一个固定的目录结构：

   ```python
   @pytest.fixture
   def sample_tree(tmp_path):
       (tmp_path / "app.log").write_text("INFO start\nERROR failed\nwarn retry\nERROR again\n", encoding="utf-8")
       (tmp_path / "notes.txt").write_text("alpha\nBeta\ngamma\n", encoding="utf-8")
       nested = tmp_path / "sub"
       nested.mkdir()
       (nested / "deep.txt").write_text("error in deep\nnothing here\n", encoding="utf-8")
       return tmp_path
   ```

**为什么输出断言写全等而不是 `in`。** `assert out == "ERROR failed\nERROR again\n"` 比 `assert "ERROR failed" in out` 严格得多。多输出一行、前缀格式变了、行尾多空格了，后者照样通过，前者会失败。grep 的输出格式是要对齐 GNU 的，值得严格断言。

**为什么不测真实的进程。** 绝大多数用例直接调 `grep(namespace, ctx)`，输入输出都是内存对象，跑得快也不受终端编码影响。只有少数几条走 `main()`（`test_cli_dispatch_returns_match_code`、`test_cli_unknown_command`、`test_cli_help_lists_commands`），用 pytest 的 `capsys` 捕获 stdout/stderr。

## 这个文件是做什么

`tests/conftest.py` 提供：

| 名字 | 类型 | 作用 |
|---|---|---|
| `ROOT` | 常量 | 项目根目录路径 |
| `_Tty` | 类 | 伪装成终端的 `StringIO`，`isatty()` 返回 `True` |
| `run_grep(argv, cwd=None, stdin_text="")` | 函数 | 跑一次 grep，返回 `(退出码, stdout, stderr)` |
| `sample_tree` | fixture | 造出 `app.log` / `notes.txt` / `sub/deep.txt` 三个文件 |

`tests/test_grep.py` 是 36 个用例，按行为分组：

| 组 | 用例 |
|---|---|
| 基础匹配 | `test_basic_match`、`test_no_match_returns_one` |
| 单选项 | `test_ignore_case`、`test_invert_match`、`test_line_number` |
| 递归 | `test_recursive_with_prefix` |
| 错误路径 | `test_directory_without_recursive_is_usage_error`、`test_trailing_backslash_is_usage_error`、`test_invalid_regex_is_usage_error`、`test_missing_file_reports_error` |
| BRE / ERE | `test_extended_regexp`、`test_basic_regexp_treats_pipe_as_literal`、`test_basic_regexp_escaped_alternation`、`test_basic_regexp_escaped_group`、`test_basic_regexp_treats_plus_as_literal` |
| 汇总类选项 | `test_word_regexp`、`test_count`、`test_count_multiple_files_prefixed`、`test_files_with_matches`、`test_only_matching`、`test_only_matching_with_line_number` |
| 二进制 | `test_binary_file_message`、`test_binary_file_listed_with_l` |
| 标准输入 | `test_stdin_search`、`test_stdin_count`、`test_no_path_reads_stdin_like_gnu_grep`、`test_no_path_in_terminal_searches_current_directory`、`test_no_path_in_terminal_searches_recursively` |
| 编码 / 行尾 | `test_crlf_line_endings`、`test_gbk_encoding`、`test_gbk_encoding_on_non_chinese_locale`、`test_utf8_file_on_non_chinese_locale`、`test_latin1_file_stays_readable` |
| 分发层 | `test_cli_dispatch_returns_match_code`、`test_cli_unknown_command`、`test_cli_help_lists_commands` |

不负责：被测代码本身（`w2l/`）、CI 配置（`.github/workflows/ci.yml`）。

## 有什么用

- 改 `w2l/commands/grep.py` 之后，一条命令确认没改坏行为。
- 加新指令时照着抄结构，不用重新设计测试骨架。
- 行为契约写成了可执行的断言：BRE/ERE 差异、退出码语义、二进制处理、编码判定这些「容易被人记错」的细节都有用例钉住。

## 怎么用（过程教程）

### 第 1 步：跑全部测试

```bash
cd E:\1\NULL\Windows-to-Linux
python -m pytest
```

预期输出（`pyproject.toml` 里已配 `addopts = "-q"`，所以裸跑也是安静模式）：

```
...............................                                          [100%]
36 passed in 0.15s
```

### 第 2 步：跑单个文件 / 单条用例

```bash
cd E:\1\NULL\Windows-to-Linux
python -m pytest tests/test_grep.py
```

预期：`36 passed`（用例全在这个文件里）。

```bash
cd E:\1\NULL\Windows-to-Linux
python -m pytest tests/test_grep.py::test_gbk_encoding
```

预期：`1 passed`。

```bash
cd E:\1\NULL\Windows-to-Linux
python -m pytest -k "word or count"
```

预期：

```
....                                                                     [100%]
4 passed, 27 deselected in 0.03s
```

`-k` 是按用例名做子串匹配，`or` / `and` / `not` 都能用。

### 第 3 步：看收集到了哪些用例

```bash
cd E:\1\NULL\Windows-to-Linux
python -m pytest --collect-only -q
```

预期最后一行：

```
tests/test_grep.py: 31
```

### 第 4 步：写一条新用例

在 `tests/test_grep.py` 里加：

```python
def test_ignore_case_with_line_number(sample_tree):
    code, out, _ = run_grep(["-in", "error", str(sample_tree / "app.log")])
    assert code == 0
    assert out == "2:ERROR failed\n4:ERROR again\n"
```

跑：

```bash
cd E:\1\NULL\Windows-to-Linux
python -m pytest -k ignore_case_with_line_number
```

预期：

```
.                                                                        [100%]
1 passed, 30 deselected in 0.01s
```

`-k` 的匹配规则是「表达式里的标识符是否出现在用例名中」，不是「用例名是否出现在表达式里」。`test_ignore_case` 里没有 `ignore_case_with_line_number` 这个整串，所以不会被选中。

### 第 5 步：加一条「新指令」的测试

新指令 `ls` 的测试放在 `tests/test_ls.py`，不要塞进 `test_grep.py`：

```python
import io

import pytest

from conftest import _Tty
from w2l.commands.ls import build_parser, ls
from w2l.context import RunContext


def run_ls(argv, cwd):
    namespace = build_parser().parse_args(list(argv))
    out, err = io.StringIO(), io.StringIO()
    ctx = RunContext(cwd=cwd, stdout=out, stderr=err, stdin=_Tty())
    code = ls(namespace, ctx)
    return code, out.getvalue(), err.getvalue()


def test_ls_lists_names(tmp_path):
    (tmp_path / "b.txt").write_text("x", encoding="utf-8")
    (tmp_path / "a.txt").write_text("y", encoding="utf-8")
    code, out, err = run_ls([str(tmp_path)], tmp_path)
    assert code == 0
    assert out == "a.txt\nb.txt\n"
```

`from conftest import ...` 能直接用，是因为 `tests/` 目录下没有 `__init__.py`，pytest 会把测试文件所在目录插进 `sys.path`。

### 第 6 步：三类用例都要有

`cron.md` 第 3 节规定每条新指令至少要覆盖：正常路径、选项组合、错误路径。对 `ls` 来说：

```python
def test_ls_missing_directory(tmp_path):
    with pytest.raises(UsageError):
        ...  # 目录不存在
```

错误路径用 `pytest.raises` 断言异常，别断言 stdout 为空——异常路径的输出本来就该在 stderr 上。

### 第 7 步：提交前跑一次全量

```bash
cd E:\1\NULL\Windows-to-Linux
python -m pytest -q
git status
```

预期：`36 passed`（或加了新用例后的新数字），且 `git status` 里只有本次改动。`AGENTS.md` 第 5 节写明「全绿才允许提交」。

### 第 8 步：pytest 本身不是项目依赖

`pyproject.toml` 的 `dependencies = []`，pytest 不在里面，也没建 `optional-dependencies` 的 dev 组。所以：

- `pip install -e .` **不会**装上 pytest。
- 本机能跑 pytest，说明环境里已经装了（当前是 pytest 9.0.2、Python 3.14.0）。
- CI 的 `Install` 步骤也只升级 pip，没装 pytest——见 `11-github-actions-ci.yml-持续集成.md`。
