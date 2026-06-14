"""Unit tests for SQLAlchemy base model mixins."""

from __future__ import annotations

import uuid
from datetime import datetime

import pytest
from sqlalchemy import DateTime, String, create_engine
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin


class SampleUUIDModel(UUIDMixin, Base):
    __tablename__ = "test_uuid"


class SampleTimestampModel(TimestampMixin, Base):
    __tablename__ = "test_timestamp"
    id: Mapped[int] = mapped_column(primary_key=True)


class SampleSoftDeleteModel(SoftDeleteMixin, Base):
    __tablename__ = "test_soft_delete"
    id: Mapped[int] = mapped_column(primary_key=True)


class SampleFullModel(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "test_full"
    name: Mapped[str] = mapped_column(String(50))


@pytest.fixture()
def in_memory_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    Base.metadata.drop_all(engine)


class TestUUIDMixin:
    """Tests for UUIDMixin."""

    def test_has_uuid_primary_key(self, in_memory_db: Session) -> None:
        obj = SampleUUIDModel()
        in_memory_db.add(obj)
        in_memory_db.commit()
        in_memory_db.refresh(obj)
        assert isinstance(obj.id, uuid.UUID)

    def test_uuid_generated_on_insert(self, in_memory_db: Session) -> None:
        obj = SampleUUIDModel()
        in_memory_db.add(obj)
        in_memory_db.flush()
        assert obj.id is not None
        assert isinstance(obj.id, uuid.UUID)

    def test_unique_uuids(self, in_memory_db: Session) -> None:
        obj1 = SampleUUIDModel()
        obj2 = SampleUUIDModel()
        in_memory_db.add_all([obj1, obj2])
        in_memory_db.flush()
        assert obj1.id != obj2.id

    def test_uuid_version(self, in_memory_db: Session) -> None:
        obj = SampleUUIDModel()
        in_memory_db.add(obj)
        in_memory_db.flush()
        assert obj.id.version == 4

    def test_uuid_column_type(self) -> None:
        col = SampleUUIDModel.__table__.columns["id"]
        assert col.primary_key is True


class TestTimestampMixin:
    """Tests for TimestampMixin."""

    def test_has_created_at_field(self) -> None:
        assert hasattr(SampleTimestampModel, "created_at")

    def test_has_updated_at_field(self) -> None:
        assert hasattr(SampleTimestampModel, "updated_at")

    def test_columns_are_datetime(self) -> None:
        mapper = SampleTimestampModel.__table__
        created_col = mapper.columns["created_at"]
        updated_col = mapper.columns["updated_at"]
        assert isinstance(created_col.type, DateTime)
        assert isinstance(updated_col.type, DateTime)

    def test_columns_not_nullable(self) -> None:
        mapper = SampleTimestampModel.__table__
        assert mapper.columns["created_at"].nullable is False
        assert mapper.columns["updated_at"].nullable is False


class TestSoftDeleteMixin:
    """Tests for SoftDeleteMixin."""

    def test_has_deleted_at_field(self) -> None:
        assert hasattr(SampleSoftDeleteModel, "deleted_at")

    def test_deleted_at_default_none(self) -> None:
        obj = SampleSoftDeleteModel()
        assert obj.deleted_at is None

    def test_deleted_at_nullable(self) -> None:
        col = SampleSoftDeleteModel.__table__.columns["deleted_at"]
        assert col.nullable is True


class TestBase:
    """Tests for the DeclarativeBase."""

    def test_is_declarative_base(self) -> None:
        assert hasattr(Base, "metadata")

    def test_metadata_tables(self) -> None:
        assert "test_uuid" in Base.metadata.tables
        assert "test_timestamp" in Base.metadata.tables


class TestFullModel:
    """Tests combining all mixins."""

    def test_all_fields_present(self, in_memory_db: Session) -> None:
        obj = SampleFullModel(name="test")
        in_memory_db.add(obj)
        in_memory_db.commit()
        in_memory_db.refresh(obj)

        assert isinstance(obj.id, uuid.UUID)
        assert isinstance(obj.created_at, datetime)
        assert isinstance(obj.updated_at, datetime)
        assert obj.deleted_at is None
        assert obj.name == "test"

    def test_soft_delete(self, in_memory_db: Session) -> None:
        obj = SampleFullModel(name="deletable")
        in_memory_db.add(obj)
        in_memory_db.commit()

        now = datetime.now()
        obj.deleted_at = now
        in_memory_db.commit()
        in_memory_db.refresh(obj)

        assert obj.deleted_at is not None
