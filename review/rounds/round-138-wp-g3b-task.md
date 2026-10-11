# 任务书：WP-G3b 拆分 `validate_config` / `validate_review_item`（D7，`ky/models.py`）

你是固定窗口 `luna-a`，上一轮做了 G3a（拆 `load_workspace`，已提交 `0f9689d`）。本包同样是**行为逐字节不变**的拆分，照 G3a 的做法。
先读仓库根 `AGENTS.md`，再读 `ky/models.py`（`validate_config` 约 104 行、`validate_review_item` 约 88 行）、`contracts/review_progress.md`、`tests/test_contracts.py`、你上一轮的 `tests/contract/test_workspace_split_baseline.py`（对照测试写法照它）。

在主仓库 `F:\workspace\kaoyan-ai-system` 工作，**只改 `ky/models.py` 里这两个函数（拆出私有辅助函数），新增一个对照测试文件**。别的实现者可能同时在改 `ky/projection/`、`tools/`，不要碰。
不改公开接口、不改任何其他函数、不加兼容别名。

## 要做的

两个函数各自拆成按"一段校验一个函数"的私有辅助函数（例如配置：考试日期与科目、预算比例、复习策略、各科档案……；复习项：标识与科目、状态与日期、`schedule`、计数与自评……），
主函数只剩按原顺序依次调用。每个辅助函数一件事、不超过约 60 行、嵌套不超过三层。

**行为逐字节不变**：合法输入得到相等的结果对象；每种非法输入的异常类型、消息与路径完全相同；多处同时出错时先报的那一处不变。

## 测试（只写这一个）

`tests/contract/test_models_split_baseline.py`：`git show b97f3ac:ky/models.py` 取旧版（断言取到的是旧版，例如旧 `validate_config` 超过 90 行），作为独立模块加载；
以 `tests/fixtures/config/config-minimal.yaml` 与 `tests/fixtures/reviews/reviews-normal.yaml` 为种子，按规则生成变体（每个键缺失、类型错误、越界 / NaN / 布尔冒充整数、未知键、比例不闭合、日期先后颠倒、两处同时出错的组合……），
新旧各跑一遍比较结果或异常（类型、`str(exc)`、路径）。不写死科目名或数量。撤修改验证：对调某个辅助函数里两项检查的顺序 → 变红；报告写实际命令与结果。

## 顺带（sol 第 135 轮对你上一包 G3a 的建议）

`tests/contract/test_workspace_split_baseline.py` 的 55 个"非法变体"里有 3 个其实合法（`supplementary` / `products` / `settings` 本是可选顶层键）。
给每个变体标明预期"成功 / 失败"并断言新版结果符合预期（新旧对照照旧），这样以后某个非法样本意外变合法时测试会红。只改这个测试文件，不改 `ky/workspace.py`。
你本包新写的 `test_models_split_baseline.py` 也照此标明每个变体的预期。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.test_contracts tests.test_review_scheduler tests.contract.test_models_split_baseline tests.contract.test_workspace_split_baseline
```

## 报告

`review/rounds/round-138-wp-g3b-luna.md`：拆出的函数清单（名字、行数、职责）、变体类别与数目、撤修改验证、验收输出、建议。
写"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"。不提交。含中文的文件只用 `apply_patch` 编辑，写完查 `???`。
