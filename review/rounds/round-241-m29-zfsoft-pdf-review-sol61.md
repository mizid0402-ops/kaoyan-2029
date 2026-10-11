# 第 241 轮：WP-IO3 正方 PDF 适配器实现评审

结论：**FAIL**。区域、锚点与第232轮的结构覆盖修正基本落实；但周次按合法子串提取会静默改变语义，相邻页名称续写被误拒，adapter 白名单改动引入类型错误 traceback。必须改见 R1–R3。

范围为本轮 PDF 新模块、测试、CLI 和 staging 白名单改动，核对对应规格、第238轮任务书/实现报告与此前审阅项。未评审其他工作包或 worktree，未联网、未读真实 PDF 或仓库外既有文件。测试与复现均用合成输入；只新增本报告，未修改实现/测试、未提交。决策者的真实样本逐门一致是任务书提供的验收证据，本轮不作独立确认。

## 一、必须改

### R1：周次提取截取合法子串，再校验截取结果，能静默删除资格条件

位置：`ky/timetable_io/zfsoft_pdf.py:383`（`_WEEK_CANDIDATE.finditer` 与候选去重），调用位置`:414`附近。

**合成片段**：一页 `Page(1, 2000, 1000, 90)`；星期一至星期日为 x=1000、y=400/450/…/700、字号12，index1–7。另有：

```text
Fragment(1, 1100, 395, 9, Synthetic, 20)
Fragment(1, 1200, 395, 8, (1-2节)1-16周(双周)/Teacher/学分:3, 21)
```

页面、区域、d=5与详情结构均成立。`(双周)` 不在支持的 M18 周次语法中；按“版式/语法不支持就拒绝”应退出2，不能猜它的含义。

**实测结果**：解析输出 `weeks=1-16周`；再交 `maximum_written_week` 和 `semester_from_mapping` 仍成功。输入的限定文字被截掉，课程变成每周出现。即使 `(双周)` 是另一种导出写法，本模板也应明确拒绝，而不是改成全周。

同一合成输入的其他排课段也实测接受：

| 原排课段 | 实际输出 weeks | 应有结果 |
|---|---|---|
| `1-16周(双周)` | `1-16周` | 不支持的限定语法，拒绝 |
| `1-16周(单),17周(奇)` | `1-16周(单),17周` | 不支持的限定语法，拒绝 |
| `1-4周 1-4周` | `1-4周` | 出现两次候选，按实现者选择应拒绝 |

第三例还说明 `list(dict.fromkeys(candidates))` 把“两次相同候选”变成“一种候选”，不符合“恰有一个候选”的陈述。

**应有结果/修法方向**：明确已支持的排课段包裹文字，例如星期与时刻前缀；取出完整的周次字段并完整校验，不能从含未知后缀的字符串里搜出一段合法前缀。候选计数按出现的 span，不按字符串去重。未知限定、残留周次语法、多个候选均拒绝，原文不能先裁掉再交 M18。

复现命令（ASCII 脚本，全部合成输入）：

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
@'
from tests.contract.test_timetable_io_zfsoft_pdf import _pages, _labels, _course_fragments
from ky.timetable_io.zfsoft_pdf import parse_zfsoft_fragments, maximum_written_week
from ky.timetable import semester_from_mapping
from ky.models import ContractError
expressions = ["1-16\u5468(\u53cc\u5468)", "1-4\u5468 1-4\u5468",
               "1-16\u5468(\u5355),17\u5468(\u5947)"]
for expression in expressions:
    detail = "(1-2\u8282)" + expression + "/Teacher/\u5b66\u5206:3"
    fragments = [*_labels(), *_course_fragments(name="Synthetic", detail=detail)]
    try:
        courses = parse_zfsoft_fragments(_pages(), fragments)
        raw = dict(label="synthetic", school="sample", week1_monday="2025-09-01",
                   weeks=maximum_written_week(courses), courses=courses, exceptions=[])
        semester_from_mapping(raw, "semester")
        print("input=" + ascii(expression), "accepted=" + ascii(courses[0]["weeks"]))
    except ContractError as error:
        print("rejected=" + error.path)
'@ | py -3.12 -B -
```

这不是要求支持新周次方言；只是要求普通导出差异能被拒绝。静默错收无法靠暂存哈希或 M18 后续校验补救，因为两者收到的已经是错误的合法周次。

### R2：相邻页只有名称的未完成记录不能继续名称，违反已钉住的续接口径

位置：`zfsoft_pdf.py:460`。有 pending 时无条件要求下一页首片段为详情字号8；没有区分“名称尚未写完”和“详情尚未写完”。

**合成序列**：两页尺寸/旋转相同，第1页标签同 R1。

```text
Fragment(1, 1100, 395, 9, Course, 20)
Fragment(2, 1100, 395, 9, Name, 1)
Fragment(2, 1200, 395, 8, (1-2节)周一08:00-09:30 1-16周(单)/Teacher/学分:3, 2)
```

**实测结果**：`page=2,x=1100,y=395,index=1,stage=continuation` 契约拒绝。

**应有结果**：得到一门 `CourseName`、星期一、第1–2节、`1-16周(单)` 的课程。§3 名称片段可以延续；第238轮任务书还明确所有未完成记录“包括只有名称、尚无详情的”只能续到相邻页，没有把合法相邻页名称续写排除。要保留隔页/空页拒绝，但名称阶段允许9号字继续名称，详情阶段才要求详情续写。

可复现：

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
@'
from tests.contract.test_timetable_io_zfsoft_pdf import _pages, _labels, _DETAIL
from ky.timetable_io.zfsoft_pdf import Fragment, parse_zfsoft_fragments
from ky.models import ContractError
fragments = [*_labels(), Fragment(1,1100,395,9,"Course",20),
             Fragment(2,1100,395,9,"Name",1), Fragment(2,1200,395,8,_DETAIL,2)]
try:
    print(parse_zfsoft_fragments(_pages(2), fragments))
except ContractError as error:
    print(error.path)
'@ | py -3.12 -B -
```

### R3：adapter 白名单使用集合成员检查前没校验类型，手工暂存误填列表会 traceback

位置：`ky/timetable_io/staging.py:98`。旧实现字符串比较能将这种值作为非法 adapter 拒绝；新实现对列表/映射做集合成员检查，先抛 TypeError。

**具体输入**：合法合成暂存文件，把 `source.adapter` 误填成 `[zfsoft_pdf]`，其余字段保持合法；这是可编辑 YAML 的普通字段类型错误。

**实测结果**：`parse_staging_bytes` 抛 `TypeError`。CLI 的契约/I/O 捕获不含此异常，restage/apply 会出现 traceback，而不是退出2并指向 source.adapter。

**应有结果**：先确认 adapter 为字符串，再检查枚举；失败抛带 `source.adapter` 路径的 ContractError。ics 与 zfsoft_pdf 两个合法值继续接受。

可复现：

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
@'
import yaml
from pathlib import Path
from tests.contract.test_timetable_io_port import _staged
from ky.timetable_io import staged_to_bytes, parse_staging_bytes
raw = yaml.safe_load(staged_to_bytes(_staged()))
raw["source"]["adapter"] = ["zfsoft_pdf"]
try:
    parse_staging_bytes(yaml.safe_dump(raw).encode("utf-8"), Path("synthetic.yaml"))
except Exception as error:
    print(type(error).__name__)
'@ | py -3.12 -B -
```

## 二、实现者自选口径的裁定

要求排课段有一个带“周”或奇偶标记的候选，作为已知模板的保守支持范围，**可以接受**。测试里的星期/时刻数字不能被自动当作周次，零候选或多个候选拒绝也合理；不必为了支持裸数字推断任意周次。

但这种选择必须写进模板支持范围，并按完整语法执行。R1 的未知后缀被截断、重复 span 被去重是错误执行，不是合理的保守限制。不能以“最后 M18 会校验”为由保留合法子串搜索。

## 三、已符合项与不改

- 页面冻结类型、有限坐标/字号、内部换行拒绝；星期文字定序号，第一页恰七个、后页标签拒绝；共线、递增、等距及页尺寸/旋转一致检查均存在。
- Lx 取 x 极值中点，S 取相邻 y 差均值；正文9号有效差值极差≤1.0，d取中点，空集合拒绝；范围外正文9号仍经过分类，没有先静默丢弃。
- 页眉/正文互斥，页眉8/9落锚点拒绝，正文精确12号清单及前缀白名单不得落锚点。第232轮页眉拆分标记反例在本轮单命令复现中明确于 `stage=structure` 拒绝，N1 的原路径已关闭。
- 每条完整详情连接后数结构标记，恰一条；名称含完整节次标记拒绝。字段尾部不支持学分数字分页截断是已声明限制，不算返工项。
- 缺省周数取原写法上界，显式 N 交 M18 先查越界再过滤；校验候选学期本身，学校引用通过公开入口，不复制学校/周次业务校验。
- 导入使用已修正 IO1 的公开 `publish_staging`，adapter 扩展已解决实现者报告里的“只允许ics”集成阻塞；保留规范哈希、notes、只写一次及隔离路径协议。
- CLI 源字节一次读取，摘要与提取复用；隔离状态一次检查传下去。合成集成探针固定状态B、mock片段提取后，实际运行 CLI 与发布：退出0、暂存 adapter=zfsoft_pdf、PDF读1次、隔离检查1次。它验证接缝，不证明真实 PDF 提取或 Git 状态A。
- 错误集中为位置/阶段消息；PDF提取与候选校验异常包装不回显片段文字；原输入文件名不写入暂存 source。
- 每日分钟预览按本轮“已知、不在范围”保留，不把它算必须改。真实文件验收仅采用决策者提供的逐门一致结论，不再次读取个人文件。

## 四、测试与 D7 建议

本轮只运行相关模块，先在测试进程移除 `KY_TIMETABLE_PDF`，确保不触发个人文件读取：

```text
tests.contract.test_timetable_io_zfsoft_pdf
Ran 11 tests in 0.002s
OK (skipped=1)
```

另运行 R1–R3、页眉拆分结构拒绝和上述合成 CLI 接缝单命令。未跑全量；实现者旧 worktree 的20项结果未作为 master 验收结果。`git diff --check` 未报告空白错误。

正常映射测试逐字段比较课程名、星期、节次、周次；类型标记与随机打乱输入测试也比较完整结果，属于实质断言。当前结果排序、极值聚合与按 x 读取不会依赖合法片段输入的枚举顺序。错误输入首先报告哪个片段可能随顺序变化，这不等于合法结果不确定。

需随必须改补对应回归：完整候选未知后缀/相同候选重复；相邻页名称续写以及隔页对照；adapter 列表/映射类型拒绝。其他测试建议：

1. `test_record_structure_incomplete_or_orphaned_rows_reject` 把详情移到 y=695，而名称仍在395，首先破坏星期归属，未证明残缺详情/多标记真的到达记录核对。保留两片段同锚点，并断言错误阶段。
2. 页眉拆分用例的名称/详情正落课程锚点，会先被分类拒绝；拆分处也没有真正切在“节”和右括号之间。应采用第232轮 off-anchor 片段并增加单片段对照，证明结构覆盖规则，而非仅证明有其他规则会报错。
3. 名为“missing_anchor_differences”的用例只制造同 x 冲突；补实际没有有效9号差值的输入。测试里一组锚点异常构造重复出现，可合并。
4. 增加合成公开导入/CLI 接缝断言，核对发布内容、adapter/源摘要、读取次数与隔离次数；本机个人文件测试继续只由决策者选择执行。

模块头明确 M29、规格与公开接口；模板常量不含用户学校、科目或年份分支；解析、提取、候选校验与发布分步清楚，没有新增跨模块私有入口导入。建议删除未用的 `_Location` 和 `staging_hash12` 引用；纯函数输入校验补齐 Fragment.page/text 等字段类型，防止直接 API 调用的 AttributeError，但不扩成任意 PDF 防护框架。

修复可局限于周次字段边界、名称阶段续接及 adapter 类型检查，无需重写区域/锚点算法或再造暂存存储。

## 五、安全登记

本轮没有新增需登记的攻击项。普通导出使用不同限定写法、课程名跨页、手工暂存字段类型错误属于日常问题。恶意超大/复杂 PDF、恶意模板参数、并发替换及内部文件篡改继续沿用原登记范围，不为本工作包新增防攻击返工。
