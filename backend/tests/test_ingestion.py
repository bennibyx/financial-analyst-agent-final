import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.ingestion.service import persist_document
from app.models import Chunk, Company, Document


def test_persist_document_saves_document_and_chunks(tmp_path):
    database_file = tmp_path / "test_ingestion.db"
    engine = create_engine(
        f"sqlite:///{database_file}",
        connect_args={"check_same_thread": False},
    )

    try:
        Base.metadata.create_all(bind=engine)
        TestingSessionLocal = sessionmaker(bind=engine)

        with TestingSessionLocal() as db:
            company = Company(name="Test Company")
            db.add(company)
            db.commit()
            db.refresh(company)

            content = "revenue growth and risk " * 80

            document = persist_document(
                db,
                company_id=company.id,
                filename="annual_report.txt",
                content=content,
                document_type="annual_report",
                source="test",
            )

            document_id = document.id

            assert document_id is not None
            assert document.filename == "annual_report.txt"
            assert document.company_id == company.id
            assert document.document_type == "annual_report"

            saved_document = db.get(Document, document_id)
            assert saved_document is not None
            assert saved_document.content == content

            saved_chunks = db.scalars(
                select(Chunk)
                .where(Chunk.document_id == document_id)
                .order_by(Chunk.chunk_index)
            ).all()

            assert len(saved_chunks) == 2
            assert [chunk.chunk_index for chunk in saved_chunks] == [0, 1]
            assert all(chunk.text.strip() for chunk in saved_chunks)
            assert all(
                chunk.document_id == document_id for chunk in saved_chunks
            )
            assert saved_document.chunks == saved_chunks

    finally:
        engine.dispose()
