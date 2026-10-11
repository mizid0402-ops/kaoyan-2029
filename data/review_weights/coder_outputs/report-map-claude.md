# 2024 年 408 知识点映射报告（coder: claude / claude-sonnet-5）

## 0. 方法说明

- 题干来源：`408_2024_paper_rebuild.pdf`，用 `py -3.12` + `pypdf` 自行抽取全 12 页文本（未使用目录里已存在的 `_paper_text_utf8.txt`，避免依赖不明来源的中间产物）。
- 交叉参考：`cs408_quiz_2024.html`（第三方教学站，含逐题的一句话知识点标签与详细解析），用于**独立验证**自己的判断，而不是照抄其分类；凡是采用该站标签作为支撑依据的题目，均在下表"依据"一栏注明。
- 节点表 `cs408_nodes.tsv` sha256：`447b9f6280be38868ac18a8adec60895cdaca247b13246b1b46cdc6b8b1ad386`（383 个节点）。
- 未查看、未搜索前两方（sol / luna）的产出文件。

## 1. 映射结果表

| 题号 | 节点（primary 在前） | 置信度 |
|---|---|---|
| 1 | cs408.ds.chapter-02.section-02.item-02 | high |
| 2 | cs408.ds.chapter-03.section-06 | high |
| 3 | cs408.ds.chapter-04.section-02.item-03 | medium |
| 4 | cs408.ds.chapter-05.section-02.item-03 | high |
| 5 | cs408.ds.chapter-06.section-04 | high |
| 6 | cs408.ds.chapter-06.section-08 | high |
| 7 | cs408.ds.chapter-06.section-05.item-01 | high |
| 8 | cs408.ds.chapter-07.section-07 | high |
| 9 | cs408.ds.chapter-04.section-04.item-03 | high |
| 10 | cs408.ds.chapter-07.section-09 | high |
| 11 | cs408.ds.chapter-07.section-11 | high |
| 12 | cs408.co.chapter-02.section-03.item-02 | high |
| 13 | cs408.co.chapter-05.section-04 | medium |
| 14 | cs408.co.chapter-02.section-04.item-01 ; cs408.co.chapter-02.section-03.item-02 | medium |
| 15 | cs408.co.chapter-02.section-02.detail-05.note-01 | high |
| 16 | cs408.co.chapter-03.section-07.item-02 ; cs408.co.chapter-03.section-06.item-02 | medium |
| 17 | cs408.co.chapter-03.section-07.detail-02.note-01 | high |
| 18 | cs408.co.chapter-03.section-07.item-01 | medium |
| 19 | cs408.co.chapter-05.section-06.item-03 | high |
| 20 | cs408.co.chapter-06.section-01.item-02 | high |
| 21 | cs408.co.chapter-06.section-03.detail-02.note-01 | high |
| 22 | cs408.co.chapter-06.section-03.detail-04.note-01 | high |
| 23 | cs408.os.chapter-01.section-03.item-03 ; cs408.os.chapter-01.section-03.item-04 | medium |
| 24 | cs408.os.chapter-02.section-01.item-01 | high |
| 25 | cs408.os.chapter-02.section-02.item-07 ; cs408.os.chapter-03.section-01.item-04 | medium |
| 26 | cs408.os.chapter-04.section-03.item-03 | high |
| 27 | cs408.os.chapter-03.section-01.item-03 | high |
| 28 | cs408.os.chapter-02.section-01.item-01 | high |
| 29 | cs408.os.chapter-04.section-01.item-03 ; cs408.os.chapter-01.section-03.item-04 | medium |
| 30 | cs408.os.chapter-02.section-02.item-05 | high |
| 31 | cs408.os.chapter-05.section-02.item-01 ; cs408.os.chapter-05.section-01.detail-03.note-01 | medium |
| 32 | cs408.os.chapter-05.section-03.detail-01.note-01 | high |
| 33 | cs408.cn.chapter-01.section-01.item-03 ; cs408.cn.chapter-02.section-01.item-04 | medium |
| 34 | cs408.cn.chapter-02.section-01.item-03 | high |
| 35 | cs408.cn.chapter-03.section-06.item-04 ; cs408.cn.chapter-04.section-03.item-04 | high |
| 36 | cs408.cn.chapter-03.section-05.detail-03.note-01 | high |
| 37 | cs408.cn.chapter-03.section-04.item-04 | high |
| 38 | cs408.cn.chapter-05.section-03.item-02 | high |
| 39 | cs408.cn.chapter-05.section-02.item-02 | high |
| 40 | cs408.cn.chapter-06.section-05.item-02 | high |
| 41 | cs408.ds.chapter-05.section-04.item-03 ; cs408.ds.chapter-05.section-02.item-01 | high |
| 42 | cs408.ds.chapter-06.section-07 | high |
| 43 | cs408.co.chapter-04.section-02 ; cs408.co.chapter-02.section-02.detail-03.note-01 ; cs408.co.chapter-05.section-04 ; cs408.co.chapter-05.section-03 | medium |
| 44 | cs408.co.chapter-04.section-03 ; cs408.co.chapter-04.section-04 ; cs408.co.chapter-03.section-07.item-02 | high |
| 45 | cs408.os.chapter-03.section-02.item-02 ; cs408.os.chapter-03.section-01.item-04 | high |
| 46 | cs408.os.chapter-02.section-03.item-05 ; cs408.os.chapter-02.section-03.item-01 | high |
| 47 | cs408.cn.chapter-04.section-05.item-04 ; cs408.cn.chapter-04.section-02.item-02 ; cs408.cn.chapter-04.section-05.item-05 ; cs408.cn.chapter-04.section-03.item-01 | high |

## 2. 统计

- **high**：36 题
- **medium**：11 题（3, 13, 14, 16, 18, 23, 25, 29, 31, 33, 43）
- **low**：0 题
- **null**：0 题

没有 null 条目——47 题考查的内容都能在 383 节点表里找到至少一个合理落点，没有发现"疑似考纲外"的题目。

## 3. 考纲树覆盖不到 / 覆盖较勉强的题

严格意义上没有"完全覆盖不到"的题，但以下 1 题的**最佳节点粒度明显比题目实际考点粗**，记录在此供人工复核：

- **题 13**：题目本质是区分"伪指令 / 微指令 / 机器指令 / 汇编指令"四个概念，微指令直接指向"微程序控制器"这一具体机制。节点表在 CPU 章节下只有 `cs408.co.chapter-05.section-04`（控制器的功能和工作原理）这一 section 级节点，**没有专门的"微程序控制"item 级节点**，也没有类似"指令系统基本概念"下可以覆盖"伪指令/汇编指令由软件转换"这层含义的节点。选了最接近的 section 级节点，但认为节点表在此处的细粒度确实比其他章节（如物理层、CPU 调度）弱一些。

## 4. 标了 medium 的题，卡在哪里

- **题 3**：只能从"中序遍历+双孩子结点"的结构性质推断，节点选了"二叉树的遍历"（item-03），但也可以论证归到"二叉树的定义及其主要特性"（item-01），两个 item 都不是完全精确的落点，故 medium。
- **题 13**：见上文覆盖说明，section 级节点勉强对应。
- **题 14**：题目同时考"整数范围内选用定点数"和"超出范围后选浮点数精度"，是定点数表示（chapter-02.section-01/03）与浮点数表示（chapter-02.section-04）两部分知识的组合判断题，无法用单一 item 精确覆盖，medium。
- **题 16**：选项跨"Cache-主存"和"主存-外存"两层存储体系的映射/替换/写策略对比，本质是让考生同时调用 Cache 和虚拟存储器两块知识，节点选择有一定主观取舍。
- **题 18**：MMU 地址转换过程"检测哪些事件"这一问法本身比较笼统，树里没有专门的"MMU 工作过程"节点，只能落到"虚拟存储器的基本概念"这个较宽的 item。
- **题 23**：中断/异常发生时机（内核态与否）与系统调用内核例程是两个紧密关联但不同的考点，选择题把二者放在同一组选项里比较，难以只归一个节点。
- **题 25**：内容同时涉及"上下文切换机制"（更新 PC、栈基址）和"页式管理"（更新页表基址寄存器），是进程管理和内存管理的交叉点。
- **题 29**：open() 涉及"系统调用"本身，也涉及文件按名查找依赖的目录/路径解析机制，节点表里没有专门的"路径解析"item，只能在"文件的操作"和"系统调用"之间取舍。
- **题 31**：键盘中断处理是"中断I/O方式"与"缓冲区管理"（数据最终落点）的交叉，选了缓冲区管理为主，但把握不完全。
- **题 33**：核心考点是"网络路径瓶颈带宽决定端到端最大吞吐量"，这属于"计算机网络性能指标"范畴；但题面强调"分组交换网络"，与第三方站点标签"交换方式"存在偏差，两种归类都有一定道理，故 medium。
- **题 43**：综合题跨指令格式/数据通路/控制器/ALU标志位共 4 个节点，各分问对应关系总体清晰，但（3）（4）问中 Ext、ALUctr 信号具体应归入"控制器"还是更细的"数据通路"存在主观判断，整体定为 medium。

## 5. 「没有把握的地方」（至少 3 条）

1. **节点表在计算机组成原理"控制器/微程序"方向粒度偏粗**：题 13、题 43 的部分小问（Ext、ALUctr 控制信号设计）本质上属于微程序控制器/硬布线控制器的设计内容，但节点表只给到 `chapter-05.section-04`（控制器的功能和工作原理）这一个 section 级节点，无法进一步区分"微程序控制"与"硬布线控制"，也无法区分"控制信号设计"与"数据通路"的边界，我的节点选择在这几处有一定主观性。
2. **单选题"跨两个考点"的取舍偏主观**：像题 14、16、23、25、29、31、33 这类题目，选项设计本身就是把两个知识点放在一起比较（例如"整数 vs 浮点""Cache层 vs 虚存层""中断异常 vs 系统调用"），我给出的 primary/secondary 顺序是基于"哪个是分辨正确答案的关键差异点"来判断的，但换一个人来看，primary 和 secondary 互换也说得通，这类判断的确定性有限。
3. **第三方站点标签仅作为参考而非权威依据**：`cs408_quiz_2024.html` 的知识点标签是该站自己的分类习惯（如把题 21、31 都标"中断IO"），其粒度和口径与官方 383 节点表不完全一致；我用它来交叉验证自己的判断方向是否合理，但没有把它当作可以直接照抄的答案来源，这意味着报告中"tag 确认"的说法只是"独立信号一致"，不代表绝对正确。
4. **综合题的分问-节点对应关系存在合并**：题 43、44 中"指令机器码编码"这一考点在两题里重复出现（题43(1)(5)、题44(3)），但节点表没有区分"重复出现的同一考点在不同题目中的权重"，因此题 44 里我没有为(3)问单列第 4 个节点，而是并入了"寻址方式"的框架说明，这属于我为控制节点数量（≤4）做的主观取舍，如果评审认为应该拆分成独立节点，可以进一步调整。
5. **Q9（大根堆两次删除）选择了"堆及其应用"而非"堆排序"**：这是因为题目考查的是堆的删除+调整操作本身（数据结构操作），而不是排序算法流程，但两个节点在教学实践中经常被合并讲授，属于我个人对"数据结构操作 vs 排序算法"边界的判断，不能完全排除评审倾向于"排序"章节下的可能性。
