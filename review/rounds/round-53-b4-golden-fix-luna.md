# Round 53：B′4 新旧输出对照测试修复

## 修改

- `tests/test_cs408_lecture_pipeline.py` 将旧工具来源固定为 `762786f`，并确认源码包含迁移前的绝对根路径。注释说明 `HEAD` 会随 worktree 指向变化，不能作为稳定旧版基线。
- 新旧输出比较按字节执行：CSV/JSON 只删除 `is_effective`、`view_name` 后比较；manifest 只删除 `supplementary_view` 属性，并断言新增顶层键集合及其三个字段集合精确；其他文件集合必须相同，新增文件允许清单当前为空。
- 大纲与讲解单元只剥离非生效节点行上的 legacy 标注。讲解单元比较只移除补充视图元数据行，并验证视图名和 description 行存在且唯一。年份说明不再归一化，直接逐字节比较。
- 覆盖报告与讲解单元恢复旧句式，年份范围从题目索引内容推导，卷数从登记索引清单推导，并用中文数字生成套数。当前登记数据生成的说明与迁移前输出逐字节相同。
- 添加临时副本删去 `### 练习指向` 行的探针；对照断言按预期失败，仓库源文件不受修改。

## 验收

- `py -3.12 -m unittest tests.test_cs408_lecture_pipeline -v`：2 项通过。
- `git diff --check`：通过。
- 修改文件未发现连续三个问号。
- 全量测试未跑（按 `AGENTS.md`，由决策者提交前统一运行）。未提交。

## 说明

任务书引用的 `review/rounds/round-50-review-sol-out.md` 在当前 worktree 中不存在；本轮按任务书给出的 T1/T3/T4 复现与验收要求实现。仓库内现有的 `round-50-wp-b-wrapup-luna.md` 仅作补充背景。
