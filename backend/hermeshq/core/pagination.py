"""Reusable pagination helpers for list endpoints."""
from __future__ import annotations

from typing import Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel
from sqlalchemy import Select, func, select

T = TypeVar("T")

# ── Parameters ──────────────────────────────────────────────────────────────

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200


class PaginationParams:
    """FastAPI dependency that extracts ``page`` and ``page_size`` from the
    query string with sensible defaults and bounds."""

    def __init__(
        self,
        page: int = Query(default=1, ge=1, description="1‑based page number"),
        page_size: int = Query(
            default=DEFAULT_PAGE_SIZE,
            ge=1,
            le=MAX_PAGE_SIZE,
            description="Items per page",
        ),
    ):
        self.page = page
        self.page_size = page_size

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        return self.page_size


# ── Response schema ─────────────────────────────────────────────────────────


class PaginatedResponse(BaseModel, Generic[T]):
    """Envelope returned by every paginated endpoint."""

    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int


# ── Query helper ────────────────────────────────────────────────────────────


async def paginate(
    stmt: Select,
    db,  # AsyncSession — avoid hard import to prevent circular issues
    params: PaginationParams,
    serializer=None,
) -> PaginatedResponse:
    """Apply ``offset``/``limit`` to *stmt*, count total rows, and return a
    :class:`PaginatedResponse`.

    *serializer* is an optional callable applied to every ORM object before
    inclusion in ``items`` (e.g. ``TaskRead.model_validate``).
    """
    # Count total matching rows (before pagination)
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    # Apply pagination
    paginated_stmt = stmt.offset(params.offset).limit(params.limit)
    result = await db.execute(paginated_stmt)
    rows = result.scalars().all()

    items = [serializer(r) for r in rows] if serializer else list(rows)

    total_pages = max(1, -(-total // params.page_size))  # ceil division

    return PaginatedResponse(
        items=items,
        total=total,
        page=params.page,
        page_size=params.page_size,
        total_pages=total_pages,
    )
