"""Immutable, database-backed documents supporting excused attendance."""
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String, UniqueConstraint, false
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.education import UTCDateTime, utc_now


class ProofDocument(Base):
    __tablename__ = 'proof_documents'
    __table_args__ = (UniqueConstraint('revision_id', 'sha256'),
                      CheckConstraint('size > 0 AND size <= 5242880'))
    revision_id: Mapped[int] = mapped_column(ForeignKey('attendance_revisions.id', ondelete='RESTRICT'))
    filename: Mapped[str] = mapped_column(String(255))
    mime: Mapped[str] = mapped_column(String(32))
    size: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    sealed: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    approved_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class ProofChunk(Base):
    __tablename__ = 'proof_chunks'
    __table_args__ = (UniqueConstraint('document_id', 'position'),
                      CheckConstraint('position >= 0 AND length(data_text) > 0 AND length(data_text) <= 12000'))
    document_id: Mapped[int] = mapped_column(ForeignKey('proof_documents.id', ondelete='RESTRICT'))
    position: Mapped[int] = mapped_column(Integer)
    data_text: Mapped[str] = mapped_column(String(12000))
