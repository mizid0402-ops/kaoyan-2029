# WP-E3b 实现报告

## 改动文件

- `ky/planner/port.py`：M19 日/路线输入、共享 staging 与提案头/输入包哈希校验、日/路线提案 apply、`--plan` staging 路径拒绝。
- `ky/__main__.py`：`planner-input --kind route`；路线 `submit` 两种互斥输入；日/路线 `--plan` 调用 staging 路径拒绝。
- `tests/contract/test_planner_port.py`：本轮路线与信任边界契约测试都放在此文件。
- `contracts/planner_port.md`、`contracts/route_plan.md`：补充 M19 输入、提案、信任边界与 CLI 规格。
- `docs/模块地图.md`：更新 M19 的读写键和验收命令；§4 现在只列 E4 `availability`。

## 设计落点

1. **路线输入包**：`create_route_planner_input()` 写入 `staging/inputs/route--<day>--<hash前12位>.json`；内容严格由 `schema_version`、`kind`、`day`、完整 config、状态快照和 `current_route` 组成。继续使用 `canonical_json_bytes()` 与 `replace_bytes()`。CLI 的 `--kind` 默认 `day`，日输入原输出形式未变。
2. **路线提案**：M19 接受严格头字段和 `parse_route_plan` 映射；真实路径必须在 `staging/routes/`。共享 `_proposal_header()`、`_validate_staging_path()`、`_read_hashed_package()` 避免日/路线分叉复制校验。路线 `stage1_input_hash` 必须等于提案 `input_hash`；匹配输入包并重建输入后才调用共同 `_apply_route_plan()`。revision CAS 仍由 `RoutePlanStore.write_route_plan()` 负责，存储实现未改。
3. **日输入 `route_plan`**：有路线且日期处于包络范围时输出 route id、revision 和当天 envelope；无当前路线、未登记 `state.routes` 或日期超出范围则为 null。固定从 `f0df351d80e3cd0b042ecc88fa11ccc116b65c98` 取旧 `ky/planner/port.py`，测试断言来源确为旧版本，再用同一配置/工作区将旧、新输入对象按原始 canonical 字节比较。
4. **H1 staging 拒绝**：`reject_staging_plan_path()` 解析真实路径；CLI 在可加载注册表时对两种 `--plan` 拒绝 staging 路径并退出 2。无显式 workspace 且发现不到注册表时略过此检查；显式 workspace 错误仍返回契约错误。无写入断言覆盖两类 submit。
5. **共同 apply**：`route submit --plan` 和 `--from-staging` 分别进入 M19 包装函数；测试 mock `_apply_route_plan()` 并断言两种 CLI 路径都调用该共同函数。

## 规格与检查

`planner_port.md` 新增路线输入包、路线提案、日输入路线包络和 `--plan` staging 拒绝规则；`route_plan.md` 说明 `stage1_input_hash` 的提案含义并列出 `--from-staging`。模块地图已登记 M19 读写键和本轮验收命令。

`git diff --check` 通过；本轮含中文文件未发现连续 `???`。

## 验收

首次运行任务书列出的命令：

```text
py -3.12 -m unittest tests.contract.test_planner_port tests.contract.test_route_plan_port tests.test_cli tests.test_day_plan_store
```

共运行 91 项，只有路线库为空、revision 为 2 的负例断言文本不符：存储按既有 CAS 契约返回 `first revision must be 1`，测试原先期待 `expected revision 1, got 2`。修正断言后按 AGENTS.md 只重跑受影响的 `tests.contract.test_planner_port`：24 项通过。第一遍命令中的 `tests.contract.test_route_plan_port`、`tests.test_cli`、`tests.test_day_plan_store` 均通过。

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）

## 建议

输入新鲜度检查仍发生在存储写入之前，与既有 M19 日计划及 RoutePlanStore CAS 的事务边界一致；并发状态变化仍可能发生在检查后、写入前，规格没有承诺该窗口内的原子新鲜度。
