# 第 265 轮：数学一考试要求条目拆分

本轮新增 123 个 `scope: item` 节点；知识树由 69 增至 192。仅拆分 22 章「考试要求」编号条目，保留父小节；「考试内容」不拆。所有新节点保持 `extracted`，未推进状态。

原始 69 节点构建器 `tools/build_math1_tree.py` 未纳入本轮允许修改范围，仍只生成旧骨架；不要用它覆盖本轮更新后的知识树。

来源为 2022 中国教育在线转录和 2026 新都转录；每条分别保存两源 SHA-256 与该源原文（空白归一后）的 `quote_ref`。两源各章编号条数相同，均合计 123。2022 第十二章第 1 条源编号为小写 `l.`，按第 258 轮报告已确认排版识别为第 1 条。

旧构建报告的 121/120 是排版计数；第 258 轮报告复核并更正为 123/123。以下是本树实际新增数量：

| 科目 / 章节 | 新增条目 |
|---|---:|
| 一、函数、极限、连续 (`math1.hs.ch01.chapter`) | 10 |
| 二、一元函数微分学 (`math1.hs.ch02.chapter`) | 9 |
| 三、一元函数积分学 (`math1.hs.ch03.chapter`) | 6 |
| 四、向量代数和空间解析几何 (`math1.hs.ch04.chapter`) | 9 |
| 五、多元函数微分学 (`math1.hs.ch05.chapter`) | 9 |
| 六、多元函数积分学 (`math1.hs.ch06.chapter`) | 8 |
| 七、无穷级数 (`math1.hs.ch07.chapter`) | 11 |
| 八、常微分方程 (`math1.hs.ch08.chapter`) | 9 |
| 一、行列式 (`math1.la.ch09.chapter`) | 2 |
| 二、矩阵 (`math1.la.ch10.chapter`) | 5 |
| 三、向量 (`math1.la.ch11.chapter`) | 8 |
| 四、线性方程组 (`math1.la.ch12.chapter`) | 5 |
| 五、矩阵的特征值和特征向量 (`math1.la.ch13.chapter`) | 3 |
| 六、二次型 (`math1.la.ch14.chapter`) | 3 |
| 一、随机事件和概率 (`math1.pr.ch15.chapter`) | 3 |
| 二、随机变量及其分布 (`math1.pr.ch16.chapter`) | 5 |
| 三、多维随机变量及其分布 (`math1.pr.ch17.chapter`) | 4 |
| 四、随机变量的数字特征 (`math1.pr.ch18.chapter`) | 2 |
| 五、大数定律和中心极限定理 (`math1.pr.ch19.chapter`) | 3 |
| 六、数理统计的基本概念 (`math1.pr.ch20.chapter`) | 3 |
| 七、参数估计 (`math1.pr.ch21.chapter`) | 4 |
| 八、假设检验 (`math1.pr.ch22.chapter`) | 2 |
| 合计 | 123 |

## 已确认的转录错字修正

- `math1.hs.ch07.requirements.item-07`：2026 转录 `幕级数` → `幂级数`，依据 2022 转录与第 258 轮报告。
- `math1.hs.ch07.requirements.item-08`：2026 转录 `幕级数` → `幂级数`，依据 2022 转录与第 258 轮报告。
- `math1.pr.ch17.requirements.item-04`：2026 转录 `稠` → `随机`，依据 2022 转录与第 258 轮报告。
- `math1.pr.ch19.requirements.item-02`：2026 转录 `伯努利大数定` → `伯努利大数定律`，依据 2022 转录与第 258 轮报告。
- `math1.pr.ch21.requirements.item-03`：2026 转录 `柑合性` → `相合性`，依据 2022 转录与第 258 轮报告。

## 已确认的考试要求变更

- `math1.pr.ch15.chapter.requirements.item-03`：2026 写法含「概率计算的方法」；第 258 轮报告确认 2025 起增加「的方法」，标题保留 2026 写法。

## 其他未确认差异

不据两份第三方转录推断官方增删；下列条目保留 2026 转录写法。定位只列节点 ID，不重复粘贴长段原文：
- `math1.hs.ch01.requirements.item-09`：两源措辞/标点或转录内容不同；保留 2026 写法。
- `math1.hs.ch01.requirements.item-10`：两源措辞/标点或转录内容不同；保留 2026 写法。
- `math1.hs.ch02.requirements.item-01`：两源措辞/标点或转录内容不同；保留 2026 写法。
- `math1.hs.ch02.requirements.item-08`：两源措辞/标点或转录内容不同；保留 2026 写法。
- `math1.hs.ch04.requirements.item-02`：两源措辞/标点或转录内容不同；保留 2026 写法。
- `math1.hs.ch04.requirements.item-05`：两源措辞/标点或转录内容不同；保留 2026 写法。
- `math1.hs.ch06.requirements.item-02`：两源措辞/标点或转录内容不同；保留 2026 写法。
- `math1.hs.ch06.requirements.item-06`：两源措辞/标点或转录内容不同；保留 2026 写法。
- `math1.hs.ch06.requirements.item-08`：两源措辞/标点或转录内容不同；保留 2026 写法。
- `math1.hs.ch07.requirements.item-02`：两源措辞/标点或转录内容不同；保留 2026 写法。
- `math1.hs.ch07.requirements.item-05`：两源措辞/标点或转录内容不同；保留 2026 写法。
- `math1.hs.ch07.requirements.item-10`：两源措辞/标点或转录内容不同；保留 2026 写法。
- `math1.hs.ch07.requirements.item-11`：两源措辞/标点或转录内容不同；保留 2026 写法。
- `math1.hs.ch08.requirements.item-04`：两源措辞/标点或转录内容不同；保留 2026 写法。
- `math1.la.ch09.requirements.item-01`：两源措辞/标点或转录内容不同；保留 2026 写法。
- `math1.la.ch10.requirements.item-02`：两源措辞/标点或转录内容不同；保留 2026 写法。
- `math1.pr.ch15.requirements.item-02`：两源措辞/标点或转录内容不同；保留 2026 写法。
- `math1.pr.ch15.requirements.item-03`：两源措辞/标点或转录内容不同；保留 2026 写法。
- `math1.pr.ch16.requirements.item-01`：两源措辞/标点或转录内容不同；保留 2026 写法。
- `math1.pr.ch16.requirements.item-02`：两源措辞/标点或转录内容不同；保留 2026 写法。
- `math1.pr.ch16.requirements.item-04`：两源措辞/标点或转录内容不同；保留 2026 写法。
- `math1.pr.ch17.requirements.item-03`：两源措辞/标点或转录内容不同；保留 2026 写法。
- `math1.pr.ch18.requirements.item-01`：两源措辞/标点或转录内容不同；保留 2026 写法。
- `math1.pr.ch19.requirements.item-03`：两源措辞/标点或转录内容不同；保留 2026 写法。
- `math1.pr.ch20.requirements.item-01`：两源措辞/标点或转录内容不同；保留 2026 写法。
- `math1.pr.ch20.requirements.item-02`：两源措辞/标点或转录内容不同；保留 2026 写法。

空白归一后有 31 个条目的两源文本不同；已确认错字修正 5 处，已确认考试要求变更 1 处，其余 25 处按 2026 写法保留。
