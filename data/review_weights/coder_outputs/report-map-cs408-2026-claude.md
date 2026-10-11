# 2026 年 408 计算机学科专业基础 47 题知识点映射报告（coder: claude）

## 数据来源

- 题干：
  - `C:\Users\Lenovo\AppData\Local\Temp\kaoyan-probe\cs408_2026\iqihang_2026_408.pdf`（回忆版，含1~47题完整文本，主要依据）
  - `C:\Users\Lenovo\AppData\Local\Temp\kaoyan-probe\cs408_2026\kaoyan_static_2026_408.pdf`（1~40题文本+解析，用于交叉核对，41~47为图片无文本层，未单独重新OCR，以iqihang版为准）
  - `F:\workspace\kaoyan-ai-system\data\raw_materials\cs408\quiz_pages\cs408_quiz_2026.html`（未作为主要抽取来源，两份PDF文本已足以判定47题知识点，未逐题比对）
- 节点表：`C:\Users\Lenovo\AppData\Local\Temp\kaoyan-probe\mapping\tasks\cs408_2026_nodes.tsv`，共 383 个节点。

## 关于节点表 sha256 的说明

任务书中给出的 sha256 为 `23151e22cec17069b2dc682541a92391024ee9ff20d570ff9fc79afb342bc149`，
但本次会话中用 Python 实际计算该 tsv 文件得到的 sha256 为
`447b9f6280be38868ac18a8adec60895cdaca247b13246b1b46cdc6b8b1ad386`。
两者不一致（可能任务书文档与当前磁盘文件版本不同步）。JSON 的 `meta.node_table_sha256`
字段记录的是**本次实际读取并用于选择节点的文件**的真实哈希值，以保证可复现性；未对文件本身做任何修改。

## 方法与工具

- 使用 `py -3.12` + `pypdfium2` 提取两份 PDF 的文本层（均写为 UTF-8 文件后用 Read 工具读取，避免终端吞中文）。
- iqihang 版 PDF 文本层完整覆盖 1~47 题（含综合应用题正文），是本次映射的主要依据。
- static 版 PDF 用于交叉核对选择题（1~40）的题干与选项，二者内容一致，仅个别选项数字/字母顺序略有出入（如第39题IP地址、第9题选项数值），不影响知识点判断。
- 未修改 `F:\workspace\kaoyan-ai-system` 下任何文件，未执行 git 命令。

## 结果概览

- entries：47 条，number 1~47，无缺无重（已用脚本校验）。
- confidence 分布：high 36 条，medium 10 条，low 1 条。
- null（疑似考纲外）：0 条 —— 47 题均能在节点表中找到可用节点，未出现需要标 null 的情况。
- 所有 nodes / primary_node 均已逐一核对存在于 `cs408_2026_nodes.tsv` 中（脚本校验通过，无缺失）。

## 需要说明的低置信度/多节点题目

- **第7题（medium）**：有向图上从起点到多个终点的路径字符串集合的性质判断，节点表在"图的基本概念"下没有更细的"路径计数/环"子项，只能落到 section 级节点 `cs408.ds.chapter-05.section-01`。
- **第17题（low）**：条件跳转/过程调用/陷阱/过程返回指令执行后能否顺序执行下一条指令，节点表中没有专门的"控制转移指令"条目，只能勉强归入 `cs408.co.chapter-04.section-01`（指令系统的基本概念），把握有限，故标 low。
- **第21、22、24、28、30 题（medium）**：均为计算机组成原理与操作系统交叉的内容（特权指令/中断响应硬件部分/虚拟存储器地址转换与异常处理/多级页表/共享文件页映射），命题人可能倾向于将其归入 OS 或 CO 中的任一门，两门课在这些主题上高度重叠，故标 medium，部分题（如第24题）列出了两个候选节点。
- **第47题（medium）**：TCP综合题同时考查连接管理（三次握手/四次挥手、序号确认号）、流量控制（rwnd）与拥塞控制（拥塞窗口增长），主计算量落在拥塞控制上，故以拥塞控制为 primary_node，并列出连接管理、流量控制作为次要节点。

## 文件产出

- JSON：`C:\Users\Lenovo\AppData\Local\Temp\kaoyan-probe\mapping\map-cs408-2026-claude.json`
- 本报告：`C:\Users\Lenovo\AppData\Local\Temp\kaoyan-probe\mapping\report-map-cs408-2026-claude.md`
