# 第 178 轮：WP-G3h M1-R1 / S1 返工

## M1-R1：原始资料根目录缺失

`_require_html_inputs` 改用已解析的公开属性 `workspace.raw_root`，先将整个原始资料根交给 `require_path`，再根据登记索引逐年检查 HTML 文件。整个 `data/raw_materials` 不存在时会明确跳过依赖输入的成功场景；不再先调用要求目录存在的 `workspace.require("materials.raw_root")`。参数失败场景仍独立运行，不依赖外部资源。

### 干净归档自证

从 `HEAD=58f44bc` 执行 `git archive --format=zip --output=<系统临时目录>.zip HEAD`，展开后**只复制**本轮 `tests/test_tools_split_baseline.py`；确认没有 `data/raw_materials`。设 `GIT_DIR=F:\workspace\kaoyan-ai-system\.git`、`PYTHONDONTWRITEBYTECODE=1`、`PYTHONUTF8=1`，在归档中运行：

```text
py -3.12 -m unittest tests.test_tools_split_baseline -v
Ran 12 tests in 18.949s
OK (skipped=4)
```

四条跳过原因原文：

```text
missing resource: C:\Users\Lenovo\AppData\Local\Temp\kaoyan-probe\claude2\dl\bv_e1_2024.pdf; restore the registered English exam PDFs from the acquisition source
missing resource: C:\Users\Lenovo\AppData\Local\Temp\g3h-r178-archive-e05769ea42fc45228d34634e6aa44a99\data\raw_materials; restore registered raw materials from the acquisition source
missing resource: C:\Users\Lenovo\AppData\Local\Temp\g3h-r178-archive-e05769ea42fc45228d34634e6aa44a99\review\408知识点树与真题\questions\questions_index.json; generate registered products with tools/extract_408_questions_from_html.py
missing resource: C:\Users\Lenovo\AppData\Local\Temp\g3h-r178-archive-e05769ea42fc45228d34634e6aa44a99\data\raw_materials\cs408\syllabus\archive408_408_outline_2026.html; restore the registered CS408 source listed in data/materials.yaml
```

主仓库中原始资料与登记产品均存在，HTML 成功对照执行通过。主仓库验收共 5 项跳过；其具体资源原因见下方验收输出对应的 verbose 复跑。

## S1：round24 双错误顺序对照

新增 `test_round24_dual_error_order_matches_fixed_baseline`。它从登记 weighted tree 生成临时 JSON 副本，同时将同一节点设为 `status="approved"`、`sources=[]`，新旧版分别执行 `validate` 与 CLI `main`。测试比较错误列表和 `(退出码, stdout, stderr)`，并断言状态错误在来源错误之前。M2 校验器实现未改。

### 撤实现验证

在临时归档副本 `C:\Users\Lenovo\AppData\Local\Temp\g3h-r178-archive-e05769ea42fc45228d34634e6aa44a99` 中，将 `_validate_node_status_and_scope(...)` 与 `_validate_node_sources(...)` 两次调用调换；设 `PYTHONDONTWRITEBYTECODE=1` 与 `GIT_DIR=F:\workspace\kaoyan-ai-system\.git` 后运行：

```text
py -3.12 -m unittest tests.test_tools_split_baseline.ValidatorSplitBaselineTests.test_round24_dual_error_order_matches_fixed_baseline
```

实测 `FAILED (failures=1)`：`tests/test_tools_split_baseline.py:448` 的 `self.assertEqual(errors[0], errors[1])` 失败，变异版把 `sources must be a non-empty list` 移到 `status 'approved' not in ...` 前面。变异副本 SHA-256 为 `91D6981D07FE37676CEEE5BF1A75BFABCC5C5872D80BE4DA16DF708800C686B8`。随后从主仓库恢复副本，恢复前后 SHA-256 均为 `3ABD52A8BA10F22CE52BF8761C884DA515B76F5DA0CEBF3513133D28626BF38E`；同一测试恢复后 `Ran 1 test ... OK`。

## 验收

主仓库按任务书运行：

```text
py -3.12 -m unittest tests.test_tools_split_baseline tests.test_round24_weighted_tree
Ran 27 tests in 32.839s
OK (skipped=5)
```

另以 `-v` 运行相同两个模块以读取跳过原因，`Ran 27 tests in 27.811s`、`OK (skipped=5)`。五条跳过原因原文：

```text
missing resource: C:\Users\Lenovo\AppData\Local\Temp\kaoyan-probe\claude2\dl\bv_e1_2024.pdf; restore the registered English exam PDFs from the acquisition source
missing resource: C:\Users\Lenovo\AppData\Local\Temp\kaoyan-probe\ghsurvey\downloads\408_syllabus_2022.pdf; restore the registered CS408 source listed in data/materials.yaml
missing resource: C:\Users\Lenovo\AppData\Local\Temp\kaoyan-probe\ghsurvey\downloads\408_syllabus_2022.pdf; 按 data/materials.yaml 对应的 2022 大纲来源重新获取
missing resource: C:\Users\Lenovo\AppData\Local\Temp\kaoyan-probe\ghsurvey\downloads\408_syllabus_2022.pdf; 按 data/materials.yaml 对应的 cs408 来源记录重新获取
```

以上四条提示对应五个跳过测试：2022 来源 PDF 在 `test_round24_success_matches_fixed_baseline`、`test_fabricated_alias_text_is_rejected`、`test_real_file_alias_provenance_passes`、`test_real_file_passes_validation` 中各造成一项跳过；英语真题 PDF 造成另一项跳过。

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。不提交。
