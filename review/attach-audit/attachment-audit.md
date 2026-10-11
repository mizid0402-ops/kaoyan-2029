# 附件（用户提供的资料索引）可靠性审计

被审文件 sha256 `c99635318bb22179351edc6bb07d1f0883aa8403b73c9d14f3e9896ca6d072a0`

逐条判定：{'SUPPORTED': 18, 'NOT_FOUND': 1, 'UNREACHABLE': 1}

| # | 类别 | 判定 | HTTP | 字节 | 缺失探针 | 主张 |
|---|---|---|---:|---:|---|---|
| A1 | official | **SUPPORTED** | 200 | 76773 | - | 2026 研考初试时间 2025-12-20—21；数学一/英语一为全国统一命题科目 |
| A2 | publisher | **SUPPORTED** | 200 | 48508 | - | 数学大纲 ISBN 9787107404689 / 157 页 / 29.00 元 / 人教社 / 2026 版目录 |
| A3 | publisher | **NOT_FOUND** | 200 | 102 | 9787、数学 | 数学大纲目录（境外核验页，台湾大书城） |
| A4 | publisher | **SUPPORTED** | 200 | 25173 | - | 英语一大纲 ISBN 9787107404603 / 236 页 / 含附录三 2024-2025 真题及参考答案 |
| A5 | publisher | **SUPPORTED** | 200 | 8045 | - | 英语一大纲目录（台湾大书城） |
| B1 | math-reprint | **SUPPORTED** | 200 | 29747 | - | 2024 数学一真题及答案（网络整理 PDF） |
| B2 | math-reprint | **SUPPORTED** | 200 | 17702 | - | 同站下载中心提供该 PDF |
| B3 | math-university | **SUPPORTED** | 200 | 16738 | - | 天津仁爱学院数学教学部提供 2025 数学一真题及答案解析 PDF 附件 |
| B4 | math-reprint | **SUPPORTED** | 200 | 21108 | - | 聚创考研 2025 数学一解析 |
| B5 | math-reprint | **SUPPORTED** | 200 | 121054 | - | 启航数学真题索引 |
| B6 | math-reprint | **SUPPORTED** | 200 | 106638 | - | 启航 2026 数学一完整卷 + 解析 |
| B7 | math-reprint | **SUPPORTED** | 200 | 24472 | - | 聚创考研 2026 数学一手写版 PDF |
| C1 | eng-reprint | **SUPPORTED** | 200 | 229272 | - | 懒笔记 2024 英语一整卷 + PDF + Word + 解析 |
| C2 | eng-reprint | **SUPPORTED** | 200 | 33869 | - | 中国考研网 2024 英语一各题型答案索引 |
| C3 | eng-reprint | **SUPPORTED** | 200 | 225659 | - | 懒笔记 2025 英语一整卷 |
| C4 | eng-reprint | **SUPPORTED** | 200 | 64814 | - | 新东方 2025 英语一试题及答案 |
| C5 | eng-reprint | **UNREACHABLE** | SSLError: HTTPSConnectionPool(host='www.yanbbs.com', port=443): Max retries exceeded with url: /nd.jsp?id=47 (Caused by SSLError(SSLCertVerificationError(1, '[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: self-signed certificate (_ssl.c:1000)'))) | None | 参考答案 | 考研之家标注的「2025 英语一试题参考答案.pdf」 |
| C6 | eng-reprint | **SUPPORTED** | 200 | 228441 | - | 懒笔记 2026 英语一整卷 + 分模块解析 |
| C7 | eng-reprint | **SUPPORTED** | 200 | 903877 | - | kaoyan.cn 静态 PDF 含 2026 英语一试题及答案 |
| C8 | eng-reprint | **SUPPORTED** | 200 | 157020 | - | 懒笔记 2010—2026 英语一真题总库 |

## 关于 C7（kaoyan.cn 静态 PDF）

已实际下载到完整 PDF 字节；按项目 §4.3/侦察 §2.4 第 8-10 条，真题与答案原文不得入库，此文件仅作「该链接确实提供真题」的存在性证据，不得进入 data/raw_materials。
magic bytes: `%PDF-1.3`
