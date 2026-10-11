# 第 238 轮任务书：WP-IO3 正方 PDF 导入适配器（④b-2）（gpt-6-luna，独立 worktree）

## 背景

规格 `contracts/timetable_import_zfsoft_pdf.md`（sol 第 231、232 轮审过，修正 N1 后可实现；**以它为准**）与上级 `contracts/timetable_import.md`。
你的 worktree（`../kaoyan-wt-io3`）里已放入你上一轮做的 IO1 改动（未提交，作为起点，正在由 sol 评审）：**不要修改这些 IO1 文件**，
若必须改动其公开接口，在报告里写明原因，由决策者合并时处理。你只新增 PDF 相关文件、测试与一个子命令。
只用 `ky.timetable`、`ky.timetable_io` 的公开入口，不 import `_` 开头的名字。依赖 `pypdf` 已在 `pyproject.toml`。

## 要做的

1. `ky/timetable_io/zfsoft_pdf.py`（模块头写 M29、规格、公开接口）：
   - 模板常量对象 `ZFSOFT_ROTATED_V1`（字号 8/9/12、容差、12 号字精确清单、白名单前缀、页眉区禁用字符）。
   - 片段层 `extract_fragments(data: bytes) -> tuple[Page, ...], tuple[Fragment, ...]`：`pypdf` 读同一份字节，`visitor_text` 的 `cm × tm` 求坐标；冻结数据类；
     文本去首尾空白、空则丢弃、含换行违约；坐标 / 字号须有限。
   - 解析层纯函数 `parse_zfsoft_fragments(pages, fragments, template) -> 课程映射列表`，分阶段：页面一致 → 标签 → 区域 → 锚点 `d` → 分类 → 结构覆盖 → 逐星期切分 → 核对。
   钉死的口径（sol 232 细节）：
   - `Lx` = 7 个标签 x 的最小值与最大值的中点；`S` = 相邻标签 y 差的均值；星期按标签文字定序号，再核对 y 递增。
   - 没有有效的字号 9 差值 → 违约，不对空集合求 min / max；正文区字号 9 片段若不在有效差值范围内，仍须经过分类（不在锚点即按未知片段拒绝）。
   - 所有未完成记录（包括只有名称、尚无详情的）的跨页续接都只到相邻页；空白页或某星期整页无片段不能被跳过去续接。
   - 节次头按完整结构 `\((\d+)(?:-(\d+))?节\)` 在连接后的详情上匹配；名称连接后含结构标记即违约。
   - 所有违约只报页码、坐标、提取序号与阶段，**不回显片段文字**；解析失败不写任何文件。
2. CLI `ky timetable import-pdf FILE --school ID --label L --week1 D [--weeks N]`：规格 §4（缺省周数取各项原写法上界；学校 `system` 须为 `zfsoft`；
   PDF 字节只读一次；之后走上级 §4 第 11–12 条与 IO1 的暂存发布、隔离检查）。
3. 测试（`tests/contract/test_timetable_io_zfsoft_pdf.py`，新文件）：解析层全部用**合成片段**，覆盖规格 §5 列表与 sol 231 的 P1 两例、P2、P3，sol 232 的 N1（切成两段的详情落在页眉区）
   及其单片段对照、锚点差值超范围、结果不依赖片段输入顺序（打乱输入顺序结果相同）。片段层只写"本机存在用户 PDF 时能取出片段并解析成功"的用例，
   路径从环境变量 `KY_TIMETABLE_PDF` 读取，未设置即 skip（个人数据，不进仓库、不写进测试）。

## 不做

ics（IO2）；不改 IO1 行为、M18；不改注册表、个人数据、`docs/模块地图.md`。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.contract.test_timetable_io_zfsoft_pdf tests.contract.test_timetable_io_port
```

报告 `review/rounds/round-238-m29-zfsoft-pdf-luna.md`（写在 worktree 里）：改动、做法、测试输出原文、"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"、歧义与选择。
报告与测试不得含个人数据。不提交。
