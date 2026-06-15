"""B6 v4.0 — 메일 발송 시 doc_type 별 첨부 추천.

doc_type → 권장 첨부 항목 매핑. 누락 방지 체크리스트로 활용.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AttachmentSuggestion:
    """첨부 제안 한 건."""

    label: str
    description: str = ""
    required: bool = False  # 빠지면 거의 반려되는 핵심 첨부
    file_hint: str = ""     # 예상 확장자/형식


# doc_type → 추천 첨부 리스트
ATTACHMENT_RECOMMENDATIONS: dict[str, list[AttachmentSuggestion]] = {
    "8d_report": [
        AttachmentSuggestion("불량 사진", "D2/D3 단계 시각 자료", required=True, file_hint="JPG/PNG"),
        AttachmentSuggestion("측정 데이터", "수치 근거 (CMM/마이크로미터 등)", required=True, file_hint="XLSX/CSV"),
        AttachmentSuggestion("FMEA 관련 항목 발췌", "Why-Why 5단계 보강", file_hint="DOCX/XLSX"),
        AttachmentSuggestion("교정 조치 도면 변경본", "D5 영구 시정 조치", file_hint="PDF/DWG"),
    ],
    "ecn": [
        AttachmentSuggestion("개정 도면 (Rev. 차수 명시)", "변경 전후 도면 비교", required=True, file_hint="PDF/DWG"),
        AttachmentSuggestion("영향 분석 표", "기능/성능/원가 영향", file_hint="XLSX"),
        AttachmentSuggestion("PPAP 재제출 증빙", "Level 3 기준", file_hint="PDF"),
        AttachmentSuggestion("FMEA 업데이트", "변경 부품 리스크 재평가", file_hint="XLSX"),
    ],
    "ppap": [
        AttachmentSuggestion("PSW (Part Submission Warrant)", "고객 양식", required=True, file_hint="PDF"),
        AttachmentSuggestion("FMEA", "Process FMEA", required=True, file_hint="XLSX"),
        AttachmentSuggestion("Control Plan", "공정 관리 계획", required=True, file_hint="XLSX"),
        AttachmentSuggestion("MSA 보고서", "Gage R&R 결과", required=True, file_hint="XLSX/PDF"),
        AttachmentSuggestion("Capability Study (Cpk 차트)", "Cpk 1.33 이상", required=True, file_hint="XLSX/PDF"),
        AttachmentSuggestion("초도품 측정 보고서", "치수 검증", required=True, file_hint="XLSX"),
        AttachmentSuggestion("재료 시험 성적서", "MTC", file_hint="PDF"),
    ],
    "fmea": [
        AttachmentSuggestion("FMEA 워크북", "AIAG-VDA 양식", required=True, file_hint="XLSX"),
        AttachmentSuggestion("공정 흐름도", "Process Flow Diagram", file_hint="PDF"),
        AttachmentSuggestion("RPN 트렌드", "이전 분기 대비", file_hint="XLSX"),
    ],
    "msa": [
        AttachmentSuggestion("원시 측정 데이터", "ANOVA 분석 입력", required=True, file_hint="XLSX/CSV"),
        AttachmentSuggestion("측정 차트 (X-bar/R)", "관리도", file_hint="PNG/PDF"),
        AttachmentSuggestion("ANOVA 분산 분석 표", "GRR/AV/EV 분해", file_hint="XLSX"),
    ],
    "oem_email": [
        AttachmentSuggestion("관련 도면 / 사양서", "맥락 자료", file_hint="PDF"),
        AttachmentSuggestion("측정 보고서", "수치 근거", file_hint="PDF/XLSX"),
        AttachmentSuggestion("일정표", "Gantt 또는 마일스톤", file_hint="XLSX/PDF"),
    ],
    "internal_email": [
        AttachmentSuggestion("회의 자료", "참고 슬라이드", file_hint="PPTX/PDF"),
        AttachmentSuggestion("이전 결재 문서 사본", "참고용", file_hint="PDF"),
    ],
    "meeting_min": [
        AttachmentSuggestion("발표 자료", "회의에 사용된 슬라이드", file_hint="PPTX"),
        AttachmentSuggestion("부속 데이터 시트", "수치 근거", file_hint="XLSX"),
        AttachmentSuggestion("녹취록 (선택)", "원문 전사본", file_hint="TXT/DOCX"),
    ],
    "weekly_report": [
        AttachmentSuggestion("KPI 차트", "그래프 시각화", file_hint="PNG/XLSX"),
        AttachmentSuggestion("이슈 상세 노트", "방해 요소 보고", file_hint="DOCX"),
    ],
    "leave_request": [
        AttachmentSuggestion("증빙 서류", "병가/경조사 등 사유 증빙", file_hint="PDF/JPG"),
    ],
    "business_trip_request": [
        AttachmentSuggestion("출장지 회의 안건", "사전 공유 자료", file_hint="DOCX/PDF"),
        AttachmentSuggestion("예산 견적", "교통/숙박 견적", file_hint="XLSX"),
    ],
    "resignation_letter": [
        AttachmentSuggestion("인수인계 매뉴얼", "주요 업무 정리", required=True, file_hint="DOCX"),
    ],
    "personnel_notice": [
        AttachmentSuggestion("발령 공문", "인사 공식 문서", file_hint="PDF"),
    ],
    "quote": [
        AttachmentSuggestion("부품 사양서", "스펙 시트", required=True, file_hint="PDF"),
        AttachmentSuggestion("재료 인증서 (MTC)", "재료 추적성", file_hint="PDF"),
        AttachmentSuggestion("BOM (Bill of Materials)", "부품 구성", file_hint="XLSX"),
    ],
    "travel_report": [
        AttachmentSuggestion("회의록 / 사진", "출장 기록", required=True, file_hint="DOCX/JPG"),
        AttachmentSuggestion("측정 데이터 (있을 시)", "현장 점검 결과", file_hint="XLSX"),
        AttachmentSuggestion("영수증 원본", "비용 정산", required=True, file_hint="PDF/JPG"),
    ],
    "spc_report": [
        AttachmentSuggestion("X-bar / R 차트", "관리도 시각화", required=True, file_hint="PNG/XLSX"),
        AttachmentSuggestion("Cpk 분포 차트", "공정 능력 시각화", required=True, file_hint="PNG/XLSX"),
        AttachmentSuggestion("Nelson 위반 상세 로그", "이상 패턴 추적", file_hint="XLSX"),
    ],
}


def recommend_attachments(doc_type: str) -> list[AttachmentSuggestion]:
    """doc_type 에 맞는 첨부 추천 목록.

    매칭 doc_type 없으면 빈 리스트 반환 (UI 가 안내 노출).
    """
    return list(ATTACHMENT_RECOMMENDATIONS.get(doc_type, []))


def required_attachment_labels(doc_type: str) -> list[str]:
    """누락 시 거의 반려되는 핵심 첨부 라벨만 반환."""
    return [s.label for s in recommend_attachments(doc_type) if s.required]
