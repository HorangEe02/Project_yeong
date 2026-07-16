"""요청 본문 검증용 Pydantic 모델 (FastAPI에 포함되어 있어 추가 설치 불필요)."""
from typing import List, Optional

from pydantic import BaseModel


class MeetingPatch(BaseModel):
    title: str


class SegmentPatch(BaseModel):
    corrected_text: Optional[str] = None
    bookmarked: Optional[bool] = None


class SpeakerPatch(BaseModel):
    speaker_name: str


class DecisionIn(BaseModel):
    text: str
    source_segment_ids: List[str] = []


class ActionItemIn(BaseModel):
    owner: Optional[str] = None
    task: str
    due_date: Optional[str] = None
    source_segment_ids: List[str] = []
    confidence: Optional[float] = None
    status: str = "open"


class CalendarCandidateIn(BaseModel):
    title: str
    start_at: Optional[str] = None
    end_at: Optional[str] = None
    attendees: List[str] = []
    source_segment_ids: List[str] = []
    confidence: Optional[float] = None
    status: str = "pending"
    created_calendar_url: Optional[str] = None


class SummaryPatch(BaseModel):
    title: str
    summary: str
    decisions: List[DecisionIn] = []
    action_items: List[ActionItemIn] = []
    calendar_candidates: List[CalendarCandidateIn] = []


class ExportIn(BaseModel):
    format: str = "md"           # md | txt
    include_transcript: bool = True
    summary_version_id: Optional[str] = None


class SlackShareIn(BaseModel):
    summary_version_id: Optional[str] = None
    channel_label: Optional[str] = None
    message_override: Optional[str] = None
