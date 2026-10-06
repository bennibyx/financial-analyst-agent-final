from pathlib import Path
import re

from bs4 import BeautifulSoup
from pypdf import PdfReader


QA_MARKERS = [
    "question-and-answer",
    "question and answer",
    "questions and answers",
    "q&a",
    "q & a",
]


def clean_text(text: str) -> str:
    """Normalize extracted document text while preserving line breaks."""

    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]

    return "\n".join(lines)


def format_pdf_tables(text: str) -> str:
    """
    Convert aligned PDF columns into Markdown-style table rows.

    Example:
        Revenue       10.5 billion       9.2 billion

    Becomes:
        | Revenue | 10.5 billion | 9.2 billion |

    This works best when the PDF layout extractor preserves spacing
    between columns. It is a heuristic, not a full table detector.
    """

    formatted_lines = []

    for line in text.splitlines():
        stripped_line = line.strip()

        if not stripped_line:
            continue

        # Split columns separated by two or more spaces.
        columns = re.split(r"\s{2,}", stripped_line)

        if len(columns) >= 2:
            columns = [column.strip() for column in columns]

            # Avoid emitting empty table cells.
            columns = [column for column in columns if column]

            if len(columns) >= 2:
                formatted_lines.append(
                    "| " + " | ".join(columns) + " |"
                )
                continue

        formatted_lines.append(stripped_line)

    return "\n".join(formatted_lines)


def extract_text(file_path: Path) -> str:
    """Extract text from TXT, HTML, or PDF files."""

    extension = file_path.suffix.lower()

    if extension == ".txt":
        # Try UTF-8 first. Fall back to Latin-1 for invalid UTF-8 bytes.
        try:
            text = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = file_path.read_text(encoding="latin-1")

    elif extension in {".html", ".htm"}:
        # HTML files may contain legacy characters.
        try:
            text = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = file_path.read_text(encoding="latin-1")

    elif extension == ".pdf":
        reader = PdfReader(str(file_path))
        pages = []

        for page in reader.pages:
            try:
                # Layout mode attempts to preserve columns and spacing.
                page_text = page.extract_text(
                    extraction_mode="layout"
                ) or ""
            except (TypeError, ValueError):
                # Compatibility fallback for older pypdf versions.
                page_text = page.extract_text() or ""

            # Convert aligned columns into pipe-delimited rows.
            page_text = format_pdf_tables(page_text)
            pages.append(page_text)

        text = "\n".join(pages)

    else:
        raise ValueError(f"Unsupported file type: {extension}")

    return clean_text(text)


def split_transcript(text: str) -> dict:
    """Split an earnings-call transcript into prepared remarks and Q&A."""

    cleaned = clean_text(text)
    lower_text = cleaned.lower()

    qa_position = None
    matched_marker = None

    for marker in QA_MARKERS:
        position = lower_text.find(marker)

        if position != -1:
            if qa_position is None or position < qa_position:
                qa_position = position
                matched_marker = marker

    if qa_position is None:
        return {
            "prepared_remarks": cleaned,
            "qa": "",
            "qa_detected": False,
        }

    prepared_remarks = cleaned[:qa_position].strip()
    qa = cleaned[qa_position + len(matched_marker):].strip()

    return {
        "prepared_remarks": prepared_remarks,
        "qa": qa,
        "qa_detected": True,
    }


def parse_speakers(text: str) -> list[dict]:
    """Convert speaker-labelled transcript text into structured records."""

    cleaned = clean_text(text)

    speaker_pattern = re.compile(
        r"^(.+?)\s*:\s*(.*)$"
    )

    records = []
    current_speaker = None
    current_lines = []

    for line in cleaned.splitlines():
        match = speaker_pattern.match(line)

        if match:
            if current_speaker is not None:
                records.append(
                    {
                        "speaker": current_speaker,
                        "text": " ".join(current_lines).strip(),
                    }
                )

            current_speaker = match.group(1).strip()
            current_lines = []

            if match.group(2).strip():
                current_lines.append(match.group(2).strip())

        elif current_speaker is not None:
            current_lines.append(line)

    if current_speaker is not None:
        records.append(
            {
                "speaker": current_speaker,
                "text": " ".join(current_lines).strip(),
            }
        )

    return records


def parse_transcript(text: str) -> dict:
    """Parse a transcript into sections and speaker records."""

    sections = split_transcript(text)

    prepared_speakers = parse_speakers(
        sections["prepared_remarks"]
    )

    qa_speakers = parse_speakers(
        sections["qa"]
    )

    return {
        "prepared_remarks": prepared_speakers,
        "qa": qa_speakers,
        "qa_detected": sections["qa_detected"],
    }


# ---------------------------------------------------------------------------
# SEC filings (10-K / 10-Q)
# ---------------------------------------------------------------------------

# Matches by section TITLE, not by item number, because the numbering differs
# between forms (10-Q: Item 1 = Financial Statements, Item 2 = MD&A;
# 10-K: Item 1 = Business, Item 7 = MD&A, Item 8 = Financial Statements).
_ITEM = r"\bitem\s+\d+[a-c]?[\.\s:\u2013\u2014-]+"

SEC_SECTION_PATTERNS = [
    ("Business", _ITEM + r"business\b"),
    ("Risk Factors", _ITEM + r"risk\s+factors\b"),
    ("Unresolved Staff Comments", _ITEM + r"unresolved\s+staff\s+comments\b"),
    ("Properties", _ITEM + r"properties\b"),
    ("Legal Proceedings", _ITEM + r"legal\s+proceedings\b"),
    (
        "Market for Registrant's Common Equity",
        _ITEM + r"market\s+for\s+(?:the\s+)?registrant\W{0,3}s\s+common\s+equity",
    ),
    (
        "Management's Discussion and Analysis",
        _ITEM + r"management\W{0,3}s\s+discussion\s+and\s+analysis",
    ),
    (
        "Quantitative and Qualitative Disclosures",
        _ITEM + r"quantitative\s+and\s+qualitative\s+disclosures?\s+about\s+market\s+risk",
    ),
    ("Financial Statements", _ITEM + r"financial\s+statements"),
    ("Controls and Procedures", _ITEM + r"controls\s+and\s+procedures"),
]


def _row_cells(tr) -> list[str]:
    """
    Return the cell texts of one HTML table row.

    EDGAR often splits one number across cells: "$", "(250", ")".
    Drop the lone "$" cells and glue ")" / "%" back onto the previous cell.
    """

    cells = []

    for td in tr.find_all(["td", "th"]):
        value = td.get_text(" ", strip=True).replace("\xa0", " ").strip()

        if not value or value == "$":
            continue

        if value in {")", "%", ")%"} and cells:
            cells[-1] += value
        else:
            cells.append(value)

    return cells


def html_to_text(html: str) -> str:
    """Convert an EDGAR HTML filing to text, with tables as pipe rows."""

    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style"]):
        tag.decompose()

    # Inline-XBRL hidden header: machine data, not readable filing text.
    for tag in soup.find_all("ix:header"):
        tag.decompose()

    for table in soup.find_all("table"):
        lines = []

        for tr in table.find_all("tr"):
            cells = _row_cells(tr)

            if len(cells) >= 2:
                lines.append("| " + " | ".join(cells) + " |")
            elif cells:
                lines.append(cells[0])

        table.replace_with("\n" + "\n".join(lines) + "\n")

    return soup.get_text("\n").replace("\xa0", " ")


def _looks_like_html(text: str) -> bool:
    return bool(
        re.search(r"<\s*(html|body|table)\b", text[:20000], flags=re.IGNORECASE)
    )


def extract_sec_tables(text: str) -> list[str]:
    """
    Extract table-like blocks from SEC filing text.

    A table must contain at least two consecutive rows that either:
    - already use pipe separators, or
    - contain multiple spaced columns.
    """
    tables = []
    current_table = []

    def is_table_row(line: str) -> bool:
        stripped = line.strip()

        # Explicit pipe-delimited row
        if stripped.startswith("|") and stripped.endswith("|"):
            parts = [
                part.strip()
                for part in stripped.strip("|").split("|")
            ]
            return len(parts) >= 2

        # Space-aligned columns
        columns = re.split(r"\s{2,}", stripped)
        return len(columns) >= 2

    def normalize_row(line: str) -> str:
        stripped = line.strip()

        if stripped.startswith("|") and stripped.endswith("|"):
            parts = [
                part.strip()
                for part in stripped.strip("|").split("|")
                if part.strip()
            ]
        else:
            parts = [
                part.strip()
                for part in re.split(r"\s{2,}", stripped)
                if part.strip()
            ]

        return "| " + " | ".join(parts) + " |"

    for line in text.splitlines():
        stripped = line.strip()

        if not stripped:
            if len(current_table) >= 2:
                tables.append("\n".join(current_table))
            current_table = []
            continue

        if is_table_row(stripped):
            current_table.append(normalize_row(stripped))
        else:
            if len(current_table) >= 2:
                tables.append("\n".join(current_table))
            current_table = []

    if len(current_table) >= 2:
        tables.append("\n".join(current_table))

    return tables


def extract_sec_sections(text: str) -> list[dict]:
    """
    Split an SEC 10-K/10-Q filing into major Item-based sections.
    """

    matches = []

    for section_name, pattern in SEC_SECTION_PATTERNS:
        for match in re.finditer(
            pattern,
            text,
            flags=re.IGNORECASE,
        ):
            matches.append(
                {
                    "name": section_name,
                    "start": match.start(),
                    "end": match.end(),
                }
            )

    # Sort sections by their position in the filing.
    matches.sort(key=lambda item: item["start"])

    sections = []

    for index, current in enumerate(matches):
        start = current["end"]

        if index + 1 < len(matches):
            end = matches[index + 1]["start"]
        else:
            end = len(text)

        section_text = text[start:end].strip()

        if not section_text:
            continue

        tables = extract_sec_tables(section_text)

        sections.append(
            {
                "section": current["name"],
                "text": section_text,
                "tables": tables,
                "_start": current["start"],
            }
        )

    # The table of contents repeats every Item heading with almost no text.
    # If a section name appears more than once, keep the longest one.
    best = {}

    for section in sections:
        name = section["section"]

        if name not in best or len(section["text"]) > len(best[name]["text"]):
            best[name] = section

    # Keep the sections in the order they appear in the filing.
    ordered = sorted(best.values(), key=lambda item: item["_start"])

    for section in ordered:
        section.pop("_start")

    return ordered


def parse_sec_filing(text: str) -> dict:
    """
    Parse an SEC 10-K or 10-Q filing (HTML or plain text) into
    structured sections and tables.
    """

    if _looks_like_html(text):
        text = html_to_text(text)

    cleaned = clean_text(text)

    sections = extract_sec_sections(cleaned)

    return {
        "document_type": "SEC filing",
        "sections": sections,
        "section_count": len(sections),
    }
