# 第 212 轮：包 B 最后一处复审（sol61-main）

结论：**PASS，包 B 可提交**。第 210 轮 M1 已关闭；第 204、206、208 轮全部必须改项
沿用第 210 轮的关闭结论。包 B 的评审阻断项全部关闭，提交前全量由决策者执行。

本轮只复核 `tests/contract/test_workspace.py` 相对第 210 轮所见版本的过滤修改。
已读 211 任务书与实现报告，沿用 code-review-gate、AGENTS.md；其余已确认部分不重审。
没有修改实现或测试、没有提交；本报告是本轮唯一仓库写入。

## 必须改

无。

## 建议改

无。

## 不改

`tests.contract.test_workspace.WorkspaceContractTests.test_single_error_variant_table`
已将前缀 / lambda 过滤改为显式 retired 名单，只按集合成员关系过滤。
三条已移回 cases，仍使用生成器的原 `expected_success=False`，进入
`assertRaises(ContractError)`，没有修改输入、抄录当前结果或放过其他异常。

| 恢复的原变体 | 正常正式表执行 | 临时源码变异后 |
|---|---|---|
| double-error-schema-before-supplementary | 通过，当前 ContractError | ContractError not raised，失败 |
| double-error-schema-before-products | 通过，当前 ContractError | ContractError not raised，失败 |
| double-error-schema-before-settings | 通过，当前 ContractError | ContractError not raised，失败 |

从真实 unittest.addSubTest 回调记录执行集合，确认三条均执行且无 skip。
生成器本次实际产出 **55 条，正式断言 36 条，退役 19 条**，与实现报告一致；
没有把数量写死进正式测试。

## 退役名单逐条核对

没有凭名字判断是否多错误。探针以当前合法 seed 为底稿，对每个退役 document
计算实际结构差异，确认有两处编辑；然后把每处编辑分别单独应用到合法底稿，
写入系统临时注册表并调用当前 load_workspace。合法底稿先确认成功，
以下每行的两部分均分别抛 ContractError，表中为实测 path。

| 显式退役项 | 第一处独立错误 | 第二处独立错误 |
|---|---|---|
| double-error-schema-before-schema_version | schema_version 缺失 | subjects=[] |
| double-error-schema-before-subjects | schema_version='2' | subjects 缺失 |
| double-error-schema-before-reference | schema_version='2' | reference 缺失 |
| double-error-schema-before-materials | schema_version='2' | materials 缺失 |
| double-error-schema-before-state | schema_version='2' | state 缺失 |
| double-error-schema-before-staging | schema_version='2' | staging 缺失 |
| double-error-schema-before-projection | schema_version='2' | projection 缺失 |
| subject-before-reference | subjects[首个登记科目]='profile' | reference.topic_weights='../bad' |
| knowledge-before-syllabus | reference.knowledge_trees=[] | reference.syllabus_versions=[] |
| syllabus-before-exam-indexes | reference.syllabus_versions=[] | reference.exam_indexes=[] |
| exam-indexes-before-paper-shapes | reference.exam_indexes=[] | reference.paper_shapes=[] |
| paper-shapes-before-weight-path | reference.paper_shapes=[] | reference.topic_weights='../bad' |
| reference-before-supplementary | reference.topic_weights='../bad' | supplementary=[] |
| supplementary-before-materials | supplementary=[] | materials=[] |
| materials-before-products | materials=[] | products=[] |
| products-before-settings | products=[] | settings=[] |
| settings-before-state | settings=[] | state=[] |
| state-before-staging | state=[] | staging='../bad' |
| staging-before-projection | staging='../bad' | projection='../bad' |

列表中的 [] / 字符串是实际替换值，不是仅删可选块。
三项可选块缺失已不在名单中；19 项均确实包含两个独立拒绝条件，退役成立。

## 独立源码变异与最小验证

系统临时脚本：`C:\Users\Lenovo\AppData\Local\Temp\round212_probe.py`。

```powershell
py -3.12 -B $env:TEMP\round212_probe.py
```

正常验证只运行正式 `test_single_error_variant_table`：**1 test，0.239s，OK，无 skip**。
另对 19 条的两部分分别调用当前 load_workspace，验证拒绝类别和路径，未跑模块全集。

变异只复制 ky 到系统临时 checkout，在副本 workspace.py 的 `_parse_document` 中，
读取 version 后增加 `if version == "2": version = 2`，其他校验保留。
使用未修改的正式表，runner 断言 ky.workspace.__file__ 来自该临时副本。
没有在测试侧 patch 被测函数，也没有改仓库源码。

结果：**1 test，4 个失败子项，0.248s**。除既有 schema-version-type 外，恢复的三条
全部在原 assertRaises 处报 `ContractError not raised`；失败原因不是导入错误或前置错误。

证据目录：`C:\Users\Lenovo\AppData\Local\Temp\round212-sol61-8i7enpe9`，包含
临时源码、runner、正常表输出及变异 stdout / stderr。19 条独立错误核对的路径由脚本输出。

全量未跑，按 AGENTS.md 由决策者提交前统一跑。本轮无新增安全登记。
