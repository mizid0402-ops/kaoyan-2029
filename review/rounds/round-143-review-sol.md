# 复审：G2b README（`ad3b78a`）与 G3b 测试（`95bbc1a`）

遵守 `AGENTS.md`（不跑全量；严重度按威胁模型，安全类单列）。各用对应提交的 `git archive`（补原始资料与 `products` 空目录；`git show` 基线用 `GIT_DIR`），只在你自己的临时目录运行。

1. **G2b `ad3b78a`**：你第 140 轮 M3（分类器产物被称作编码批次）、M4（索引归档理由里的 `paper_source`、英语一年份）。请核对 README 新写法与 `contracts/topic_weights.md`、实际脚本行为一致；"没有脚本生成编码员文档"是否属实。
2. **G3b `95bbc1a`**：你第 140 轮的必须改（漏掉的相邻段）。决策者另外发现测试辅助 `_with_value` 对列表下标用 `key not in node`（成员判断），所有改 `subjects[i]` 的变体原先都把整个科目换成了 `{}`——已修。
   请重放你 139 / 140 轮的全部调换变异（**设 `PYTHONDONTWRITEBYTECODE=1` 或每次清 `__pycache__`**：决策者的探针曾因改写后文件大小与秒级 mtime 不变而复用了旧 `.pyc`）；并查修复后的变体是否真按意图构造。

产物：`review/rounds/round-143-review-sol-out.md`，两包分节，"必须改 / 建议改 / 不改"附可复现输入，"安全登记"，各给 PASS / FAIL。只写这一个文件。
