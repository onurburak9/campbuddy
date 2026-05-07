from datetime import datetime, date
from typing import Optional
from sqlalchemy import JSON, DateTime, Boolean, Integer, String, ForeignKey, Date
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    telegram_chat_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    recreationgov_email: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    recreationgov_password: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    scans: Mapped[list["Scan"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Scan(Base):
    __tablename__ = "scans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String, nullable=False, default="RecreationDotGov")
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    polling_interval: Mapped[int] = mapped_column(Integer, nullable=False, default=300)
    rec_area_ids: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    campground_ids: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    campsite_ids: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    search_windows: Mapped[list] = mapped_column(JSON, nullable=False)
    nights: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    days_of_week: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    weekends_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notify_via_email: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notify_via_telegram: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notify_on_new_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="scans")
    runs: Mapped[list["ScanRun"]] = relationship(back_populates="scan", cascade="all, delete-orphan")
    results: Mapped[list["ScanResult"]] = relationship(back_populates="scan", cascade="all, delete-orphan")


class ScanRun(Base):
    __tablename__ = "scan_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scan_id: Mapped[int] = mapped_column(Integer, ForeignKey("scans.id"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    outcome: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    sites_found: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    scan: Mapped["Scan"] = relationship(back_populates="runs")
    results: Mapped[list["ScanResult"]] = relationship(back_populates="run")


class ScanResult(Base):
    __tablename__ = "scan_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scan_run_id: Mapped[int] = mapped_column(Integer, ForeignKey("scan_runs.id"), nullable=False)
    scan_id: Mapped[int] = mapped_column(Integer, ForeignKey("scans.id"), nullable=False)
    campsite_id: Mapped[str] = mapped_column(String, nullable=False)
    facility_name: Mapped[str] = mapped_column(String, nullable=False)
    site_name: Mapped[str] = mapped_column(String, nullable=False)
    campsite_type: Mapped[str] = mapped_column(String, nullable=False)
    booking_date: Mapped[date] = mapped_column(Date, nullable=False)
    booking_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    booking_url: Mapped[str] = mapped_column(String, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    cart_added: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cart_added_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    notified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    run: Mapped["ScanRun"] = relationship(back_populates="results")
    scan: Mapped["Scan"] = relationship(back_populates="results")
