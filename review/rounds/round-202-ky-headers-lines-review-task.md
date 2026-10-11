# 评审任务书：技术债包 D（第 201 轮，窗口 `sol61-main`）

请评审 `luna-c` 第 201 轮：任务书 `review/rounds/round-201-ky-headers-lines-task.md`，报告 `review/rounds/round-201-ky-headers-lines-luna.md`。
背景：`docs/技术债与整改清单.md` P0-5、P1-4、P2-4 与 §9。

**范围只有 `ky/`**：`git diff f52b8f6 -- ky` 与新增 `ky/exam/__init__.py`。工作区里 `tests/` 的改动是另一个窗口（包 B）在做，**不在范围**。

## 重点看

1. **行为不变**：对每个改动文件，自己比较 `git show f52b8f6:<文件>` 与当前文件去掉 docstring 后的 AST（`include_attributes=False`）；
   另外核对**被改动的 docstring 里有没有运行时会读到的**（例如 `argparse` 的 `description=__doc__`、`-h` 输出、`MonthClose.utilisation` 这类 docstring
   是否被任何代码当值使用）——这类 docstring 的改动会改变输出，不能用"去 docstring 的 AST 相同"放过。
2. `ky/exam/__init__.py` 把命名空间包变成普通包：有没有任何导入路径、`pkgutil` / 相对导入、或测试依赖命名空间包行为而因此改变。
3. 25 份规格的反向引用是否落在**正确的**实现模块（对照 `docs/模块地图.md`），不是随手塞进一个文件。
4. 折行后可读性：有没有为压到 100 字符而把一个表达式拆得更难读（`AGENTS.md`"不要把多个步骤塞进一行"的反面）。

## 规则

只跑与结论直接相关的单个模块或单条命令，**不跑全量**；复现用系统临时目录。结论 PASS / FAIL，分"必须改 / 建议改 / 不改"。

## 报告

`review/rounds/round-202-ky-headers-lines-review-sol61.md`。
