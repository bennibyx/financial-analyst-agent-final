from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    ticker: Mapped[str | None] = mapped_column(String(20), unique=True, index=True)
    cik: Mapped[str | None] = mapped_column(String(20), unique=True, index=True)
    industry: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    documents = relationship(
        "Document",
        back_populates="company",
        cascade="all, delete-orphan",
    )

    metrics = relationship(
        "Metric",
        back_populates="company",
        cascade="all, delete-orphan",
    )

    risks = relationship(
        "Risk",
        back_populates="company",
        cascade="all, delete-orphan",
    )

    chat_history = relationship(
        "ChatHistory",
        back_populates="company",
        cascade="all, delete-orphan",
    )