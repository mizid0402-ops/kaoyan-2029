# 2026 年 408 真题知识节点映射报告（sol）

## 结论

- 编码完成度：47/47，题号 1..47 无缺失、无重复。
- 置信度：high 44，medium 3，low 0。
- `null`：0。当前 47 题均能在给定节点表中找到对应节点，未发现需标记“疑似考纲外”的题目。
- 节点合法性：所有 `nodes` 与 `primary_node` 均来自指定 TSV，且每题的主节点均包含在该题 `nodes` 中。

## 来源核对与边界

- 完整题号和题面结构以只读 HTML 与两份只读 PDF 交叉核对；HTML 覆盖 1..47，两份 PDF 的文本层用于复核题号、学科段与知识主题。
- 回忆版来源之间存在局部题面差异，例如一份 PDF 的第 15 题重复了第 14 题，而另两处来源将第 15 题记为交叉编址 DRAM；第 28、35、39 题的个别数字或选项也不完全一致。这些差异不改变对应的知识节点，因此未据某一版本的具体数值扩展或缩减节点。
- PDF 均有可提取文本层；图表题的 HTML 文本保留了题号、标签和主要图中文字，足以确定知识主题，因此未把图中具体计算结果当作映射依据。
- 未参考或搜索其他 coder 的输出。

## 节点表完整性

- TSV 共 383 个节点。当前文件使用 CRLF 时的原始字节 SHA-256 为 `447b9f6280be38868ac18a8adec60895cdaca247b13246b1b46cdc6b8b1ad386`。
- 将 CRLF 规范化为 LF 后，SHA-256 为任务书声明的 `23151e22cec17069b2dc682541a92391024ee9ff20d570ff9fc79afb342bc149`。因此这是换行差异，不是节点内容差异；JSON 的 `meta.node_table_sha256` 记录任务书的规范化哈希。

## 映射明细

| 题号 | 主节点 | 其他节点 | 置信度 | 判断依据 |
|---:|---|---|:---:|---|
| 1 | `cs408.ds.chapter-02.section-02.item-01`<br>顺序存储 | - | high | 考查顺序存储在线性表端点增删时的元素搬移规律，直接对应顺序表实现。 |
| 2 | `cs408.ds.chapter-02.section-02.item-02`<br>链式存储 | - | high | 核心是双向链式结点的指针更新与空指针边界处理，属于线性表的链式存储。 |
| 3 | `cs408.ds.chapter-04.section-02.item-03`<br>二叉树的遍历 | - | high | 需要结合两种访问次序还原树形关系并推出另一种访问序列，中心知识是二叉树遍历。 |
| 4 | `cs408.ds.chapter-04.section-03.item-02`<br>森林与二叉树的转换 | - | high | 需利用左孩子右兄弟表示下森林次序对所得二叉树高度的影响，直接对应森林与二叉树转换。 |
| 5 | `cs408.ds.chapter-04.section-04.item-01`<br>哈夫曼（Huffman）树和哈夫曼编码 | - | high | 以最小带权路径长度构造最优前缀树并判断叶结点深度，属于哈夫曼树及编码。 |
| 6 | `cs408.ds.chapter-05.section-02.item-02`<br>邻接表 | - | high | 入度统计的扫描范围由有向图的邻接表组织方式决定，核心落在邻接表存储。 |
| 7 | `cs408.ds.chapter-05.section-01`<br>（一）图的基本概念 | - | medium | 判断字符串集合有限性依赖有向图的路径、环及路径长度上界，节点表没有更细的路径与环条目。 |
| 8 | `cs408.ds.chapter-06.section-05.item-02`<br>平衡二叉树 | - | high | 由高度平衡约束推导左右子树规模差的极值，直接考查平衡二叉树性质。 |
| 9 | `cs408.ds.chapter-07.section-02`<br>（二）直接插入排序 | - | high | 比较不同初始序列下逐项插入的比较次数，直接对应直接插入排序。 |
| 10 | `cs408.ds.chapter-07.section-10`<br>（十）基数排序 | - | high | 多关键字分级排序要求按低优先级到高优先级稳定处理，匹配基数排序的思想。 |
| 11 | `cs408.ds.chapter-07.section-11`<br>（十一）外部排序 | - | high | 考查多路归并路数、初始归并段数量、内存规模与归并趟数的关系，属于外部排序。 |
| 12 | `cs408.co.chapter-01.section-01`<br>（一）计算机系统层次结构 | - | high | 围绕应用软件、操作系统、指令集体系结构与微体系结构的层次关系作辨析，对应系统层次结构。 |
| 13 | `cs408.co.chapter-02.section-03.item-02`<br>带符号整数的表示和运算 | - | high | 算术移位需要按符号位扩展并判断定长结果，本质是带符号机器整数的表示与运算。 |
| 14 | `cs408.co.chapter-02.section-04.detail-01.note-01`<br>IEEE 754 标准。 | - | high | 需完成单精度格式的符号、阶码、尾数编码及舍入，直接对应 IEEE 754 标准。 |
| 15 | `cs408.co.chapter-03.section-04.item-02`<br>多模块存储器 | - | high | 依据交叉编址和总线宽度判断地址落入的存储体，中心知识是多模块存储器。 |
| 16 | `cs408.co.chapter-04.section-01`<br>（一）指令系统的基本概念 | - | high | 要求区分指令集可见规范与微体系结构实现细节，属于指令系统的基本概念。 |
| 17 | `cs408.co.chapter-04.section-01`<br>（一）指令系统的基本概念 | `cs408.co.chapter-04.section-06.item-04`<br>过程（函数）调用对应的机器级表示<br><br>`cs408.co.chapter-05.section-05.item-01`<br>异常和中断的基本概念 | medium | 需比较条件转移、过程调用与返回、陷入等控制转移的后继地址语义；节点表无统一的控制转移叶节点，故以指令系统概念为主并补充过程调用和异常入口。 |
| 18 | `cs408.co.chapter-03.section-06.item-02`<br>Cache 和主存之间的映射方式 | - | high | 由行数、相联度、块大小和主存地址计算组索引，直接考查 Cache 与主存的映射。 |
| 19 | `cs408.co.chapter-03.section-07.detail-02.note-01`<br>基本原理，页表，地址转换，TLB（快表）。 | - | high | 需联合虚页号的组相联索引、TLB 标记有效位与页表驻留位判断一致性，完全对应页表、地址转换和 TLB。 |
| 20 | `cs408.co.chapter-05.section-03`<br>（三）数据通路的功能和基本结构 | `cs408.co.chapter-01.section-02.detail-01`<br>吞吐量、响应时间；CPU 时钟周期、主频、CPI、CPU 执行时间；MIPS、MFLOPS、GFLOPS、TFLOPS、PFLOPS、EFLOPS、ZFLOPS。<br><br>`cs408.co.chapter-05.section-06.item-01`<br>指令流水线的基本概念 | high | 比较单周期、多周期与流水数据通路的每指令周期数，主线是数据通路结构，并涉及 CPI 指标和流水线基本概念。 |
| 21 | `cs408.os.chapter-01.section-03.detail-01.note-01`<br>内核模式，用户模式。 | `cs408.os.chapter-01.section-03.item-04`<br>系统调用 | high | 通过 I/O、关中断、中断返回和陷入入口区分特权级要求，核心是内核态与用户态，并直接涉及系统调用。 |
| 22 | `cs408.co.chapter-05.section-05.item-03`<br>异常和中断的检测与响应 | `cs408.co.chapter-06.section-03.item-02`<br>程序中断方式 | high | 辨认中断响应阶段由硬件自动完成的现场动作，主考中断检测与响应，同时置于程序中断 I/O 场景。 |
| 23 | `cs408.os.chapter-01.section-03.item-05`<br>程序的链接与装入 | `cs408.os.chapter-01.section-03.detail-01.note-01`<br>内核模式，用户模式。 | high | 依据编译、链接、装入和命令解释各阶段的权限需求判断执行模式，重点是程序链接与装入。 |
| 24 | `cs408.os.chapter-03.section-02.item-02`<br>请求页式管理 | `cs408.os.chapter-01.section-03.item-03`<br>中断和异常的处理 | high | 围绕虚拟地址转换、页表维护和缺页异常的软件硬件分工作判断，主考请求页式管理并涉及异常处理。 |
| 25 | `cs408.os.chapter-02.section-01.item-03`<br>线程的实现 | `cs408.os.chapter-02.section-01.item-01`<br>进程与线程的基本概念 | high | 辨析用户级与内核级线程的创建、映射以及同进程线程的资源共享，核心是线程实现。 |
| 26 | `cs408.os.chapter-02.section-03.item-05`<br>信号量 | - | high | 由计数信号量的负值推断已获资源和阻塞进程数量，直接对应信号量语义。 |
| 27 | `cs408.os.chapter-02.section-03.item-01`<br>同步与互斥的基本概念 | - | medium | 通过两个进程读写集合的交集条件判断并发是否产生数据冲突，属于同步与互斥的基本判定；节点表无更细的读写冲突条目。 |
| 28 | `cs408.os.chapter-03.section-01.item-04`<br>页式管理 | - | high | 根据多级虚拟地址字段和页内偏移计算末级页表规模及占用页框，直接考查页式管理。 |
| 29 | `cs408.os.chapter-03.section-02.item-06`<br>虚拟存储器性能的影响因素及改进方法 | `cs408.co.chapter-03.section-07.detail-02.note-01`<br>基本原理，页表，地址转换，TLB（快表）。 | high | 比较 TLB、页表层次、工作集和页缓冲机制对平均访问代价的作用，主线是虚拟存储性能优化，并明确涉及 TLB。 |
| 30 | `cs408.os.chapter-03.section-02.item-05`<br>内存映射文件（memory-mapped files） | - | high | 判断两个进程映射同一文件时虚拟地址、页表项与物理页的关系，直接对应内存映射文件。 |
| 31 | `cs408.os.chapter-05.section-02.item-04`<br>设备驱动程序接口 | `cs408.os.chapter-05.section-01.item-05`<br>I/O 软件层次结构 | high | 辨析设备驱动的硬件相关性、内核接口及字符设备与块设备差异，重点是驱动程序接口并涉及 I/O 软件层次。 |
| 32 | `cs408.os.chapter-05.section-01.item-05`<br>I/O 软件层次结构 | `cs408.os.chapter-05.section-02.item-01`<br>缓冲区管理 | high | 要求区分设备硬件、中断处理程序和上层应用各自的数据搬运职责，核心是 I/O 软件层次，并涉及内核缓冲。 |
| 33 | `cs408.cn.chapter-01.section-02.item-01`<br>计算机网络分层结构 | - | high | 考查网络分层的边界、封装代价、独立演化和抽象作用，直接对应网络分层结构。 |
| 34 | `cs408.cn.chapter-02.section-01.item-02`<br>奈奎斯特定理与香农定理 | `cs408.cn.chapter-01.section-01.item-03`<br>计算机网络的主要性能指标 | high | 先由带宽和信噪比求信道容量上界，再据分组长度求最小发送时间，涉及香农定理和网络性能指标。 |
| 35 | `cs408.cn.chapter-03.section-05.detail-03.note-01`<br>ALOHA 协议，CSMA 协议，CSMA/CD 协议，CSMA/CA 协议。 | `cs408.cn.chapter-03.section-06.item-03`<br>IEEE 802.11 无线局域网 | high | 需组合帧发送时间、短帧间隔与确认过程计算无线介质访问时序，主考 CSMA/CA，并处于 802.11 场景。 |
| 36 | `cs408.cn.chapter-03.section-06.item-04`<br>VLAN 基本概念与基本原理 | `cs408.cn.chapter-03.section-08.detail-01`<br>以太网交换机及其工作原理。 | high | 根据端口所属广播域和目的地址类型判断主机能收到的帧，联合考查 VLAN 隔离与交换机转发。 |
| 37 | `cs408.cn.chapter-04.section-02.item-03`<br>链路状态路由算法 | `cs408.cn.chapter-04.section-03.item-03`<br>子网划分、路由聚集、子网掩码与 CIDR<br><br>`cs408.cn.chapter-04.section-08.item-02`<br>路由表与分组转发 | high | 链路失效后需重新计算最短路，再合并可聚集前缀并形成新路由表，覆盖链路状态算法、CIDR 聚集和路由表。 |
| 38 | `cs408.cn.chapter-04.section-05.item-04`<br>OSPF 路由协议 | - | high | 以是否支持自治系统内部的区域划分来识别路由协议，直接对应 OSPF。 |
| 39 | `cs408.cn.chapter-04.section-03.item-03`<br>子网划分、路由聚集、子网掩码与 CIDR | - | high | 由原前缀和均分子网数量确定新前缀，再定位给定地址的网络边界，直接对应子网划分与 CIDR。 |
| 40 | `cs408.cn.chapter-06.section-05.item-02`<br>HTTP 协议 | - | high | 辨析 Cookie 在无状态 Web 会话中的用途，属于 HTTP 的状态管理机制。 |
| 41 | `cs408.ds.chapter-06.section-05.item-01`<br>二叉搜索树 | - | high | 利用搜索树的有序性剪枝查找与目标差值最小的关键字，直接对应二叉搜索树及其操作。 |
| 42 | `cs408.ds.chapter-03.section-06`<br>（六）栈、队列和数组的应用 | `cs408.ds.chapter-03.section-01`<br>（一）栈和队列的基本概念 | high | 综合判断合法出栈序列、禁用排列模式及序列计数，属于栈的应用，并以栈的后进先出性质为基础。 |
| 43 | `cs408.co.chapter-04.section-02`<br>（二）指令格式 | `cs408.co.chapter-04.section-06`<br>（六）高级语言程序与机器级代码之间的对应 | high | 围绕多种定长格式的字段解释、操作码复用、指令译码与短程序编码展开，主考指令格式并涉及机器级代码对应。 |
| 44 | `cs408.co.chapter-05.section-03`<br>（三）数据通路的功能和基本结构 | `cs408.co.chapter-05.section-04`<br>（四）控制器的功能和工作原理<br><br>`cs408.co.chapter-05.section-02`<br>（二）指令执行过程 | high | 需识别通路部件并为取指、移位和访存类操作设置多路选择与写使能信号，联合考查数据通路、控制器和指令执行过程。 |
| 45 | `cs408.os.chapter-02.section-02.item-05`<br>CPU 调度算法 | - | high | 按动态优先级、时间片和时钟中断事件推演进程运行次序与调度次数，直接对应 CPU 调度算法。 |
| 46 | `cs408.os.chapter-04.section-01.item-02`<br>文件元数据和索引节点（inode） | `cs408.os.chapter-04.section-01.item-07`<br>文件的物理结构<br><br>`cs408.os.chapter-04.section-02.item-03`<br>目录的操作<br><br>`cs408.os.chapter-04.section-03.item-03`<br>外存空闲空间管理方法 | high | 分别计算索引节点位置与多级索引访问次数，并分析删除目录时目录项、位图和索引节点的更新，覆盖 inode、文件物理结构、目录操作和空闲空间管理。 |
| 47 | `cs408.cn.chapter-05.section-03.item-02`<br>TCP 连接管理 | `cs408.cn.chapter-05.section-03.item-04`<br>TCP 流量控制<br><br>`cs408.cn.chapter-05.section-03.item-05`<br>TCP 拥塞控制<br><br>`cs408.cn.chapter-05.section-03.item-03`<br>TCP 可靠传输 | high | 综合推导 TCP 建连与释放序号、接收窗口限制、拥塞窗口增长、确认号及往返时延，覆盖连接管理、流量控制、拥塞控制和可靠传输。 |

## 最小范围验证

- 使用 `py -3.12` 读取 JSON 与 TSV，检查 JSON 可解析、`entries == 47`、题号严格等于 1..47、置信度枚举合法、节点 id 全部存在、主节点属于该题节点集合。
- 验证结果：PASS。

_报告生成时间：2026-09-13T17:23:30+08:00_
