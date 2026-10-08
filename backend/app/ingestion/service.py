from sqlalchemy.orm import Session

from ..models import Chunk, Document
from .chunker import chunk_text


def persist_document(
    db: Session,
    *,
    company_id: int,
    filename: str,
    content: str,
    document_type: str | None = None,
    source: str | None = None,
) -> Document:
    document = Document(
        company_id=company_id,
        filename=filename,
        document_type=document_type,
        source=source,
        content=content,
    )

    document.chunks = [
        Chunk(chunk_index=index, text=chunk)
        for index, chunk in enumerate(chunk_text(content))
    ]

    db.add(document)
    db.commit()
    db.refresh(document)

    return document
