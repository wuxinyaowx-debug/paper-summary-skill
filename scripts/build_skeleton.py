#!/usr/bin/env python3
"""build_skeleton.py — Build the paper skeleton for structured note-taking.

From parse_pdf.py's structured output this module produces a *skeleton* that
anchors the note-taking step to the paper's own structure:

  - sections S1..SN (the paper's actual headings, in reading order),
  - ordered segments T0001..TNNNN with a section_id assignment,
  - figures / tables / equations / references with page anchors,
  - a human/Agent-readable source.md grouped by section.

The section_id assignment is what enables the "对得上" (structure follows the
paper, not a generic template) and "找得回" (every note points back to a real
section/paragraph/page) guarantees.
"""
import json
from pathlib import Path

# same directory modules
import segment as sg


def _norm(s):
    return (s or "").strip().lower()


def build_sections(parsed):
    """Return ordered section dicts S1..SN from parsed['sections']."""
    raw = parsed.get("sections") or []
    # stable reading order: page, then vertical position top-to-bottom
    def key(s):
        bb = s.get("bbox") or {}
        return (s.get("page") or 0, bb.get("y1", bb.get("y0", 0)) or 0)
    raw_sorted = sorted(raw, key=key)
    sections = []
    for i, s in enumerate(raw_sorted, 1):
        sections.append({
            "id": "S%d" % i,
            "title": s.get("title") or "",
            "page": s.get("page"),
            "bbox": s.get("bbox"),
        })
    # Fallback: a paper without any detected heading is still one implicit
    # section so the note skeleton never fabricates chapter boundaries.
    if not sections:
        sections = [{"id": "S0", "title": "全文（未检测到章节标题）",
                     "page": 1, "bbox": None}]
    return sections


def assign_section_ids(segments, sections):
    """Attach section_id to every segment by matching heading titles and
    inheriting the current section while walking in reading order."""
    title_to_id = {_norm(s["title"]): s["id"] for s in sections}
    current = sections[0]["id"] if sections else None
    out = []
    for seg in segments:
        seg = dict(seg)
        if seg.get("kind") == "heading":
            sid = title_to_id.get(_norm(seg.get("src")))
            if sid:
                current = sid
            seg["section_id"] = current
        else:
            # parser may already carry the paragraph's own section title
            own = title_to_id.get(_norm(seg.get("section")))
            seg["section_id"] = own or current
        out.append(seg)
    return out


def build_skeleton(parsed, pdf_path=None):
    """Return the skeleton dict (metadata + sections + anchored segments)."""
    sections = build_sections(parsed)
    segments = assign_section_ids(sg.build_segments(parsed, pdf_path), sections)
    meta = parsed.get("metadata") or {}
    return {
        "metadata": meta,
        "pages": (parsed.get("input") or {}).get("pages"),
        "sections": sections,
        "segments": segments,
        "figures": parsed.get("figures") or [],
        "tables": parsed.get("tables") or [],
        "equations": parsed.get("equations") or [],
        "references": parsed.get("references") or [],
    }


def section_text_map(skeleton):
    """section_id -> concatenated source text of its segments (for quote checks)."""
    m = {}
    for seg in skeleton["segments"]:
        sid = seg.get("section_id") or "S0"
        m.setdefault(sid, []).append(seg.get("src") or "")
    return {sid: "\n".join(txts) for sid, txts in m.items()}


def render_source_md(skeleton):
    """Structured source.md: one block per section, segment IDs + page anchors."""
    lines = []
    last_page = [0]
    last_section = [None]
    for seg in skeleton["segments"]:
        p = seg.get("page")
        sid = seg.get("section_id")
        if sid != last_section[0]:
            title = ""
            for s in skeleton["sections"]:
                if s["id"] == sid:
                    title = s["title"]
                    break
            lines.append("\n## %s %s\n" % (sid or "S0", title))
            last_section[0] = sid
        if p and p != last_page[0]:
            lines.append("\n[p.%d]\n" % p)
            last_page[0] = p
        kind = seg.get("kind")
        if kind == "equation":
            lines.append("[%s] $$\n%s\n$$\n" % (seg["id"], seg.get("src")))
        else:
            lines.append("[%s] %s\n" % (seg["id"], seg.get("src")))
    return "\n".join(lines)


def main():
    import argparse
    import sys
    ap = argparse.ArgumentParser()
    ap.add_argument("parse_result", help="parse_pdf.py result.json")
    ap.add_argument("--pdf", help="original PDF for reading-order recovery")
    ap.add_argument("--out", default=".", help="output directory")
    args = ap.parse_args()
    parsed = json.loads(Path(args.parse_result).read_text(encoding="utf-8"))
    skeleton = build_skeleton(parsed, args.pdf)
    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "skeleton.json").write_text(
        json.dumps(skeleton, ensure_ascii=False, indent=2), encoding="utf-8")
    (outdir / "source.md").write_text(render_source_md(skeleton),
                                      encoding="utf-8")
    print("sections=%d segments=%d" % (len(skeleton["sections"]),
                                       len(skeleton["segments"])))
    return 0


if __name__ == "__main__":
    main()
