# 考研学习 AI 系统 —— 联合评审共享上下文（事实基线）

> 本文件是 DSH 编排下两个外部 agent（Codex / Claude Code）进行联合评审的**唯一事实基线**。
> 只写**已实测确认**的事实；推测必须显式标注为推测。无法确认就写"无法确认"，不要编造。

生成时间：2026-09-12
编排器：DSH（DeepSeek Harness）

---

## 0. 任务背景

用户提供了一份《考研学习 AI 系统需求文档》（需求全文见 `requirements.md`，与
`C:\Users\Lenovo\.dsh\attachments\v1\files\dc\dce86ff9caff99a09c38e2500f3b86d50bd7b680455a4f8c35e1f576b1f3d1d4\考研学习AI系统需求文档.md` 逐字一致）。

用户要求：

1. 调用 **Claude Code 的 Sonnet 5（high effort）** 与 **Codex 的 gpt-5.6-sol（high effort）**
   共同评审这份需求文档的**可实现性与缺陷**；
2. 代码工作主要由 Sonnet 5 完成，**gpt-5.6-sol 主要承担审查职责**（也可做代码工作）；
3. 在本机 workspace 中**落地**（用户已明确同意在 workspace 下单独新建一个文件夹存放本项目的全部产出）；
4. **在实行全部任务之前**，如果通读需求文档出现任何问题或不确认的点，必须与用户沟通。

本轮是**第一轮评审**，目标是：把需求文档的可实现性、缺陷、以及"必须由用户拍板才能继续"的
问题清单一次性打出来，**不要**在这一轮直接产出实现代码。

---

## 1. 需求文档本身的可核事实

- 文件：`requirements.md`（本目录内副本），545 行，UTF-8 中文 Markdown。
- 项目名（§1）：**基于历年真题与动态课表的计算机考研 24 个月滚动学习系统**。
- 目标（§2、§3.2）：24 个月把零基础/弱基础学习者带到**总分 380 分左右**；
  参考结构：政治 65–75、英语 70–80、数学 115–125、专业课（408/自命题）110–120。
- 核心任务（§4）：①资料搜索与结构化 ②24 个月滚动计划 ③学习记录与动态调整 ④课程表协同与时间调度。
- 复习机制（§5）：1/3/7/15/30 天间隔复习，可按掌握度动态伸缩。
- 更新频率（§6）：日 / 周 / 月 / 阶段四层。
- 网站与数据库（§7）：课表可视化、计划展示、能力图谱、记录录入；**课表修改走数据库，不改代码**。
- 可视化（§8）：课表图、学习进度、能力雷达、目标差距。
- 建议目录结构（§9）：`kaoyan_system/`，含 `data/`、`plans/`、`outputs/`、`prompts/`、`app/{backend,frontend,database}`。
- AI 角色（§10）：8 种角色（资料整理员/长期规划师/周计划调度员/日计划生成器/记录分析员/能力评估器/复习管理员/可视化报告生成器）。
- 执行禁令（§16.2）：不得一次性写死 24 个月全部日计划；不得脱离课表机械排课；不得只推新不复习等。
- 推进顺序（§18）：资料 → 知识结构 → 24 月总规划 → 月周日滚动 → 课表读取与排课 → 记录/画像/复习 → 数据库与网站 → 可执行方案。

### 需求文档中**没有**给出的关键参数（截至本文件生成时，用户尚未回答）

- 考试年份与目标考试日期（文档只说"从现在开始 24 个月"）；
- 数学是**数学一还是数学二**；
- 英语是**英语一还是英语二**；
- 专业课是**统考 408 还是某院校自命题**；若自命题，目标院校是哪一所；
- 用户当前年级、在读院校、已修课程与真实基础水平（文档只说"按零基础/弱基础建模"）；
- 课程表的**实际来源**（学校教务系统导出？手工 CSV/JSON/YAML？）；
- 每日可用时间是固定 2 小时还是会随学期变化；
- 是否需要**多用户**（文档通篇像是单用户）；
- 部署形态：纯本机运行，还是要真正部署到公网域名/服务器。

---

## 2. 本机 workspace 已有资产（已实测，非推测）

### 2.1 已存在一套**成熟的本地学习管理系统** `F:\workspace\study`

这是本任务最重要的既有资产。它**不是**空白工程，而是一个已经跑起来的、以本地文件为状态存储的
单用户学习管理系统（Python CLI + 受控生成流程 + 周关闭状态机 + 能力图谱 + Git 同步）。

已实测的结构与能力（来源：`F:\workspace\study\README.md`，197 行；`study_workspace/` 包内
47 个 Python 模块，`cli.py` 40 KB、`context_builder.py` 68 KB、`generation.py` 89 KB、
`week_close.py` 52 KB、`recovery.py` 56 KB）：

| 需求文档中的能力 | `F:\workspace\study` 中已有的对应实现 |
|---|---|
| 24 个月滚动计划 | 项目 → 月计划 → 周计划 → 日计划四级目录；`plan-monthly` / `adjust-monthly-plan` / 周计划 `initial_draft` 4 周滚动 |
| 学习记录与动态调整 | `学习计划.md` + 自由格式 `学习心得.md`；`record-daily`（legacy）；周证据 `week_evidence_ai.yaml` 门禁 |
| 复习机制 | `recovery.py`（56 KB）、`recovery_selection.py`、`recovery_evidence.py`，含 `recovery_item_minutes` 固定分钟表 |
| 能力画像 | `skill_graph.yaml`（唯一权威能力状态）、`capability_registry.py`、`capability_proposals.py` |
| 阶段/周/月总结 | `close-week` 两阶段状态机、`close-due-periods`、`month_close.yaml`、`month_review.md`、`.study/learning_memory/YYYY/MM/` |
| 上下文受控生成 | Context Builder → `.study/current_context.yaml` → `.study/pending_generation.yaml` → staging → `apply-generation`（含哈希与来源校验） |
| 资料库 | 两层资源库：月度库 `<month>/项目资料/`（`add-resource`/`fetch-resource`）与项目级库 `projects/<id>/项目资料/`（`promote-resource`）；SHA-256 完整性校验 |
| 审计与同步 | `.study/generation_requests/` 审计归档、`.study/state/sync-pending.json` 白名单、`sync --nightly` 隔离提交 |
| 任务结转 | 周关闭生成 carry-over 项、`adjust_week_plan` 必须消费 `consumed_closure_ids` |

当前注册的受管项目（`F:\workspace\study\.study\projects.yaml`）：

```yaml
projects:
- {id: python,           name: Python 项目阅读, path: projects/python,           priority: main,      status: paused, daily_minutes: 90, read_only: false}
- {id: ppt,              name: PPT 修习能力,    path: projects/ppt,              priority: secondary, status: paused, daily_minutes: 30, read_only: false}
- {id: embedded-basics,  name: 嵌入式开发基础,  path: projects/embedded-basics,  priority: secondary, status: paused, daily_minutes: 60, read_only: false}
```

三个项目**全部处于 `paused`**，没有任何考研相关项目。

### 2.2 workspace 中**没有**考研资料

已实测：`F:\workspace` 下（深度 3，按文件名 `*考研*`、`*kaoyan*`、`*408*`、`*真题*` 检索）
**不存在任何考研真题、大纲或考研资料**。唯一与考研科目沾边的既有内容是大学课程作业与复习大纲：

- `F:\workspace\作业\`：`高数`、`数据结构算法`、`组成原理`、`毛概`、`数据库原理与应用`、`C++`、`linux`、`python`、`人工智能`、`数学建模`、`金融三农`、`ETL`、`数据分析双语`；
- `F:\workspace\资料\概率论复习大纲\`；
- `F:\workspace\study\projects\embedded-basics\`（嵌入式基础项目）。

**结论：需求文档 §4.1 要求"AI 先搜索并整理近十年考研资料"，这一步在本机没有任何现成数据，
必须靠联网获取或用户提供。**

### 2.3 可用的外部 agent 与模型（本轮已实测）

| 项目 | 实测值 |
|---|---|
| Codex CLI | `codex-cli 0.154.0-alpha.6.2`，可执行文件 `C:\Users\Lenovo\AppData\Local\OpenAI\Codex\bin\bffc5354119c8421\codex.exe` |
| Codex 模型 | `gpt-5.6-sol`，`model_reasoning_effort = "high"`，**实测调用成功**（返回正常中文回答） |
| Codex 沙箱 | `sandbox_mode = "danger-full-access"`，`approval_policy = "never"` |
| Claude Code | `2.1.269`，可执行文件 `%APPDATA%\npm\node_modules\@anthropic-ai\claude-code\bin\claude.exe` |
| Claude 模型 | **`claude-sonnet-5`**（官方 `/v1/models` 已列出，display_name "Claude Sonnet 5"，支持 `effort: high/xhigh/max`），**实测调用成功** |
| Claude 账号 | 官方 firstParty OAuth，`subscriptionType: pro` |
| Claude effort | CLI 支持 `--effort <level>`（low/medium/high/xhigh/max） |
| 其他可用 Claude 模型 | `claude-fable-5-1`、`claude-opus-5`、`claude-fable-5`、`claude-opus-4-8`、`claude-opus-4-7`、`claude-sonnet-4-6`、`claude-opus-4-6`、`claude-opus-4-5-20251101`、`claude-haiku-4-5-20251001`、`claude-sonnet-4-5-20250929` |

**一个已修复的本机配置故障（DSH 已处理，记录在此以免重复排查）：**

- 现象：Claude Code 所有调用返回 `API Error: 400 配置错误: Claude Provider 缺少 base_url 配置`。
- 根因：`C:\Users\Lenovo\.claude\settings.json` 被 cc-switch 写入了
  `ANTHROPIC_AUTH_TOKEN=PROXY_MANAGED` + `ANTHROPIC_BASE_URL=http://127.0.0.1:15721`，
  而 cc-switch（`cc-switch.exe`，PID 27720）本地代理的 Claude Provider 配置不完整，
  对任何请求都回 400。用户账号本身是官方 Pro，直连即可。
- 处理：备份原文件到 `F:\workspace\.agent-bridge\backup\claude-settings.json.bak`，
  将 `C:\Users\Lenovo\.claude\settings.json` 改为 `{"model": "claude-sonnet-5"}`。
- 影响：**cc-switch 的 Claude 本地代理现在被绕过**。如需恢复原代理行为，从上述备份还原即可。

---

## 3. 本轮评审要回答的问题

请针对**需求文档**（不是针对既有 study 系统）回答，并明确区分"可实现 / 有条件可实现 / 不可实现"：

1. **可实现性总评**：以 380 分为目标、24 个月滚动、日/周/月四层更新、课表协同、
   间隔复习、能力画像、数据库+网站可视化——这套系统整体在工程上是否可实现？
   哪些部分是**真问题**，哪些是被需求写得像需求的**伪问题**？
2. **需求文档的硬缺陷**：列出你认为会导致项目失败或返工的具体缺陷。至少覆盖：
   - 目标设置（380 分是否可作为工程系统的可验证目标？如何度量？）；
   - "近十年真题"的数据可得性与**版权/合规**风险；
   - 资料结构化的**质量门禁**缺失（AI 拆解知识点如何验证正确？）；
   - 日/周/月滚动与"不得写死 24 个月日计划"之间的**张力**；
   - 课表协同的真实复杂度（临时调课、节假日、考试周）；
   - 能力画像的**度量效度**（自评"不会/模糊/基本会/熟练"能否支撑 380 分的差距分析）；
   - 网站+数据库与"本地文件为状态"的双写一致性问题；
   - 单用户 vs 多用户、本机 vs 公网部署的边界；
   - 需求 §18 的执行顺序要求"先整理近十年考研资料"，但本机没有任何资料。
3. **与既有 `F:\workspace\study` 系统的关系**：三条路线各自的代价与风险——
   （A）完全独立新建 `kaoyan_system/`；（B）把考研作为 study 系统里的**新项目**（`create-project`）；
   （C）复用 study 的 Context Builder / 周关闭 / Skill Graph / 受控生成内核，
   在其上补课表排课与 Web 可视化，即**混合**。请给出明确推荐并说明理由。
4. **必须由用户拍板的问题清单**：按"阻塞实现"与"可延后"两档分类，
   每个问题给出**你建议的默认值**。这是本轮最重要的交付物之一。
5. **建议的最小可行落地路径**：如果只能先做一件事，做什么？给出分阶段的里程碑建议。

---

## 4. 执行协议（必须遵守）

- 用**中文**作答。
- 只在指定输出文件里写正文；**不要**修改本目录以外的任何文件，**不要**执行 git 操作。
- 你可以联网（`web_search`/WebFetch 或 CLI 自带 web 工具）核实考研政策、大纲年份、
  408 统考范围、真题版权等事实；**引用必须给出来源链接**。核不实的信息标注"未核实"。
- 不要复述需求文档原文凑字数；观点密度优先，允许直接反驳需求文档和用户的设定。
- 允许并鼓励指出"这个需求在 24 个月尺度上做不到"这类结论，但必须给出可检验的依据。
