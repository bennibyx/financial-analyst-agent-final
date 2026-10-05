from pathlib import Path
import re

from pypdf import PdfReader


QA_MARKERS = [
    "question-and-answer",
    "question and answer",
    "questions and answers",
    "q&a",
    "q & a",
]


def clean_text(text: str) -> str:
    """Normalize extracted document text."""

    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]

    return "\n".join(lines)


def extract_text(file_path: Path) -> str:
    """Extract text from TXT, HTML, or PDF files."""

    extension = file_path.suffix.lower()

    if extension == ".txt":
        text = file_path.read_text(
            encoding="utf-8",
            errors="ignore",
        )

    elif extension in {".html", ".htm"}:
        text = file_path.read_text(
            encoding="utf-8",
            errors="ignore",
        )

    elif extension == ".pdf":
        reader = PdfReader(str(file_path))
        pages = []

        for page in reader.pages:
            page_text = page.extract_text() or ""
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
    """Parse an earnings-call transcript into structured sections and speakers."""

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