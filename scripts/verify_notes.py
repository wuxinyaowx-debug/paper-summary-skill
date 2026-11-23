#!/usr/bin/env python3
"""verify_notes.py — Deterministic verification of structured paper notes.

Checks the four qualities the challenge scores:
  对得上 (structure)  — chapter_notes reference real paper sections, in order;
  留得住 (completeness)— required card fields present, every section has a note;
  找得回 (anchoring)   — anchors resolve to real pages/sections/segments and
                         each quote verbatim appears at its anchor;
  用得上 (reusability) — valid schema, unique ids, deduplicated knowledge points.

Hard checks raise `issues_found` (mapped to status=partial by the harness);
soft checks are reported as human-review items without failing the run.
"""
import json
import re
from collections import Counter

_NUM_RE = re.compile(r"\b\d+(?:[.,]\d+)*(?:[eE][+-]?\d+)?\b")

CARD_FIELDS = ["research_question", "data", "method", "conclusion", "limitations"]
# findings and optional preconditions are lists
LIST_FIELDS = ["main_findings", "preconditions"]


def _norm(s):
    return "".join(str(s or "").split()).lower()


def _field_text(obj):
    if isinstance(obj, dict):
        return (obj.get("text") or "").strip()
    return ""


def _anchors_ok(obj, skeleton):
    """Validate one note's source anchor. Returns list of issue strings."""
    src = obj.get("source") or {}
    issues = []
    pages = skeleton.get("pages")
    if pages is not None and src.get("page") is not None:
        try:
            p = int(src["page"])
            if not (1 <= p <= int(pages)):
                issues.append("page %s out of range 1..%s" % (src["page"], pages))
        except (TypeError, ValueError):
            issues.append("page not numeric: %r" % src.get("page"))
    sec_ids = {s["id"] for s in skeleton["sections"]}
    if src.get("section_id") and src["section_id"] not in sec_ids:
        issues.append("unknown section_id %s" % src["section_id"])
    seg_ids = {s["id"] for s in skeleton["segments"]}
    if src.get("segment_id") and src["segment_id"] not in seg_ids:
        issues.append("unknown segment_id %s" % src["segment_id"])
    return issues


def _quote_ok(obj, skeleton, sec_text):
    quote = (obj.get("quote") or "").strip()
    if not quote:
        return []  # quote optional; absence handled by completeness warnings
    src = obj.get("source") or {}
    seg_id = src.get("segment_id")
    sid = src.get("section_id")
    page = src.get("page")
    # choose candidate source text
    if seg_id:
        for s in skeleton["segments"]:
            if s["id"] == seg_id:
                candid = s.get("src") or ""
                break
        else:
            candid = ""
    elif sid:
        candid = sec_text.get(sid, "")
    elif page is not None:
        candid = "\n".join(s.get("src") or "" for s in skeleton["segments"]
                           if s.get("page") == page)
    else:
        candid = "\n".join(s.get("src") or "" for s in skeleton["segments"])
    q = _norm(quote)
    c = _norm(candid)
    if q and (q not in c):
        return ["quote not found at anchor: %s" % quote[:60]]
    return []


def _numbers_present_in_source(text, skeleton):
    """Soft check: numbers of length >=2 asserted in a note should appear
    somewhere in the paper text."""
    all_src = _norm("\n".join(s.get("src") or "" for s in skeleton["segments"]))
    missing = []
    for m in set(re.findall(r"\b\d+(?:[.,]\d+)*\b", text or "")):
        if len(m) >= 2 and m not in all_src:
            missing.append(m)
    return missing


def verify_notes(skeleton, notes):
    issues, warnings = [], []
    checks = {}
    sections = skeleton["sections"]
    sec_ids = [s["id"] for s in sections]
    sec_text = {}
    for s in skeleton["segments"]:
        sid = s.get("section_id") or "S0"
        sec_text.setdefault(sid, []).append(s.get("src") or "")
    sec_text = {sid: "\n".join(t) for sid, t in sec_text.items()}

    card = notes.get("card") or {}
    chapters = notes.get("chapter_notes") or []
    kps = notes.get("knowledge_points") or []

    # ---- 1. structure (对得上)
    chap_ids = [c.get("section_id") for c in chapters]
    unknown = [c for c in chap_ids if c not in sec_ids]
    dup = [c for c, n in Counter(chap_ids).items() if n > 1]
    if unknown:
        issues.append("chapter_notes reference unknown section: %s" % unknown)
    if dup:
        issues.append("duplicate chapter_notes for sections: %s" % dup)
    seen = [sec_ids.index(c) for c in chap_ids if c in sec_ids]
    if seen != sorted(seen):
        warnings.append("chapter_notes order differs from paper section order")

    # ---- 2. completeness (留得住)
    missing = [f for f in CARD_FIELDS if not _field_text(card.get(f))]
    if "main_findings" in LIST_FIELDS and not card.get("main_findings"):
        missing.append("main_findings")
    for f in missing:
        issues.append("card field missing or empty: %s" % f)
    uncovered = [sid for sid in sec_ids if sid not in chap_ids]
    if uncovered:
        issues.append("sections without a chapter note: %s" % uncovered)
    if not card.get("preconditions"):
        warnings.append("no preconditions recorded (结论成立的前提条件未单独列出)")

    # ---- 3-a. anchoring (找得回)
    anchor_fail = 0
    def check_anchor(obj, tag):
        nonlocal anchor_fail
        for i in _anchors_ok(obj, skeleton):
            issues.append("%s: %s" % (tag, i)); anchor_fail += 1
        for i in _quote_ok(obj, skeleton, sec_text):
            issues.append("%s: %s" % (tag, i)); anchor_fail += 1
    for k in CARD_FIELDS:
        if card.get(k):
            check_anchor(card[k], "card.%s" % k)
    for i, f in enumerate(card.get("main_findings", [])):
        check_anchor(f, "card.main_findings[%d]" % i)
    for i, f in enumerate(card.get("preconditions", [])):
        check_anchor(f, "card.preconditions[%d]" % i)
    for i, c in enumerate(chapters):
        check_anchor(c, "chapter_notes[%d]" % i)
    for i, k in enumerate(kps):
        check_anchor(k, "knowledge_points[%d]" % i)

    # ---- 3-b. number/unit soft consistency
    def _nums_str(miss):
        return ",".join(sorted(set(miss)))
    for k in CARD_FIELDS:
        t = _field_text(card.get(k))
        miss = _numbers_present_in_source(t, skeleton)
        if miss:
            warnings.append("card.%s numbers not found in source: %s" % (k, _nums_str(miss)))
    for i, f in enumerate(card.get("main_findings", [])):
        miss = _numbers_present_in_source(_field_text(f), skeleton)
        if miss:
            warnings.append("main_findings[%d] numbers not found in source: %s" % (i, _nums_str(miss)))

    # ---- 4. reusability (用得上)
    kp_ids = [k.get("id") for k in kps]
    if Counter(kp_ids) and max(Counter(kp_ids).values()) > 1:
        issues.append("duplicate knowledge_point ids")
    # knowledge points use concept/definition (per assets/note-schema.md),
    # not text — check those fields instead of _field_text
    bad_kp = [k.get("id") or "?" for k in kps
              if not ((k.get("concept") or "").strip()
                      or (k.get("definition") or "").strip())]
    if bad_kp:
        warnings.append("knowledge points missing concept text: %s" % bad_kp[:5])

    # ---- metrics
    n_chap_hits = len([c for c in chap_ids if c in sec_ids])
    structure_rate = (n_chap_hits / len(chap_ids)) if chap_ids else 0.0
    coverage_rate = (len(sec_ids) - len(uncovered)) / len(sec_ids) if sec_ids else 1.0
    required = len(CARD_FIELDS) + 1
    present = required - len(missing)
    checks = {
        "structure": {"known_sections": n_chap_hits, "total_notes": len(chap_ids),
                      "rate": round(structure_rate, 4)},
        "completeness": {"card_fields_present": present, "card_fields_required": required,
                         "sections_covered": len(sec_ids) - len(uncovered),
                         "sections_total": len(sec_ids), "rate": round(coverage_rate, 4)},
        "anchoring": {"verified": anchor_fail == 0, "failures": anchor_fail},
        "reusability": {"knowledge_point_ids": len(kp_ids),
                        "unique_ids": len(set(kp_ids)) == len(kp_ids)},
    }
    status = "issues_found" if issues else "ok"
    report = {"status": status, "issues": issues, "warnings": warnings,
              "checks": checks}
    return report, _markdown(report)


def _markdown(report):
    c = report["checks"]
    L = ["# 笔记核验报告", "- 状态：`%s`" % report["status"],
         "- 结构对齐：%.1f%%  ·  章节覆盖：%.1f%%  ·  锚点核验：%s" % (
             c["structure"]["rate"] * 100, c["completeness"]["rate"] * 100,
             "通过" if c["anchoring"]["verified"] else "存在失败"),
         ""]
    if report["issues"]:
        L.append("## 问题（阻断）")
        for i in report["issues"]:
            L.append("- %s" % i)
        L.append("")
    if report["warnings"]:
        L.append("## 提示（人工复核）")
        for w in report["warnings"]:
            L.append("- %s" % w)
        L.append("")
    return "\n".join(L)


def main():
    import argparse
    import sys
    ap = argparse.ArgumentParser()
    ap.add_argument("skeleton", help="skeleton.json")
    ap.add_argument("notes", help="notes.json")
    ap.add_argument("--out", default=".", help="output directory")
    args = ap.parse_args()
    skeleton = json.loads(Path(args.skeleton).read_text(encoding="utf-8"))
    notes = json.loads(Path(args.notes).read_text(encoding="utf-8"))
    report, md = verify_notes(skeleton, notes)
    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "verification.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (outdir / "verification.md").write_text(md, encoding="utf-8")
    print("status=%s issues=%d warnings=%d" % (
        report["status"], len(report["issues"]), len(report["warnings"])))
    return 0


if __name__ == "__main__":
    main()