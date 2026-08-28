from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any
from uuid import uuid4


EMAIL_SCENARIOS = [
    "活動前陌生開發",
    "活動前確認出席通知",
    "活動後關懷",
    "活動未出席／活動精華分享",
    "陌生開發",
    "二次追蹤",
]

EVENT_EMAIL_SCENARIOS = EMAIL_SCENARIOS[:4]
NON_EVENT_EMAIL_SCENARIOS = EMAIL_SCENARIOS[4:]

LINE_SCENARIOS = [
    "陌生開發",
    "活動邀約",
    "報名後打招呼",
    "活動前交流",
    "活動審核通知",
    "活動出席確認",
    "活動提醒",
    "活動後關懷",
    "簡報分享",
    "回放分享",
    "Demo 邀約",
    "第二次追蹤",
    "最後追蹤",
]

# Backward-compatible alias for existing imports and saved templates.
SCENARIOS = EMAIL_SCENARIOS

CONTENT_SECTIONS = ["周周文案風格", "歷史活動資料", "產業切角", "品牌案例"]


@dataclass
class Campaign:
    name: str
    event_date: str = field(default_factory=lambda: date.today().isoformat())
    event_time: str = ""
    event_format: str = "線上"
    location: str = ""
    address: str = ""
    partner: str = ""
    primary_industry: str = ""
    summary: str = ""
    introduction: str = ""
    activity_points: list[str] = field(default_factory=list)
    activity_point_1: str = ""
    activity_point_2: str = ""
    activity_point_3: str = ""
    activity_point_4: str = ""
    subject_a: str = ""
    subject_b: str = ""
    subject_c: str = ""
    selected_subject: str = ""
    subject_generation_round: int = 0
    # Legacy subject fields remain readable but are no longer shown in the UI.
    email_title_a: str = ""
    email_title_b: str = ""
    email_title_c: str = ""
    # Legacy fields remain readable for existing campaigns.
    topic: str = ""
    highlights: str = ""
    suitable_industries: str = ""
    case_industries: str = ""
    registration_url: str = ""
    booking_url: str = ""
    materials_url: str = ""
    image_path: str = ""
    id: str = field(default_factory=lambda: str(uuid4()))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Template:
    name: str
    channel: str
    scenario: str
    content: str
    id: str = field(default_factory=lambda: str(uuid4()))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
