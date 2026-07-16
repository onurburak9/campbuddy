import enum
from datetime import datetime, date, timezone
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    Index,
    String,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator):
    """DateTime that always round-trips as UTC-aware.

    SQLite drops tzinfo on DateTime(timezone=True) columns, so a naive
    datetime read back from the DB would otherwise get serialized without
    a UTC marker and get misinterpreted as local time by API clients.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: Optional[datetime], dialect) -> Optional[datetime]:
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def process_result_value(self, value: Optional[datetime], dialect) -> Optional[datetime]:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class ScanStatus(str, enum.Enum):
    active = "active"
    paused = "paused"
    completed = "completed"


class ScanOutcome(str, enum.Enum):
    success = "success"
    no_results = "no_results"
    error = "error"


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_email_active", "email", sqlite_where=text("deleted_at IS NULL"), unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String, nullable=False)
    telegram_chat_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    recreationgov_email: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    recreationgov_password: Mapped[Optional[str]] = mapped_column(
        String(256), nullable=True, comment="Fernet-encrypted; key in ENCRYPTION_KEY env"
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=_utcnow
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        UTCDateTime, nullable=True
    )
    hashed_password: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    scan_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=5)

    scans: Mapped[list["Scan"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    used_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=_utcnow)


class Scan(Base):
    __tablename__ = "scans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    provider: Mapped[str] = mapped_column(String, nullable=False, default="RecreationDotGov")
    status: Mapped[ScanStatus] = mapped_column(
        SQLEnum(ScanStatus, native_enum=False),
        nullable=False,
        default=ScanStatus.active,
    )
    polling_interval: Mapped[int] = mapped_column(Integer, nullable=False, default=300)
    rec_area_ids: Mapped[Optional[list[int]]] = mapped_column(JSON, nullable=True)
    campground_ids: Mapped[Optional[list[int]]] = mapped_column(JSON, nullable=True)
    campsite_ids: Mapped[Optional[list[int]]] = mapped_column(JSON, nullable=True)
    search_windows: Mapped[list[dict]] = mapped_column(JSON, nullable=False)
    nights: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    days_of_week: Mapped[Optional[list[int]]] = mapped_column(JSON, nullable=True)
    weekends_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notify_via_email: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notify_via_telegram: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notify_on_new_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    auto_book: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=_utcnow
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        UTCDateTime, nullable=True
    )

    user: Mapped["User"] = relationship(back_populates="scans")
    runs: Mapped[list["ScanRun"]] = relationship(
        back_populates="scan", cascade="all, delete-orphan"
    )
    results: Mapped[list["ScanResult"]] = relationship(
        back_populates="scan", cascade="all, delete-orphan"
    )


class ScanRun(Base):
    __tablename__ = "scan_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scan_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("scans.id"), nullable=False, index=True
    )
    started_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        UTCDateTime, nullable=True
    )
    outcome: Mapped[Optional[ScanOutcome]] = mapped_column(
        SQLEnum(ScanOutcome, native_enum=False), nullable=True
    )
    sites_found: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    scan: Mapped["Scan"] = relationship(back_populates="runs")
    results: Mapped[list["ScanResult"]] = relationship(back_populates="run")


class ScanResult(Base):
    __tablename__ = "scan_results"
    __table_args__ = (
        Index("ix_scan_results_dedup", "scan_id", "campsite_id", "booking_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scan_run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("scan_runs.id"), nullable=False, index=True
    )
    scan_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("scans.id"), nullable=False
    )
    campsite_id: Mapped[str] = mapped_column(String, nullable=False)
    facility_name: Mapped[str] = mapped_column(String, nullable=False)
    site_name: Mapped[str] = mapped_column(String, nullable=False)
    campsite_type: Mapped[str] = mapped_column(String, nullable=False)
    booking_date: Mapped[date] = mapped_column(Date, nullable=False)
    booking_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    booking_url: Mapped[str] = mapped_column(String, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    cart_added: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cart_added_at: Mapped[Optional[datetime]] = mapped_column(
        UTCDateTime, nullable=True
    )
    notified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notified_at: Mapped[Optional[datetime]] = mapped_column(
        UTCDateTime, nullable=True
    )

    run: Mapped["ScanRun"] = relationship(back_populates="results")
    scan: Mapped["Scan"] = relationship(back_populates="results")
