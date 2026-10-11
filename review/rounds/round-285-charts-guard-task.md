# 第 285 轮任务书：图表数据端口的参数护栏（gpt-6-luna，窗口 luna-fix-charts，新会话）

## 来源

最终大检查 B（`review/rounds/round-282-final-b-sol61.md`）的必须改 M1，决策者已按代码位置复核：
`ky/charts/data.py:20`、`:204`、`:322` 三个公开数据端口没有"先校验参数再运算"（`AGENTS.md` 已知缺陷 #6）。

- `week_chart_data(..., days=None)` → `TypeError`
- `progress_chart_data(..., start=None)` → `TypeError`
- `ability_chart_data(..., today=None)` → `AttributeError`

非法参数应当是**带参数路径的契约错误**，不是 `TypeError` / `AttributeError`。

## 要做

1. 先读 `contracts/charts.md`，确认这三个参数的**缺省语义**。如果某个参数按规格允许为 `None`（例如"未登记"），
   就**不要**拒绝它，在报告里写明；只有规格不允许的非法形态才报错。
2. 在三个公开端口入口加参数校验，照 `ky/charts/data.py` 或同包已有校验的写法与错误类型，
   错误文本带参数路径（`week.days` / `progress.start` / `ability.today` 这类）。
3. 合法输入的输出必须**逐字节不变**（不要改映射内容、不要重排键）。
4. 回归测试放 `tests/contract/test_charts_port.py`，照该文件既有夹具：每个端口至少一个非法输入断言
   `ContractError` 与参数路径。合法输入的断言如果该文件已有等价的，就不要重复写。

## 不要做

- 不动 `ky/charts/render.py`、不动 CLI 装配、不动 M30 端口。
- 不顺带处理"建议改"（学期文件名规则、图例文字、零权重展示、能力页解释）——那些另开包。
- 不跑全量、不提交。

## 验收（只跑这两条 + 三条复现探针）

```
py -3.12 -m unittest tests.contract.test_charts_port
py -3.12 -m unittest tests.contract.test_mastery_port
```

复现探针：三个非法参数各一条，贴修复前后输出（异常类型 + 错误文本）。

## 报告

写 `review/rounds/round-285-charts-guard-luna.md`，≤ 60 行：逐条端口改了什么（`文件:行`）；
先校验后运算的依据（规格哪一句 / 你如何判定 `None` 是否合法）；修复前后探针输出；
两条验收命令的 `Ran ... OK` 原文；"全量：未跑"；怀疑模块；未做。

## 规则（照 `AGENTS.md`）

- 含中文的文件只用编辑工具写；写完查连续 `???`。
- 行宽 ≤ 100；函数 ≤ 约 60 行；注释引用 M17 / sol 282 M1。
- 模块头 docstring 保持 M 编号与规格引用（`contracts/charts.md`）。
- 临时输入放系统临时目录；设 `PYTHONDONTWRITEBYTECODE=1`。
