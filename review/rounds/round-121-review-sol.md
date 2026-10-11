# 评审：WP-G1 缺资源跳过 + 数据文件 LF（C1、C3），含决策者合并后修补与投影重建

遵守 `AGENTS.md`。**本轮例外**：C1 的验收就是"干净克隆全量 0 失败"，你可以在系统临时目录做一次干净克隆（`git -c core.autocrlf=false clone`，本机系统级 `core.autocrlf=true`）跑一次全量；除此之外不跑全量。

范围：合并提交 `682d1f4`（实现 `f30588d`）、`eec49ae`（注册表测试跳过 gitignore 目录）、`31a25c1`（投影重建）。
任务书 `review/rounds/round-115-wp-g1-task.md`；实现者报告 `review/rounds/round-115-wp-g1-luna.md`。
决策者审查 / 合并时改了：恢复 `tools/register_408_quiz_pages.py` 被实现者移出 `if` 分支的台账写入（实现者称原文件无法解析，实测可以）；主仓库 54 个 index-LF / 工作区-CRLF 数据文件与 `data/materials.yaml`（混合）按 index 字节还原（只差换行）；
`tests/test_cs408_lecture_pipeline.py` 与固定基线比较文本产物时两边都把 CRLF 归一为 LF（部分写入器仍写 CRLF，产物不是受跟踪数据）；注册表契约测试对 `materials.raw_root` 与 `products.*` 缺失时跳过。

请判断：
1. C1：每个 `require_path` 是否只放在"读外部资源"那一步、断言未被削弱；有无把**受跟踪**的数据也当"缺资源"跳过（那会掩盖真缺陷）；`KY_REQUIRE_RESOURCES=1` 能否把全部跳过变回失败。干净克隆全量结果（`Ran` 行、跳过数与原因抽查）。
2. C3：24 个写入工具的改动是否只涉及换行（逐个核对 diff）；LF 守护测试的覆盖面（扩展名、`git ls-files` 取法、归档跳过）；三处固定基线测试的归一化是否只放过换行、仍能抓住内容删改。
3. 行尾例外对 `AGENTS.md` 第 11 条的影响是否限于任务书明写的范围。
4. 投影重建：18 个输入哈希与文件一致；数量与 `tests/test_data_manifest.py` 一致。
5. 撤实现变红：至少抽两处 `require_path` 与 LF 守护测试做撤回验证。

产物：`review/rounds/round-121-review-sol-out.md`，每项"必须改 / 建议改 / 不改"附可复现输入，最后 PASS / FAIL。只写这一个文件。
