from typing import Optional, List
from datetime import date, datetime
from pydantic import BaseModel


class LoginRequest(BaseModel):
    email: str
    password: str


class MeResponse(BaseModel):
    id: int
    email: str
    scan_limit: int
    scans_used: int

    class Config:
        orm_mode = True


class ScanCreate(BaseModel):
    provider: str = "RecreationDotGov"
    name: Optional[str] = None
    polling_interval: int = 300
    rec_area_ids: Optional[List[int]] = None
    campground_ids: Optional[List[int]] = None
    campsite_ids: Optional[List[int]] = None
    search_windows: List[dict]
    nights: int = 1
    days_of_week: Optional[List[int]] = None
    weekends_only: bool = False
    notify_via_email: bool = True
    notify_via_telegram: bool = False
    notify_on_new_only: bool = True


class ScanUpdate(BaseModel):
    name: Optional[str] = None
    polling_interval: Optional[int] = None
    rec_area_ids: Optional[List[int]] = None
    campground_ids: Optional[List[int]] = None
    campsite_ids: Optional[List[int]] = None
    search_windows: Optional[List[dict]] = None
    nights: Optional[int] = None
    days_of_week: Optional[List[int]] = None
    weekends_only: Optional[bool] = None
    notify_via_email: Optional[bool] = None
    notify_via_telegram: Optional[bool] = None
    notify_on_new_only: Optional[bool] = None


class ScanResponse(BaseModel):
    id: int
    user_id: int
    provider: str
    name: Optional[str]
    status: str
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
    created_at: datetime

    class Config:
        orm_mode = True


class ScanRunResponse(BaseModel):
    id: int
    scan_id: int
    started_at: datetime
    finished_at: Optional[datetime]
    outcome: Optional[str]
    sites_found: int
    error_message: Optional[str]

    class Config:
        orm_mode = True


class ScanResultResponse(BaseModel):
    id: int
    scan_id: int
    campsite_id: str
    facility_name: str
    site_name: str
    campsite_type: str
    booking_date: date
    booking_end_date: date
    booking_url: str
    first_seen_at: datetime
    cart_added: bool
    notified: bool

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
