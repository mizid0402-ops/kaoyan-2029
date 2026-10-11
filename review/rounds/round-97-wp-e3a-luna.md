# Round 97 — WP-E3a 路线包络落盘

## 改动文件

- `ky/schedule/planning.py`：加入路线映射序列化与严格解析；保留既有 `validate_route_plan()` 语义。
- `ky/storage/route_store.py`：新增 M13 版本化 RoutePlan 存储、revision 比较交换、历史来源与 SHA-256 校验。
- `ky/__main__.py`：新增 `ky route submit|show`，人工提交来源固定为 `human` / `null`。
- `contracts/route_plan.md`：记录格式、版本库、manifest、CLI、错误路径及 E3b 后续边界。
- `kaoyan.workspace.yaml`：在 `state` 下登记 `routes: data/routes`。
- `tests/contract/test_route_plan_port.py`：新增指定格式、存储和 CLI 契约测试，样本月份由 `envelope_bounds()` 生成。
- `docs/模块地图.md`：更新 M11、M13 和 §4 的 E3b / E4 剩余缺口。
- `review/rounds/round-97-wp-e3a-luna.md`：本报告。

## 设计落点

1. **格式**：`route_plan_to_mapping()` 是 YAML / JSON 映射形状的唯一来源。`parse_route_plan()` 严格拒绝未知键、缺键、布尔整数字段、浮点整数字段和 `datetime`；日期输出为 ISO 字符串。YAML 通过 `load_yaml_text()` 读取，重复键 fail-closed。解析后调用原有 `validate_route_plan()`。
2. **存储**：版本文件为 `route--r<revision>.yaml`，manifest 为 `routes_manifest.yaml`。版本写入临时文件并重读解析后替换；manifest 通过 `replace_bytes()` 原子替换。独占短锁串行化 revision 比较与写入。revision 文件不可覆盖；CAS 拒绝以 `revision` / `route_id` 为路径。manifest 为每个版本保留 `actor`、`input_hash`、路径与 SHA-256；读版本先校验哈希。
3. **CLI**：`submit` 读取 YAML 并以 `actor="human"`、`input_hash=null` 写入；`show` 支持当前版本、指定版本和 JSON。空库的文本输出为“尚无路线”，JSON 输出 `null`。默认存储目录取注册表 `state.routes`，缺失时提示 `--store` 或注册该键。
4. **范围**：未修改 `ky/planner/`、`contracts/planner_port.md`、`RoutePlan` / `MonthEnvelope` 字段或日计划护栏。

## 验收

- `py -3.12 -m unittest tests.contract.test_route_plan_port`：7 项通过。
- `py -3.12 -m unittest tests.contract.test_route_plan_port tests.test_planning tests.contract.test_workspace tests.test_cli`：Ran 90，1 skipped，1 error。唯一错误为 `tests.contract.test_workspace.WorkspaceContractTests.test_1_repository_registry` 检查已有 `materials.raw_root` 时发现注册目标 `data/raw_materials` 不存在；本包没有改动该注册项。命令复跑结果相同。
- `git diff --check`：通过。
- 新增/修改中文文件检查乱码标记：未发现异常。
- 全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。

## 建议

- 由决策者确认 `data/raw_materials` 缺失是否为当前 worktree 的已知基线，之后再复跑指定验收命令。
- E3b 可直接复用本包 `route_plan_to_mapping()` / `parse_route_plan()` 与 `RoutePlanStore`，接入 staging 提案和输入包 `route_plan` 字段。
