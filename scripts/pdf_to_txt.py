import sys, pathlib
from pypdf import PdfReader

src = pathlib.Path(sys.argv[1])
dst = src.with_suffix(".txt")
reader = PdfReader(src)
text = "\n".join((page.extract_text() or "") for page in reader.pages)
dst.write_text(text)
print(f"{len(reader.pages)} pages, {len(text)} chars -> {dst}")
