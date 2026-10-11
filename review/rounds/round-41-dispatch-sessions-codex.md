# Round 41：CLI 持久会话派发验收报告

## 结论

`tools/dispatch/codex-session.ps1` 与 `tools/dispatch/claude-session.ps1` 均已在本机真实 CLI 上通过首次建会话、同 id 续会话、`-NewSession` 强制换 id、长中文首尾传输和无效 id 不降级测试。8 条完成标准通过 8 条。

测试环境：Windows PowerShell 5.1；Codex CLI `0.154.0`，测试模型 `gpt-5.6-luna`；Claude Code `2.1.269`，测试模型 `claude-haiku-4-5`（命令使用别名 `haiku`）。模型选择只用于压低机制测试成本，不是对两个模型能力的比较。

## 用法

第一次调用时没有对应 session 文件，脚本新建会话；相同 `-Name` 的后续调用自动读取 session id 并续会话，只需把本轮增量提示词放进新的 UTF-8 文件。当前 PowerShell 执行策略会阻止直接运行本地 `.ps1`，因此本机验证使用：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\dispatch\codex-session.ps1 `
  -Name round42-codex `
  -PromptFile .\review\rounds\round-42-increment.md `
  -ArtifactPath .\review\rounds\round-42-codex.md `
  -WorkingDirectory .

powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\dispatch\claude-session.ps1 `
  -Name round42-claude `
  -PromptFile .\review\rounds\round-42-increment.md `
  -ArtifactPath .\review\rounds\round-42-claude.md `
  -WorkingDirectory .
```

换任务或明确放弃旧上下文时添加 `-NewSession`。脚本只有在指定产物于本轮被创建或更新且非空、CLI 返回的 session id 可提取并与预期一致后，才原子更新 `logs/dispatch/<cli>-<name>.session`。失败的新会话不会覆盖原 session 文件。

每次调用生成带时间戳的最终日志和 `.raw.log`。最终日志记录模式、提示词字符数与首尾、产物检查、请求/观察到的 id、CLI 退出码、可复制原始命令和完整 CLI 输出。

## 省 token 对照证据

实验方法：先用长中文背景创建会话并给出暗号“海盐-417”；实验组续该会话，只发送增量提示词，要求从上下文恢复暗号；对照组用 `-NewSession`，发送旧方式所需的完整背景，再原样附加同一增量任务。两组均实际生成 `RESUME_OK 海盐-417`。

| CLI | 续会话增量字符 | 新开会话字符 | 少发送字符 | 比例 |
|---|---:|---:|---:|---:|
| Codex | 119 | 2,115 | 1,996 | 94.37% |
| Claude | 120 | 2,116 | 1,996 | 94.33% |

字符数是用户提示词代理指标，不是真实 token 数。两个 CLI 本次也打印了 usage，原始数值如下：

| CLI / 组别 | input | cached/cache read | cache create | output | reasoning | cost |
|---|---:|---:|---:|---:|---:|---:|
| Codex 续会话 | 146,711 | 129,536 | 0 | 1,158 | 414 | 未打印 |
| Codex 新开对照 | 121,359 | 91,904 | 0 | 915 | 305 | 未打印 |
| Claude 续会话 | 17 | 55,997 | 1,842 | 351 | 未单列 | $0.0110557 |
| Claude 新开对照 | 32 | 102,116 | 8,003 | 1,138 | 未单列 | $0.0349396 |

这些 usage 不能被简化成“续会话总 input 一定更少”。Codex 续会话保留历史后，报告的总 input 反而比新开多 25,352（20.89%）；但按 `input - cached_input` 派生的未缓存输入为 17,175 对 29,455，少 12,280（41.69%）。Claude 三类输入相加为 57,856 对 110,151，少 52,295（47.48%），本轮报告成本低 `$0.0238839`（68.36%）。输出 token 还受代理采取的工具步骤影响；例如 Codex 续会话输出反而多 243。因此最稳固的结论是：封装器消除了重复发送的 1,996 个提示词字符并复用了同一会话；本次 Claude 成本和两者未缓存输入也下降，但不能据单次测试保证所有任务的总 token 都下降。

证据集中保存在 `logs/dispatch/round41-evidence-summary.json`、`round41-proof-*.log` 与 `round41-proof-*.raw.log`。`logs/` 被忽略，这些是本机运行证据，不作为版本化交付物。

## 四个坑的防护

1. **续会话而非每轮重开**：按 CLI 与 `-Name` 分别保存 id；Codex 使用 `exec resume <id> -`，Claude 使用 `--resume <id>`。只有显式 `-NewSession` 才换 id。续会话失败时直接抛错，绝不回退到新会话。
2. **长中文经文件和 stdin**：两个脚本均使用 `[System.IO.File]::ReadAllText(path, [System.Text.Encoding]::UTF8)`，并把 Windows PowerShell 5.1 的 `$OutputEncoding` 显式设为无 BOM UTF-8，再经 stdin 送入 CLI。提示词没有拼进命令行。
3. **使用 `*>`**：原生 CLI 的全部输出用 `*>` 写 `.raw.log`，没有 `2>&1 | Tee-Object | Out-Null`。PowerShell 5.1 会把原生 stderr 包装成 `NativeCommandError`，脚本只在原生调用范围把错误偏好设为 `Continue`，避免 stderr 绕过产物检查；调用后立即恢复严格模式。
4. **判产物而非退出码**：调用前后比较产物存在性、非空长度、SHA-256 和修改时间。`$LASTEXITCODE` 只进日志。产物未变化时即使退出码为 0 也失败；产物已变化时仍必须取得并核对 session id。

## 8 条标准的实际输出

| # | 结果 | 实测证据 |
|---:|---|---|
| 1 | PASS | Codex 首次 id `01a0aa28-666a-75d3-b2cd-81a9e3b03e6a`；Claude 首次 id `2aa1f227-07ea-457c-99b2-d7a98fdc7b98`。对应 session 文件和非空首次产物均生成。 |
| 2 | PASS | 第二次 Codex 仍为 `01a0aa28-666a-75d3-b2cd-81a9e3b03e6a`；第二次 Claude 仍为 `2aa1f227-07ea-457c-99b2-d7a98fdc7b98`。两者增量产物均为 `RESUME_OK 海盐-417`，证明不只是命令形式上使用 resume，也取回了上轮上下文。 |
| 3 | PASS | Codex `-NewSession` 得到 `01a0aa2d-cb47-7123-b41f-2100bb3344c2`；Claude 得到 `ddae8046-3dc2-4323-bf63-d66c4acb0950`，均不同于旧 id。 |
| 4 | PASS | Codex 首次提示 2,018 字符、Claude 2,019 字符；日志首部是 `PROMPT_HEAD_长中文开始_甲`，尾部是 `PROMPT_TAIL_长中文结束_乙`。两个首次产物均精确包含 `BEGIN_OK 海盐-417` 与 `END_OK 长中文结尾已收到`；UTF-8 字节核对通过。 |
| 5 | PASS | 对随机不存在 id，Codex 原始错误为 `no rollout found for thread id`，Claude 为 `No conversation found with session ID`；两个最终日志均为 `mode=resume`、`artifact_changed=False`、`cli_exit_code=1`，两个无效续会话产物均不存在，脚本报错明确提示 `-NewSession`。 |
| 6 | PASS | 提示词字符代理：Codex 少 1,996（94.37%），Claude 少 1,996（94.33%）；同时如实记录 CLI usage 与相反方向的 Codex 总 input。 |
| 7 | PASS | `docs/CLI派发会话纪律.md` 存在，写明默认续会话、UTF-8 文件管道、`*>`、产物判成功，以及本地 session 状态处置。 |
| 8 | PASS | `py -3.12 -m unittest discover -s tests -q`：`Ran 436 tests in 116.302s`，`OK`。 |

## `logs/` 被忽略是否是问题

这不是版本库缺陷，而是有意的本地状态边界。session id 只有在同一台机器还保留对应 Codex/Claude 会话存档时才有用；单独提交 `.session` 文件不能迁移上下文，反而会把不可用 id 传播给协作者。实际限制是换机器、清理 CLI 会话库或删除 `logs/` 后不能续会话。处置是把任务书、增量指令和最终产物作为版本化审计材料，在新机器上显式 `-NewSession`；不得复制一个 id 后宣称会话已迁移。

## 我实测到了

- 两个真实 CLI 的版本、首次与续会话命令、相同/不同 session id、上下文暗号恢复、长中文首尾和 UTF-8 字节、无效 id 原始报错、产物存在性、CLI usage、成本及 436 个单测。
- 本机 npm 的 `.ps1` shim 会被执行策略拦截，脚本因此优先解析 `.cmd`；本机运行封装器使用 `powershell.exe -ExecutionPolicy Bypass -File`。
- 初次 Claude 预检继承了失效的 `ANTHROPIC_BASE_URL=http://127.0.0.1:15721`，返回 provider 配置错误且 0 token、无产物，封装器正确判失败。正式机制测试只在子进程中临时移除 `ANTHROPIC_API_KEY`、`ANTHROPIC_AUTH_TOKEN`、`ANTHROPIC_BASE_URL`，使用现有 Claude 登录；没有修改持久环境。
- 开始核对时上一轮 projection 文件已暂存；并行期间它们由另一个进程在 `2026-09-16T20:10:58+08:00` 提交为 `6c24316 feat: add immutable projection service`。本任务没有执行 commit、reset、restore 或 push；最终工作树只显示本轮允许目录下的未跟踪文件。

## 我推断与没有把握的地方

1. 单次提示词字符减少可以稳定说明“主控不再重复发送背景”，但字符数不是 tokenizer 结果，也不能直接换算账单 token。
2. Codex 的 `input_tokens` 包含大量缓存命中与保留历史；我用 `input - cached_input` 计算“未缓存输入”是基于字段语义的合理推导，不是 CLI 单独打印的计费字段。
3. Claude 的成本差异来自这一组真实运行，但系统提示、缓存状态、代理工具步骤和模型输出都没有完全控制；不能把 68.36% 当作长期固定节省率。
4. 脚本没有为相同 `-Name` 的并发调用加跨进程锁；纪律上应避免并发派发同一名字，否则最后完成者会覆盖 session 映射。
5. 成功必须要求产物在本轮变化。若任务本意是确认现有产物无需修改，代理即使给出正确结论也会被封装器判失败；此时应指定一个本轮专用的审计产物。
6. `.session` 文件不等于完整会话备份。CLI 自身会话数据库过期、清理或不可迁移时只能显式新开，脚本不会也不应伪装成已恢复上下文。

## 文件边界

本轮新增或修改仅位于 `tools/dispatch/**`、`docs/**`、`logs/dispatch/**` 和本报告；没有由本轮改动 `ky/**`、`tests/**` 或 `data/**`，没有执行 `git push`。
