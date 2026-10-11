# WP-F-a 评审结果：FAIL

## 范围与验证

- 基线：`git archive b97f3ac` 在独立临时目录解包；补入原始资料，并创建 `products/` 空目录。另将父提交 `b90dc70` 解包供差异核对。主仓库实现文件未运行或改动。
- 对照：`round-133-wp-fa-task.md`、`round-134-wp-fa-rework-task.md`、两份实现报告、`contracts/state_sources.md`、第 132 轮最终规则第 2/5 条；完整查看四个实现文件及相关测试的变更。
- 指定的六个模块：归档中运行 76 项，73 项通过、3 项因归档没有 `.git` 而在固定旧提交的 `git show` 处失败；只给这 3 项设置只读 `GIT_DIR` 后重跑，3 项均通过。这 3 项失败不是实现行为失败。未跑全量。

## 必须改

### M1 — 已登记当前计划文件丢失时抛原始异常

- **严重度：MAJOR。位置：**`ky/storage/day_plan_store.py:702`，`DayPlanStore._read_current_plans()`。
- **可复现输入：**在临时存储成功写入 `2026-09-15` 的日计划，再让 manifest 指向的 `2026-09/day_plans/2026-09-15--v1.yaml` 丢失；保留原 manifest。独立探针用 `DayPlanStore.write_day_plan()` 写入后删除 `WriteReport.path` 来模拟文件丢失。
- **实际：**`read_state_sources()` 的 `plan_path.read_bytes()` 抛 `FileNotFoundError`，没有变成带路径的 `StorageError`。若重建命令只捕获契约错误，用户得到 traceback，无法按损坏来源定位恢复。
- **应有：**已登记的当前版本缺失属于无效状态，应带缺失路径报 `StorageError`，旧投影仍保留；这符合第 132 轮 F5 和任务书“无效来源报契约错误”。队列/路线新端口的文件读取已有 `OSError → StorageError` 处理。
- **最小修法与回归：**仅给新读取端口的当前计划 `read_bytes()` 加 `OSError` 转换；增加“manifest 存在、当前版本文件缺失”这一条定向测试。保留旧 `load_day_plan()` 的兼容行为，除非另行决议。

### M2 — 存储根已存在但类型错误时被当成空库

- **严重度：MAJOR。位置：**`ky/storage/day_plan_store.py:646`、`ky/storage/review_shards.py:506`、`ky/storage/route_store.py:171`。
- **可复现输入：**临时目录下建一个普通文件 `plans`，分别以它为 `DayPlanStore`、`ReviewShardStore`、`RoutePlanStore` 的根，调用各自 `read_state_sources()`。
- **实际：**三者均无异常：计划返回全空，队列返回空项/空来源，路线返回 `None`/空来源。独立探针已复现。正常配置把 `state.plans` 等误指向已有文件时，这会把“登记路径无效”展示为“尚无学习记录”。`Workspace.write_target()` 能检查类型，但这四个新端口的规格没有规定调用方必须先调用它，F-b 也尚未实现。
- **应有：**“根不存在”才是空存储；“根存在但不是目录”应是带路径的契约错误（第 132 轮 F5）。
- **最小修法与回归：**三个新方法入口区分 `not exists` 与 `exists and not is_dir`，后者报 `StorageError`；各加一条文件占据根路径的最小测试。也可由决策者将 `Workspace.write_target()` 检查写成 F-b 的强制前置契约并据此重审，但当前 F-a 不能自行声称此输入已被排除。

两项探针的完整输入（在归档根用 `py -3.12 -B` 运行，文件只写入系统临时目录）：

```python
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from tests.contract.test_state_sources_port import WEIGHTS, _plan
from ky.storage.day_plan_store import DayPlanStore
from ky.storage.review_shards import ReviewShardStore
from ky.storage.route_store import RoutePlanStore

with TemporaryDirectory() as directory:
    root = Path(directory)
    occupied = root / "plans"
    occupied.write_bytes(b"occupied")
    for store_type in (DayPlanStore, ReviewShardStore, RoutePlanStore):
        print(store_type.__name__, store_type(occupied).read_state_sources())
    store = DayPlanStore(root / "valid", subject_weights=WEIGHTS)
    written = store.write_day_plan(_plan(date(2026, 9, 15)))
    Path(written.path).unlink()
    store.read_state_sources()  # FileNotFoundError; expected StorageError
```

## 建议改

- **S1 — M26 顶层导出。**`ky/availability/port.py` 已声明 `AvailabilitySource`、`load_availability_with_source` 为公开接口，`ky/availability/__init__.py` 尚未导出它们。F-b 可从 `ky.availability.port` 直接导入，当前不阻断；若项目惯用 `from ky.availability import ...`，应补顶层导出和文档。
- **S2 — F-b 合并命名空间。**三份 `sources` 的键都只相对各自根，单独使用符合规格；合并时须先用 `state.review_queue`、`state.plans`、`state.routes`、`state.availability` 作命名空间或转为工作区相对路径，不能直接 `dict.update`。availability 只返回摘要，文件路径应由 F-b 的注册表键提供。这是 F-b 工作，不要求 F-a 改形状。

## 不改（已核实）

- **对象与哈希：**计划当前版本、完成事件、冻结事件，队列项及顺序，当前路线与 availability 均沿旧解析/校验口径。新端口中实际读取来源字节的位置分别是 `Path.read_bytes()`；私有解析函数接收该字节串，摘要也由同一字节串计算。队列旧 `load()` 继续共用 `_load_items()`，路线旧 `current()/load_revision()` 与新端口共用 `_load_entry_from_bytes()`，冻结事件与 manifest 也共用私有解析函数。审查这些调用链未发现绕过计数测试的另一次 `open`/`os.open`；测试只钩住 `Path.read_bytes/read_text` 本身并非对所有未来 I/O 写法的证明。
- **布局：**合法 `<root>/<YYYY-MM>/day_plans_manifest.yaml` 才收计划；其他位置同名文件报错。月结、旧版本计划和 `freeze/` 内按自身命名写入的事件不会因这个判断误报；现有组合测试覆盖多月、旧版、月结及冻结/恢复事件。错位完成事件仍被拒绝。
- **旧接口：**差异审查和指定模块测试未见 `freeze_events()`、`load_day_plan()`、`load()`、`current()`、`load_revision()` 的正常返回或已覆盖错误路径回归。极端损坏字节的异常文字没有逐种证明逐字相同，不能把 76 项通过扩展成全输入等价声明。

## 安全登记（不计入本包门禁）

- **内部 manifest 路径未先做包含校验。**`DayPlanStore._read_current_plans()` 直接拼接 `entry["path"]` 后读取。触发需有人刻意修改内部 `day_plans_manifest.yaml` 并配套摘要；路径含 `..` 时可能令读取越出计划存储根。这是手工篡改内部文件的攻击面，按 `AGENTS.md` 个人本机威胁模型登记，不列为本轮必须改。将来若开放给不可信输入，可在读取前验证 manifest 路径为存储生成的相对布局并检查解析后仍在根内。

## 门禁结论

**FAIL。**M1 会把来源损坏变成 traceback；M2 会把无效登记根静默显示为空。修好上述两点后，定向重跑 `tests.contract.test_state_sources_port` 及受影响的旧存储测试即可；全量由决策者提交前统一跑。
