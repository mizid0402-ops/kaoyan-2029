# 2023 年 408 试题知识树映射报告（sol）

## 汇总

- 编码完成：47/47
- confidence：high 46，medium 1，low 0
- primary_node 为 null：0
- 节点表记录数：383
- 节点表任务书哈希（LF 规范化）：`23151e22cec17069b2dc682541a92391024ee9ff20d570ff9fc79afb342bc149`
- 节点表当前原始字节哈希（CRLF）：`447b9f6280be38868ac18a8adec60895cdaca247b13246b1b46cdc6b8b1ad386`

任务书给出的 SHA-256 与当前文件按 LF 规范化后的内容一致；原始字节哈希不同仅由 CRLF 换行造成。所有非空节点均经指定 TSV 集合校验。

## 逐题映射

| 题号 | primary_node | 其他节点 | confidence | 判断依据 |
|---:|---|---|---|---|
| 1 | `cs408.ds.chapter-02.section-02.item-01`（顺序存储） | — | high | 关键在连续地址支持按下标直接定位，属于顺序表的随机存取性质。 |
| 2 | `cs408.ds.chapter-02.section-02.item-02`（链式存储） | — | high | 需要维护双向链结点的前驱、后继指针关系，是链式存储中的插入操作。 |
| 3 | `cs408.ds.chapter-03.section-05`（（五）特殊矩阵的压缩存储） | — | high | 三元组表示稀疏矩阵时还须记录矩阵维度，属于特殊矩阵的压缩存储。 |
| 4 | `cs408.ds.chapter-04.section-04.item-01`（哈夫曼（Huffman）树和哈夫曼编码） | — | high | 需按频次合并结点并由编码长度计算带权平均值，直接考查哈夫曼树与编码。 |
| 5 | `cs408.ds.chapter-04.section-02.item-03`（二叉树的遍历） | — | high | 依据树形和后序序列恢复根与子树次序，再写出先序结果，核心是二叉树遍历。 |
| 6 | `cs408.ds.chapter-05.section-04.item-02`（最短路径） | `cs408.ds.chapter-05.section-03.item-02`（广度优先搜索） | high | 无权图按层扩展时首次到达即得到最少边数路径，连接了广度优先搜索与最短路径。 |
| 7 | `cs408.ds.chapter-06.section-06`（（六）B 树及其基本操作、B+ 树的基本概念） | — | high | 判断关键字插入、删除和查找对层次及叶结点的影响，属于 B 树基本操作。 |
| 8 | `cs408.ds.chapter-06.section-04`（（四）折半查找法） | — | high | 最大比较次数由有序表规模对应的判定树高度确定，考查折半查找。 |
| 9 | `cs408.ds.chapter-06.section-07`（（七）散列（hash）表） | `cs408.ds.chapter-06.section-09`（（九）查找算法的分析及应用） | high | 需要模拟线性探测及删除标记，并统计失败查找长度，核心是散列表。 |
| 10 | `cs408.ds.chapter-07.section-12`（（十二）排序算法的分析与应用） | `cs408.ds.chapter-07.section-06`（（六）希尔排序（shell sort））<br>`cs408.ds.chapter-07.section-07`（（七）快速排序）<br>`cs408.ds.chapter-07.section-08`（（八）堆排序）<br>`cs408.ds.chapter-07.section-09`（（九）二路归并排序（merge sort））<br>`cs408.ds.chapter-07.section-10`（（十）基数排序） | high | 通过相等关键字的相对次序是否保持来比较多种排序方法，属于排序算法性质分析。 |
| 11 | `cs408.ds.chapter-07.section-07`（（七）快速排序） | — | high | 枢轴应满足划分后左侧均不大于它、右侧均不小于它，是快速排序的一趟划分。 |
| 12 | `cs408.co.chapter-01.section-02.detail-01`（吞吐量、响应时间；CPU 时钟周期、主频、CPI、CPU 执行时间；MIPS、MFLOPS、GFLOPS、TFLOPS、PFLOPS、EFLOPS、ZFLOPS。） | — | high | 由主频和平均 CPI 求指令吞吐率，再由指令数换算执行时间，直接对应性能指标。 |
| 13 | `cs408.co.chapter-02.section-03.item-02`（带符号整数的表示和运算） | — | high | 把负整数转换为固定字长补码，属于带符号整数的机器表示。 |
| 14 | `cs408.co.chapter-02.section-04.detail-01.note-01`（IEEE 754 标准。） | — | high | 需拆分符号位、阶码和尾数并识别非规格化数，直接使用 IEEE 754 规则。 |
| 15 | `cs408.co.chapter-03.section-04.item-03`（主存和 CPU 之间的连接） | — | high | 根据地址线容量和 RAM/ROM 分区比例确定高地址译码范围，属于主存与 CPU 连接。 |
| 16 | `cs408.co.chapter-02.section-02.detail-03.note-01`（补码加/减运算器，标志位的生成。） | — | high | 分别按有符号溢出和无符号借位规则判断减法标志，核心是补码加减器的标志生成。 |
| 17 | `cs408.co.chapter-04.section-03`（（三）寻址方式） | — | high | 寄存器内容被解释为数据还是地址由指令中的寻址方式字段决定。 |
| 18 | `cs408.co.chapter-05.section-03`（（三）数据通路的功能和基本结构） | — | high | 区分组合逻辑操作部件与保存状态的时序部件，属于数据通路结构。 |
| 19 | `cs408.co.chapter-05.section-06.item-03`（结构冒险、数据冒险和控制冒险的处理） | — | high | 需要识别装入后使用的数据相关和分支控制相关，并判断转发后仍需停顿的位置。 |
| 20 | `cs408.co.chapter-06.section-01.item-03`（总线事务和定时） | `cs408.co.chapter-06.section-01.item-02`（总线的组成及性能指标） | high | 由总线宽度、周期、存储器准备时间和非突发事务次数累计块传送耗时。 |
| 21 | `cs408.co.chapter-05.section-05.item-03`（异常和中断的检测与响应） | — | high | 考点是异常在指令内部检测、外部中断在指令边界检测及请求响应的硬件流程。 |
| 22 | `cs408.co.chapter-06.section-03.item-04`（DMA 方式） | `cs408.co.chapter-06.section-03.item-01`（程序查询方式）<br>`cs408.co.chapter-06.section-03.item-02`（程序中断方式） | high | 通过比较查询、中断和 DMA 中 CPU 与控制器的职责，关键错误落在 DMA 传送机制。 |
| 23 | `cs408.os.chapter-01.section-04.detail-01`（分层，模块化，宏内核，微内核，外核。） | — | high | 可靠性、安全性、扩展性及通信开销的权衡是微内核与宏内核结构比较。 |
| 24 | `cs408.os.chapter-01.section-03.item-03`（中断和异常的处理） | — | medium | 中断号到处理入口需要固定下标快速定位；节点表未单列向量表，归入中断和异常处理最贴近。 |
| 25 | `cs408.os.chapter-03.section-02.item-03`（页框分配与回收） | — | high | 按物理页框总数为每个页框设置一个状态位，属于页框分配与回收的数据结构。 |
| 26 | `cs408.os.chapter-01.section-03.item-04`（系统调用） | `cs408.os.chapter-01.section-03.detail-01.note-01`（内核模式，用户模式。）<br>`cs408.os.chapter-01.section-03.item-01`（CPU 运行模式） | high | 系统调用服务结束后恢复用户程序执行，涉及系统调用返回与 CPU 运行模式切换。 |
| 27 | `cs408.os.chapter-02.section-01.item-02`（进程/线程的状态与转换） | — | high | 主动放弃处理器会把当前线程重新置入可运行集合，直接考查线程状态转换。 |
| 28 | `cs408.os.chapter-01.section-03.item-06`（程序运行时的内存映像与地址空间） | `cs408.os.chapter-03.section-02.item-01`（虚拟内存的基本概念） | high | 判断独立地址空间、虚拟地址返回值、段权限以及地址宽度来源，核心是进程内存映像与虚拟地址空间。 |
| 29 | `cs408.os.chapter-02.section-02.item-05`（CPU 调度算法） | `cs408.os.chapter-02.section-02.item-02`（调度的目标） | high | 按到达时刻和动态抢占顺序排出运行区间，再用完成时刻计算平均周转时间。 |
| 30 | `cs408.os.chapter-03.section-01.detail-01.note-01`（逻辑地址空间与物理地址空间，地址变换，内存共享，内存保护，内存分配与回收。） | — | high | 共享页可在不同进程中使用不同虚拟页号，但必须映射到同一物理页框。 |
| 31 | `cs408.os.chapter-04.section-01.item-02`（文件元数据和索引节点（inode）） | `cs408.os.chapter-04.section-01.item-03`（文件的操作） | high | 最后一个打开者关闭文件时处理的是内存中的索引节点引用，而非删除目录项或磁盘元数据。 |
| 32 | `cs408.os.chapter-05.section-02.item-02`（设备分配与回收） | — | high | 设备类型、权限、占用状态及逻辑到物理映射都属于设备分配决策信息。 |
| 33 | `cs408.cn.chapter-01.section-01.item-03`（计算机网络的主要性能指标） | `cs408.cn.chapter-02.section-01.item-04`（电路交换、报文交换与分组交换） | high | 将分组序列化、两段传播和路由器存储转发形成的流水时间相加，属于网络时延性能计算。 |
| 34 | `cs408.cn.chapter-02.section-01.item-02`（奈奎斯特定理与香农定理） | `cs408.cn.chapter-02.section-01.item-03`（编码与调制） | high | 先用理想信道极限求每码元比特数，再换算 QAM 状态数，结合奈奎斯特定理与调制。 |
| 35 | `cs408.cn.chapter-03.section-04.item-01`（流量控制、可靠传输与滑动窗口机制） | `cs408.cn.chapter-03.section-04.item-02`（停止-等待协议）<br>`cs408.cn.chapter-03.section-04.item-03`（后退 N 帧协议（GBN））<br>`cs408.cn.chapter-03.section-04.item-04`（选择重传协议（SR）） | high | 信道利用率上限取决于协议窗口规模，而序号位数分别约束 GBN 与 SR 的最大窗口。 |
| 36 | `cs408.cn.chapter-03.section-05.detail-03.note-01`（ALOHA 协议，CSMA 协议，CSMA/CD 协议，CSMA/CA 协议。） | — | high | 连续冲突次数确定随机退避槽上界，再乘争用时间片，属于 CSMA/CD 的指数退避。 |
| 37 | `cs408.cn.chapter-03.section-03.item-01`（检错编码） | — | high | 对接收比特串作生成多项式的模二除法，以余数是否为零完成 CRC 检错判断。 |
| 38 | `cs408.cn.chapter-04.section-03.item-02`（IPv4 地址与 NAT） | `cs408.cn.chapter-04.section-03.item-03`（子网划分、路由聚集、子网掩码与 CIDR） | high | 出口路由器把内部源地址替换为外侧接口可用地址，并需依据前缀长度排除网络与广播地址。 |
| 39 | `cs408.cn.chapter-04.section-03.item-03`（子网划分、路由聚集、子网掩码与 CIDR） | — | high | 由前缀长度求网络边界，再去除网络地址和广播地址得到可分配范围。 |
| 40 | `cs408.cn.chapter-04.section-04.item-01`（IPv6 的主要特点） | `cs408.cn.chapter-04.section-03.item-01`（IPv4 分组） | high | 比较两代 IP 的地址规模、基本首部、过渡方案和跳数限制，核心是 IPv6 主要特点。 |
| 41 | `cs408.ds.chapter-05.section-02.item-01`（邻接矩阵） | — | high | 有向图矩阵的一行和一列分别可累计出度与入度，算法直接建立在邻接矩阵表示上。 |
| 42 | `cs408.ds.chapter-07.section-11`（（十一）外部排序） | — | high | 利用工作区按置换选择规则生成长度可变的初始归并段，是外部排序的归并准备过程。 |
| 43 | `cs408.co.chapter-03.section-06.item-01`（Cache 的基本原理） | `cs408.co.chapter-03.section-06.item-02`（Cache 和主存之间的映射方式）<br>`cs408.co.chapter-03.section-07.item-02`（页式虚拟存储器） | high | 综合计算数组跨页、缺页、块内偏移、组索引及两种访问次序下的命中率，覆盖页式虚存与 Cache。 |
| 44 | `cs408.co.chapter-04.section-03`（（三）寻址方式） | `cs408.co.chapter-03.section-07.item-02`（页式虚拟存储器）<br>`cs408.co.chapter-04.section-04`（（四）数据的对齐和大/小端存放方式）<br>`cs408.co.chapter-04.section-06.item-03`（循环结构语句的机器级表示） | high | 从机器码长度与位移求跳转目标，辨认立即和变址成分、字节序，并结合指令页驻留判断缺页。 |
| 45 | `cs408.os.chapter-02.section-03.item-02`（基本的实现方法） | `cs408.os.chapter-02.section-03.detail-02.note-01`（软件方法，硬件方法。） | high | 互斥成立依赖交换指令的原子性、忙等条件和正确释放；普通函数的多步读写不能替代原子操作。 |
| 46 | `cs408.os.chapter-05.section-01.item-05`（I/O 软件层次结构） | `cs408.os.chapter-01.section-03.detail-01.note-01`（内核模式，用户模式。）<br>`cs408.os.chapter-01.section-03.item-03`（中断和异常的处理）<br>`cs408.os.chapter-02.section-01.item-02`（进程/线程的状态与转换）<br>`cs408.os.chapter-02.section-02.item-03`（调度的实现） | high | 键盘输入路径贯穿阻塞与唤醒、中断处理、调度、驱动程序层次以及内核态执行。 |
| 47 | `cs408.cn.chapter-05.section-03.item-02`（TCP 连接管理） | `cs408.cn.chapter-05.section-03.item-01`（TCP 段）<br>`cs408.cn.chapter-05.section-03.item-05`（TCP 拥塞控制）<br>`cs408.cn.chapter-06.section-03.item-02`（控制连接与数据连接） | high | 上传过程同时涉及 FTP 双连接、TCP 序号与挥手、拥塞窗口增长和按 RTT 计算完成时间。 |
