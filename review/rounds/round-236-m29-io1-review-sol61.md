# 第 236 轮：WP-IO1 实现评审

结论：**FAIL**。主要流程与规格相符，现有最小验证通过；但隔离检查误拒合法的按文件忽略布局，主文件替换临时路径未逐一检查，M18 重构在共享学校路径的错误输入上多读一次文件。两项必须改见 R1、R2。

范围：主工作区 IO1 的 diff、新增模块、契约测试、第228轮任务书/实现报告以及对应规格；固定基线为 `4816a14`。未读取两个 M28 worktree，未联网、未跑全量、未读取个人文件或仓库外既有文件。复现只使用本轮生成的合成临时工作区。只新增本报告，未修改实现/测试、未提交。

## 一、必须改

### R1：隔离检查把“文件被忽略”扩大为“父目录也必须被忽略”，并漏检真正的替换临时文件

位置：`ky/timetable_io/operations.py:360`、`:284`、`:369`；类似额外目录要求见 `ky/timetable_io/staging.py:167`、`:177`。

**具体输入**：Git 工作区中主课表为 `data/timetable.yaml`，学校档案是合成数据；`.gitignore` 按文件忽略主课表、备份与临时文件，staging 整目录忽略：

```gitignore
staging/
data/timetable.yaml
data/timetable.previous-*.yaml
data/.timetable*.tmp
```

主课表、候选、备份、替换临时文件均未跟踪且被忽略，`data/` 本身没有忽略。这是规格允许的路径布局，不要求目录里其他项目文件也不能跟踪。

**实测结果**：三个实际文件类别的 `check_isolated_path` 均通过；`apply_staging` 在检查主课表父目录 `data/` 时抛契约错误。CLI 因此退出2，合法新增学期不能应用，主文件不变。

**应有结果**：检查实际写入文件及临时文件，全部安全则应用成功；父目录需要检查解析位置/类型，但不能把它当成必须被 gitignore 忽略的个人文件。相同误拒还可能发生在按文件规则忽略的 staging 子目录。

可复现命令（仓库根运行；全部脚本/数据为合成内容）：

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
@'
import tempfile, subprocess
from pathlib import Path
from tests.contract import test_timetable_io_port as f
from ky.timetable_io import inspect_isolation, check_isolated_path, publish_staging, apply_staging
from ky.models import ContractError
with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp) / "repo"
    ws, target, _ = f._workspace(root)
    subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
    (root / ".gitignore").write_text(
        "staging/\ndata/timetable.yaml\ndata/timetable.previous-*.yaml\n"
        "data/.timetable*.tmp\n", encoding="utf-8")
    isolation = inspect_isolation(root)
    stage, _ = publish_staging(ws, f._staged(f._semester("term-b", "2027-01-04")), isolation)
    paths = [("target", target),
             ("backup", target.with_name("timetable.previous-123456789abc.yaml")),
             ("replace_temp", target.with_name(".timetable.yaml.synthetic.tmp"))]
    for name, path in paths:
        check_isolated_path(isolation, path)
        print(name, "allowed")
    try:
        print("apply", apply_staging(ws, stage, isolation).status)
    except ContractError as error:
        print("apply rejected", Path(error.path).name)
'@ | py -3.12 -B -
```

本轮观察到的结果为 `target allowed`、`backup allowed`、`replace_temp allowed`，随后 `apply rejected data`。

**同一修复必须补齐真实临时路径检查**：目前 apply 直接调用 `replace_bytes`，其 `mkstemp` 生成的主课表替换临时文件从未交给 `check_isolated_path`。检查父目录不能代替上级 §1 明写的“每个临时文件写入前检查”。本轮用 `operations.check_isolated_path` 记录检查路径、用 `atomic.tempfile.mkstemp` 记录实际创建路径，实测：

```text
apply_status=applied
replacement_temporaries=1
replacement_temporary_checked=False
```

现有 `test_apply_staging_guard_and_recover_after_backup_interruption` 的“有一个 .tmp 被检查”断言只证明备份临时文件被检查，而且替换函数被 mock 掉；它不覆盖替换临时文件。修复应保留原子替换方式，通过明确的公开写入接口/检查回调或本模块受检查的临时发布流程完成检查，不 import M13 私有函数。不要只删除父目录限制而继续漏检临时路径。

### R2：M18 的路径缓存变成每次学校加载重建，固定基线读取次数改变

位置：`ky/timetable/calendar.py:247`、`:300`。`load_referenced_schools` 的 `by_path` 是调用内缓存；`timetable_for_workspace` 对每个新 school ID 单独调用它，缓存不能跨学校登记键共享。

**具体输入**：两个不重叠的合成学期，第一引用 `demo`、第二引用 `other`；两个登记键都指向 `data/schools/demo.yaml`，文件内 school_id 为 demo。第二项属于普通登记笔误，应按既有身份错误拒绝。

**实测结果**：旧版与新版都报 `semesters[1].school`；但旧版学校文件读1次，新版读2次。违反任务书明确要求的读取次数不变和 AGENTS.md“同一份数据一次操作只读一次”。不能因为最终仍拒绝就忽略基线变化。

**应有结果**：学校文件读1次，以同一份已解析对象与原始摘要判断两个登记键，保留第二学期的错误路径。仍按学期顺序校验，不能改成预加载全部学校而把后学期的读取错误提前到前学期的节次错误之前。

可复现命令：

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
@'
import tempfile, subprocess, tarfile, io, yaml
from pathlib import Path
from tests.contract import test_timetable_io_port as f
with tempfile.TemporaryDirectory() as tmp:
    temp = Path(tmp)
    ws, target, _ = f._workspace(temp / "fixture")
    registry = yaml.safe_load(ws.source.read_bytes())
    registry["reference"]["timetable_schools"]["other"] = "data/schools/demo.yaml"
    ws.source.write_text(yaml.safe_dump(registry), encoding="utf-8")
    table = yaml.safe_load(target.read_bytes())
    term = f._semester("term-b", "2027-01-04")
    term["school"] = "other"
    table["semesters"].append(term)
    target.write_text(yaml.safe_dump(table), encoding="utf-8")
    archive = subprocess.run(["git", "archive", "4816a14", "ky"],
                             capture_output=True, check=True).stdout
    old = temp / "old"
    old.mkdir()
    with tarfile.open(fileobj=io.BytesIO(archive)) as bundle:
        bundle.extractall(old, filter="data")
    script = """import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from ky.timetable import timetable_for_workspace
from ky.workspace import load_workspace
from ky.models import ContractError
original = Path.read_bytes
reads = []
def counted(path):
    if path.name == 'demo.yaml': reads.append(path.name)
    return original(path)
Path.read_bytes = counted
ws = load_workspace(sys.argv[2])
try: timetable_for_workspace(ws)
except ContractError as error: print('error_path=' + error.path)
print('school_reads=' + str(len(reads)))
"""
    for label, package in [("baseline", old), ("current", Path.cwd())]:
        result = subprocess.run(["py", "-3.12", "-B", "-c", script,
                                 str(package), str(ws.source)], capture_output=True, check=True)
        print(label, result.stdout.decode().strip())
'@ | py -3.12 -B -
```

结果：baseline 为 `error_path=semesters[1].school / school_reads=1`；current 为同路径、`school_reads=2`。

## 二、逐条符合性与不改

| 规格/任务要求 | 评审结果 |
|---|---|
| 三种隔离状态 | A 由两次成功 git 查询确认；B 由向上没有 `.git` 确认；查询失败/OSError 为 C，拒绝写入。与规格一致 |
| 仓库边界而非 workspace 边界 | `check_isolated_path` 使用确认的工作树根；工作区外、仓库内仍检查 ignore/tracked，符合 |
| 每个写入路径含临时文件 | 暂存与备份显式检查；主课表替换临时文件遗漏，且额外目录检查误拒，见 R1 |
| 暂存封闭形状、重复键、hash12 | 根/source 封闭字段、精确版本、摘要、notes类型齐全；哈希用公开 canonical_json_bytes 与 M18 规范学期映射，不含 notes |
| 只写一次发布 | 临时写入并重读后 os.link；已存在只有逐字节相同才成功，不覆盖不同 notes/内容。备份保留原始主文件字节 |
| restage 两种结果 | 同规范哈希返回原文件；变化发布新文件，原文件不动；例外保留；差异基于当前同 label 学期 |
| apply 先校验再判已应用 | 先解析现有/候选、合并、整表校验、学校引用校验，再判同内容。档案缺失不会被“已应用”掩盖 |
| 追加/替换/顺序 | 同 label 替换原位置，新增追加；其余学期对象顺序与 rules 保留；冲突无 replace 拒绝 |
| 备份与中断 | 备份先发布、主文件后原子替换；备份后替换失败主文件不变，重跑复用相同备份；替换成功后重跑已应用不再备份 |
| staging 两步包含检查 | 子目录解析后在 staging 内、文件解析后在子目录内；具名 M29 辅助，无跨模块私有导入 |
| CLI 退出码 | argparse 用法错误3；契约/存储/OSError 2；成功0。状态检查一次传下去，未重算 |

**M18 公开入口范围**：单学期解析不看学校/其他学期；整表解析含 rules、label唯一和学期不重叠；引用校验查 school_id 与全部节次；学校加载只读请求ID；build_calendar 不读文件且验证每个引用；序列化规范日期/时刻/周集合，保留课程/例外对象顺序，空 exceptions 写列表、缺省 cap 省略。已检查的业务范围符合规格，不要求把学校引用规则塞回单学期解析器。

固定基线测试确实使用 `4816a14`，`fixed_source` 检查旧源码身份；`git archive 4816a14 ky` 加到独立子进程 sys.path 首位，旧侧不是旧文件配新版包。正常单学期与一个节次错误场景比较了 day 字段、sources、错误路径及读取计数。这些现有场景通过，但覆盖不到 R2 的共享路径及跨学期错误优先顺序。

## 三、测试核验与缺口

本轮实际运行：

```text
py -3.12 -B -m unittest tests.contract.test_timetable_io_port
Ran 9 tests in 1.291s — OK

py -3.12 -B -m unittest tests.contract.test_timetable_port.TimetablePortTests.test_timetable_for_workspace_matches_fixed_4816a14
Ran 1 test in 1.331s — OK
```

另运行 R1、R2 及替换临时路径记录三个单命令复现。使用禁写字节码环境，未新增测试文件。实现者报告的102项验收结果未重跑，本轮通过数不代表全部验收。全量未跑，按 AGENTS.md 由决策者统一进行。

任务书的大部分列举用例有实质断言：hash12 独立计算；发布冲突保留字节；apply 比较备份原字节、学期标签、rules、新名称；冲突/重叠/备份不同内容不改主文件；已应用/dry-run 不生成备份；中断后复用备份成功。

需随 R1/R2 补回的直接缺口：按文件忽略而父目录可跟踪的布局；主文件替换实际临时路径逐个检查；共享学校路径的旧/新读取计数；前学期节次错误与后学期学校错误的优先顺序。

其他建议补强，非独立阻断：

- 基线 `compare_runs` 返回值未断言成功场景一定有 schedule/sources 且进程退出0；加这些断言，防止以后两侧同时变成相同契约拒绝仍通过。
- CLI 成功 apply 只断言主文件非空和网格标题，并未核对 CLI 写入的新学期；模块测试虽覆盖真实结果，CLI 这条自身仍接近“能跑”。还缺 CLI 退出2的直接用例。
- restage 同哈希目前测试未实际改 notes/缩进/等价周次；改课程用 `edited.yaml`，没证明在旧 hash12 文件名上编辑后原文件仍保留。建议按任务书的人工编辑流程补断言；已保存例外的语义断言可保留。
- “其余学期保持”目前主要断言标签与 rules，没有逐项比较未修改学期的规范映射；公开学校加载、build_calendar 的负面范围也可用现有合成夹具增强。
- 暂存根/source 未知字段、apply 旧文件名对应错误哈希等代码路径可见有检查，但现有测试未直接断言；不要扩大为全链路测试，补必要契约分支即可。

## 四、AGENTS.md / D7 与建议改

已知缺陷逐项：不可覆盖发布遵循 link、普通替换遵循 atomic；同源一次读取除 R2 外正确；分支以类型/退出码区分而非错误文案；未登记与登记无效区分；包含检查两步存在；CLI 参数先 argparse 后装配；固定基线真实且不使用 HEAD；存储不依赖别的 worktree 空目录。新 API 的无效类型校验可在后续契约用例中明确，不声称所有构造的 Python 类型输入都已有防护。

模块分层清楚，M29 通过公开 M18、M19 canonical_json_bytes 和 M13 replace_bytes 交互；未发现新增跨业务模块私有名导入。函数大多按步骤拆分，未见把整个 IO 流程塞进大型函数的必要。M18 内部子文件互用私有辅助属于同一组件，不视为跨模块违规。

建议随修改整理：

1. `calendar.py`、`timetable.py` 模块头仍列旧接口，更新新增公开入口清单。
2. 学校身份异常已有 `ContractError.message`，用它重包装路径，避免 `str(exc).split(': ', 1)` 依赖格式化文案；当前是按异常类型分支，不算“以错误消息判断情况”。
3. M29 的两份 YAML/重复键遍历代码几乎相同，可建立本模块的具名共享辅助；避免未来 staging 与主课表校验口径各自漂移。
4. 已应用 CLI 目前打印两次“已应用”；去掉一次即可，无需改变存储或重开规格。

## 五、个人数据核对

在本包新增/修改的代码、测试、规格与实现报告中，未发现可确认的用户学校标识或真实课表内容；新增测试夹具为合成数据。对已知标识做仅返回文件名的被跟踪代码/测试/规格/报告扫描，未命中；本地补充文件及个人目录也未发现被跟踪文件。

没有读取真实个人文件作全仓逐项比对，因此不作“任何历史泛用课程名都不可能与真实课程重合”的绝对保证。本轮没有需报告的具体泄漏位置，也没有在报告复述个人数据。

## 六、安全登记

**YAML 自引用别名递归**：`staging.py:_walk_duplicates` 与 `operations.py:_check_duplicate_nodes` 没有已访问节点/祖先保护。自引用 YAML 节点可使遍历无限递归，形状校验前出现 RecursionError；现象为静态推断，本轮未执行攻击样本。触发需要提供正常导入不会生成的畸形/篡改输入，按现有威胁模型只登记。可参考 M18 已有祖先集合写法，或复用经过审查的公开 YAML 辅助。

恶意链接、并发插手和短摘要碰撞继续沿用原登记范围，不以这些假设要求本轮额外返工。R1 的正常 Git 忽略布局与 R2 的普通登记笔误属于必须改。
