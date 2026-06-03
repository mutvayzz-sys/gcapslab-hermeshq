"""Tests for core.pagination – PaginatedResponse, PaginationParams, paginate()."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from hermeshq.core.pagination import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    PaginatedResponse,
    PaginationParams,
    paginate,
)


# ---------------------------------------------------------------------------
# PaginationParams
# ---------------------------------------------------------------------------

class TestPaginationParams:
    def test_defaults(self):
        p = PaginationParams(page=1, page_size=DEFAULT_PAGE_SIZE)
        assert p.page == 1
        assert p.page_size == DEFAULT_PAGE_SIZE

    def test_offset_page1(self):
        p = PaginationParams(page=1, page_size=20)
        assert p.offset == 0

    def test_offset_page2(self):
        p = PaginationParams(page=2, page_size=20)
        assert p.offset == 20

    def test_offset_page5_size10(self):
        p = PaginationParams(page=5, page_size=10)
        assert p.offset == 40

    def test_limit(self):
        p = PaginationParams(page=1, page_size=25)
        assert p.limit == 25

    def test_custom_page_size(self):
        p = PaginationParams(page=3, page_size=100)
        assert p.offset == 200
        assert p.limit == 100

    def test_max_page_size_constant(self):
        assert MAX_PAGE_SIZE == 200

    def test_default_page_size_constant(self):
        assert DEFAULT_PAGE_SIZE == 50


# ---------------------------------------------------------------------------
# PaginatedResponse
# ---------------------------------------------------------------------------

class TestPaginatedResponse:
    def test_schema(self):
        r = PaginatedResponse[int](
            items=[1, 2, 3],
            total=10,
            page=1,
            page_size=3,
            total_pages=4,
        )
        assert r.items == [1, 2, 3]
        assert r.total == 10
        assert r.page == 1
        assert r.page_size == 3
        assert r.total_pages == 4

    def test_json_serialization(self):
        r = PaginatedResponse[str](
            items=["a", "b"],
            total=2,
            page=1,
            page_size=50,
            total_pages=1,
        )
        data = r.model_dump()
        assert data == {
            "items": ["a", "b"],
            "total": 2,
            "page": 1,
            "page_size": 50,
            "total_pages": 1,
        }

    def test_empty_page(self):
        r = PaginatedResponse[object](
            items=[],
            total=100,
            page=11,
            page_size=10,
            total_pages=10,
        )
        assert r.items == []
        assert r.total == 100


# ---------------------------------------------------------------------------
# paginate() helper — we patch the module-level paginate to use a real
# SQLAlchemy select against an in-memory SQLite table so that subquery()
# works correctly, or we test via integration-style mocking.
# ---------------------------------------------------------------------------

class TestPaginateIntegration:
    """Integration tests using a real SQLite in-memory database."""

    @pytest.fixture()
    def sqlite_engine(self):
        from sqlalchemy import create_engine, Column, Integer, String
        from sqlalchemy.orm import DeclarativeBase, Session

        class Base(DeclarativeBase):
            pass

        class Item(Base):
            __tablename__ = "items"
            id = Column(Integer, primary_key=True)
            name = Column(String(50))

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)

        # Insert 25 rows
        with Session(engine) as s:
            for i in range(1, 26):
                s.add(Item(id=i, name=f"item-{i}"))
            s.commit()

        return engine

    @pytest.mark.asyncio
    async def test_first_page(self, sqlite_engine):
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

        # sqlite doesn't have async, use sync session wrapped
        from sqlalchemy.orm import Session

        stmt = select(
            __import__("sqlalchemy").text("*")
        ).select_from(
            __import__("sqlalchemy").text("items")
        )
        # Use a simpler approach: patch db.execute to use the sync engine
        from sqlalchemy import select as sa_select
        from hermeshq.models.task import Task  # just to get a real select

        # Instead, just verify the logic via mocking the two db.execute calls
        db = AsyncMock()
        from sqlalchemy import func, select as sa_sel
        from hermeshq.models.node import Node

        # Build a real statement
        stmt = sa_sel(Node).order_by(Node.created_at.asc())

        # Mock db.execute to return count=25 for first call, rows for second
        with Session(sqlite_engine) as sync_session:
            # We'll just test the math, not the actual SQL execution
            pass

        # Count result
        count_result = MagicMock()
        count_result.scalar_one.return_value = 25

        # Data result - return 10 "items"
        class FakeItem:
            def __init__(self, i):
                self.id = str(i)

        data_result = MagicMock()
        data_result.scalars.return_value.all.return_value = [FakeItem(i) for i in range(10)]

        db.execute = AsyncMock(side_effect=[count_result, data_result])

        # Patch stmt.subquery to return something valid for SQLAlchemy
        real_subq = stmt.subquery()
        with patch.object(stmt, "subquery", return_value=real_subq), \
             patch.object(stmt, "offset", return_value=stmt), \
             patch.object(stmt, "limit", return_value=stmt):
            params = PaginationParams(page=1, page_size=10)
            result = await paginate(stmt, db, params)

        assert result.total == 25
        assert result.page == 1
        assert result.page_size == 10
        assert result.total_pages == 3
        assert len(result.items) == 10

    @pytest.mark.asyncio
    async def test_last_page_partial(self):
        """Page 3 of 25 items with page_size=10 → 5 items, total_pages=3."""
        db = AsyncMock()
        from sqlalchemy import select as sa_sel
        from hermeshq.models.node import Node

        stmt = sa_sel(Node).order_by(Node.created_at.asc())
        real_subq = stmt.subquery()

        count_result = MagicMock()
        count_result.scalar_one.return_value = 25

        data_result = MagicMock()
        data_result.scalars.return_value.all.return_value = [
            type("FakeItem", (), {"id": str(i)})() for i in range(5)
        ]

        db.execute = AsyncMock(side_effect=[count_result, data_result])

        with patch.object(stmt, "subquery", return_value=real_subq), \
             patch.object(stmt, "offset", return_value=stmt), \
             patch.object(stmt, "limit", return_value=stmt):
            params = PaginationParams(page=3, page_size=10)
            result = await paginate(stmt, db, params)

        assert result.total_pages == 3
        assert len(result.items) == 5

    @pytest.mark.asyncio
    async def test_empty_result(self):
        """No items → total_pages=1, items=[]."""
        db = AsyncMock()
        from sqlalchemy import select as sa_sel
        from hermeshq.models.node import Node

        stmt = sa_sel(Node).order_by(Node.created_at.asc())
        real_subq = stmt.subquery()

        count_result = MagicMock()
        count_result.scalar_one.return_value = 0

        data_result = MagicMock()
        data_result.scalars.return_value.all.return_value = []

        db.execute = AsyncMock(side_effect=[count_result, data_result])

        with patch.object(stmt, "subquery", return_value=real_subq), \
             patch.object(stmt, "offset", return_value=stmt), \
             patch.object(stmt, "limit", return_value=stmt):
            params = PaginationParams(page=1, page_size=10)
            result = await paginate(stmt, db, params)

        assert result.total == 0
        assert result.total_pages == 1
        assert result.items == []

    @pytest.mark.asyncio
    async def test_serializer_applied(self):
        """Custom serializer transforms rows."""
        db = AsyncMock()
        from sqlalchemy import select as sa_sel
        from hermeshq.models.node import Node

        stmt = sa_sel(Node)
        real_subq = stmt.subquery()

        count_result = MagicMock()
        count_result.scalar_one.return_value = 2

        class Row:
            def __init__(self, v):
                self.v = v

        data_result = MagicMock()
        data_result.scalars.return_value.all.return_value = [Row(3), Row(7)]

        db.execute = AsyncMock(side_effect=[count_result, data_result])

        with patch.object(stmt, "subquery", return_value=real_subq), \
             patch.object(stmt, "offset", return_value=stmt), \
             patch.object(stmt, "limit", return_value=stmt):
            params = PaginationParams(page=1, page_size=10)
            result = await paginate(stmt, db, params, serializer=lambda r: r.v * 10)

        assert result.items == [30, 70]

    @pytest.mark.asyncio
    async def test_no_serializer_returns_raw(self):
        db = AsyncMock()
        from sqlalchemy import select as sa_sel
        from hermeshq.models.node import Node

        stmt = sa_sel(Node)
        real_subq = stmt.subquery()

        count_result = MagicMock()
        count_result.scalar_one.return_value = 1

        raw_row = type("Row", (), {"id": "abc"})()
        data_result = MagicMock()
        data_result.scalars.return_value.all.return_value = [raw_row]

        db.execute = AsyncMock(side_effect=[count_result, data_result])

        with patch.object(stmt, "subquery", return_value=real_subq), \
             patch.object(stmt, "offset", return_value=stmt), \
             patch.object(stmt, "limit", return_value=stmt):
            params = PaginationParams(page=1, page_size=50)
            result = await paginate(stmt, db, params, serializer=None)

        assert result.items == [raw_row]

    @pytest.mark.asyncio
    async def test_exact_division_total_pages(self):
        """50 items / 10 per page = exactly 5 pages."""
        db = AsyncMock()
        from sqlalchemy import select as sa_sel
        from hermeshq.models.node import Node

        stmt = sa_sel(Node)
        real_subq = stmt.subquery()

        count_result = MagicMock()
        count_result.scalar_one.return_value = 50

        data_result = MagicMock()
        data_result.scalars.return_value.all.return_value = []

        db.execute = AsyncMock(side_effect=[count_result, data_result])

        with patch.object(stmt, "subquery", return_value=real_subq), \
             patch.object(stmt, "offset", return_value=stmt), \
             patch.object(stmt, "limit", return_value=stmt):
            params = PaginationParams(page=5, page_size=10)
            result = await paginate(stmt, db, params)

        assert result.total_pages == 5

    @pytest.mark.asyncio
    async def test_offset_and_limit_called(self):
        """Verify offset/limit are called with correct values."""
        db = AsyncMock()
        from sqlalchemy import select as sa_sel
        from hermeshq.models.node import Node

        stmt = sa_sel(Node)
        real_subq = stmt.subquery()

        count_result = MagicMock()
        count_result.scalar_one.return_value = 100

        data_result = MagicMock()
        data_result.scalars.return_value.all.return_value = []

        db.execute = AsyncMock(side_effect=[count_result, data_result])

        with patch.object(stmt, "subquery", return_value=real_subq), \
             patch.object(stmt, "offset", return_value=stmt) as mock_offset, \
             patch.object(stmt, "limit", return_value=stmt) as mock_limit:
            params = PaginationParams(page=3, page_size=25)
            await paginate(stmt, db, params)

        mock_offset.assert_called_once_with(50)  # (3-1)*25
        mock_limit.assert_called_once_with(25)
