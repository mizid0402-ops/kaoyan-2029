# Round 53 任务书：B′4 新旧输出对照测试修复（sol 第 50 轮 FAIL：T1/T3/T4）

你是实现者，在独立 worktree（分支 `stage25/b4-golden-fix`，基于 master `ab86529`）里工作。先读仓库根 `AGENTS.md`。
依据：`review/rounds/round-50-review-sol-out.md` 第 1 节（sol 给了复现方法）。只动下面三个文件。

1. **T1 旧版来源固定**（`tests/test_cs408_lecture_pipeline.py`）：`_head_script` 不得用 `HEAD`；改为固定提交 `762786f`（B′4 之前的最后一个提交）取旧版工具，
   并**断言取到的确实是旧版**（例如旧版源码含 `Path(r"F:\workspace\kaoyan-ai-system")`）。常量名改为 `PRE_MIGRATION_COMMIT` 并在注释里写明为什么不能用 HEAD。
2. **T3 文案**（`tools/extract_cs408_bundle.py`、`tools/build_408_deck_scaffold.py`）：恢复旧句式，**只把年份区间与套数改为从登记索引推导**：
   - 覆盖报告：旧 `> 无命中 **不等于** 不考：只说明在 2023–2026 这四套卷子的映射里没出现。` → 同一句式，`2023–2026` 与 `四` 由登记的该科索引年份区间与份数生成（份数用中文数字：一、二、三、四、五……，写一个小函数）。
   - 讲解单元：旧 `> 本单元在 2023–2026 四套卷的映射中**无真题命中**。无命中不等于不考，只说明这四套里没出现。` → 同一句式，同样只替换年份区间与两处套数。
   - 不得出现多余空格。对当前仓库数据（2023–2026、4 份），输出必须与旧版**逐字节相同**。
3. **T4 收窄归一化**（测试）：按**原始字节**比较输出文件；只允许任务书第 49 轮明写的差异：`tree_flat.csv/json` 新增的 `is_effective`、`view_name` 列（用确定的列删除变换后再逐字节比较）、manifest **恰好**新增的那几个键（精确集合）、非生效节点的可见标注行、补充视图名与 description 行。
   去掉把"在 … 映射"之间任意文字抹掉的正则；文件集合必须相同（新增文件要在允许清单里）。
4. 复现 sol 的探针并写进测试：删掉当前工具里含 `### 练习指向` 的一行后，对照测试必须失败（用临时副本，不改仓库文件）。

验收：`py -3.12 -m unittest tests.test_cs408_lecture_pipeline -v`（在本 worktree）。全量不跑。写完检查无 `???`。
报告：`review/rounds/round-53-b4-golden-fix-luna.md`（用 `apply_patch` 写）。不提交。
