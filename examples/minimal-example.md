# 最小调用示例（示例，非正式案例结果）

> 本示例仅说明接口与完整使用流程；论文内容、数值与锚点均为虚构示意，
> 不冒充任何正式测试案例的运行结果。

## 输入

```
/input/case.json:
{"case_id": "demo-001",
 "materials": ["paper.pdf"],
 "output_contract": {"fields": ["status", "result", "sources", "uncertainties"]}}

/input/task.md:   任务说明（如“章节笔记 + 论文卡片 + 知识点”）
/input/paper.pdf: 一篇 3 页英文论文（虚构）
```

## 调用

```bash
# 阶段 1：确定性解析与骨架构建，写出 status=partial 的 result.json
python <skill_dir>/scripts/run_case.py --input /input --output /app/output --work /app/work
# → /app/work/skeleton.json（章节 S1…SN、段落 T0001…，含页码/bbox）
# → /app/work/source.md（按阅读顺序的分段原文）
# → /app/output/result.json（partial，不冒充完成）

# 阶段 2：Agent 按 references/note-schema.md 撰写 /app/work/notes.json，合并核验
python <skill_dir>/scripts/run_case.py --input /input --output /app/output --work /app/work \
    --notes /app/work/notes.json
# → 最终 result.json + notes.md + verification.md（合并运行不重解析 PDF）
```

## 示意输出（示例）

`notes.json` 片段（Agent 撰写）：

```json
{
  "card": {
    "research_question": {
      "text": "研究旋转机械的小样本故障诊断问题。",
      "quote": "we address the problem of few-shot fault diagnosis",
      "source": {"page": 1, "section_id": "S1", "segment_id": "T0003"}
    },
    "main_findings": [
      {"text": "所提方法在测试集上达到 94.2% 准确率。",
       "quote": "our method reaches 94.2% accuracy on the test set",
       "source": {"page": 3, "section_id": "S3", "segment_id": "T0007"}}
    ]
  },
  "chapter_notes": [
    {"section_id": "S1", "purpose": "引出小样本故障诊断问题",
     "quote": "few-shot fault diagnosis in rotating machines",
     "source": {"page": 1}, "confidence": "high"}
  ],
  "knowledge_points": [
    {"id": "K001", "concept": "few-shot fault diagnosis",
     "definition": "小样本条件下的故障诊断任务", "aliases": ["FSFD"],
     "quote": "few-shot fault diagnosis",
     "source": {"page": 1, "section_id": "S1"}, "confidence": "high"}
  ]
}
```

`result.json` 片段（合并核验后）：

```json
{
  "case_id": "demo-001",
  "status": "success",
  "result": {
    "verification": {
      "checks": {
        "structure": {"rate": 1.0},
        "completeness": {"rate": 1.0},
        "anchoring": {"verified": true, "failures": 0},
        "reusability": {"unique_ids": true}
      }
    }
  },
  "uncertainties": [
    {"item": "limitations", "reason": "作者未报告局限（已核查 Conclusion）"}
  ]
}
```
