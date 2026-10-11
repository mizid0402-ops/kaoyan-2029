# 第 254 轮任务书：M17 可视化 ⑤a 实现（gpt-6-luna，luna-c 新会话）

## 先读

`AGENTS.md`（全文，尤其 D7、验证范围、编码、已知缺陷清单）、规格 `contracts/charts.md`（本包唯一依据）、
`contracts/timetable.md` §7–§8、`ky/timetable_io/preview.py`（`base_resolver`）、`ky/pacing/cli.py`（`--workspace` / `--config` 取法、`_load_state` 一次读取各来源的写法）、
`contracts/state_sources.md`、`contracts/workspace.md`（`products`）。

## 工作区

主仓库 `F:\workspace\kaoyan-ai-system`，master 当前提交之上直接改（本包与其他进行中的工作不重叠）。

## 要做的

1. 新包 `ky/charts/`：`data.py`（`week_chart_data`、`progress_chart_data` 等纯函数）、`render.py`（plotly `graph_objects` → HTML）、`cli.py`（`chart_main`）、`__init__.py`。
   每个模块头按 D7 写明 M17、`contracts/charts.md` 与对外接口。
2. `ky/__main__.py` 注册 `chart` 子命令（照 `pacing` 的注册方式），`ky chart week` / `ky chart progress` 参数与退出码照规格 §3–§5。
3. `kaoyan.workspace.yaml` 加 `products: charts: outputs/charts`；`.gitignore` 加 `outputs/`（附一行注释：图里有个人课表与学习记录）；
   `pyproject.toml` 依赖加 `"plotly>=6,<7"`（本机已装 6.9.0，**不要再 pip install**）。
   加注册表键前先 `grep -rn 'products' tests/` 看复制注册表的测试辅助函数是否需要同步。
4. `docs/模块地图.md` 拆出 M17 一行；README "模块替换速查" 的 "M16–M17" 行拆出 M17，"四、上手" 加两行 `ky chart` 用法。

## 不做的

- 不做能力画像 / 目标差距（⑤b）；不做 `plotly.express`、不引入 pandas；不改任何既有命令输出与 M8 / M18 / M28 / M29 接口。
- 不跑 datasette、不改投影；不读 `data/personal/` 与 gitignore 的学习状态（测试一律用临时工作区合成数据）。

## 测试（只写这些，`tests/contract/test_charts_port.py`）

1. `week_chart_data`：合成学校档案 + 课表（含一门跨午休的 3–8 节课、一个 `no_class` 例外、一个 `follow` 例外、一个 `unconfirmed` 节次、一天不在学期内），
   断言 7 天映射逐字段（`covered`、`classes`、`free_segments`、`minutes`、`base_minutes`、`unconfirmed`、`time_range`）；复盘设置登记时 `base_minutes` 取 `initial`。
2. `progress_chart_data`：
   - 4.1 有 / 无完成事件、`study_minutes` 为 `null` 的日子 `actual` 为 `null`；`daily_totals` 只合计有记录的日子；`reference` 与 `resolve_day_budget(...).total_minutes` 相等（含一天有手填、一天有课表）。
   - 4.2 跨三个 ISO 周的区间（首尾不满一周）按周汇总，科目按配置顺序、缺省 0。
   - 4.3 合成小树：叶子直接引用、引用非叶子覆盖其子树叶子、引用不在树里的 ID 进 `unknown_refs`、任意状态都算；未登记树的科目 `covered` / `total` 为 `null`。
   - 4.4 有路线：阶段列表与 `days_to_exam`；无路线：`route` 为 `null`。
3. 渲染与 CLI：
   - 同一临时工作区运行两次 `ky chart week` / `ky chart progress`，HTML **逐字节相同**；同目录 `plotly.min.js` 与 `plotly.offline.get_plotlyjs()` 字节相同；HTML 不含 `cdn.plot.ly` / `http` 引用 plotly。
   - 缺 `products.charts` 且无 `--out` → 退出 2；`--out` 生效；`--from` 晚于 `--to` → 退出 3；`--week` 超范围 → 退出 3；未登记课表 → `chart week` 退出 3（文字同 `timetable show`）。
   - 登记了但文件无效的完成事件 → 退出 2，无 traceback。
   - 规格 §5（sol 253 M1）：新工作区登记了 `state.plans` / `state.review_queue` / `state.routes` 但目录尚未创建 → `chart progress` 退出 0，四图按"没有数据"画（"尚无路线"等）。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.contract.test_charts_port tests.contract.test_workspace tests.test_cli
```

报告写 `review/rounds/round-254-m17-luna.md`：改动、做法、测试输出原文、"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"、歧义与选择。
不提交；报告与测试不含个人数据；含中文的文件只用 `apply_patch` 编辑，**中文字符串写字面量，不要写成 `\uXXXX` 转义**；写完 `rg -n '\?\?\?'` 检查。
