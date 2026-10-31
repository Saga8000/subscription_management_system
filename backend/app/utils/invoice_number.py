"""Gap-tolerant, concurrency-safe document numbers backed by PostgreSQL sequences
(created in the initial migration)."""

from typing import Literal

from sqlalchemy import text
from sqlalchemy.orm import Session

DocumentKind = Literal["quotation", "subscription", "invoice"]

_SEQUENCES: dict[str, tuple[str, str]] = {
    "quotation": ("quotation_number_seq", "QT"),
    "subscription": ("subscription_number_seq", "SUB"),
    "invoice": ("invoice_number_seq", "INV"),
}


def next_document_number(db: Session, kind: DocumentKind) -> str:
    sequence, prefix = _SEQUENCES[kind]
    value = db.execute(text(f"SELECT nextval('{sequence}')")).scalar_one()
    return f"{prefix}-{value:06d}"
