# check_pdfs.py -- reports pages and extractable text for each PDF
from pathlib import Path
from pypdf import PdfReader

for pdf in sorted(Path("data/sample").glob("*.pdf")):
    reader = PdfReader(pdf)
    # extract_text() returns "" for pages that are only images
    chars = sum(len(p.extract_text() or "") for p in reader.pages)
    mb = pdf.stat().st_size / 1e6
    print(f"{pdf.name:32} pages={len(reader.pages):4} chars={chars:8} size={mb:.1f}MB")
