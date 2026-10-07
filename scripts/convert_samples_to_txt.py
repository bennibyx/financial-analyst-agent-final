# Converts every PDF in data/samples/ into a .txt file next to it (fast version).
import pathlib
import fitz  # PyMuPDF

for pdf in sorted(pathlib.Path("data/samples").glob("*.pdf")):
    out = pdf.with_suffix(".txt")
    if out.exists():
        print(f"skip {out.name} (already exists)")
        continue
    print(f"converting {pdf.name} ...", flush=True)
    doc = fitz.open(pdf)
    text = "\n".join(page.get_text() for page in doc)
    out.write_text(text)
    print(f"  done: {len(doc)} pages, {len(text)} characters -> {out.name}", flush=True)
