# cs408 2023 题目节点映射报告（luna）

- 题目年份：2023
- 题目数量：47
- 节点表：`C:\Users\Lenovo\AppData\Local\Temp\kaoyan-probe\mapping\tasks\cs408_2023_nodes.tsv`
- 节点表实际 SHA-256：`447b9f6280be38868ac18a8adec60895cdaca247b13246b1b46cdc6b8b1ad386`
- 任务书声明 SHA-256：`23151e22cec17069b2dc682541a92391024ee9ff20d570ff9fc79afb342bc149`
- SHA-256 状态：不一致；本映射以实际读取并校验过的节点表为准，未修改节点表。
- 题源：`F:\workspace\kaoyan-ai-system\data\raw_materials\cs408\quiz_pages\cs408_quiz_2023.html`（只读）

## 完整性统计

- entries：47；number 覆盖 1..47 且无缺无重。
- confidence：high=42，medium=5，low=0。
- null：0。

## 逐题依据

| 题号 | primary_node | confidence | reason |
|---:|---|---|---|
| 1 | `cs408.ds.chapter-02.section-02.item-01` | high | 题目考查顺序存储下按下标直接访问的复杂度。 |
| 2 | `cs408.ds.chapter-02.section-02.item-02` | high | 题目要求维护双向链式结构的前驱和后继指针。 |
| 3 | `cs408.ds.chapter-03.section-05` | high | 三元组压缩表示稀疏矩阵时还需记录矩阵规模信息。 |
| 4 | `cs408.ds.chapter-04.section-04.item-01` | high | 题目依据字符频次构造 Huffman 树并计算加权路径长度。 |
| 5 | `cs408.ds.chapter-04.section-02.item-03` | high | 题目要求由二叉树后序序列恢复先序遍历结果。 |
| 6 | `cs408.ds.chapter-05.section-04.item-02` | high | 目标是单源最短路；等权图中 BFS 可实现该任务，最小生成树算法不对应此目标。 |
| 7 | `cs408.ds.chapter-06.section-06` | high | 题目比较 B 树插入、删除、查找及叶结点性质。 |
| 8 | `cs408.ds.chapter-06.section-04` | high | 题目要求计算有序表折半查找的最坏比较次数。 |
| 9 | `cs408.ds.chapter-06.section-07` | high | 题目围绕线性探测散列表删除后的失败查找长度。 |
| 10 | `cs408.ds.chapter-07.section-12` | high | 题目比较希尔、快速、堆和基数排序的稳定性，节点表没有单独的稳定性条目，归入排序分析与相关算法章节。 |
| 11 | `cs408.ds.chapter-07.section-07` | high | 一次快速排序划分后的两侧大小关系用于确定枢轴元素。 |
| 12 | `cs408.co.chapter-01.section-02.detail-01` | high | 题目联立主频、CPI、指令数和 CPU 时间计算性能指标。 |
| 13 | `cs408.co.chapter-02.section-03.item-02` | high | 题目把负整数转换为定长有符号整数的补码机器表示。 |
| 14 | `cs408.co.chapter-02.section-04.item-01` | high | 题目解析 IEEE 754 单精度的符号、阶码和尾数，包括非规格化数。 |
| 15 | `cs408.co.chapter-03.section-04.item-03` | high | 题目根据地址线数量、字节编址和主存芯片分区确定地址范围。 |
| 16 | `cs408.co.chapter-02.section-02.detail-03.note-01` | high | 题目区分补码减法中的溢出标志与借位标志。 |
| 17 | `cs408.co.chapter-04.section-03` | high | 题目依据操作码区分寄存器中保存的操作数及其地址。 |
| 18 | `cs408.co.chapter-05.section-03` | high | 题目区分数据通路中的组合逻辑部件和时序状态部件。 |
| 19 | `cs408.co.chapter-05.section-06.item-03` | high | 题目同时涉及数据冒险、装入使用冒险和控制冒险的处理。 |
| 20 | `cs408.co.chapter-06.section-01.item-02` | high | 题目由总线宽度、时钟周期、传输次数和主存响应时间计算块传送时间。 |
| 21 | `cs408.co.chapter-05.section-05` | high | 题目辨析异常检测、外部中断请求检查及中断响应信号的时机和含义。 |
| 22 | `cs408.co.chapter-06.section-03` | high | 题目比较程序查询、中断和 DMA 三种 I/O 控制方式。 |
| 23 | `cs408.os.chapter-01.section-04.detail-01` | high | 题目比较微内核与宏内核在可靠性、安全性和扩展性方面的结构性差异。 |
| 24 | `cs408.co.chapter-05.section-05.item-03` | medium | 中断向量表服务于中断响应入口的组织；节点表未提供 vector table 专属项，采用异常和中断响应节点。 |
| 25 | `cs408.os.chapter-03.section-02.item-03` | high | 题目计算页框数量对应的位图占用空间，属于页框分配与回收。 |
| 26 | `cs408.os.chapter-01.section-03.item-01` | high | 题目判断哪些处理会触发 CPU 从内核运行模式返回用户运行模式。 |
| 27 | `cs408.os.chapter-02.section-01.item-02` | high | 题目判断运行态线程在事件或操作作用下转为就绪态的状态转换。 |
| 28 | `cs408.os.chapter-03.section-02.item-01` | high | 题目考查虚拟内存进程地址空间与物理内存映射的基本关系。 |
| 29 | `cs408.os.chapter-02.section-02.item-05` | high | 题目按抢占式优先级调度轨迹计算周转时间，涉及调度算法和评价指标。 |
| 30 | `cs408.os.chapter-03.section-01.detail-01.note-01` | high | 题目比较不同进程页表中的虚拟页号与共享数据对应物理页框的关系。 |
| 31 | `cs408.os.chapter-04.section-01.item-02` | high | 题目考查文件关闭时内存中 inode 副本的释放，而非磁盘 inode 本身。 |
| 32 | `cs408.os.chapter-05.section-02.item-02` | high | 题目列举设备类型、权限、占用状态及逻辑到物理映射等分配依据。 |
| 33 | `cs408.cn.chapter-02.section-01.item-01` | medium | 题目综合链路带宽、传播时延、传输时延和分组转发，节点表中最细对应为信道与速率基本概念。 |
| 34 | `cs408.cn.chapter-02.section-01.item-02` | high | 题目先用奈奎斯特定理确定码元速率，再由每码元比特数确定 QAM 阶数。 |
| 35 | `cs408.cn.chapter-03.section-04.item-01` | high | 题目比较停等、GBN 与 SR 的窗口约束和信道利用率。 |
| 36 | `cs408.cn.chapter-03.section-05.detail-03.note-01` | high | 题目使用 CSMA/CD 的二进制指数退避计算冲突后的最长等待时间。 |
| 37 | `cs408.cn.chapter-03.section-03.item-01` | high | 题目通过生成多项式做模 2 除法以判断 CRC 检错结果。 |
| 38 | `cs408.cn.chapter-04.section-03.item-02` | high | 题目判断 NAT 转发后数据报源地址的转换结果。 |
| 39 | `cs408.cn.chapter-04.section-03.item-03` | high | 题目按 CIDR 前缀划分网络号和主机号并求可分配地址边界。 |
| 40 | `cs408.cn.chapter-04.section-04.item-01` | high | 题目综合 IPv6 地址空间、基本首部、过渡技术和 Hop-Limit 特性。 |
| 41 | `cs408.ds.chapter-05.section-02.item-01` | high | 题目用邻接矩阵的行列统计实现有向图顶点度数筛选。 |
| 42 | `cs408.ds.chapter-07.section-11` | high | 题目考查置换选择生成初始归并段及其长度范围。 |
| 43 | `cs408.co.chapter-03.section-07.item-02` | medium | 综合题同时覆盖分页虚拟存储、Cache 基本原理与映射；节点表没有将数组局部性单列，因此并列挂接相关节点。 |
| 44 | `cs408.co.chapter-04.section-03` | medium | 综合题覆盖分页缺页、指令格式、寻址方式及大小端，分别挂接对应章节节点。 |
| 45 | `cs408.os.chapter-02.section-03.item-04` | high | 题目要求用原子交换和锁实现临界区互斥，并判断函数调用能否替代原子指令。 |
| 46 | `cs408.os.chapter-01.section-03.item-04` | medium | 综合题串联系统调用返回、进程阻塞与唤醒、键盘中断处理以及内核/用户模式切换。 |
| 47 | `cs408.cn.chapter-06.section-03.item-01` | high | 综合题覆盖 FTP 控制/数据连接，以及 TCP 连接管理、可靠传输、流量控制和拥塞控制。 |

## 复核说明

题号 24、33、43、44、46 使用 medium：题目知识点属于 408 范围，但节点表没有完全同名的专属条目，或一题横跨多个章节，因此保留多个相关节点并降低置信度。
没有题目被判断为无法在考纲树中定位，故未使用 null；这不等同于节点表 SHA-256 与任务书声明一致。
