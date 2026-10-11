# 第 177 轮评审：WP-G3h 第 173 轮返工

## 结论

**FAIL。** 第 172 轮 M1 所指的“缺登记产物导致旧新 traceback 对照失败”已修复；M2 两支校验器的现有实现与固定旧版逐段一致。但 HTML 成功测试在**整个原始资料根目录缺失**时，尚未走到要求的 `require_path` 跳过；这在普通干净归档中会使本模块报 ERROR。另有一处错误顺序未被新增对照测试锁住，列为建议。

范围仅为 `git diff 58f44bc -- tests/test_tools_split_baseline.py tools/round24_validate_weighted_tree.py tools/round29_validate_agreement.py`。用 `git archive 58f44bc` 展开至系统临时目录，只复制这三个待审文件；第 176 轮的卷面测试不纳入评审，也未运行全量测试。全量：未跑（按 AGENTS.md）。

## 必须改

### M1-R1：原始资料根目录缺失时，HTML 成功场景报 ERROR 而未按资源规则跳过

位置：`tests/test_tools_split_baseline.py::_require_html_inputs` 首先调用 `workspace.require("materials.raw_root")`，之后才对每个 HTML 文件调用 `require_path`。`git archive` 不含 gitignore 的 `data/raw_materials`；当该目录整体未恢复时，前一句已抛 `ContractError`，缺资源提示没有机会执行。返工任务书要求依赖的原始 HTML 缺失时用 `tests._resources.require_path` 写明路径及恢复来源并跳过，因此此处仍需处理。

复现：在只含 `git archive 58f44bc` 加本轮三个文件的临时目录中，不补 `data/raw_materials`，设 `GIT_DIR=<主库 .git>`、`PYTHONDONTWRITEBYTECODE=1`，单跑 `py -3.12 -m unittest tests.test_tools_split_baseline.ToolsSplitBaselineTests.test_html_extraction_success_uses_temporary_product_root -v`。实测 `FAILED (errors=1)`，栈停在 `_require_html_inputs` 的 `workspace.require("materials.raw_root")`，异常为 `ky.models.ContractError: materials.raw_root: registered directory does not exist: ...\data\raw_materials`。同条件下 `test_html_extraction_argument_failure_needs_no_external_inputs` 单跑为 `OK`。建议从注册表已解析的 `workspace.raw_root` 取得待检查路径，先交给 `require_path`，再检查各年 HTML；不要先用要求目录已存在的 `workspace.require`。

## 建议改

**S1：新增 round24 失败对照尚未锁住跨检查段的错误顺序。** 在临时副本中仅把 `validate` 内 `_validate_node_status_and_scope` 与 `_validate_node_sources` 两个调用调换，设置 `PYTHONDONTWRITEBYTECODE=1`，单跑 `ValidatorSplitBaselineTests.test_round24_status_error_matches_fixed_baseline`，实测仍 `OK`：现有夹具只使状态段出错，来源段没有出错。独立探针从当前 `load_doc()` 复制第一项，同时令 `status="approved"`、`sources=[]`，旧版和未变异新版的前四条错误均依次为状态不合法、禁止 `approved`、来源列表为空、来源数不符；调换后的新版把两条来源错误移到前面，与旧版列表不等，探针退出 1、`AssertionError`。当前实现顺序经 diff 和此探针确认正确，因此不把测试盲区当作已发生的输出回归；建议把这个双错误输入加入固定基线对照，便于以后守住顺序。

## 不改

- **原 M1 的产物问题已修复。** 在只补四个登记 quiz HTML、建立空 `products` 目录、完全不补 `review/408知识点树与真题` 产物的归档中，`py -3.12 -m unittest tests.test_tools_split_baseline -v` 实测 `Ran 11 tests in 14.266s`、`OK (skipped=3)`。`test_html_extraction_success_uses_temporary_product_root` 为 `ok`，并非跳过：代理仅将 `products.cs408_lecture_workspace` 的 `require` 返回值改为同一个临时目录；原始 HTML、登记索引及其他 `require` 仍由同一注册表提供。每版运行前清空临时产物，随后比较 `(退出码, stdout, stderr)` 及目录内全部相对路径和文件原始字节。参数失败支路独立为 `ok`。
- **登记产物验证器只跳过自己。** 上述归档中，`test_question_extraction_verifier_success_when_products_are_registered` 的跳过提示为 `missing resource: ...\review\408知识点树与真题\questions\questions_index.json; generate registered products with tools/extract_408_questions_from_html.py`；同一轮 `test_verifier_and_report_tools_match_fixed_baseline` 为 `ok`，其中 NETEM、英语数据库与参数错误对照均实际执行。另两项跳过分别是缺英语来源 PDF 与 round24 登记来源缓存；它们均给出了缺失路径及恢复线索。其余外部路径在测试中有 `require_path`，唯 M1-R1 所述整个 `materials.raw_root` 缺失的入口例外。
- **round24/round29 的固定旧版与现有行为。** `VALIDATOR_BASELINE = "58f44bc"`，通过 `git show 58f44bc:tools/<文件>` 读取，不依赖 `HEAD`；独立 AST 核对旧 `validate` 分别为 76、78 行（断言下界 70），新版均为 20 行。完整 diff 显示 round24 的身份→状态/范围→来源→权重→别名→基线 ID→来源登记顺序、缺 ID 的 `continue` 与原版相同；round29 的身份→schema→主表包含→字段值→重算支持度→别名→缺失 ID 顺序及 `continue` 与原版相同。错误文字、返回列表及 CLI 输出未见改动。干净归档里 round24 的 `status=approved is forbidden` 失败、round29 的成功和 `source_support=0.42` 失败对照均为 `ok`，各自断言了目标检查消息。
- **round24 无外部缓存的独立成功探针。** 在临时副本读取登记 weighted tree，只把 `sources_registry.A/B` 的路径和 SHA-256 换成两份临时合成来源，令 `validate_alias_provenance` 在旧新两版中同样返回空列表。旧新 `validate(doc)` 均返回 `[]`；旧新 CLI 三元组均为 `(0, b'VALID: 410 nodes, 0 errors\n', b'')`。`410` 是本次登记输入的输出，不作为测试固定期望。原新增 round24 登记数据成功用例因缺来源缓存而单独跳过；此探针只补充证明已拆 `validate` 的成功返回路径，并不冒称真实来源别名核验已通过。
- **定点撤实现验证有效。** 在临时副本将 round24 的 `_validate_node_status_and_scope(...)` 调用替成 `pass`，设 `PYTHONDONTWRITEBYTECODE=1`，单跑 `ValidatorSplitBaselineTests.test_round24_status_error_matches_fixed_baseline`，实测 `FAILED (failures=1)`，`tests/test_tools_split_baseline.py:415` 的旧新错误列表比较变红，旧版含两条 `approved` 错误而变异版缺失。随后从工作区重复制文件，SHA-256 与待审版一致。S1 所述调换探针也在临时副本恢复，不涉及仓库源码。
- **目录分类与现有测试。** 按 `tools/README.md` 的 `active`、`validation`、`acquisition` 行解析 32 个脚本，逐个 AST 计算 `end_lineno - lineno + 1`：超过 60 行的函数为 0，最大值 60。两支 `round*_validate_*` 仍列为 `validation`。另外只跑 `tests.test_tools_catalog tests.test_round24_weighted_tree tests.test_round29_tree_split`，实测 `Ran 26 tests in 18.377s`、`OK (skipped=6)`；缺来源缓存的路径未被当成通过。

## 安全登记

本轮未见需另行登记的恶意输入、手工篡改内部文件或精确竞态问题。M1-R1 是正常缺资源时的测试错误处理，按日常使用问题归类。
