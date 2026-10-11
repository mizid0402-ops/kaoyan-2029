# 任务：把 CLI 派发改成"一次开会话、后续续会话"（省 token）

## 问题（用户提出，主控承认）

主控此前派发 Claude / Codex **每次都用 `codex exec` / `claude -p` 开新进程**，
导致**每轮都要把任务书与背景重讲一遍**，上下文全丢、**token 消耗很高**。

**用户原话**：「你派他俩出去干活的时候尽量在一个对话窗口里，不然每次都是重新输入，token 烧的飞快」。

## 已实测的事实（主控刚跑的，可采信）

**两个 CLI 都原生支持续会话**：

```
codex  exec resume   Resume a previous session by id or pick the most recent with --last
codex  exec fork     Fork a previous session by id into a new session
claude -c, --continue  Continue the most recent conversation
claude --resume <session-id>
claude --fork-session
```

即：**本可以"一次开、后续续"，主控却每次重开。这是用法错误，不是工具限制。**

## 你要交付什么

### 1. 两个 PowerShell 封装脚本

放在 `tools/dispatch/` 下（新目录），例如：
- `tools/dispatch/codex-session.ps1`
- `tools/dispatch/claude-session.ps1`

**要求**：

| 要求 | 说明 |
|---|---|
| **首次调用** | 开新会话，**把 session id 记录下来**（存到 `logs/dispatch/<name>.session` 之类的地方） |
| **后续调用** | **自动续上一个会话**（codex 用 `exec resume --last` 或记录的 id；claude 用 `-c` 或 `--resume <id>`） |
| **显式刷新** | 提供 `-NewSession` 开关，强制开新会话（用于换任务、或旧会话已跑偏） |
| **不破坏既有行为** | 续会话时**只发增量提示词**，不重复任务书 |
| **日志** | 每次写 `logs/dispatch/<name>-<timestamp>.log`，并**保留可复制的原始命令** |
| **失败可诊断** | 若续会话失败（会话不存在/过期），**明确报错并提示加 `-NewSession`**，不要静默退化成新会话 |

### 2. 更新派发文档

在 `docs/` 或 `review/rounds/` 写一份**派发纪律**，说明：
- 默认续会话；只在换任务时才 `-NewSession`
- **长中文提示词必须走文件管道**（`[System.IO.File]::ReadAllText(..., UTF8)`），
  **不要拼进命令行**——主控在这个坑上栽过两次（命令被截断 / 中文被吃掉）
- 用 `*>` 重定向，**不要 `2>&1 | Tee-Object | Out-Null`**（会让子进程在提示词回显后被杀）
- 判成功看**产物文件**，不看退出码（codex 成功也可能返回非 0）

### 3. 实测证明省了 token

**必须给证据**，不能只说"应该能省"：

- **对照组**：用旧方式（新开会话）+ 同一份增量提示词，记录**输出的 token 用量**（若 CLI 会打印）
  或至少记录**提示词字符数**与**会话是否被复用**
- **实验组**：用新方式（续会话）+ 同一份增量提示词
- **给出两者的差异数字**

**若 CLI 不打印 token 用量**，那就用**提示词字符数**与**是否复用会话**作为代理指标，
**并如实说明这不是真实 token 数**。

### 4. 边界

- **可新建/可改**：`tools/dispatch/**`、`docs/**`、`logs/dispatch/**`、`review/rounds/**`
- **禁止改**：`ky/**`、`tests/**`、`data/**`（除 `data/projections/**` 若已存在）
- **不要执行 git push**；可以 `git add && git commit`
- 本机**没有 `rg`**；必须用 `py -3.12`
- **注意**：`logs/` 已在 `.gitignore` 里，所以会话 id 文件不会被提交——
  **请在报告里说明这是否是问题**（例如换机器后无法续会话），并给出你的处置

## 完成标准

| # | 标准 |
|---|---|
| 1 | 两个封装脚本存在，且**首次调用能开新会话并记录 id** |
| 2 | **第二次调用确实复用会话**，有证据（如会话 id 相同、或 CLI 明确表示 continue） |
| 3 | `-NewSession` 能强制开新会话 |
| 4 | **长中文提示词经文件管道传入，实测未被截断**（给出提示词首尾字符的核对） |
| 5 | 续会话失败时**明确报错**，不静默退化 |
| 6 | 省 token 的**对照数字**（或代理指标 + 如实说明） |
| 7 | 派发纪律文档存在且写明四个坑（续会话 / 文件管道 / `*>` 重定向 / 判产物不判退出码） |
| 8 | `py -3.12 -m unittest discover -s tests -q` **仍全绿**（你没碰 ky/tests，应无影响） |

## 报告

`review/rounds/round-41-dispatch-sessions-codex.md`，含：
1. 两个脚本的用法（首次 / 续 / 强制新开）
2. **省 token 的对照证据**
3. 四个坑各自怎么防的
4. 8 条标准的实际输出
5. 「我实测到了」vs「我推断」
6. 没有把握的地方至少 3 条

最后用一句话回复：两个脚本是否可用 + 续会话是否有证据 + 省 token 的对照数字 + 8 条标准过了几条 + 报告路径。
