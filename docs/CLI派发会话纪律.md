# CLI 派发会话纪律

## 默认规则

同一任务、同一代理使用固定的 `-Name`。第一次调用创建会话并把 session id 写入 `logs/dispatch/`；后续调用默认读取该 id 并续会话，只发送本轮新增指令。换任务、上下文已经跑偏或人工确认旧会话不再适用时，才使用 `-NewSession`。

两个封装器都要求指定产物文件。成功以该产物在本次调用中被创建或更新且非空为准，CLI 退出码只作为日志中的诊断信息。Codex 即使完成工作也可能返回非零码，因此不得把 `$LASTEXITCODE -eq 0` 当作唯一成功条件。

## 调用方式

首次调用和默认续会话使用同一条命令；是否存在对应的 session 文件决定实际模式：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\dispatch\codex-session.ps1 `
  -Name round42-codex `
  -PromptFile .\review\rounds\round-42-increment.md `
  -ArtifactPath .\review\rounds\round-42-codex.md

powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\dispatch\claude-session.ps1 `
  -Name round42-claude `
  -PromptFile .\review\rounds\round-42-increment.md `
  -ArtifactPath .\review\rounds\round-42-claude.md
```

换任务或明确放弃旧上下文时强制新开：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\dispatch\codex-session.ps1 `
  -Name round42-codex -NewSession `
  -PromptFile .\review\rounds\round-42-new-task.md `
  -ArtifactPath .\review\rounds\round-42-codex.md
```

如需指定模型，使用 `-Model`。需要联网搜索公开资料的任务（例如找大纲，第 256 / 258 轮）给 Codex 加 `-WebSearch`（传 `-c web_search="live"`），默认关闭；
任务书须写明只取哪类页面、下载走 `tools/fetch_evidence.py`、报告不贴原文（`交接文档.md` §5.0 A）。只有已经完成权限评估时，才可显式传入 Codex 的 `-DangerouslyBypassApprovalsAndSandbox` 或 Claude 的 `-DangerouslySkipPermissions`；脚本默认不绕过权限。

## 四条不可违反的纪律

1. **默认续会话。** 固定 `-Name` 就会固定到 `logs/dispatch/codex-<name>.session` 或 `claude-<name>.session`。续会话失败会明确报错并提示 `-NewSession`，脚本不会退化为新会话。
2. **长中文提示词只走文件和 stdin。** 脚本使用 `[System.IO.File]::ReadAllText(..., [System.Text.Encoding]::UTF8)` 读取，把 PowerShell 原生进程管道的 `$OutputEncoding` 显式设为无 BOM UTF-8，然后通过 stdin 传给 CLI。不得把长提示词拼进命令行；这会造成命令截断或中文丢失。日志记录字符数及首尾片段，供核对传输边界。
3. **原始输出只用 `*>` 捕获。** 每次调用先把所有输出流写入原始日志，再合并进最终日志。不得使用 `2>&1 | Tee-Object | Out-Null`；该管线曾在提示词回显后提前终止子进程。
4. **判产物，不判退出码。** 调用前后比较产物的 SHA-256、修改时间和长度；只有产物被创建或更新且非空才算成功。退出码、请求 id 和 CLI 返回 id 全部保留在日志中用于诊断。

## 日志、状态与迁移

每次调用生成 `logs/dispatch/<name>-<cli>-<timestamp>.log`，并保留同时间戳的 `.raw.log`。最终日志包含模式、提示词路径和字符数、首尾片段、产物检查、session id、CLI 退出码、可复制的原始命令及 CLI 完整输出；raw 日志保留 `*>` 捕获的原始输出流，避免 Windows 进程刚退出时清理仍被占用的文件。

`logs/` 已被 `.gitignore` 忽略，因此会话 id 不会提交。这对本机日常使用是合适的：session id 属于机器本地的临时运行状态，提交它既不能保证另一台机器拥有对应的 CLI 会话存档，也会把无效状态传播给协作者。代价是换机器、清理本机 CLI 会话库或删除 `logs/` 后无法续会话。处置是保留任务书和增量记录作为可审计材料，在新机器上使用 `-NewSession` 建立新会话；不要把 `.session` 文件复制或提交后宣称上下文已迁移。

## 失败处理

若提示会话不存在、过期、id 不一致或产物未更新，先查看对应日志。确认需要放弃旧上下文后再加 `-NewSession`。不得删除 session 文件并无说明地重跑，也不得把失败的续会话包装成一次成功的新会话。

## 验证范围纪律（2026-09-25 追加）

实测问题：第 43–47 轮里，任务书把"全量测试只允许基线失败"写成了每个工作包的验收条件，
覆盖了 Codex 全局规则"能用最小范围验证就不跑全量"。结果 gpt-6-luna 每包跑 1–3 次全量（WP-B 里改一行断言就重跑一次），
决策者提交前又跑一次，每次约 100 秒，全是重复。

规则（常驻于仓库根 `AGENTS.md`，Codex 自动加载）：

1. 任务书的"验收"只点名**受影响的测试模块**，不再写"全量"。
2. 实现者只跑点名模块；改了东西只重跑受影响模块；不写任务书没要求的冒烟/全链路测试。
3. 评审者不跑全量。
4. **全量只由决策者在提交前跑一次**，结果写进提交信息。
5. 确有必要让代理跑全量时，任务书必须逐字写"本轮例外：需要全量测试"并说明理由。

## 证据最小充分（2026-10-08 追加）

实测问题：`gpt-6.1-sol` 在评审里倾向给每条结论配哈希 / 摘要绑定、字节对照链和跨来源哈希交叉验证，
把"证据链缺少密码学绑定"写成必须改。对个人单用户本机系统，这些门槛与"日常会不会出问题"无关，只让报告变长。

规则（常驻于 `AGENTS.md`「证据最小充分」，Codex 自动加载）：

1. 复现一条结论给一个能跑的输入或 `文件:行` 即可，每项最多一个探针。
2. 不要求 SHA-256 绑定、字节级对照链、跨来源哈希交叉验证；这类诉求只能进"建议"或"安全登记"。
3. "输出逐字节不变"只出现在迁移 / 重构任务书里（`AGENTS.md` 第 11–13 条），不是评审的通用要求。
4. 派发评审任务书时在纪律一节写明这一条，避免每轮重复。
