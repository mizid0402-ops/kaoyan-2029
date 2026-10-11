# 评审任务书：技术债包 B 再返工（第 207 轮，窗口 `sol61-main`，续你第 206 轮）

请复审 `luna-a` 第 207 轮：任务书 `review/rounds/round-207-baseline-harness-gaps2-task.md`，报告 `review/rounds/round-207-baseline-harness-gaps2-luna.md`，
你上一轮 `review/rounds/round-206-baseline-harness-gaps-review-sol61.md`。范围：第 207 轮对 `tests/` 的新增 / 修改。

## 重点看

1. R1、R3、m1、m2：是否按你第 206 轮的修法落实，诊断断言能挡住"被前置错误提前挡住"的假通过。
2. R2：实现者给的是**按生成规则归并**的映射表，并自报"不是每个原变体实例都已独立重建"。请按你第 206 轮的标准判断：
   映射表里指向的现存测试是否对**同类输入**给出**同一成功 / 拒绝期望**。抽查每一类（config 类型 / 范围 / 结构、review 必填 / 类型 / 值、schedule、workspace 顶层块），
   对真正缺等价的具体变体列必须改；只是"首错次序只在新旧对比时才有意义"的，接受退役。
3. 实现者的变异是在测试侧 patch 被测函数（而不是改 `ky/` 源码的临时副本）。判断这种变异是否足以证明断言有效；
   workspace 顶层块缺失与 M2 诊断断言未做变异——请你自己在临时 `ky/` 副本里各做一处。
4. 仓库里没有遗留临时探针文件。

## 规则

只跑与结论直接相关的单个模块或单条命令，**不跑全量**；复现用系统临时目录。结论 PASS / FAIL，分"必须改 / 建议改 / 不改"。

## 报告

`review/rounds/round-208-baseline-harness-gaps2-review-sol61.md`。
