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
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


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

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    telegram_chat_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    recreationgov_email: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    recreationgov_password: Mapped[Optional[str]] = mapped_column(
        String(256), nullable=True, comment="Fernet-encrypted; key in ENCRYPTION_KEY env"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    scans: Mapped[list["Scan"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
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
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
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
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cart_added: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cart_added_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    notified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notified_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    run: Mapped["ScanRun"] = relationship(back_populates="results")
    scan: Mapped["Scan"] = relationship(back_populates="results")
