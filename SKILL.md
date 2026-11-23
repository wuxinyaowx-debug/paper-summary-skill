---
name: scientific-paper-notes
description: 将科研文献 PDF 整理为可核验的结构化笔记：按论文自身章节生成对齐的章节笔记，抽取统一字段的论文卡片（研究问题、数据、方法、主要发现、结论、局限与前提条件），每条笔记锚回原文页码/章节/段落并保留原文引文供复核，另可输出可检索的知识点条目。Use when the task requires summarizing a scientific paper (PDF or extracted text) into structured, source-anchored, reusable notes rather than a flat abstract. 当任务要求把科研论文做成章节对齐、字段化、可回指原文且可复用的结构化笔记时使用。
---

# Scientific Paper Notes（科研文献总结与结构化笔记）

将科研论文 PDF 整理为**可核验、可复用**的结构化笔记。核心原则：**对得上、留得住、找得回、用得上**——笔记骨架跟随论文自身章节与论证顺序，关键要素与前提条件不丢失，每条笔记都能回指原文并被复核。

## 适用条件与触发场景

- 输入为科研文献 PDF（单/双/多栏、中英文、文本型或扫描件），任务要求"总结/结构化笔记/论文卡片/知识点提取/证据链接"。
- 需要章节对齐、字段化、锚点回链，以及能回指原文证据的结构化输出（`result.json`）。
- 不适用：只需一句"大意概括"而无需回指原文、或已有可靠人工笔记且仅需润色。

## 环境与依赖

- 必需：`pdftotext`（Poppler）、Python ≥ 3.9（仅标准库）。
- 可选：`pdfinfo`、`pdftoppm` + `tesseract`（扫描页 OCR，真实坐标）。
- 所有路径相对于 Skill 目录解析；脚本用 `python <skill_dir>/scripts/…` 调用，不依赖个人文件或手工中间步骤。

## 两阶段流程（务必按序执行）

评测环境（DeepSeek Harness，单案例单次执行）内，一次执行完成一个案例并确认
`/app/output/result.json` 已写出。

### 阶段 1：确定性解析与骨架构建（脚本完成）

```
python <skill_dir>/scripts/run_case.py --input /input --output /app/output --work /app/work
```

脚本读取 `case.json`（`case_id`、`output_contract`、材料路径）与 `task.md`，定位 PDF，
运行解析器与骨架构建，产出 `<work>/skeleton.json`、`<work>/source.md`，
并把**部分** `result.json` 写入 `<output>/`（此时 `status=partial`，卡片/章节笔记为空，
**不冒充完成**）。骨架从论文自身的标题层级生成：章节 `S1…SN` 与正文段 `T0001…`
（含页码/bbox），并按真实阅读顺序（含双栏跨栏）排序；每个正文段归到所属章节。

### 阶段 2：Agent 语义整理（调用者完成）

Agent 阅读 `<output>/source.md` 与 `<output>/result.json` 的骨架，按下方规则生成
`<work>/notes.json`，再合并核验：

```
python <skill_dir>/scripts/run_case.py --input /input --output /app/output --work /app/work \
    --notes <work>/notes.json
```

合并运行**不重解析 PDF**（内容哈希指纹复用），确定性核验结构对齐、完整性、
锚点有效性与可复用性后，产出最终 `result.json` + `notes.md` + `verification.md`。

## 笔记规则（阶段 2 必须遵守）

### 1. 对得上（骨架来自论文自身，不套通用模板）

1. `chapter_notes` 的 `section_id` 必须来自 `skeleton.json` 的 `sections`，**不新增、
   不改名、不跳号**；每个章节一条，顺序与论文顺序一致。
2. 章节笔记按该章自身内容提炼 `purpose/method/result/conclusion` 四要素，保留章节间
   承接关系（上一章结论如何引出下一章）。

### 2. 留得住（关键要素与前提条件不丢失）

1. 论文卡片 `card` 必须含六个字段：`research_question`（研究问题）、`data`（数据）、
   `method`（方法条件）、`main_findings`（主要发现，数组，≥1 条）、`conclusion`（结论）、
   `limitations`（局限）。
2. 结论成立的前提条件单独列在 `preconditions`（数组，如样本范围、温度压力区间、
   假设、适用边界）；缺材料无法判断时，如实写"未报告/无法判断"，**不补造**。
3. 论断中的数值、单位、变量、方法条件必须与原文一致，不得改写、四舍五入或张冠李戴。

### 3. 找得回（每条笔记可回指原文并可核验）

1. 每条笔记带 `source`：`page`（页码）、`section_id`（章节）、可选 `segment_id`（段号）；
   锚点必须指向真正对应的位置。
2. 每条关键笔记带 `quote`（**原文逐字摘录**，短句即可）；核验脚本会到该锚点处查找
   `quote` 是否真实存在，找不到即判"锚点失配"。摘录要与锚点同处，不得跨段拼贴。

### 4. 用得上（可检索、可比较、可继续加工）

1. `knowledge_points` 为可检索条目：`id`（`K001…` 唯一）、`concept`（概念/变量/方法）、
   `definition`（一句话定义）、`aliases`（缩写/同义表述）、`quote`、`source`、`confidence`。
2. 同一概念只建一条，缩写/同义放进 `aliases`，避免条目重复或彼此矛盾。
3. 字段结构统一（见 `assets/note-schema.md`），同一领域多篇论文可并排比较。

## 输出约定

- `result.json`：`case_id` + `output_contract` 声明字段（`status`/`result`/`sources`/
  `uncertainties`）+ `result.paper`（标题/作者/摘要/章节清单）+ `result.card` +
  `result.chapter_notes` + `result.knowledge_points` + `result.verification`。
  字段完整定义见 `references/output-contract.md`。
- `notes.md`：结构化笔记（卡片 + 章节笔记 + 知识点 + 依据 + 待确认）。
- `verification.md`：确定性核验报告（结构/完整性/锚点/可复用性 + 人工复核清单）。

## 交付物清单

| 路径 | 作用 | 使用条件 |
|-|-|-|
| `scripts/run_case.py` | 评测入口（两阶段、缓存复用、核验合并） | Python ≥ 3.9 + pdftotext |
| `scripts/parse_pdf.py` | PDF 结构化解析（阅读顺序/章节/段落/图表/公式/文献） | 同上；OCR 需 pdftoppm + tesseract |
| `scripts/segment.py` | 分段 + 保护令牌（数字/单位/引用/公式编号） | 同上 |
| `scripts/build_skeleton.py` | 章节骨架 + 段落到章节归属 + source.md | 同上 |
| `scripts/verify_notes.py` | 确定性核验（结构/完整性/锚点/可复用性） | 同上 |
| `assets/note-schema.md` | `notes.json` 字段字典与示例 | 阶段 2 |
| `references/output-contract.md` | 输入输出字段约定 | 文档 |
| `references/note-method.md` | 方法、阈值与规则细节 | 文档 |
| `references/failure-modes.md` | 已知失败模式与处置 | 文档 |
| `examples/minimal-example.md` | 最小调用示例（输出为示意） | 文档 |

## 异常处理

- 加密/损坏 PDF：`status=failed`，记录工具原始报错，不绕过权限。
- 扫描件：有 OCR 时按真实坐标恢复并标 `verified:false`；无 OCR 时对应页标
  `unreadable`，不编造文字、不臆造结论。
- 双栏错序：解析器按 bbox 阅读顺序恢复；仍存疑处标 `uncertain` 并保留页码。
- 图表/公式缺失或为图片：按"结构元素"保留占位并在 `uncertainties` 说明，不做无依据笔记。
- 参考文献无法解析：如实标注"未解析"，逐条保留原始行。
- 原文残缺/语言混杂：残缺处标 `⚠️[原文残缺]`；无法判断的字段置空并写明原因，不填假值。
- `output_contract` 中无法产出的字段置 `null` 并在 `uncertainties` 说明原因。

## 最小调用示例

见 `examples/minimal-example.md`（输出为示意，不冒充正式案例结果）。
