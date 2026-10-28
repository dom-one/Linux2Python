#!/usr/bin/env python
"""Windows-to-Linux 统一入口。

用法:
    python main.py <指令> [参数]
"""

import sys

from w2l.cli import main

if __name__ == "__main__":
    sys.exit(main())
