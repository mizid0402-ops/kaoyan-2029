# 评审任务书：第 185 轮 —— B6 配置键改名（窗口 `sol-main`）

请评审 `luna-b` 第 185 轮。任务书 `review/rounds/round-185-b6-rename-task.md`（用户 2026-09-29 决定改名），
实现报告 `review/rounds/round-185-b6-rename-luna.md`。范围：`git diff d692365` 的全部改动（`ky/`、`contracts/`、`docs/`、`tests/`）。
同一工作区里没有其它窗口在改文件。

先读 `AGENTS.md`（"不留兼容别名"、"迁移 / 重构不得改变输出"第 11–13 条与 12a）。

## 重点看

1. **行为不变**：除键名外，任何分钟计算、比例、保底、硬上限、7 天份额排序、校验范围都没变。
2. **旧键拒绝**：只有旧键、新旧并存两种情况都在未知键检查之前报 `ContractError`，路径 `total_daily_minutes`，
   不读旧值、不迁移。报错文字是中文，而 `ky/models.py` 其它 `ContractError` 消息是英文——
   按 `AGENTS.md`"跟周围代码长得一样"判断是否要改成英文（给出你的结论与理由）。报告里 `git grep` 段落的英文输出与代码不符，请核实是否只是报告过时。
3. **对外输出**：preflight 与规划者输入包里只有这个键名变化（`config.default_daily_minutes`、输入包顶层的同名键），`input_hash` 随之变；其它字节不变。
4. **固定基线测试的改法**：实现者在 `test_models_split_baseline`、`test_schedule_split_baseline`、`test_availability_port`、
   `test_planner_port`、`test_freeze_port` 里给旧代码喂旧键 / 旧字段视图，并在比较前做了替换——
   `test_models_split_baseline` 对错误消息 `str(exc).replace(...)`、`test_availability_port` 对**基线 CLI 源码**做属性名替换。
   检查每一处替换是否只放过这一个名字、有没有顺带抹掉别的差异（第 12a 条：按原始字节比较，不用正则抹整段），
   以及基线仍固定在提交哈希上、确实取到旧版。
5. `git grep total_daily_minutes -- ky contracts tests docs README.md` 的剩余位置是否都属于"改名提示 / 规格说明 / 基线适配"。
6. 自己做一次撤实现变异（例如让旧键检查放在未知键检查之后，或让输入包漏改键名），确认对应测试变红。

## 规则

只跑与结论直接相关的单个模块或单条命令，**不跑全量**；复现用系统临时目录。
结论 PASS / FAIL，分"必须改 / 建议改 / 不改"，每条附可复现输入；安全类单列"安全登记"。

## 报告

`review/rounds/round-188-b6-rename-review-codex.md`。
