# 输入输出契约（output-contract）

## 输入

- `/input/case.json`：`case_id`、`output_contract`（字段名数组或对象）、材料路径
  （`pdf`/`pdf_path`/`file`/`document`/`material` 或 `materials` 数组中的 `.pdf`）。
- `/input/task.md`：任务说明（阅读边界、要求的输出形式）。
- 科研材料：实际 PDF（文本型或扫描件）。事实依据是原论文，不依据错误标签补造数据。

## 输出

- `/app/output/result.json`：顶层含 `case_id` + `output_contract` 声明的全部字段
  （通常 `status`/`result`/`sources`/`uncertainties`），另含 `changes`、`runtime`。
- `/app/output/notes.md`：结构化笔记（Markdown）。
- `/app/output/verification.md`：核验报告。
- `/app/output/source.md`：章节化原文骨架。

### result 对象

| 字段 | 说明 |
|-|-|
| `paper` | `title`/`authors`/`abstract`/`sections[{id,title,page}]`（骨架） |
| `card` | 论文卡片（六字段 + 前提条件，见 `assets/note-schema.md`） |
| `chapter_notes` | 章节笔记（每章一条，`section_id` 回指 `paper.sections`） |
| `knowledge_points` | 知识点条目（可选） |
| `verification` | 核验报告（`status`/`issues`/`warnings`/`checks`） |
| `summary` | 覆盖率摘要（卡片字段数、发现数、章节覆盖数等） |

### status 取值

- `success`：骨架生成且笔记通过全部硬核验（结构/完整性/锚点/可复用性）。
- `partial`：已产出部分成果但未通过核验、或字段/章节不完整。
- `unreadable`：全文档无文字层且无 OCR；不编造文字。
- `failed`：解析器失败、无 PDF、或 case_id 失配等无法产出成果的情况。

### 核验 checks

| 项 | 含义 |
|-|-|
| `structure` | 章节笔记是否引用真实章节、无跳号无重复 |
| `completeness` | 卡片必填字段是否齐备、每个章节是否都有笔记 |
| `anchoring` | 锚点页码/章节/段号是否有效、quote 是否在该锚点处真实存在 |
| `reusability` | 知识点 id 是否唯一、schema 是否可解析 |

`issues` 为阻断项（映射为 `partial`）；`warnings` 为人工复核项（数字未见于原文、
无前提条件、章节顺序差异等），不阻断但如实记录。
