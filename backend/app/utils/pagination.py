from typing import Any, Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

T = TypeVar("T")

MAX_PAGE_SIZE = 100


class PageParams:
    def __init__(
        self,
        page: int = Query(1, ge=1, le=100_000),
        page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
    ) -> None:
        self.page = page
        self.page_size = page_size

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


def paginate(db: Session, stmt: Select[Any], params: PageParams) -> tuple[list[Any], int]:
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    items = list(db.scalars(stmt.limit(params.page_size).offset(params.offset)).all())
    return items, total
