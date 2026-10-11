# 第 289 轮：最终大检查的 11 条必须改——独立复验（gpt-6.1-sol，窗口 sol61-recheck，新会话）

你是独立评审者。最终大检查 A / B / C 三包判 FAIL 共 11 条必须改，实现者已全部修完并提交。
本轮**只做一件事**：确认这 11 条是不是真的修好了，以及修复有没有引入新的日常问题。

## 先读

1. `AGENTS.md`（验证范围、严重度与威胁模型、**证据最小充分**、已知缺陷清单）。
2. 三份原报告：`review/rounds/round-281-final-a-sol61.md`、`round-282-final-b-sol61.md`、`round-283-final-c-sol61.md`。
3. 五个修复报告：`round-284-ics-duration-luna.md`、`round-285-charts-guard-luna.md`、`round-286-qb-fixes-luna.md`、
   `round-287-today-fixes-luna.md`、`round-288-web-pending-luna.md`。
4. 五个修复提交：`0ad2b53`（charts）、`623b22d`（ICS）、`2d9bd23`（题库 + 停用提示 + 基线例外）、
   `3d28c6c`（web pending）、`b14bdf5`（M33 来源一次读取等）。`git show <hash>` 看改动。

## 逐条核对（每条最多 1 个探针）

- **A-M1** 坏 `DURATION` 的 ics：公开入口抛 `ContractError`（带 `UID <uid>.DURATION`）、CLI 退出 **2**、不发布暂存文件。
- **B-M1** `ky/charts/data.py` 三个端口：非法 `None` 抛带参数路径的 `ContractError`；**合法输入输出不变**。
- **B-M2** 停用提示行现在能被执行环境解析（PowerShell 里 `<` 曾是重定向运算符）。
- **B-M4** 题库读端：**只**跳过写入器自己的临时名（合法题号 + 同知识点目录 + `tempfile` 的 8 位随机后缀 + `.tmp`，
  随机字符集含下划线）；`manual-notes.txt`、别的知识点的临时名等**仍然** fail-closed。
- **B-M5** `append_question` 对同一份题库只解析一次。
- **B-M6** dry-run 与正式提交共用入库预检、结论一致、dry-run 不写库。
- **B-M3** `progressing` 且自己的改编题全被停用时：给出"先生成"、注明全停用、带生成命令。
- **C-M1** M33：装配一次读取并贯穿计算与记录——请自己数一遍 `Path.open` 读模式（索引 / 权重 / manifest / 每个分片 / 树
  都应各 1 次），并确认公开映射（`schema_version: 1`）与固定基线 `60a4fd2` 的字节关系没有变化。
- **C-M2** 冻结发布后的清理失败仍报 `freeze_written`；发布前的失败仍抛出；不靠错误文字判断阶段。
- **C-M3** pending 页同时显示已存结果与补推进提示；`None` 仍显示"未填写"、`0` 仍显示"0 分钟"。
- **C-M4** `ky/today/port.py` 模块头列出四个公开接口。

## 还要额外确认两件事

1. **新增端口是加法**：`load_check_question_sources` / `candidate_check_questions_loaded`（M24）、
   `load_pacing_report_state`（M28）、`preflight_review_queue` / `advance_review_queue` 的 `source_state` 参数（M13）、
   `ReviewQueueStateSources` 新增字段——旧调用方（`ky/charts`、`ky/question_bank`、CLI、测试夹具）
   是否仍按原签名工作；四份规格是否同步。
2. **固定基线例外只有两条**：`contracts/today.md` §6 现在只允许（a）`event_written` 失败分支多出的恢复命令行、
   （b）停用提示行的原因占位符带引号。请确认测试确实**只**放过这两处，其余字节仍逐字节比对。

## 输出

写 `review/rounds/round-289-recheck-sol61.md`，≤ 80 行：

1. 结论 **PASS / FAIL**（只有发现"必须改"才 FAIL）。
2. 11 条逐条：已修好（附一条探针结果）/ 没修好（附可复现输入）/ 无法核实（说明缺什么）。
3. 上面两件额外确认的结论。
4. **必须改**（若有，附复现；每项 1 个探针为限）。
5. **建议改**（一行一条）。
6. **安全登记**（若有新现象；沿用既有登记就写"无新增"）。
7. **最坏情况**。

## 纪律

- 只创建你这一份报告；不改实现 / 测试 / 规格 / 文档，不提交，不联网。
- **不跑全量**（决策者已跑：`Ran 1145 tests in 415.535s, OK (skipped=7)`）；复现只跑点名模块或单条命令。
- **证据最小充分**：一条结论一个能跑的输入或 `文件:行`，不要哈希绑定、字节对照链或跨来源交叉验证。
- 不读 gitignore 的个人数据；合成输入放系统临时目录；`PYTHONDONTWRITEBYTECODE=1`。
