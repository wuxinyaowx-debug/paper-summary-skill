# 已知失败模式与处置（failure-modes）

| 失败模式 | 表现 | 处置 |
|-|-|-|
| 加密/损坏 PDF | `pdftotext` 报错或输出为空 | `status=failed`，记录原始报错，不绕过权限 |
| 扫描件（无文字层） | 无文本块 | 有 OCR 时按真实坐标恢复并标 `verified:false`；无 OCR 时该页标 `unreadable`，不编造 |
| 双栏/多栏错序 | 段落顺序跨栏错乱 | 按 bbox 阅读顺序恢复；仍存疑处标 `uncertain` 并保留页码 |
| 图表/公式为图片 | 无可提取文字 | 保留结构占位，`uncertainties` 说明，不做无依据笔记 |
| 参考文献无法解析 | 条目残缺 | 逐条保留原始行，标"未解析"，不臆造编号 |
| 原文残缺/语言混杂 | 段落截断、中英混杂 | 残缺处标 `⚠️[原文残缺]`；可读部分照常整理并说明 |
| 无章节标题 | 骨架只有隐式 `S0` | 全篇归入 `S0`，不伪造章节边界 |
| 锚点失配（quote 找不到） | 引文与锚点不一致 | 硬核验判错 → `partial`，要求回填正确 quote/锚点 |
| 数字写错（软） | 笔记数字未见于原文 | 记 `warning` 进 `uncertainties`，人工复核 |
| output_contract 含无法产出字段 | 字段超出本 Skill 能力 | 置 `null` 并在 `uncertainties` 说明，不填假值 |

## 自查方法

1. `run_case.py --notes …` 后看 `verification.md`：`issues` 必须清零才算 `success`。
2. 逐条核对 `warnings`：数字/前提条件/顺序差异逐项人工确认或补写。
3. 打开 `notes.md`，抽查每条"原文依据"回到 `source.md` 对应 `Txxxx` 段是否吻合。
