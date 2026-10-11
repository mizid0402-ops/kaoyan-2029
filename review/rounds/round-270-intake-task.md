# 第 270 轮任务书：M32 学完入队 `ky learn`（gpt-6-luna，luna-b 新会话）

## 先读

`AGENTS.md`；规格 `contracts/review_intake.md`（本包唯一依据）；sol 第 269 轮初检 `review/rounds/round-269-intake-spec-review-sol61.md`（必须改已改进规格，以规格为准）。
现有实现：`ky/models.py`（`ReviewItem`、`validate_review_item`）、`ky/storage/review_shards.py`（读用 `read_state_sources().items`——`load()` 在空队列时报错；写用 `write()`）、`ky/knowledge/hierarchy.py`（`learnable_tree`）、
`ky/__main__.py`（子命令注册方式、`--workspace` / 配置取法照 `ky review-questions`）。

## 工作区与并行

主仓库 master 当前提交之上。luna-a 同时在改 `ky/question_bank/` 与 `ky/__main__.py` 里 `question-bank` / `review-questions` 两处（标记坏题）。
你在 `ky/__main__.py` **只新增** `learn` 子命令的注册与入口函数，放在文件里与 `question_bank_main` 不相邻的位置，不改其他命令；不改 README、`docs/模块地图.md`（决策者统一改）。

## 要做的

1. 新包 `ky/review_intake/`：纯函数 `new_review_items(points, grammar, existing_items, knowledge_point_ids | leaves_under, day, minutes)` 按规格 §2–§3 产出新复习项与"跳过"清单；常量 `DEFAULT_REVIEW_MINUTES = 5`；模块头写 M32、规格、对外接口。
2. `ky learn` CLI（规格 §1、§4）：读配置、注册表、知识树、当前队列各一次；校验全过后一次 `ReviewShardStore.write()`；`--dry-run` 零写入。

## 不做的

不改 M9 / M10 / 队列存储格式 / 既有命令输出；不读 `data/personal/`；测试一律用临时工作区。

## 测试（只写这些，`tests/contract/test_review_intake_port.py`）

- 空队列（目录不存在）首次 `learn` 建出合法复习项，字段逐一断言（§3 表）；次日到期。
- 重复入队、跟踪节点、未登记树、未在考科目、同命令重复 ID → 对应退出码且队列字节不变。
- `--leaves-under`：只建可学叶子、已在队列的跳过并列出、结果为空 → 退出 2。
- `review_id` 被 `retired` 旧项占用时用 `-2`。
- `--dry-run` 零写入；新项能被 `ky review-questions` 读到（`learned` 档）。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.contract.test_review_intake_port tests.test_cli
```

报告 `review/rounds/round-270-intake-luna.md`：改动、做法、测试输出原文、"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"、歧义与选择。
不提交；中文字符串写字面量；含中文的文件只用 `apply_patch`；写完 `rg -n '\?\?\?'` 检查；保持 LF 换行。
