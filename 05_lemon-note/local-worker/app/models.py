"""요청 본문 검증용 Pydantic 모델 (FastAPI에 포함되어 있어 추가 설치 불필요)."""
from typing import List, Optional

from pydantic import BaseModel


class MeetingPatch(BaseModel):
    title: str


class FolderCreate(BaseModel):
    name: str
    parent_id: Optional[str] = None


class FolderPatch(BaseModel):
    name: Optional[str] = None
    parent_id: Optional[str] = None


class FolderMoveIn(BaseModel):
    folder_id: Optional[str] = None


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
    # 낙관적 잠금: 편집을 시작한 시점의 요약 버전. 그 사이 다른 탭·다른 방문자가
    # 저장했으면 서버가 409 로 거부한다. 없으면(구 클라이언트) 검사하지 않는다.
    base_version: Optional[int] = None


class ExportIn(BaseModel):
    format: str = "md"           # md | txt
    include_transcript: bool = True
    summary_version_id: Optional[str] = None


class SlackShareIn(BaseModel):
    summary_version_id: Optional[str] = None
    channel_label: Optional[str] = None
    message_override: Optional[str] = None
