# paper-summary-skill｜文献总结与结构化笔记 Skill

本仓库为玻尔产品赛第 06 题「阅读10｜文献总结与结构化笔记」的作品。
将科研论文 PDF 整理为**可核验、可复用**的结构化笔记：章节对齐、论文卡片、
知识点清单，每条笔记锚回原文并可由脚本确定性复核。

## 快速开始

```bash
python scripts/run_case.py --input /input --output /app/output --work /app/work
# Agent 按 assets/note-schema.md 撰写 <work>/notes.json 后：
python scripts/run_case.py --input /input --output /app/output --work /app/work \
    --notes /app/work/notes.json
```

设计要点与字段定义见 `SKILL.md`；最小调用示例见 `examples/minimal-example.md`
（示意输出，非正式案例结果）。依赖：Python ≥ 3.9（仅标准库）+ pdftotext（Poppler）；
OCR 分支需 pdftoppm + tesseract。
