# luna 独立映射报告：2024 年 408

## 范围与依据

本报告独立依据 2024 年 408 重排版 PDF 的文本层、2024 年题目索引的题号/题型/分值，以及临时目录中的 `cs408_nodes.tsv` 完成映射。节点 id 未在 TSV 中出现的候选一律不采用。

- 题目数：47；题号覆盖：1–47，无缺号、重号。
- 分值依据：选择题 1–40 各 2 分；综合题 41–47 为 13/10/13/10/7/8/9 分。
- 节点表 SHA-256：`447b9f6280be38868ac18a8adec60895cdaca247b13246b1b46cdc6b8b1ad386`。
- 统计：high 37，medium 9，low 1；null 0。

## 逐题映射

| 题号 | 节点 id | primary | confidence | 判断依据 |
|---:|---|---|---|---|
| 1 | `cs408.ds.chapter-02.section-02.item-02` | `cs408.ds.chapter-02.section-02.item-02` | high | 操作序列体现链式存储中结点摘接与头部插入，直接对应链式存储的基本操作。 |
| 2 | `cs408.ds.chapter-03.section-06` | `cs408.ds.chapter-03.section-06` | high | 运算符优先级转换为后缀形式需要借助栈保存尚未输出的运算符，属于栈的典型应用。 |
| 3 | `cs408.ds.chapter-04.section-02.item-03` | `cs408.ds.chapter-04.section-02.item-03` | high | 结论依据二叉树中序遍历的访问次序与左右子树约束，属于二叉树遍历。 |
| 4 | `cs408.ds.chapter-05.section-02.item-03` | `cs408.ds.chapter-05.section-02.item-03` | medium | 度数统计依赖无向图邻接多重表中边结点与顶点关联的表示方式。 |
| 5 | `cs408.ds.chapter-06.section-04` | `cs408.ds.chapter-06.section-04` | high | 折半查找要求关键字序列可按位置比较并保持有序，判断对象正是折半查找的适用条件。 |
| 6 | `cs408.ds.chapter-06.section-08` | `cs408.ds.chapter-06.section-08` | high | 失配时利用模式串前后缀信息计算滑动距离，属于 KMP 字符串模式匹配。 |
| 7 | `cs408.ds.chapter-06.section-05.item-01` | `cs408.ds.chapter-06.section-05.item-01` | high | 不等式关系由二叉搜索树的左小右大性质和子树范围约束推出。 |
| 8 | `cs408.ds.chapter-07.section-07` | `cs408.ds.chapter-07.section-07` | high | 首轮划分后两侧均非空，考查快速排序一次划分所得区间的相对次序性质。 |
| 9 | `cs408.ds.chapter-04.section-04.item-03` | `cs408.ds.chapter-04.section-04.item-03` | high | 两次删除最大关键字并恢复堆序，属于堆及其优先队列应用。 |
| 10 | `cs408.ds.chapter-07.section-09` | `cs408.ds.chapter-07.section-09` | high | 按给定顺序进行二路归并并累计关键字比较次数，直接考查归并排序。 |
| 11 | `cs408.ds.chapter-07.section-11` | `cs408.ds.chapter-07.section-11` | high | 败者树用于多路归并时维护各归并段当前候选值，属于外部排序。 |
| 12 | `cs408.co.chapter-02.section-03.item-02` | `cs408.co.chapter-02.section-03.item-02` | high | 赋值经过 short 截断再恢复为 int，关键在有符号整数的补码表示与窄化转换。 |
| 13 | `cs408.co.chapter-04.section-01` | `cs408.co.chapter-04.section-01` | high | 区分伪指令、微指令、机器指令和汇编指令，考查指令系统的基本概念及执行层次。 |
| 14 | `cs408.co.chapter-02.section-03`<br>`cs408.co.chapter-02.section-04.item-01` | `cs408.co.chapter-02.section-03` | high | 两个参数的数量级分别对应定长整数和双精度浮点数的表示选择，涉及整数与浮点数表示。 |
| 15 | `cs408.co.chapter-02.section-02.detail-05.note-01` | `cs408.co.chapter-02.section-02.detail-05.note-01` | high | 比较阵列乘法器、移位累加和常数乘法优化，核心是乘法运算的基本原理与实现。 |
| 16 | `cs408.co.chapter-03.section-02` | `cs408.co.chapter-03.section-02` | medium | 选项同时比较 Cache—主存和主存—外存的交换单位、替换、写策略及映射方式，最自然的归属是层次化存储器结构。 |
| 17 | `cs408.co.chapter-03.section-07.detail-02.note-01` | `cs408.co.chapter-03.section-07.detail-02.note-01` | high | 标记字段位数由虚拟页号、组相联路数和 TLB 表项数量共同决定，属于页式虚拟存储器地址转换。 |
| 18 | `cs408.co.chapter-03.section-07.detail-02.note-01` | `cs408.co.chapter-03.section-07.detail-02.note-01` | high | MMU 地址转换阶段直接涉及 TLB、页表和越权检查，不负责检测 Cache 缺失。 |
| 19 | `cs408.co.chapter-05.section-06.item-03` | `cs408.co.chapter-05.section-06.item-03` | high | 相邻指令的操作数依赖以及旁路、停顿和重排的适用性，属于流水线数据冒险处理。 |
| 20 | `cs408.co.chapter-06.section-01.item-02` | `cs408.co.chapter-06.section-01.item-02` | high | 带宽由总线宽度、时钟频率和每周期传输次数决定，突发传输只改变事务过程而不改变峰值计算框架。 |
| 21 | `cs408.co.chapter-06.section-03.item-02` | `cs408.co.chapter-06.section-03.item-02` | high | 中断屏蔽、断点和通用寄存器保存以及单重中断状态均属于程序中断方式及其中断响应。 |
| 22 | `cs408.co.chapter-06.section-03.item-04` | `cs408.co.chapter-06.section-03.item-04` | high | DMA 在设备接口与主存之间直接搬运数据，CPU 只负责初始化和收尾控制。 |
| 23 | `cs408.os.chapter-01.section-03.item-03`<br>`cs408.os.chapter-01.section-03.item-04` | `cs408.os.chapter-01.section-03.item-03` | medium | 判断同时涉及中断/异常进入内核态和系统调用对应内核服务，需并列覆盖两类程序运行机制。 |
| 24 | `cs408.os.chapter-02.section-01.item-01` | `cs408.os.chapter-02.section-01.item-01` | high | 进程终止时对子进程、设备、控制块和内存等资源的回收，属于进程基本管理。 |
| 25 | `cs408.os.chapter-02.section-02.item-07`<br>`cs408.os.chapter-03.section-01.detail-01.note-01` | `cs408.os.chapter-02.section-02.item-07` | medium | 进程切换保存恢复执行上下文，同时在页式管理下更新地址转换所需的页表基址。 |
| 26 | `cs408.os.chapter-04.section-03.item-03` | `cs408.os.chapter-04.section-03.item-03` | high | 比较位图、空闲表、成组链接和空闲链表的元数据规模，考查外存空闲空间管理方法。 |
| 27 | `cs408.os.chapter-03.section-01.item-03` | `cs408.os.chapter-03.section-01.item-03` | high | 伙伴算法按相等大小的伙伴块合并，属于连续内存分配与回收方法。 |
| 28 | `cs408.os.chapter-02.section-01.item-03` | `cs408.os.chapter-02.section-01.item-03` | high | 同一进程的线程共享地址空间和已打开文件描述符，但各自拥有独立栈，属于线程实现。 |
| 29 | `cs408.os.chapter-04.section-01.detail-03.note-01` | `cs408.os.chapter-04.section-01.detail-03.note-01` | high | 按文件名解析目录并建立打开文件引用发生在 open 操作，而非数据读写或关闭操作。 |
| 30 | `cs408.os.chapter-02.section-02.item-05` | `cs408.os.chapter-02.section-02.item-05` | high | 根据时间片轮转的队列次序、剩余 CPU 时间和完成时刻计算周转时间，属于 CPU 调度算法。 |
| 31 | `cs408.co.chapter-06.section-02.item-01` | `cs408.co.chapter-06.section-02.item-01` | medium | 键盘中断服务程序取得输入数据依赖设备接口中的数据寄存器，核心是 I/O 接口结构。 |
| 32 | `cs408.os.chapter-05.section-03.detail-01.note-01` | `cs408.os.chapter-05.section-03.detail-01.note-01` | high | 磁头按循环扫描方向访问请求并跨越端点回绕，直接对应磁盘调度方法。 |
| 33 | `cs408.cn.chapter-04.section-01.item-02` | `cs408.cn.chapter-04.section-01.item-02` | low | 吞吐量由从源到目的路径上的瓶颈链路决定，能归入网络层转发与路径选择；但节点表没有单列最大流/瓶颈吞吐量，因此降低置信度。 |
| 34 | `cs408.cn.chapter-02.section-01.item-03` | `cs408.cn.chapter-02.section-01.item-03` | high | 四种二进制调制方式中只有 FSK 以不同载波频率区分符号，属于编码与调制。 |
| 35 | `cs408.cn.chapter-03.section-06.item-04`<br>`cs408.cn.chapter-04.section-03.item-04` | `cs408.cn.chapter-03.section-06.item-04` | high | 主机是否处于同一 VLAN 决定二层广播域，ARP 表项又依赖同网段解析，需同时使用 VLAN 与 ARP 节点。 |
| 36 | `cs408.cn.chapter-03.section-06.item-03`<br>`cs408.cn.chapter-03.section-05.detail-03.note-01` | `cs408.cn.chapter-03.section-06.item-03` | high | NAV 计时来自 802.11 的 RTS/CTS 预约机制，基础访问规则属于 CSMA/CA。 |
| 37 | `cs408.cn.chapter-03.section-04.item-04` | `cs408.cn.chapter-03.section-04.item-04` | high | 发送窗口、接收窗口、序号和逐帧确认的行为是选择重传协议的典型机制。 |
| 38 | `cs408.cn.chapter-05.section-03.item-02`<br>`cs408.cn.chapter-05.section-03.item-03` | `cs408.cn.chapter-05.section-03.item-02` | medium | 总时间同时包含 TCP 建连、按 MSS 分段可靠传输、主动关闭和 TIME-WAIT 保持，需覆盖连接管理与可靠传输。 |
| 39 | `cs408.cn.chapter-05.section-02.item-02` | `cs408.cn.chapter-05.section-02.item-02` | high | 对 16 位字进行反码加法并取反得到结果，考查 UDP 校验和。 |
| 40 | `cs408.cn.chapter-06.section-05.item-02`<br>`cs408.cn.chapter-05.section-03.item-02` | `cs408.cn.chapter-06.section-05.item-02` | high | HTTP/1.0 非持久连接为页面及各对象重复建立 TCP 连接，核心是 HTTP 工作方式并依赖 TCP 连接管理。 |
| 41 | `cs408.ds.chapter-05.section-04.item-03` | `cs408.ds.chapter-05.section-04.item-03` | high | 唯一拓扑序列可由反复选择唯一入度为零顶点并删除其出边来判定，属于拓扑排序。 |
| 42 | `cs408.ds.chapter-06.section-07` | `cs408.ds.chapter-06.section-07` | high | 初始散列地址、二次探查序列、装填因子和失败地址均属于散列表及冲突处理。 |
| 43 | `cs408.co.chapter-05.section-03`<br>`cs408.co.chapter-04.section-02` | `cs408.co.chapter-05.section-03` | medium | 题目把寄存器字段、立即数扩展、ALU 控制、指令编码和 load 地址计算结合起来，分别落在数据通路与指令格式。 |
| 44 | `cs408.co.chapter-04.section-06`<br>`cs408.os.chapter-03.section-02.item-02` | `cs408.co.chapter-04.section-06` | medium | 指令序列映射变量和数组寻址依赖高级语言到机器代码的对应，跨页取数部分依赖请求分页管理。 |
| 45 | `cs408.os.chapter-03.section-02.item-02` | `cs408.os.chapter-03.section-02.item-02` | high | 虚拟页号、页内偏移、页表项和缺页分配的计算，直接对应请求分页管理。 |
| 46 | `cs408.os.chapter-02.section-03.item-07`<br>`cs408.os.chapter-02.section-03.item-05` | `cs408.os.chapter-02.section-03.item-07` | high | 有界缓冲区的空/满约束和对修改操作的互斥要求构成经典同步问题，wait/signal 实现使用信号量。 |
| 47 | `cs408.cn.chapter-04.section-05`<br>`cs408.cn.chapter-04.section-05.item-01` | `cs408.cn.chapter-04.section-05` | medium | 题目综合比较 AS 内部路由、RIP/OSPF 收敛及 BGP 会话和路径选择，路由协议总节是比硬塞单一协议 item 更自然的主节点，并辅以自治系统。 |

## 低置信度与疑难项

- 第 33 题为网络拓扑上的路径瓶颈吞吐量计算；TSV 没有单列最大流或瓶颈带宽节点，因此保守映射到网络层转发，并标为 low。该题不是因题干无法理解，而是节点粒度与考查表述不完全同构。
- 第 44 题同时覆盖机器代码/数组寻址和分页取数，选择高级语言到机器代码、请求分页两个节点，未再硬塞端序等旁支节点，标为 medium。
- 第 47 题把自治系统、RIP、OSPF、BGP 和路径选择放在同一综合场景中；用路由协议 section 作为主节点比任取单一协议 item 更能覆盖全题，辅以自治系统 item，标为 medium。

## null 与未覆盖项

本轮没有 null。逐题复核后，47 题均能在考纲树中找到至少一个自然归属；第 33 题虽存在节点粒度不完全匹配，但仍有网络层转发这一合理上位节点，未达到“疑似考纲外”的 null 条件。

## 独立性说明

以上判断按题目考查机制与节点语义独立作出，没有使用其他编码者的映射来回填或调整。
