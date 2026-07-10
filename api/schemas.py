from typing import Optional, List
from datetime import date, datetime
from pydantic import BaseModel, Field, validator
from db.models import ScanStatus, ScanOutcome
import re

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

VALID_PROVIDERS = {
    "RecreationDotGov",
    "Yellowstone",
    "GoingToCamp",
    "ReserveCalifornia",
    "AlabamaStateParks",
    "ArizonaStateParks",
    "FloridaStateParks",
    "MinnesotaStateParks",
    "MissouriStateParks",
    "OhioStateParks",
    "VirginiaStateParks",
    "NorthernTerritory",
    "FairfaxCountyParks",
    "MaricopaCountyParks",
    "OregonMetro",
    "RecreationDotGovTicket",
    "RecreationDotGovTimedEntry",
    "RecreationDotGovDailyTicket",
    "RecreationDotGovDailyTimedEntry",
}


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class RegisterRequest(BaseModel):
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=8)

    @validator("email")
    def valid_email_format(cls, v):
        if not _EMAIL_RE.fullmatch(v):
            raise ValueError("Invalid email format")
        return v


class MeResponse(BaseModel):
    id: int
    email: str
    scan_limit: int
    scans_used: int
    has_telegram: bool

    class Config:
        orm_mode = True


class SearchWindow(BaseModel):
    start_date: date
    end_date: date

    @validator("end_date")
    def end_after_start(cls, v, values):
        if "start_date" in values and v <= values["start_date"]:
            raise ValueError("end_date must be after start_date")
        return v


class ScanCreate(BaseModel):
    provider: str = "RecreationDotGov"
    name: Optional[str] = None
    polling_interval: int = Field(300, ge=60)
    rec_area_ids: Optional[List[int]] = None
    campground_ids: Optional[List[int]] = None
    campsite_ids: Optional[List[int]] = None
    search_windows: List[SearchWindow] = Field(..., min_items=1)
    nights: int = Field(1, ge=1)
    days_of_week: Optional[List[int]] = None
    weekends_only: bool = False
    notify_via_email: bool = True
    notify_via_telegram: bool = False
    notify_on_new_only: bool = True
    auto_book: bool = False

    @validator("provider")
    def valid_provider(cls, v):
        if v not in VALID_PROVIDERS:
            raise ValueError(f"Unknown provider: {v}. Must be one of: {sorted(VALID_PROVIDERS)}")
        return v

    @validator("days_of_week", each_item=True)
    def valid_day(cls, v):
        if v < 0 or v > 6:
            raise ValueError("days_of_week values must be 0-6 (Monday=0, Sunday=6)")
        return v


class ScanUpdate(BaseModel):
    name: Optional[str] = None
    polling_interval: Optional[int] = Field(None, ge=60)
    rec_area_ids: Optional[List[int]] = None
    campground_ids: Optional[List[int]] = None
    campsite_ids: Optional[List[int]] = None
    search_windows: Optional[List[SearchWindow]] = None
    nights: Optional[int] = Field(None, ge=1)
    days_of_week: Optional[List[int]] = None
    weekends_only: Optional[bool] = None
    notify_via_email: Optional[bool] = None
    notify_via_telegram: Optional[bool] = None
    notify_on_new_only: Optional[bool] = None
    auto_book: Optional[bool] = None

    @validator("search_windows")
    def at_least_one_window(cls, v):
        if v is not None and len(v) == 0:
            raise ValueError("search_windows must not be empty")
        return v

    @validator("days_of_week", each_item=True)
    def valid_day(cls, v):
        if v < 0 or v > 6:
            raise ValueError("days_of_week values must be 0-6 (Monday=0, Sunday=6)")
        return v


class ScanResponse(BaseModel):
    id: int
    user_id: int
    provider: str
    name: Optional[str]
    status: ScanStatus
    polling_interval: int
    rec_area_ids: Optional[List[int]]
    campground_ids: Optional[List[int]]
    campsite_ids: Optional[List[int]]
    search_windows: List[dict]
    nights: int
    days_of_week: Optional[List[int]]
    weekends_only: bool
    notify_via_email: bool
    notify_via_telegram: bool
    notify_on_new_only: bool
    auto_book: bool
    created_at: datetime

    class Config:
        orm_mode = True


class ScanRunResponse(BaseModel):
    id: int
    scan_id: int
    started_at: datetime
    finished_at: Optional[datetime]
    outcome: Optional[ScanOutcome]
    sites_found: int
    error_message: Optional[str]

    class Config:
        orm_mode = True


class ScanResultResponse(BaseModel):
    id: int
    scan_run_id: int
    scan_id: int
    campsite_id: str
    facility_name: str
    site_name: str
    campsite_type: str
    booking_date: date
    booking_end_date: date
    booking_url: str
    first_seen_at: datetime
    last_seen_at: datetime
    is_available: bool
    cart_added: bool
    notified: bool

    class Config:
        orm_mode = True


class ScanStatsResponse(BaseModel):
    sites_found: int
    in_cart: int
    total_runs: int
    success_rate: int

    class Config:
        orm_mode = True


class ProfileUpdate(BaseModel):
    email: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    recreationgov_email: Optional[str] = None
    recreationgov_password: Optional[str] = None


class ProfileResponse(BaseModel):
    id: int
    email: str
    telegram_chat_id: Optional[str]
    recreationgov_email: Optional[str]
    scan_limit: int

    class Config:
        orm_mode = True
