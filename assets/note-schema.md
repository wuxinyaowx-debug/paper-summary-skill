# notes.json 字段字典

阶段 2 由 Agent 生成 `notes.json`，核验脚本据此做确定性核验。所有 `source` 锚点、
`quote` 引文都要能回到 `source.md` 的 `Txxxx` 段与 `Sx` 章节。

## 顶层结构

```json
{
  "card": { ... },
  "chapter_notes": [ ... ],
  "knowledge_points": [ ... ]
}
```

## card（论文卡片，六个必填字段）

| 字段 | 类型 | 必填 | 说明 |
|-|-|-|-|
| `research_question` | 对象 | 是 | 研究问题 |
| `data` | 对象 | 是 | 数据/样本/语料 |
| `method` | 对象 | 是 | 方法条件（含让结论成立的实验条件） |
| `main_findings` | 对象数组 | 是（≥1） | 主要发现，逐条成对象 |
| `conclusion` | 对象 | 是 | 结论 |
| `limitations` | 对象 | 是 | 局限 |
| `preconditions` | 对象数组 | 推荐 | 结论成立的前提/假设/适用边界 |

单条字段对象（`research_question`/`data`/`method`/`conclusion`/`limitations`，
以及 `main_findings`、`preconditions` 的每个元素）：

```json
{
  "text": "一句话或几句话的中文表述",
  "quote": "原文逐字摘录（短句）",
  "source": {"page": 1, "section_id": "S1", "segment_id": "T0003"}
}
```

- `text`：笔记内容，**非空**。
- `quote`：原文逐字摘录，须与 `source` 指向处同处；核验脚本会在该锚点查找它。
- `source.page`：页码（1 起）；`section_id`：`S1…SN`；`segment_id`：`T0001…`（可选）。

## chapter_notes（章节笔记，每章一条）

```json
{
  "section_id": "S1",
  "purpose": "本章目的",
  "method": "本章方法",
  "result": "本章结果",
  "conclusion": "本章结论",
  "quote": "本章一句原文摘录",
  "source": {"page": 1},
  "confidence": "high",
  "note": "译法/取舍说明（可选）"
}
```

- `section_id` 必须来自 `skeleton.json` 的 `sections`，顺序与论文一致。
- `purpose/method/result/conclusion` 至少填一项；`quote` 建议填写。

## knowledge_points（知识点，可选，可检索条目）

```json
{
  "id": "K001",
  "concept": "概念/变量/方法名",
  "definition": "一句话定义",
  "aliases": ["缩写", "同义表述"],
  "quote": "原文摘录",
  "source": {"page": 2, "section_id": "S2"},
  "confidence": "high"
}
```

- `id` 全篇唯一（`K001`、`K002`…）。
- 同一概念只建一条，缩写/同义放进 `aliases`，避免重复条目。

## 判空约定

材料缺失、无法判断的字段：`text` 置 `""` 或省略该项，并在 `note`/`uncertainties`
写明"未报告/无法判断"；**不补造数值或结论**。核验脚本会据此判"完整性"。
