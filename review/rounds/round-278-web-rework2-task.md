# 第 278 轮任务书：⑥ 前端首版第二次返工（续 luna-a）

sol 第 277 轮实现初检 FAIL（报告：`review/rounds/round-277-web-impl-review-sol61.md`，每项都附了可复现输入，先读它）。决策者另在真实页面上发现两处显示问题。
注意：决策者已把重复的冻结锁存合并为 `ky/today/record.py::latch_freeze_if_needed`（CLI `submit` / `record` 与 M33 共用），在此基础上改，不要拆回去。
规格 `contracts/today.md` §4.1 已补一句 `advance` 与 `record` 在 `--review-store` 缺省上的唯一差别。

## 必须改

1. **C1 恢复提示带齐实际路径**：用本次**已解析**的完成事件存储、复习队列、配置路径构造恢复命令（不论它们来自显式参数还是注册表），
   注册表是隐式发现的也写出 `--workspace <实际注册表路径>`；恢复命令不得重新选择来源。补一个测试：注册表缺省路径 + 推进失败 → 提示里有三条实际路径。
2. **C2 阶段码**：冻结事件发布后，`freeze_written` 必须由发布这一步直接交回，不能靠之后重读文件；锁存后的任何失败（含 `OSError`）都按已持久化阶段包装。
   完成事件写入、队列推进抛出的 `OSError` 同样按阶段包装。按 sol 的输入补测试。
3. **C3 真题显示**：按 `question_level`（或 `check`）区分：真题显示题号（`question_ref`）与年份 / 题号元数据，不把元数据当题面；改编题才显示题面、选项与折叠答案。补渲染测试。
4. **C4 基线身份断言**：两个基线用例的 `fixed_source` 身份条件要用**只存在于旧版**的特征（例如已删除的 `_day_plan_record_freeze`、`_day_plan_record_advance_queue`
   或旧函数体里的特征行），并加一行断言当前工作区源码**不**满足该条件。
5. **C5 D7**：`ky/today/port.py::_load_today_context`（78 行）拆成有名字的步骤（读取 / 计算 / 各段映射构造），读取次数与输出字节不变。
6. **网页显示**（决策者实看）：
   - 路线复习配额那几行显示科目中文名（`display_name`），不显示 `cs408` 等 ID；
   - 复盘段不要把周期终日写成"下次复盘"：写"本周期到 <终日> 结束，<终日+1> 复盘"；无周期时写"复盘尚未开始（起点 <start>）"或省略，二选一并在报告说明；
   - `study_minutes` 为 0 显示"0 分钟"，只有 `None` 显示"未填写"。
7. **补一个对照分支**：固定基线矩阵加一条**带复习项、会推进队列**的 `day-plan record --review-store`（比较退出码、输出与完整文件树字节）。

## 验收（只跑这些模块）

```
py -3.12 -m unittest tests.contract.test_today_port tests.contract.test_web_port tests.test_cli tests.contract.test_freeze_port tests.contract.test_pacing_port
```

## 报告

`F:\workspace\kaoyan-ai-system\review\rounds\round-278-web-rework2-luna.md`：逐条写怎么改的；新增测试；验收 `Ran …` 行；仍未覆盖的。约 50 行。

其余规则同第 275 轮任务书（不提交、不跑全量、不联网、编码规则、不读个人数据、不改 `docs/安全风险登记.md`）。
