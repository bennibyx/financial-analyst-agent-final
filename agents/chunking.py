# agents/chunking.py
# Cuts a filing into section-aware chunks (max ~4000 chars, 400 overlap, tables never split).
import re
from dataclasses import dataclass

# A heading must START a line (so "Refer to Item 1A..." inside a sentence is ignored).
SECTION_PATTERNS = [
    ("risk_factors", r"item\s+1a\.?\s+risk factors"),
    ("mdna", r"item\s+[27]\.?\s+management.s discussion and analysis"),
    ("financial_statements", r"item\s+[18]\.?\s+financial statements"),
]

@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    section: str
    text: str
    is_table: bool = False

def split_sections(text):
    hits = []
    for name, pat in SECTION_PATTERNS:
        for m in re.finditer(r"^[ \t]*" + pat, text, flags=re.I | re.M):
            line_end = text.find("\n", m.start())
            line = text[m.start(): line_end if line_end != -1 else len(text)]
            if re.search(r"\d+\s*$", line):   # table-of-contents lines end with a page number
                continue
            hits.append((m.start(), name))
    hits.sort()
    if not hits:
        return [("other", text)]            # fallback: no headings found
    out = []
    if hits[0][0] > 0:                      # keep text before the first heading
        out.append(("other", text[:hits[0][0]]))
    for i, (start, name) in enumerate(hits):
        end = hits[i + 1][0] if i + 1 < len(hits) else len(text)
        out.append((name, text[start:end]))
    return out

def chunk_section(section, text, doc_id, max_chars=4000, overlap=400):
    blocks, buf = [], []
    for line in text.split("\n"):
        buf.append(line)
        if line.strip() == "":
            blocks.append("\n".join(buf).strip()); buf = []
    if buf:
        blocks.append("\n".join(buf).strip())
    chunks, cur = [], ""
    def flush():
        nonlocal cur
        if cur.strip():
            chunks.append(Chunk(f"{doc_id}-{section}-{len(chunks)}", doc_id, section, cur.strip()))
        cur = cur[-overlap:] if overlap else ""
    for b in blocks:
        if b.lstrip().startswith("|"):          # a table: keep whole
            flush(); cur = ""
            chunks.append(Chunk(f"{doc_id}-{section}-{len(chunks)}", doc_id, section, b, True))
        elif len(cur) + len(b) > max_chars:
            flush(); cur += "\n" + b
        else:
            cur += "\n" + b
    flush()
    return chunks

def chunk_document(text, doc_id):
    return [c for name, body in split_sections(text) for c in chunk_section(name, body, doc_id)]
