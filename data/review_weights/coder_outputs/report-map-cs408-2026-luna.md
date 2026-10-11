# CS408 2026 题目映射报告（luna）

## 结论

共 47 条，题号连续覆盖 1–47；high=41、medium=6、low=0；null=0。

## 输入与核对

- 任务书：`mapping/tasks/task_cs408_2026.md`。
- 节点表：`mapping/tasks/cs408_2026_nodes.tsv`，读取到 383 个节点。
- 本地节点表实际 SHA-256：`447b9f6280be38868ac18a8adec60895cdaca247b13246b1b46cdc6b8b1ad386`。任务书声明的 SHA-256 为 `23151e22cec17069b2dc682541a92391024ee9ff20d570ff9fc79afb342bc149`，二者不一致；本报告和 JSON 采用当前本地文件的实际哈希，未修改节点表。
- 题干主来源：`F:/workspace/kaoyan-ai-system/data/raw_materials/cs408/quiz_pages/cs408_quiz_2026.html`；HTML 中抽取到选择题 1–40 和大题 41–47。
- 两份 PDF 均有文本层：`iqihang_2026_408.pdf` 为 10 页、提取约 8456 字符；`kaoyan_static_2026_408.pdf` 为 29 页、提取约 7010 字符。未触发渲染兜底。

## 映射明细

| 题号 | primary_node | nodes | confidence | 判断依据摘要 |
|---:|---|---|---|---|
| 1 | `cs408.ds.chapter-02.section-02.item-01` | `cs408.ds.chapter-02.section-02.item-01` | high | 题目考查顺序存储在线性表首尾插删时的元素移动，直接对应顺序存储。 |
| 2 | `cs408.ds.chapter-02.section-02.item-02` | `cs408.ds.chapter-02.section-02.item-02` | high | 题目围绕双向链结点的前后指针重设与遍历边界，属于线性表链式存储。 |
| 3 | `cs408.ds.chapter-04.section-02.item-03` | `cs408.ds.chapter-04.section-02.item-03` | high | 由中序和层序恢复树结构后求后序，核心是二叉树遍历。 |
| 4 | `cs408.ds.chapter-04.section-03.item-02` | `cs408.ds.chapter-04.section-03.item-02` | high | 题目要求把森林按顺序转成左孩子右兄弟表示并优化高度，直接对应森林与二叉树转换。 |
| 5 | `cs408.ds.chapter-04.section-04.item-01` | `cs408.ds.chapter-04.section-04.item-01` | high | 权值合并和带权路径长度最小化是 Huffman 树构造与编码的直接应用。 |
| 6 | `cs408.ds.chapter-05.section-02.item-02` | `cs408.ds.chapter-05.section-02.item-02` | high | 邻接表求有向图入度需要遍历顶点链表和边结点，考查邻接表操作及复杂度。 |
| 7 | `cs408.ds.chapter-05.section-01` | `cs408.ds.chapter-05.section-01` | high | 结论依赖有向图路径、环和边标记串的基本定义，未涉及特定图算法。 |
| 8 | `cs408.ds.chapter-06.section-05.item-02` | `cs408.ds.chapter-06.section-05.item-02` | high | 题目使用 AVL 高度约束估计左右子树规模差，属于平衡二叉树。 |
| 9 | `cs408.ds.chapter-07.section-02` | `cs408.ds.chapter-07.section-02` | high | 题干明确限定直接插入排序，比较次数只是该算法性质的计算。 |
| 10 | `cs408.ds.chapter-07.section-10` | `cs408.ds.chapter-07.section-10` | high | 双关键字排序需求适合用稳定的基数排序分配关键字优先级，节点表有对应排序方法。 |
| 11 | `cs408.ds.chapter-07.section-11` | `cs408.ds.chapter-07.section-11` | high | 题目讨论外部 k 路归并的趟数、初始归并段和内存限制，属于外部排序。 |
| 12 | `cs408.co.chapter-01.section-01` | `cs408.co.chapter-01.section-01`<br>`cs408.co.chapter-04.section-01` | medium | 选项同时涉及计算机系统层次、软硬件接口和 ISA 的定位，需要跨越系统层次与指令系统基本概念。 |
| 13 | `cs408.co.chapter-02.section-03.item-02` | `cs408.co.chapter-02.section-03.item-02` | high | 算术移位后的定长机器数结果依赖带符号整数的补码表示与运算规则。 |
| 14 | `cs408.co.chapter-02.section-04.item-01` | `cs408.co.chapter-02.section-04.item-01` | high | 需要按 IEEE 754 单精度字段和舍入规则确定浮点机器数，属于浮点数表示。 |
| 15 | `cs408.co.chapter-03.section-04.item-01` | `cs408.co.chapter-03.section-04.item-01` | high | 多片 DRAM、交叉编址和总线宽度共同决定地址到芯片的映射，属于 DRAM 芯片与内存条。 |
| 16 | `cs408.co.chapter-04.section-01` | `cs408.co.chapter-04.section-01` | high | 判断 ISA 规定的内容与微体系结构实现的区别，直接考查指令系统基本概念。 |
| 17 | `cs408.co.chapter-04.section-01` | `cs408.co.chapter-04.section-01`<br>`cs408.co.chapter-05.section-05.item-01` | medium | 条件转移、过程调用、陷入和返回的下一条地址行为属于指令类型，同时牵涉陷入这一异常入口。 |
| 18 | `cs408.co.chapter-03.section-06.item-02` | `cs408.co.chapter-03.section-06.item-02` | high | 按块大小、行数和组相联度计算主存块所在组，直接对应 Cache 与主存的映射方式。 |
| 19 | `cs408.co.chapter-03.section-07.detail-02.note-01` | `cs408.co.chapter-03.section-07.detail-02.note-01` | high | 虚拟页号、TLB 组号、标记和有效位的组合是页表地址转换与 TLB 内容。 |
| 20 | `cs408.co.chapter-05.section-03` | `cs408.co.chapter-05.section-03` | high | 单周期、多周期和流水数据通路对 CPI 的影响由数据通路组织决定。 |
| 21 | `cs408.os.chapter-01.section-03.item-01` | `cs408.os.chapter-01.section-03.item-01`<br>`cs408.co.chapter-04.section-01` | medium | I/O 特权操作的判断依赖 CPU 用户态/内核态及指令系统中的指令权限边界。 |
| 22 | `cs408.co.chapter-05.section-05.item-03` | `cs408.co.chapter-05.section-05.item-03` | high | 题目区分中断响应阶段由硬件保存的状态和软件处理步骤，属于异常与中断的检测和响应。 |
| 23 | `cs408.os.chapter-01.section-03.item-05` | `cs408.os.chapter-01.section-03.item-05` | high | 把可执行程序装入内存并建立运行环境是装入程序的职责，节点表有对应条目。 |
| 24 | `cs408.os.chapter-03.section-02.item-02` | `cs408.os.chapter-03.section-02.item-02`<br>`cs408.co.chapter-03.section-07.detail-02.note-01`<br>`cs408.os.chapter-01.section-03.item-03` | medium | 题目综合考查请求页式执行、页表地址转换、缺页异常及操作系统对异常的处理职责。 |
| 25 | `cs408.os.chapter-02.section-01.detail-03.note-01` | `cs408.os.chapter-02.section-01.detail-03.note-01` | high | 比较内核支持线程和线程库线程的映射及共享资源，正对应两类线程实现。 |
| 26 | `cs408.os.chapter-02.section-03.item-05` | `cs408.os.chapter-02.section-03.item-05` | high | 资源计数、访问资源的进程数和阻塞进程数由信号量值的含义决定。 |
| 27 | `cs408.os.chapter-02.section-03.item-01` | `cs408.os.chapter-02.section-03.item-01` | high | 四类读写集合交叉条件用于判断并发执行是否破坏互斥，属于进程同步与互斥。 |
| 28 | `cs408.co.chapter-03.section-07.detail-02.note-01` | `cs408.co.chapter-03.section-07.detail-02.note-01` | high | 三级页表的页表项数和页框占用由页表、地址转换和页面组织规则决定。 |
| 29 | `cs408.co.chapter-03.section-07.detail-02.note-01` | `cs408.co.chapter-03.section-07.detail-02.note-01`<br>`cs408.os.chapter-03.section-02.item-06` | medium | 降低平均访存时间的选项涉及 TLB、页表层次和工作集等地址转换与虚拟存储性能机制。 |
| 30 | `cs408.os.chapter-03.section-02.item-05` | `cs408.os.chapter-03.section-02.item-05` | high | 同一文件在不同进程中的映射、页表项和共享修改行为是内存映射文件机制。 |
| 31 | `cs408.os.chapter-05.section-02.item-04` | `cs408.os.chapter-05.section-02.item-04` | high | 题目判断驱动程序的硬件接口、定制开发和统一接口职责，直接对应设备驱动程序接口。 |
| 32 | `cs408.os.chapter-05.section-01.detail-05.note-01` | `cs408.os.chapter-05.section-01.detail-05.note-01`<br>`cs408.os.chapter-05.section-02.item-01` | high | 鼠标中断处理涉及中断服务程序、驱动层和内核缓冲区，节点表分别覆盖 I/O 软件层次与缓冲区管理。 |
| 33 | `cs408.cn.chapter-01.section-02.item-01` | `cs408.cn.chapter-01.section-02.item-01` | high | 选项考查分层边界、层间独立性和抽象带来的好处，直接对应网络分层结构。 |
| 34 | `cs408.cn.chapter-02.section-01.item-02` | `cs408.cn.chapter-02.section-01.item-02` | high | 由带宽和信噪比计算信道容量，再用分组长度换算最小传输时延，核心是香农定理。 |
| 35 | `cs408.cn.chapter-03.section-05.detail-03.note-01` | `cs408.cn.chapter-03.section-05.detail-03.note-01` | high | DIFS、SIFS、数据帧和确认帧的时序属于 IEEE 802.11 的 CSMA/CA。 |
| 36 | `cs408.cn.chapter-03.section-06.item-04` | `cs408.cn.chapter-03.section-06.item-04`<br>`cs408.cn.chapter-03.section-08.detail-01` | high | 帧是否跨 VLAN 转发取决于 VLAN 划分与交换机转发表，两个节点共同覆盖题目机制。 |
| 37 | `cs408.cn.chapter-04.section-02.item-03` | `cs408.cn.chapter-04.section-02.item-03`<br>`cs408.cn.chapter-04.section-03.item-03` | high | 链路状态算法负责重算路径，路由聚合负责合并表项，题目同时考查两者。 |
| 38 | `cs408.cn.chapter-04.section-05.item-04` | `cs408.cn.chapter-04.section-05.item-04` | high | 能在自治系统内部划分区域的是 OSPF 的层次化设计。 |
| 39 | `cs408.cn.chapter-04.section-03.item-03` | `cs408.cn.chapter-04.section-03.item-03` | high | 把 /22 等分为 32 个子网并定位地址，需要子网划分、掩码和 CIDR 计算。 |
| 40 | `cs408.cn.chapter-06.section-05.item-02` | `cs408.cn.chapter-06.section-05.item-02` | high | Cookie 的用途判断属于 Web 应用中的 HTTP 机制。 |
| 41 | `cs408.ds.chapter-06.section-05.item-01` | `cs408.ds.chapter-06.section-05.item-01` | high | 在二叉搜索树中按大小关系搜索并维护最小差值，核心是二叉搜索树。 |
| 42 | `cs408.ds.chapter-03.section-06` | `cs408.ds.chapter-03.section-01`<br>`cs408.ds.chapter-03.section-06` | medium | 合法出栈序列和序列计数属于栈操作及其应用；节点表未单列卡特兰数，因此不额外自创节点。 |
| 43 | `cs408.co.chapter-04.section-02` | `cs408.co.chapter-04.section-02` | high | 定长指令中的操作码、寄存器字段、立即数和地址字段划分直接对应指令格式。 |
| 44 | `cs408.co.chapter-05.section-03` | `cs408.co.chapter-05.section-03`<br>`cs408.co.chapter-05.section-04` | high | 题目逐项追踪数据通路上的源选择、扩展、写回和控制信号，分别属于数据通路与控制器。 |
| 45 | `cs408.os.chapter-02.section-02.item-05` | `cs408.os.chapter-02.section-02.item-05`<br>`cs408.os.chapter-02.section-02.detail-03.note-01` | high | 按优先级、时间片和时钟中断推演调度次数，属于 CPU 调度算法及调度时机。 |
| 46 | `cs408.os.chapter-04.section-01.item-02` | `cs408.os.chapter-04.section-01.item-02`<br>`cs408.os.chapter-04.section-01.item-07`<br>`cs408.os.chapter-04.section-02.item-03` | high | 题目同时涉及 inode 定位、直接与间接块组织、位图回收和目录项删除，分别对应文件物理结构与目录操作。 |
| 47 | `cs408.cn.chapter-05.section-03.item-05` | `cs408.cn.chapter-05.section-03.item-01`<br>`cs408.cn.chapter-05.section-03.item-02`<br>`cs408.cn.chapter-05.section-03.item-04`<br>`cs408.cn.chapter-05.section-03.item-05` | high | 题目综合 TCP 报文序号、连接建立与释放、接收窗口和拥塞窗口变化，覆盖 TCP 段、连接管理、流量控制和拥塞控制。 |

## 限定说明

- 所有 `nodes` 和 `primary_node` 均经过本地节点表 ID 集合校验；未自创节点 ID。
- 没有题目填 `null`；第 42 题的“卡特兰数”未在节点表中单列，但其考查主体仍可由栈基本概念与栈应用节点覆盖，因此未将整题判为疑似考纲外。
