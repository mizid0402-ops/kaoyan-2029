# 第 257 轮任务书：M17 可视化第二版 + M4 `tree_parent`（gpt-6-luna，续 luna-c）

用户看了第 254 轮的页面后要求改版。规格 `contracts/charts.md` 已改为第二版（看文件头与 §2、§3 渲染段、§4.1、§4.2、§4.3、§4.5、§6、§7 第二表），
M4 新端口见 `contracts/knowledge_tree.md` "Grammar-aware tree parent"。**以规格为准**。

视觉参考（决策者手写的原型，**只看样子，不要照抄代码结构**）：
`outputs/charts/proto-progress.html`（卡片页面、配色、每日列表）、`outputs/charts/proto-week.html`（周课表新样式）、
`outputs/charts/proto-trees-vertical.html` 里的"方案 E：目录树"（完成度要做成的样子）。原型脚本在
`C:\Users\Lenovo\AppData\Local\Temp\claude\F--workspace-kaoyan-ai-system\46273c79-b68f-4ac0-9073-fa45fcec97c1\scratchpad\proto_charts.py` 与 `proto_trees2.py`，可读不可依赖。
原型里的 `display_parent` 是临时规则，**以规格的 `tree_parent` 为准**。

## 工作区

主仓库 `F:\workspace\kaoyan-ai-system`，在第 254 轮未提交改动之上继续（`ky/charts/`、`tests/contract/test_charts_port.py` 等）。
**并行注意**：另一个窗口（sol61-math1）可能正在改 `data/structured_materials/math1/knowledge_tree*`、`data/materials.yaml`、`data/raw_materials/`、`tests/test_data_manifest.py`；
这些文件你**不要碰**，测试也不要依赖数学一树的具体节点数（用合成树）。

## 要做的

1. `ky/knowledge/hierarchy.py` 新增 `tree_parent`（规格四步，按顺序）；`ky/knowledge/__init__.py` 导出；模块头补上。`parent_id` / `nearest_ancestor_with_scope` 一字不改。
2. `ky/charts/data.py`：`progress_chart_data` 改收完整知识点序列 + 树语法名 + 科目名，按规格 §4.3 去掉跟踪节点、建 `Node` 树、算 `covered/total/tree/unknown_refs/tracker_refs`；
   去掉 `_field` 这类"映射或对象都收"的兼容取值（D7：不写兼容捷径），参数用确定的类型（测试里用真实的 `KnowledgePoint` / `ReviewItem` / `DayPlan` / `CompletionEvent` 构造或其最小真实替身）。
3. `ky/charts/render.py`：按 §2 卡片页面与 CSS 变量配色（浅 / 深两套 + 深色时对 plotly `relayout`）；§3 周课表新样式；§4.1 数字块 + 列表；
   §4.2 科目名图例、空 / 全 0 区分；§4.3 三列可折叠目录树（纯 HTML，初始只展开第一层）；§4.4 甘特用同一配色。plotly 图 `responsive`、不写死宽度。
   仍保持同输入逐字节相同、离线、引用同目录 `plotly.min.js`。
4. `ky/charts/cli.py`：给数据层传科目名（注册表 `subjects.<id>.name`）、知识点序列、`tree_grammar`。
5. 模块头按 D7 更新（M17 / M4、规格、对外接口）。

## 不做的

不改既有命令输出；不改 M8 / M13 / M18 / M28 / M29 接口；不加 `plotly.express`、pandas；不读 `data/personal/`；不碰上面"并行注意"列出的文件。

## 测试（只写这些）

- `tests/contract/test_knowledge_tree_port.py`（或现有 M4 契约测试模块）加 `tree_parent`：合成三种语法各一棵小树，覆盖规格四步每一步、`point_id` 自身是 `<s>.<d>.subject` 时不指向自己、未知语法报错；
  另断言 `parent_id` 对同一批 ID 的结果不变。
- `tests/contract/test_charts_port.py`：
  - §4.3：合成 `named_chapters` 小树（`.subject` / `.chapter` / `.content`）与带跟踪节点（`subject` 级、无非 subject 后代）的 `numbered_chapters` 小树：
    `Node` 树结构、同层顺序、跟踪节点被去掉、`total` 只数可学叶子、粗粒度引用点亮子树、`unknown_refs` / `tracker_refs`；
  - §4.1：数字块的四个值（含无记录与参考合计为 0 时的 `—`）与表格行顺序（最近在上）在 HTML 中出现；
  - §4.2：无日计划 vs 全 0 日计划的两种输出；
  - 保留并通过第 254 轮已有的确定性 / 离线 / 退出码测试；科目名出现在 HTML、科目 ID 不作为图例文字出现。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.contract.test_charts_port tests.contract.test_knowledge_tree_port tests.contract.test_topic_weights_port
```

（`test_topic_weights_port` 用来证明 M6 输出没变。）

报告追加到 `review/rounds/round-254-m17-luna.md` 末尾一节"第 257 轮：第二版"：改动、做法、测试输出原文、"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"、歧义与选择。
不提交；中文字符串写字面量，**不要写成 `\uXXXX` 转义**；含中文的文件只用 `apply_patch`；写完 `rg -n '\?\?\?'` 检查。
