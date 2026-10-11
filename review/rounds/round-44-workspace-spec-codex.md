# Round 44 Codex：WP-B 工作区注册表规格审查

范围：只读审查 `contracts/workspace.md` 与当前调用方；未运行测试。以下“必须改”指交给 WP-B 实现前应定清的契约，不要求把所有下游迁移提前实现。

## 1. 字段集与遗漏输入

- **必须改｜定义真题索引目录的“生效集合”。**`reference.exam_index_dir` 只给目录，而投影与校验器都遍历 `*.json`（`ky/projection/__init__.py:98,187-188`；`tools/verify_408_index.py:496-498`）。多放一个旧版或备份 JSON 就会改变投影。规格须规定命名/纳入规则、重复科目年份如何拒绝；更稳妥的是登记索引清单或 manifest。仅登记目录不能回答“当前生效的某份文件在哪里”。
- **必须改｜补齐 WP-B′ 所承诺的工具端口，或明确缩小其范围。**投影现读三棵树、`knowledge_tree_agreement.yaml`、索引目录、权重、词库，现有字段基本覆盖（`ky/projection/__init__.py:43-51`）。`tools/verify_408_index.py:118,379,394,437` 还读生效树、台账以及索引/台账内嵌的源文件路径；`tools/classify_questions.py:38,232-235` 读生效树和命令行 PDF。后两类动态源路径不必逐一登记，但**内嵌相对路径以哪个根解析**必须定为 `Workspace.root` 或明确其他端口规则。五个硬编码盘符工具还使用 `data/raw_materials/cs408/{quiz_pages,past_papers}` 和 `review/408知识点树与真题` 输入/输出（如 `tools/extract_408_questions_from_html.py:28-31`、`tools/extract_408_question_text.py:27-33`、`tools/extract_cs408_bundle.py:25-30`、`tools/build_408_deck_scaffold.py:22-29`）；若 §1:11 禁止约定式拼接，应登记原始资料根与 408 产物目录，否则 WP-B′ 无法按规格去掉这些写死路径。
- **必须改｜消除“所有模块与 CLI 只从这里取路径”与 §7 排除考试配置的矛盾。**现有 `preflight/snapshot/day-plan/month-close` 均显式要求 `--config`（`ky/__main__.py:77,409,506,556,640`），`ledger` 有 `--ledger/--root`，投影有 `--out`。可选择登记默认 `reference.config`，也可把 §1 改成“注册表提供默认数据源，显式 CLI 参数仍可覆盖”，并逐项规定优先级。否则迁移者可能删掉既有 CLI 用法。WP-E 已定手填 `availability`、RoutePlan 落盘（`docs/阶段2.5-接缝收口.md:86`），宜预留 `state.availability`、`state.routes`，或明确由各自 WP 扩展 schema_version；当前没有这两个状态路径。
- **建议改｜收窄“subjects 唯一定义处”的表述。**当前 `ky/ledger/material.py:105` 仍有含 `general` 的白名单，`ky/projection/__init__.py:62-82` 有 cs408 特判，考试配置也自带科目。注册表可定义“本工作区启用哪些科目”，不能单凭新增文件就使这些枚举消失。`politics` 无树时，快照应继续显示 `tree_total=None`（`ky/schedule/state_snapshot.py:150-174`），规格应写明未登记与已登记但文件缺失的区别。

## 2. §2.2 路径规则

- **不改｜相对注册表所在目录解析、已提交注册表默认拒绝绝对路径与环境展开。**这使跨机器复制可预测（`contracts/workspace.md:73-79`）。`--workspace` 指向注册表本身的绝对路径不属于“被登记路径”，应明确允许。
- **建议改｜为外部只读资料和独立状态盘留显式机制。**禁止全部 `..`/绝对路径会挡住配置文件移入 `config/`、状态存在另一磁盘、用临时目录替换词库等合理用法；可保持仓库内默认严格模式，在后续版本提供明确授权的外部根/CLI 覆盖，而不把静默环境变量展开塞进 v1。若坚持“工作区必须自包含”，还须说明符号链接/Windows junction 可越过词法检查；要么在 `require` 时拒绝越界解析，要么把承诺改成“登记文本可移植”。
- **必须改｜路径字符串语法写全。**规定中间反斜杠、`C:relative`、UNC、单独 `.`、尾部 `/`、文件字段指向目录等行为；“使用 `/`”尚不足以保证不同语言在 Windows 上解析一致。`require()` 对文件与目录必须按 §2.1 字段类型分别检查。

## 3. §2.3 存在性与 §3 发现顺序

- **必须改｜给每个消费者定义缺失策略。**“加载不查存在”合理，但“缺失测试据此 skip”（`contracts/workspace.md:81-91`）不能成为生产运行的默认行为。注册过且被投影/校验器必需的树、索引、权重缺失应失败；未给 politics 登记树则是明确的可选缺口；快照当前对缺树显示未知、对缺词库返回 `None`（`ky/schedule/state_snapshot.py:150-174,189-194`）。`require(key)` 还要区分未登记、路径不存在、文件/目录类型错误，不应让投影当前的 `if not path.is_file(): continue`、空目录 `glob` 静默产出“成功”投影。
- **必须改｜明确参数优先级与失败后不回退。**显式 `--workspace` 或 `KY_WORKSPACE` 指向不存在/非法文件时，应报告该来源的错误，不应继续向上找另一项目的注册表；定义空环境变量、相对的 `--workspace`/环境值以哪个 cwd 解析、从嵌套目录发现时“最近者优先”。当前 CLI 手工按首参数分派（`ky/__main__.py:122-135`），故须指定 `ky <子命令> --workspace X` 的语法；`ky --workspace X <子命令>` 若要支持，需要改分派器。
- **建议改｜WP-B 只交付加载器，不让旧 CLI 立即强制发现。**`tests/test_cli.py:28-45` 的旧命令只传 `--config/--items`，`ky/projection/__main__.py:18-24` 只传 `--out`；若注册表不存在就让这些命令全部退出，会把 WP-B 与 WP-B′ 混成一次破坏性迁移。兼容与覆盖顺序在 WP-B′ 按模块逐个验收。

## 4. 补充视图与 D1

- **必须改｜将 `cs408_multisource` 的机器契约写实。**`supplementary.<名>.files` 目前允许任意非空角色映射，`description` 只是人读字符串（`contracts/workspace.md:34-40,61-64`）；替换实现无法保证 `tree` 与 `agreement` 成对、二者都属于同一补充视图。定义该视图的 `kind/role` 与必需文件角色，并在消费端验证“403 生效 ID ⊆ 补充 ID；新增节点标 `legacy_only_pending`；附表对补充树完整且 `source_count` 匹配”。加载器本身仍可只验结构和路径。
- **必须改｜显式禁止把附表属性拼到 403 生效树。**当前投影按 ID 直接拼接附表（`ky/projection/__init__.py:123-156`）；对 403 个共同节点，实际有 **380 个** `source_count` 与生效树来源数不同。`knowledge_points` 又以 ID 为单列主键（同文件 `108-120`），不能在同表直接加入 410 版重叠行。规格至少规定生效表仅含 403、补充表/视图单独命名，跨年来源支持字段必须带补充视图身份；实现细节留 WP-B′。
- **必须改｜PPT 标注是下游验收条件，不是 `description` 自动实现的。**`tools/extract_cs408_bundle.py:53-76` 虽导出 `evidence_tag`，但不导出 `is_effective/baseline_relation`；`tools/build_408_deck_scaffold.py:119-130` 把 legacy 子节点照常列入讲解条目。补充数据出口须能机器识别 7 个旧年待定节点，PPT/投影分别显示“补充、非当年生效”。

## 5. §6 契约测试增补

- **必须改｜解析与发现边界**：非映射顶层、非字符串路径、布尔值 `schema_version: true`、非列表 `subjects`、空 `subjects` 是否允许的明确判定、嵌套重复键、缺 `tree/agreement` 的 cs408 补充视图；`C:foo`、UNC、反斜杠路径、目录/文件类型错；显式坏路径与坏 `KY_WORKSPACE` 不回退、嵌套目录最近文件优先、环境变量相对路径基准。所有错误断言字段路径，不要求不同 YAML 实现逐字同文案。
- **必须改｜存在性与不可变性**：未登记可选树、已登记却缺失的必需输入、空索引目录、目录误作文件；输出目标不存在仍能加载且不创建目录；`Workspace` 的嵌套 `supplementary.files` 也不可修改（`MappingProxyType` 不能只包最外层）。对投影的输入集合要验登记表哈希与实际消费文件哈希，而非只验字段本身。
- **必须改｜WP-B′ 增加替换演练**：将临时工作区中的生效树/词库/索引目录换到另一相对路径，快照、投影、索引校验器和分类器各自读取新路径；403 生效点数及 7 个 legacy 排除；附表只进入补充读模型且来源数不冒充 403；PPT 导出携带 legacy 标记。只测 `Workspace.require()` 无法证明“换完仍正常工作”。这些是下游模块的契约测试，不要求 WP-B 加载器现在读取数据。
- **不改｜原有原始字节 SHA-256 与纯读测试。**这两项契约清楚（`contracts/workspace.md:103-106,158-159`）；可补 LF/CRLF 字节不同则哈希不同的断言，保持与 C3 的真实字节口径一致。
