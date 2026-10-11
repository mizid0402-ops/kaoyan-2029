# 第 215 轮：tools 轮次归档入口修复

基线对照：sol61 第 214 轮评审报告。按任务书只处理 M1、M2、m1、m2；纯移动、规则和既有测试断言未改。

## 修改

- 两个活动校验器现在先将仓库根加入 `sys.path`，再导入 `ky.workspace`；同时保留 `tools/` 路径供活动库模块导入。
- `round24_build_weighted_tree.py` 与 `round29_build_tree_split.py` 的 `ROOT` 改为 `Path(__file__).resolve().parents[2]`，并可从新进程加载活动 helpers 与归档 builder。
- `round22_verify.py` 显式从 `archive.round22_extract` 导入 `HTML`、`PDF` 历史路径常量。
- `tests/test_tool_exit_paths.py` 增加真实脚本入口检查：清除子进程环境中的 `PYTHONPATH`，从仓库根启动 weighted `--help` 和 agreement 正常命令，断言退出码为 0 且 stderr 无 traceback。
- `tests/test_tools_catalog.py` 增加隔离子进程 `runpy.run_path(..., run_name="review_load")` 检查，覆盖本轮修复的三个归档脚本；两个 builder 还断言 `ROOT` 指向当前 checkout 根目录。
- README 增加两个 validator 的完整可复制命令，并说明 weighted validator 的 `--tree` 必填。

未修改校验规则、校验输出文字、退出码、`ky/` 或历史构建输入；未重跑历史构建。

## 直接启动结果

本机 `PYTHONPATH` 未设置。实际运行命令及原始 stdout：

```text
> py -3.12 tools/validate_weighted_tree.py --help
usage: validate_weighted_tree.py [-h] --tree TREE

Validate a CS408 weighted tree

options:
  -h, --help   show this help message and exit
  --tree TREE
```

```text
> py -3.12 tools/validate_supplementary_agreement.py
VALID: 410 agreement entries, 0 errors
```

两条命令均退出 0，stderr 无 traceback。

## 归档脚本只加载对照

从固定提交 `ab56529` 的 `git archive` 临时解包原文件，与当前文件分别在新进程中运行同一只加载探针。环境均移除 `PYTHONPATH`；探针只调用 `runpy.run_path(..., run_name="review_load")`，不调用 `main()`。

```text
tools/archive/round24_build_weighted_tree.py: old=0, new=0
  ROOT: old checkout=C:\Users\Lenovo\AppData\Local\Temp\tmp33imy4aj, new checkout=F:\workspace\kaoyan-ai-system
tools/archive/round29_build_tree_split.py: old=0, new=0
  ROOT: old checkout=C:\Users\Lenovo\AppData\Local\Temp\tmp33imy4aj, new checkout=F:\workspace\kaoyan-ai-system
tools/archive/round22_verify.py: old=0, new=0
PASS: all three baseline and current modules loaded without PYTHONPATH
```

两个 builder 在各自加载后都将 `ROOT` 指向各自 checkout 根目录。旧版临时 checkout 根目录由系统临时目录生成；上面记录的是本次探针路径，每次运行都会不同。新旧三项加载结果均为退出 0。

## 验收

```text
py -3.12 -m unittest tests.test_tools_catalog tests.test_tool_exit_paths tests.test_round24_weighted_tree tests.test_round29_quote_locate tests.test_round29_tree_split
Ran 49 tests in 38.434s
OK (skipped=4)
```

`git diff --check` 通过。未运行全量测试。

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）
