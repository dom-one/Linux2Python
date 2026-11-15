"""给本 tick 追加进度日志。

直接调 _t11_progress.py 的 main()，用文件里的长文本参数走 argv，
免得在 shell 里跟中文标点、单引号较劲。
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

PROGRESS = ROOT / "AI" / "阅读进度.md"

THEME = "实现 cp 指令"

REASON = (
    "固定命令队列（ls→cat→head→tail→wc→find→tree→du→sed→awk-lite）已全部实现，"
    "按 AI/AGENTS.md §1.1 的约定改走 README「后续演进路线」阶段二的顺序，"
    "本轮取 cp（阶段二里排在最前的未实现命令）"
)

PRODUCTS = (
    "w2l/commands/cp.py、tests/test_cp.py、tests/conftest.py（新增 run_cp）、"
    "README.md（cp 能力清单章节、目录结构、快速开始示例、阶段二路线）、"
    "AI/脚本/_t406_probe_cp.py、_t407_probe_cp2.py、_t408_probe_cp3.py、"
    "_t409_probe_cp4.py、_t410_diff_cp.py、_t411_cleanup_smoke.py"
)

GAIN = (
    "GNU cp 8.32 的落点规则实测清楚了：目标是已存在的目录时源落成「目录/源名」，"
    "目标不存在时目标本身就是新文件/新目录（-r 拷目录到不存在的目标时不再套一层同名目录）；"
    "源目录尾部的斜杠不影响落点（cp -r dir1/ 与 cp -r dir1 一样）；"
    "检查顺序有讲究——多个源时「目标不是目录」这条先于逐个源的存在性检查，"
    "「未指定 -r」这条先于「目录覆盖文件」；"
    "目标已有同名目录时是合并语义：同名文件被覆盖、目标多出来的文件保留；"
    "-v 只对真正动了的条目打印，目录那行只在被新建时出现；"
    "-n 压过 -i（两个一起给时不提问）；-u 要求源严格更新，mtime 相等算没更新；"
    "-p/-a 保住源的时间戳，目录的 mtime 必须在内容写完之后再设，否则被子文件写入顶掉；"
    "--parents 自己建父目录，而普通递归拷贝不建（GNU 直接报 cannot create directory）；"
    "-S 是先把旧目标改名加后缀再写新的；"
    "差分对照有两个度量上的坑：两个沙箱的夹具创建时刻不同，mtime 直接比数值必然假不一致，"
    "要归成「保住源时间戳 / 复制时刻」两类再比；"
    "GNU 的目录遍历是 readdir 顺序，两个沙箱的目录项顺序天然不同，"
    "verbose 只能比集合不能比先后（本实现走排序后的顺序，落地内容完全一致）"
)

NEGATIVE = (
    "第一版实现用 dst.mkdir(parents=True)，把「父目录不存在」也顺手建了出来，"
    "与 GNU 不一致（GNU 报 cannot create directory），是差分对照抓出来的，"
    "改成只有 --parents 才建父目录；"
    "差分对照第一轮报 6 组不一致，其中 4 组是度量上的假阳性（mtime 跨沙箱不可比、"
    "verbose 顺序是 readdir 顺序），不是实现问题——教训是差分脚本自己也会骗人，"
    "拿到不一致要先分清「实现差异」和「度量差异」再动手改；"
    "清理一个没用上的局部变量时误删了两处 del created，copy_dir 递归时直接 UnboundLocalError；"
    "探针脚本删临时目录时被只读文件挡住 PermissionError（Windows 上只读位会阻止 rmtree），"
    "补了 force_rmtree 先 chmod 再删"
)

PENDING = (
    "推送未成功：两次 git push 都失败，第一次报 error: RPC failed; curl 28 Recv failure: "
    "Connection was reset / send-pack: unexpected disconnect while reading sideband packet / "
    "fatal: the remote end hung up unexpectedly，第二次报 fatal: unable to access "
    "'https://github.com/dom-one/Linux2Python/': Recv failure: Connection was reset；"
    "本地两个提交保留（origin/main 还停在 45804ab，本地领先 2 个），下个 tick 开工前先补推；"
    "符号链接分支未实测：Windows 上创建符号链接要管理员权限（本机 WinError 1314），"
    "MSYS 的 ln -s 又落成普通文件，所以「默认解引用」与「-a 不解引用」两条路径都没验证过；"
    "-p 的 mode 在 Windows 上落成只读属性，ownership/context/xattr 接受但没有实际效果；"
    "目录遍历顺序本实现用排序后的（GNU 是 readdir 顺序），落地内容一致但 -v 的打印顺序可能不同"
)


def main() -> int:
    argv = [
        "_t11_progress.py",
        "--进度",
        str(PROGRESS),
        "--主题",
        THEME,
        "--理由",
        REASON,
        "--产出",
        PRODUCTS,
        "--收获",
        GAIN,
        "--负面",
        NEGATIVE,
        "--剩余",
        PENDING,
    ]
    sys.argv = argv
    runpy.run_path(str(HERE / "_t11_progress.py"), run_name="__main__")
    return 0


if __name__ == "__main__":
    sys.exit(main())
