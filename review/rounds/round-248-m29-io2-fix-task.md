# 第 248 轮任务书：WP-IO2 返工（gpt-6-luna，续 luna-c，**主仓库工作区**）

主仓库正处在 `git merge --no-ff --no-commit wip/io2` 的未提交状态，里面是你的 IO2 与决策者的整合（`base_resolver`、逐日基数、`import-pdf` 接公用预览、CLI 冲突解决）。
sol 第 246 轮评审 FAIL：`review/rounds/round-246-m29-io2-review-sol61.md`。决策者已核实 R1–R3 都成立。**不要执行任何 git 命令**（合并由决策者收尾）。

## 要改的

1. **R1**：一次导入只加载一次学校档案。`preview_lines` 增加可选参数接收已加载的学校（例如 `schools: Mapping[str, LoadedSchool] | None = None`），
   `import_ics` 与 `import_zfsoft_pdf` 把自己已加载的对象传进去；独立调用预览时才自行加载。不复制网格逻辑。
2. **R2**：按规格 §4 顺序，先按 UID 分组并剔除不导入的主事件（取消、全天、无结束时间，及其覆盖事件一并进 notes），**然后**只对仍参与导入的事件检查时区；
   检查范围包括 `DTSTART`、`DTEND`、`RECURRENCE-ID` 与 **`EXDATE` 的每个值**。未知 `TZID` 违约；有效 `EXDATE` 仍在原始时间域精确匹配。
3. **R3**：节次对回失败**全部收集**（至少每处的 UID 与字段、日期、时刻）后一次性违约，退出 2，不发布暂存。
4. 建议改一并做：
   - 补测试：三个独立逐次事件合并为一门课；孤立覆盖、`RANGE=THISANDFUTURE`、同实例重复覆盖、`EXDATE` 与覆盖冲突各一例拒绝；空导入结果不发布；有效 `TZID` 输入；
     导出里 `TRANSP` / `CATEGORIES` / 浮动时间的断言；重复导入第二次暂存字节不变且不重新发布；公用预览跨路线阶段的每日分钟与路线只读一次；R1–R3 各一例。
   - 公用网格保留学校档案 `unconfirmed` 节次的 `*` 标记（原 PDF 网格有，统一后丢了）。
   - `preview.py` 模块头补 `base_resolver`、`config` 参数加类型；删 `ics_import.py` 未使用的 `school_id = None`；`ics_export._publish` 的重复 `mkdir` 合并并放进转契约错误的 `try` 内。
5. 安全登记那条（混用浮动 / UTC 起止导致 `TypeError`）便宜的话一并修：起止时间域不一致 → 带 UID 与字段的契约错误。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.contract.test_timetable_io_port tests.contract.test_timetable_io_zfsoft_pdf tests.contract.test_timetable_port tests.test_cli
```

报告追加到 `review/rounds/round-237-m29-io2-luna.md` 末尾一节"第 248 轮返工"：逐条做法、测试输出原文、"全量：未跑"。报告与测试不含个人数据。
