#!/usr/bin/env python3
"""run_case.py — Harness entry point for the scientific-paper-notes skill.

Two-phase design (see SKILL.md):

  Phase 1 (deterministic, this script): read <input>/case.json + task.md,
  locate the PDF, run parse_pdf.py and build_skeleton.py. Writes a *partial*
  result.json (the paper skeleton; the note fields are empty and the status is
  partial, never faking completion) plus skeleton.json / source.md so the Agent
  has a structure-anchored view of the paper.

  Phase 2 (Agent + script): the Agent reads source.md and fills notes.json
  (a paper card + per-section chapter notes + optional knowledge points, each
  with a verbatim quote and a page/section/segment anchor), then re-runs this
  script with --notes. The script verifies deterministically (structure /
  completeness / anchoring / reusability), renders notes.md + verification.md,
  and assembles the final result.json honoring case.json's output_contract.

Defaults match the evaluation contract: --input /input --output /app/output
--work /app/work. Exit code 0 whenever a (possibly partial) result.json was
written; 1 only when no result could be produced at all.
"""
import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_skeleton as bs     # noqa: E402
import verify_notes as ver      # noqa: E402

PARSER = HERE / "parse_pdf.py"

CARD_FIELDS = ["research_question", "data", "method", "conclusion", "limitations"]
LIST_FIELDS = ["main_findings", "preconditions"]


def find_pdf(*dirs):
    for d in dirs:
        if d and d.is_dir():
            pdfs = sorted(d.rglob("*.pdf"))
            if pdfs:
                return pdfs[0]
    return None


def locate_pdf(case, indir, workdir):
    for key in ("pdf", "pdf_path", "file", "document", "material"):
        v = case.get(key)
        if isinstance(v, str):
            cand = Path(v)
            if not cand.is_absolute():
                cand = indir / v
            if cand.is_file():
                return cand
    materials = case.get("materials")
    if isinstance(materials, list):
        for m in materials:
            if isinstance(m, str) and m.lower().endswith(".pdf"):
                cand = Path(m)
                if not cand.is_absolute():
                    cand = indir / m
                if cand.is_file():
                    return cand
    return find_pdf(indir, workdir)


def contract_fields(case):
    contract = case.get("output_contract")
    fields = []
    if isinstance(contract, dict):
        fields = list(contract.get("fields", contract.keys()))
    elif isinstance(contract, list):
        fields = [f if isinstance(f, str) else (f.get("name") if isinstance(f, dict) else None)
                  for f in contract]
    return [f for f in fields if isinstance(f, str)]


def _src_str(src):
    if not src:
        return ""
    if isinstance(src, dict):
        parts = []
        if src.get("section_id"):
            parts.append(src["section_id"])
        if src.get("segment_id"):
            parts.append(src["segment_id"])
        if src.get("page"):
            parts.append("第 %s 页" % src["page"])
        return " · ".join(parts)
    return str(src)


def _field_md(label, obj):
    if not isinstance(obj, dict) or not (obj.get("text") or "").strip():
        return ""
    lines = ["- **%s**：%s" % (label, obj["text"].strip())]
    if (obj.get("quote") or "").strip():
        lines.append("  - 原文依据（%s）：「%s」" % (_src_str(obj.get("source")),
                                                    obj["quote"].strip()))
    return "\n".join(lines)


def render_notes_md(skeleton, notes):
    meta = skeleton.get("metadata") or {}
    title = (meta.get("title") or {}).get("value") or "（未识别标题）"
    L = ["# 论文笔记：%s\n" % title]
    L.append("> 骨架来自论文自身章节；每条笔记可回指页码/章节/段落，并可回到原文引文核验。\n")

    card = notes.get("card") or {}
    L.append("\n## 论文卡片\n")
    for label, key in (("研究问题", "research_question"), ("数据", "data"),
                       ("方法", "method"), ("结论", "conclusion"),
                       ("局限", "limitations")):
        b = _field_md(label, card.get(key))
        if b:
            L.append(b)
    for i, f in enumerate(card.get("main_findings", []), 1):
        b = _field_md("主要发现 %d" % i, f)
        if b:
            L.append(b)
    for i, f in enumerate(card.get("preconditions", []), 1):
        b = _field_md("前提条件 %d" % i, f)
        if b:
            L.append(b)

    sec_by_id = {s["id"]: s for s in skeleton["sections"]}
    L.append("\n## 章节笔记\n")
    for c in notes.get("chapter_notes", []):
        sid = c.get("section_id") or "S0"
        st = sec_by_id.get(sid, {}).get("title") or "（未知章节）"
        pg = c.get("source", {}).get("page")
        L.append("\n### %s · %s%s\n" % (sid, st, (" · 第 %s 页" % pg) if pg else ""))
        for label, key in (("目的", "purpose"), ("方法", "method"),
                           ("结果", "result"), ("结论", "conclusion")):
            if (c.get(key) or "").strip():
                L.append("- **%s**：%s" % (label, c[key].strip()))
        if (c.get("quote") or "").strip():
            L.append("- **原文依据**：「%s」" % c["quote"].strip())
        if (c.get("note") or "").strip():
            L.append("- **说明**：%s" % c["note"].strip())

    if notes.get("knowledge_points"):
        L.append("\n## 知识点\n")
        for k in notes["knowledge_points"]:
            L.append("\n### %s · %s\n" % (k.get("id", "K?"), k.get("concept", "").strip()))
            if (k.get("definition") or "").strip():
                L.append("- **定义**：%s" % k["definition"].strip())
            aliases = [a for a in (k.get("aliases") or []) if str(a).strip()]
            if aliases:
                L.append("- **同义/缩写**：%s" % "、".join(aliases))
            if (k.get("quote") or "").strip():
                L.append("- **原文依据**：「%s」" % k["quote"].strip())
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="/input")
    ap.add_argument("--output", default="/app/output")
    ap.add_argument("--work", default="/app/work")
    ap.add_argument("--notes", default=None, help="path to notes.json (phase 2)")
    args = ap.parse_args()

    indir, outdir, workdir = Path(args.input), Path(args.output), Path(args.work)
    outdir.mkdir(parents=True, exist_ok=True)
    workdir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    changes, uncertainties = [], []

    case = {}
    case_path = indir / "case.json"
    if case_path.is_file():
        try:
            case = json.loads(case_path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as e:
            changes.append("case.json parse error: %s" % e)
    case_id = case.get("case_id") or case.get("id") or "unknown"
    task_text = ""
    task_path = indir / "task.md"
    if task_path.is_file():
        task_text = task_path.read_text(encoding="utf-8-sig", errors="replace")

    pdf = locate_pdf(case, indir, workdir)
    if pdf is None:
        result = {"case_id": case_id, "status": "failed",
                  "reason": "no PDF material found in input directory",
                  "uncertainties": [{"issue": "missing input PDF"}],
                  "sources": [], "changes": changes,
                  "runtime": {"seconds": round(time.time() - t0, 2)}}
        (outdir / "result.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print("status=failed reason=no-pdf")
        return 1

    fp_current = {
        "case_id": case_id,
        "pdf": str(pdf.resolve()), "pdf_size": pdf.stat().st_size,
        "pdf_md5": hashlib.md5(pdf.read_bytes()).hexdigest(),
        "case_md5": hashlib.md5(case_path.read_bytes()).hexdigest()
        if case_path.is_file() else None,
        "task_md5": hashlib.md5(task_path.read_bytes()).hexdigest()
        if task_path.is_file() else None,
    }
    fp_path = workdir / "phase1_fingerprint.json"
    skel_path = workdir / "skeleton.json"

    skeleton = None
    parsed = None
    if skel_path.is_file() and fp_path.is_file():
        try:
            old = json.loads(fp_path.read_text(encoding="utf-8"))
            if old == fp_current:
                skeleton = json.loads(skel_path.read_text(encoding="utf-8"))
                parsed = json.loads((workdir / "parse_result.json").read_text(
                    encoding="utf-8"))
                changes.append("phase-1 reused from work cache (PDF not re-parsed)")
        except (json.JSONDecodeError, KeyError, FileNotFoundError):
            skeleton, parsed = None, None

    if skeleton is None:
        for stale in ("result.json", "fulltext.md", "source.md"):
            (workdir / stale).unlink(missing_ok=True)
        parser_stdout = workdir / "parser.stdout.log"
        parser_stderr = workdir / "parser.stderr.log"
        with parser_stdout.open("w", encoding="utf-8") as so, \
                parser_stderr.open("w", encoding="utf-8") as se:
            run = subprocess.run(
                [sys.executable, str(PARSER), str(pdf), "--out", str(workdir),
                 "--case-id", str(case_id)],
                stdout=so, stderr=se, timeout=600)
        if run.returncode != 0:
            result = {"case_id": case_id, "status": "failed",
                      "reason": "parser failed (code %d)" % run.returncode,
                      "parser_stderr_tail": parser_stderr.read_text(
                          encoding="utf-8", errors="replace")[-1000:],
                      "uncertainties": [{"issue": "parser failure"}],
                      "sources": [], "changes": changes,
                      "runtime": {"seconds": round(time.time() - t0, 2)}}
            (outdir / "result.json").write_text(
                json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            print("status=failed reason=parser")
            return 1
        parsed = json.loads((workdir / "result.json").read_text(encoding="utf-8"))
        if parsed.get("case_id") != case_id:
            result = {"case_id": case_id, "status": "failed",
                      "reason": "parser case_id mismatch", "uncertainties": [],
                      "sources": [], "changes": changes,
                      "runtime": {"seconds": round(time.time() - t0, 2)}}
            (outdir / "result.json").write_text(
                json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            print("status=failed reason=case-id-mismatch")
            return 1
        (workdir / "parse_result.json").write_text(
            json.dumps(parsed, ensure_ascii=False), encoding="utf-8")
        skeleton = bs.build_skeleton(parsed, str(pdf))
        (workdir / "skeleton.json").write_text(
            json.dumps(skeleton, ensure_ascii=False, indent=2), encoding="utf-8")
        (workdir / "source.md").write_text(bs.render_source_md(skeleton),
                                           encoding="utf-8")
        uncertainties.extend(parsed.get("uncertainties", []))
        fp_path.write_text(json.dumps(fp_current, ensure_ascii=False, indent=2),
                           encoding="utf-8")

    # ------------------------------------------------------------- phase 2
    notes = None
    if args.notes and Path(args.notes).is_file():
        try:
            notes = json.loads(Path(args.notes).read_text(encoding="utf-8-sig"))
            if not isinstance(notes, dict):
                notes = {"card": notes}
            changes.append("merged notes.json")
        except json.JSONDecodeError as e:
            uncertainties.append({"issue": "notes.json parse error", "detail": str(e)})

    verification = None
    if notes:
        ver_result = ver.verify_notes(skeleton, notes)
        verification = ver_result[0]
        (workdir / "verification.json").write_text(
            json.dumps(verification, ensure_ascii=False, indent=2), encoding="utf-8")
        (workdir / "verification.md").write_text(ver_result[1], encoding="utf-8")
        changes.append("verification executed (structure/completeness/anchoring/reuse)")

    # ---------------------------------------------------------- assemble
    card = (notes or {}).get("card") or {}
    card_summary = {
        "card_fields_present": sum(1 for f in CARD_FIELDS
                                   if isinstance(card.get(f), dict)
                                   and (card[f].get("text") or "").strip()),
        "card_fields_required": len(CARD_FIELDS),
        "main_findings": len(card.get("main_findings") or []),
        "preconditions": len(card.get("preconditions") or []),
        "chapter_notes": len((notes or {}).get("chapter_notes") or []),
        "sections_total": len(skeleton["sections"]),
        "knowledge_points": len((notes or {}).get("knowledge_points") or []),
    }
    meta = skeleton.get("metadata") or {}
    paper_view = {
        "title": (meta.get("title") or {}).get("value"),
        "authors": (meta.get("authors") or {}).get("value"),
        "abstract": (meta.get("abstract") or {}).get("value"),
        "sections": [{"id": s["id"], "title": s["title"], "page": s["page"]}
                     for s in skeleton["sections"]],
    }
    result_obj = {
        "paper": paper_view,
        "card": card if notes else {},
        "chapter_notes": (notes or {}).get("chapter_notes") if notes else [],
        "knowledge_points": (notes or {}).get("knowledge_points") if notes else [],
        "verification": verification,
        "summary": card_summary,
    }

    if parsed and parsed.get("status") == "unreadable" and not skeleton["segments"]:
        status = "unreadable"
    elif not notes:
        status = "partial"
    elif verification and verification.get("status") == "issues_found":
        status = "partial"
    else:
        status = "success"

    sources = [
        {"item": "paper_skeleton", "locator": "result.paper.sections[*].id/.title/.page"},
        {"item": "card", "locator": "result.card[*].source.page/.section_id/.quote"},
        {"item": "chapter_notes", "locator": "result.chapter_notes[*].section_id/.source.page/.quote"},
        {"item": "verification", "locator": "result.verification.checks"},
    ]
    if verification and verification.get("issues"):
        uncertainties.extend(verification["issues"])
    if verification and verification.get("warnings"):
        uncertainties.extend([{"issue": "human_review", "detail": w}
                              for w in verification["warnings"]])

    final = {
        "case_id": case_id,
        "status": status,
        "input": {"pdf": str(pdf), "pages": skeleton.get("pages")},
        "task": task_text[:2000] if task_text else None,
        "result": result_obj,
        "sources": sources,
        "uncertainties": uncertainties,
        "changes": changes,
        "runtime": {"parser": parsed.get("runtime") if parsed else None,
                    "total_seconds": round(time.time() - t0, 2)},
    }
    for f in contract_fields(case):
        if f not in final:
            if f == "result":
                final["result"] = result_obj
            elif f == "sources":
                final["sources"] = sources
            elif f == "uncertainties":
                final["uncertainties"] = uncertainties
            elif f == "status":
                final["status"] = status
            else:
                final[f] = None
                uncertainties.append({"issue": "output_contract field not produced",
                                      "field": f})
    final["output_contract_raw"] = case.get("output_contract")

    (outdir / "result.json").write_text(
        json.dumps(final, ensure_ascii=False, indent=2), encoding="utf-8")
    (outdir / "source.md").write_text(bs.render_source_md(skeleton), encoding="utf-8")
    if notes:
        (outdir / "notes.md").write_text(render_notes_md(skeleton, notes),
                                         encoding="utf-8")
        if (workdir / "verification.md").is_file():
            (outdir / "verification.md").write_text(
                (workdir / "verification.md").read_text(encoding="utf-8"),
                encoding="utf-8")

    print("status=%s case_id=%s sections=%d segments=%d notes=%s" % (
        final["status"], case_id, len(skeleton["sections"]),
        len(skeleton["segments"]), "yes" if notes else "no"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
