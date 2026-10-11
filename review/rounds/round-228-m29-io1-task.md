# 第 228 轮任务书：WP-IO1 M18 公开入口 + M29 隔离检查 / 暂存 / restage / apply（gpt-6-luna，续 luna-c）

> 派发时间：Codex 周额度重置（2026-10-04 11:21）之后。

## 背景

规格 `contracts/timetable_import.md`（已提交 `d69cb4c`，sol 第 225–227 轮审过，**以它为准**，不改业务规则）。
本包做 §1 隔离检查、§2 M18 公开入口、§3 暂存与 `restage`、§5 `apply`。**ics 导入（§4）与导出（§6）是下一包 IO2，本包不做。**
先读 `AGENTS.md`、`contracts/timetable.md`、`contracts/timetable_import.md`、`ky/timetable/`、`ky/storage/atomic.py`、`ky/storage/route_store.py`（只写一次发布的写法）。

## 要做的

1. **M18 公开入口**（`ky/timetable/`，从包入口导出；同步 `contracts/timetable.md` §7）：规格 §2 表中六个入口。
   - `LoadedSchool` 为冻结数据类，公开字段 `profile: SchoolProfile`、`path: Path`、`sha256: str`（sol 227 细节 2）。
   - `timetable_for_workspace` 改为"读课表字节 → `timetable_from_mapping` → `load_referenced_schools` → `build_calendar(…, sources)`"；
     **每个文件仍只读一次**；错误检查顺序与现在相同（按学期顺序，先报前一学期的错误），错误字段路径不变；`sources` 仍为工作区根相对 POSIX 路径 → 解析所用字节摘要。
   - 序列化（sol 227 细节 4）：`rules` 的时刻写回严格 `HH:MM`；`daily_cap_minutes` 为 `None` 时省略该键；日期为 ISO 字符串；课程与例外保持对象顺序；
     周次由集合生成升序、合并连续周的 `N` / `N-M` 列表。`timetable_from_mapping(timetable_to_mapping(t))` 与 `t` 相等。
2. **M29 新模块 `ky/timetable_io/`**（模块头写 M29、规格、公开接口）：
   - 隔离检查（规格 §1，三种状态；状态判定对每次命令只做一次，结果传下去）。
   - 暂存文件：格式校验、`hash12`（`semester_to_mapping` 规范化后按 M19 公开的 `canonical_json_bytes`）、只写一次发布（临时文件 + 重读 + `os.link`）、已存在时的相同 / 不同处理。
   - staging 路径两步包含检查写成 M29 自己的具名辅助，**不 import** `ky/planner` 的私有函数。
3. **CLI**（`ky timetable restage FILE`、`ky timetable apply --from-staging FILE [--replace] [--dry-run]`）：规格 §3、§5 全部行为。
   - `restage` 差异：以当前已生效的同 label 学期为基准，列出课程新增 / 删除 / 周次变化与**例外**的增删变化；个人课表未登记时打印"新增学期"摘要（sol 227 细节 6）。
   - 退出码：用法错误 3；契约、I/O、隔离失败 2；成功 0（sol 227 细节 8）。
4. **测试**（只写这些；全部合成数据，不放任何个人数据）：
   - M18：新入口各自的校验范围（规格 §2 表逐行一例）；序列化往返；`timetable_for_workspace` 与重构前逐项一致——
     在同一临时工作区上，对照固定提交 **`4816a14`** 的 `ky/timetable/`（`tests/_baseline_harness.py` 的 `fixed_source` / 隔离加载，断言取到旧版），
     比较 `day()` 结果、`sources`、错误字段路径与每个文件的读取次数。
   - 隔离检查：状态 A（仓库内已忽略未跟踪允许、未忽略拒绝、已跟踪拒绝、**注册表在仓库子目录时工作区外但仓库内的目标同样检查**）、
     状态 B（临时目录里无 `.git`）、状态 C（有 `.git` 但 git 查询失败——用 `unittest.mock` 让子进程返回非零或 `OSError`）；临时文件与备份各自检查。
   - 暂存：同内容重复发布退出 0；已存在不同内容拒绝且不覆盖；`restage` 同哈希返回原文件、改课程发布新文件、保留用户例外。
   - apply：追加；`--replace`；相同内容"已应用"（带不带 `--replace` 都不写备份）；"已应用"但学校档案缺失 → 违约；label 冲突；学期重叠写前拒绝；
     备份同名不同内容拒绝且主文件不变；`--dry-run` 不写；staging 外路径拒绝；其余学期与 `rules` 保持；备份后替换前中断再重跑成功。

## 不做

ics 导入、导出、`pyproject.toml` 依赖（IO2）；PDF（④b-2）；不改 `kaoyan.workspace.yaml`、个人数据文件、`docs/模块地图.md`（决策者做）。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.contract.test_timetable_port tests.contract.test_timetable_io_port tests.contract.test_day_budget_port tests.test_cli
```

写完含中文的文件查 `rg -n '\?\?\?' <文件>`。报告 `review/rounds/round-228-m29-io1-luna.md`：改动、做法、测试输出原文、
"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"、歧义与选择。报告与测试里不得出现任何个人数据。
