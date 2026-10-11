# 第 228 轮：WP-IO1 M18 公开入口与 M29 暂存 / restage / apply

## 改动文件

- `ky/timetable/__init__.py`、`ky/timetable/_models.py`、`ky/timetable/calendar.py`、`ky/timetable/timetable.py`
- `ky/timetable_io/__init__.py`、`ky/timetable_io/isolation.py`、`ky/timetable_io/staging.py`、`ky/timetable_io/operations.py`
- `ky/__main__.py`
- `contracts/timetable.md`
- `tests/contract/test_timetable_port.py`、`tests/contract/test_timetable_io_port.py`

未修改 ICS 导入、导出、依赖、注册表、真实数据与模块地图。本包测试只使用合成数据。

## 实现

- M18 从 `ky.timetable` 导出六个新增校验 / 构造入口、序列化入口及冻结数据类 `LoadedSchool`。`timetable_for_workspace` 对课表与每份被引用档案只读一次，传递原始字节摘要；保留逐学期校验顺序和既有错误字段路径。序列化把时刻与日期规范化，周次升序合并连续区间，并保留课程及例外的对象顺序。
- M29 隔离检查每条命令只计算一次 A / B / C 状态，并把结果传给写入操作。A 状态按仓库工作树检查目标；B 状态允许写入；C 状态拒绝。暂存与备份采用同目录临时文件、重读校验和 `os.link` 防覆盖发布。应用主课表使用 `replace_bytes`；在替换前校验主文件和父目录，临时文件由该原子替换函数创建在同一已检查目录内。
- 暂存格式采用封闭字段校验与重复键拒绝。`hash12` 由 M19 `canonical_json_bytes` 对规范化学期映射计算，不含 notes。重复发布只有内容一致才返回成功；冲突不覆盖原文件。
- `restage` 以当前生效的同 label 学期比较课程周次与例外；找不到同 label 学期时输出新增学期摘要。`apply` 先验证 staging 两级路径包含、文件格式、哈希、合并后课表及学校引用，再决定已应用、label 冲突、dry-run 或写入；写入顺序为备份后原子替换。
- CLI 加入 `ky timetable restage FILE` 与 `ky timetable apply --from-staging FILE [--replace] [--dry-run]`。用法错误返回 3，契约 / I/O / 隔离错误返回 2，成功返回 0；apply 输出变更摘要及第一周课程网格。

## 测试

M18 测试覆盖公开入口校验边界、序列化往返，以及与固定提交 `4816a14` 的基线对照。对照断言旧源码身份，并比较日程、sources、错误字段路径和文件读取次数。M29 测试覆盖 A / B / C 隔离状态、工作区外但仓库内路径、临时文件与备份、发布冲突、restage、apply 写入顺序和中断重跑，以及 CLI 退出码与每次命令只检查一次隔离状态。

实际验收命令：

```text
py -3.12 -m unittest tests.contract.test_timetable_port tests.contract.test_timetable_io_port tests.contract.test_day_budget_port tests.test_cli
```

验收输出原文：

```text
----------------------------------------------------------------------
Ran 102 tests in 43.350s

OK
```

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。

行宽检查：本轮涉及的实现与测试文件最大行宽均不超过 100 字符。含中文文件已检查连续问号标记，未发现匹配。

## 歧义与选择

- 状态 A 以已确认的 Git 工作树根为界；工作区位于仓库子目录时，仓库内、工作区外的目标仍执行 ignore 与 tracked 检查，按规格的仓库边界解释。
- M18 的 `build_calendar` 只构造日历并校验其收到的引用；`timetable_for_workspace` 在按学期顺序逐个加载时先校验当前学期，再继续下一学期，以维持既有错误优先顺序。
- `apply` 对已应用的同一学期仍先完成合并与学校档案验证，再返回“已应用”；因此档案缺失不会被相同学期判断掩盖。
