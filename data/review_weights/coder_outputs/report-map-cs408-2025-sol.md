# 2025 年 408 真题知识树映射报告（sol）

## 结果摘要

- 编码范围：1–47，共 47 题，无缺号、无重复。
- 置信度：high 38，medium 9，low 0。
- null：0。当前 47 题均能在节点表中找到对应节点，无需标记“疑似考纲外”。
- 节点表：383 个节点；原始 CRLF 文件 SHA-256 为 `447b9f6280be38868ac18a8adec60895cdaca247b13246b1b46cdc6b8b1ad386`，按 LF 规范化后的 SHA-256 为 `23151e22cec17069b2dc682541a92391024ee9ff20d570ff9fc79afb342bc149`，后者与任务书给定值一致，JSON 的 `node_table_sha256` 使用规范化值。
- 映射原则：优先选能直接覆盖解题知识的最细节点；综合题保留多个必要节点，并指定最主要节点。

## 逐题映射

| 题号 | primary_node | 其他节点 | confidence | 判断依据 |
|---:|---|---|---|---|
| 1 | `cs408.ds.chapter-01.section-02` | — | high | 循环执行次数的求和用于判定渐进时间复杂度，属于算法复杂度分析。 |
| 2 | `cs408.ds.chapter-03.section-06` | — | high | 通过未配对定界符的最大嵌套深度判断栈容量是否足够，是栈的典型应用。 |
| 3 | `cs408.ds.chapter-04.section-02.item-02` | — | high | 需要检查数组位置与父结点位置的存在约束，直接考查二叉树的顺序存储。 |
| 4 | `cs408.ds.chapter-04.section-03.item-02` | — | high | 正确判断依赖森林按左孩子右兄弟规则转换为二叉树的性质。 |
| 5 | `cs408.ds.chapter-04.section-04.item-01` | — | high | 需按权值反复合并构造最优前缀树，再由叶结点深度统计编码长度。 |
| 6 | `cs408.ds.chapter-05.section-01` | — | high | 判断度数、环与有向图等基本性质，核心是图的基本概念。 |
| 7 | `cs408.ds.chapter-06.section-03` | — | high | 通过块数和块长共同决定的顺序比较次数求最优分块规模，直接对应分块查找。 |
| 8 | `cs408.ds.chapter-06.section-06` | — | high | 需要依据阶数、结点关键字上下限和树高枚举合法结构，属于 B 树基本操作与性质。 |
| 9 | `cs408.ds.chapter-06.section-07` | — | high | 比较开放定址冲突处理的探查覆盖范围及同义词关系，属于散列表。 |
| 10 | `cs408.ds.chapter-07.section-12` | — | medium | 题目横向比较多种内部排序在最坏情形下的移动代价，最贴近排序算法分析；节点表无独立的移动次数节点。 |
| 11 | `cs408.ds.chapter-07.section-06` | — | high | 相邻两趟呈现不同增量子序列分别有序的特征，可锁定希尔排序。 |
| 12 | `cs408.co.chapter-02.section-03.item-02` | `cs408.co.chapter-02.section-03.item-01` | medium | 求值依赖带符号数的补码、符号扩展以及转为无符号数后的解释；节点表未单列 C 类型转换。 |
| 13 | `cs408.co.chapter-02.section-04.detail-01.note-01` | — | high | 需拆分符号位、阶码和尾数并按偏置恢复数值，直接考查 IEEE 754。 |
| 14 | `cs408.co.chapter-02.section-02.detail-03.note-01` | `cs408.co.chapter-02.section-03.item-02` | high | 通过补码减法和最高两级进位关系判断结果及溢出标志，直接对应补码加减运算器。 |
| 15 | `cs408.co.chapter-04.section-04` | — | high | 结构体成员与数组元素地址计算同时依赖边界对齐和小端字节次序。 |
| 16 | `cs408.co.chapter-04.section-01` | `cs408.co.chapter-04.section-02` | medium | 需要区分软件可见的指令系统约定与微体系结构实现，定长格式又涉及指令格式；节点表未单列 ISA 边界。 |
| 17 | `cs408.co.chapter-04.section-05` | — | high | 判断精简指令集的控制实现、访存风格、流水化和参数传递特征，直接对应 RISC。 |
| 18 | `cs408.co.chapter-01.section-02.detail-01` | — | medium | 各判断都围绕 CPI、时钟周期及执行时间关系展开；Cache 和流水线只是这些性能量的影响因素。 |
| 19 | `cs408.co.chapter-05.section-03` | `cs408.co.chapter-05.section-04`<br>`cs408.co.chapter-05.section-06.item-03` | medium | 需辨析寄存器和数据通路组成，同时涉及控制器复杂度及流水线冒险，属于跨多个 CPU 子节点的综合判断。 |
| 20 | `cs408.co.chapter-06.section-01.item-02` | — | high | 由有效传输率和总线位宽计算带宽，直接考查总线性能指标。 |
| 21 | `cs408.co.chapter-06.section-03.item-04` | — | high | 依据设备数据传送规模与处理器干预成本判断直接存储器访问的适用对象。 |
| 22 | `cs408.co.chapter-05.section-05.item-02` | `cs408.co.chapter-06.section-03.item-04` | high | 关键是按事件来源区分外部中断与内部异常，直接存储器访问完成是用于判别的硬件事件。 |
| 23 | `cs408.os.chapter-02.section-02.item-07` | `cs408.os.chapter-03.section-01.item-04` | medium | 需区分进程私有执行现场、地址空间寄存器与全局内核状态，核心是上下文切换，页表寄存器是分页背景。 |
| 24 | `cs408.os.chapter-01.section-06` | — | high | 判断客户操作系统、虚拟机监控器、特权级和指令集仿真的关系，直接对应虚拟机。 |
| 25 | `cs408.os.chapter-02.section-02.item-05` | — | high | 就绪队列按优先权有序后，插入需定位而选取位于表头，考查优先级调度实现代价。 |
| 26 | `cs408.os.chapter-03.section-02.item-04` | — | high | 按最近最少使用次序逐次模拟驻留页集合并统计缺页，直接对应页置换算法。 |
| 27 | `cs408.os.chapter-03.section-02.item-03` | `cs408.co.chapter-04.section-03` | medium | 最少驻留页框数由一条指令可能同时访问的页面数约束，主节点是页框分配，判定依据来自寻址方式。 |
| 28 | `cs408.os.chapter-04.section-03.item-04` | — | high | 考查用统一抽象接口屏蔽本地或网络文件系统差异的机制，直接对应虚拟文件系统。 |
| 29 | `cs408.os.chapter-04.section-01.item-02` | `cs408.os.chapter-04.section-02.item-03` | high | 判断权限等元数据存于索引节点，而目录项记录名称和索引节点号，同时涉及目录建立项操作。 |
| 30 | `cs408.os.chapter-03.section-02.item-05` | `cs408.os.chapter-02.section-01.item-06` | medium | 核心是文件内容进入进程虚拟地址空间的映射语义，并可借共享映射完成进程间通信；题中磁盘块方向表述存在歧义。 |
| 31 | `cs408.os.chapter-04.section-03.item-03` | — | high | 需要识别能表示整个外存簇占用链与空闲状态的数据结构，直接对应外存空闲空间管理。 |
| 32 | `cs408.os.chapter-04.section-03.item-01` | — | medium | 逻辑块大小属于文件系统格式与总体布局，而物理扇区、机械寻道和闪存磨损均由更低层决定；节点表无独立逻辑格式化节点。 |
| 33 | `cs408.cn.chapter-02.section-01.item-04` | — | high | 需分别按建立开销、逐跳存储转发和流水化分组传输计算总时延，直接比较三种交换方式。 |
| 34 | `cs408.cn.chapter-03.section-03.item-01` | `cs408.cn.chapter-03.section-03.item-02` | high | 由码字最小海明距离同时推出可保证的检错位数和纠错位数，覆盖检错编码与纠错编码。 |
| 35 | `cs408.cn.chapter-03.section-05.detail-03.note-01` | — | high | 连续冲突后的最大等待由以太网二进制指数退避及时隙上限决定，直接对应 CSMA/CD。 |
| 36 | `cs408.cn.chapter-04.section-03.item-04` | — | high | 需判断尚未正式获得地址时请求报文采用的全网广播目的地址和未指定源地址，直接对应 DHCP。 |
| 37 | `cs408.cn.chapter-04.section-03.item-02` | `cs408.cn.chapter-05.section-02.item-02` | high | 端口复用的地址转换会改写源端口，并因伪首部与报文字段变化重算 UDP 校验和。 |
| 38 | `cs408.cn.chapter-05.section-03.item-04` | `cs408.cn.chapter-05.section-03.item-05` | high | 可继续发送量由接收窗口、拥塞窗口和在途未确认数据共同确定，覆盖 TCP 流量与拥塞控制。 |
| 39 | `cs408.cn.chapter-05.section-01.item-03` | `cs408.cn.chapter-05.section-03.item-02`<br>`cs408.cn.chapter-06.section-01.item-01` | high | 最少交互时延的差别来自无连接请求和面向连接传输的建连成本，客户服务器模型是应用背景。 |
| 40 | `cs408.cn.chapter-06.section-04.item-03` | — | high | 需区分邮件读取协议与发送协议的职责，并判断一次传输连接可完成的收取操作。 |
| 41 | `cs408.ds.chapter-03.section-06` | `cs408.ds.chapter-01.section-02` | high | 利用后缀最大值和最小值一次反向扫描完成逐元素计算，是数组应用；同时需给出复杂度分析。 |
| 42 | `cs408.ds.chapter-05.section-04.item-04` | — | high | 各问均需用事件最早和最迟发生时间求工期、关键活动、时差及压缩方案，直接对应关键路径。 |
| 43 | `cs408.co.chapter-03.section-06.item-02` | `cs408.co.chapter-03.section-06.item-01`<br>`cs408.co.chapter-03.section-07.item-02` | high | 组索引位与数组块分布依赖组相联映射，平均访存时间依赖命中机制，跨页分布和缺页次数涉及页式虚拟存储。 |
| 44 | `cs408.co.chapter-02.section-02.detail-05.note-01` | `cs408.co.chapter-05.section-05.item-03` | high | 需确定补码除法器各寄存器初值、加减控制和异常条件，并说明处理器的异常响应动作。 |
| 45 | `cs408.os.chapter-02.section-03.item-05` | `cs408.os.chapter-02.section-03.item-07` | high | 需要用计数与互斥信号量同时约束工序先后、未处理缓冲上限和共享工具，属于信号量经典同步设计。 |
| 46 | `cs408.os.chapter-01.section-03.item-06` | `cs408.os.chapter-02.section-01.item-02`<br>`cs408.os.chapter-05.section-01.item-05` | high | 主要判断代码、全局变量、局部变量与动态对象的地址空间区域，并结合输入等待状态和驱动程序层次。 |
| 47 | `cs408.cn.chapter-03.section-04.item-03` | `cs408.cn.chapter-04.section-03.item-03`<br>`cs408.cn.chapter-01.section-01.item-03` | high | 综合题分别用带宽时延关系、后退 N 帧窗口约束和变长子网划分求解，三个节点均有直接考查。 |

## 自检

- `entries` 数量严格为 47，题号严格为 1..47。
- 每条均包含 `number`、`nodes`、`primary_node`、`confidence`、`reason`。
- 所有非空节点 ID 均存在于指定 TSV；每个 `primary_node` 均包含在对应 `nodes` 中。
- `reason` 均为知识点判定依据，没有复制题干作为理由。
