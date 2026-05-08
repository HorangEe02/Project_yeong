"""v1.6: 수신처별 톤/스타일 설정 — 이메일 및 공식 문서 작성 시 참조"""

TONE_CONFIGS = {
    "현대/기아 (국내)": {
        "formality": "very_formal",
        "language": "ko",
        "honorifics": True,
        "closing": "감사합니다.",
        "signature_format": "아진산업(주) {department}\n{name} {position}\nTEL: {phone}",
        "guidelines": [
            "존댓말 + 경어체 필수 ('~하겠습니다', '~드립니다')",
            "현대/기아 SQ포털 용어 사용 (PPAP, SQ, CSR 등)",
            "수신자 직함 정확히 기재",
            "숫자/날짜는 명확히 (2026년 3월 20일)",
        ],
    },
    "HMGMA (영문)": {
        "formality": "formal",
        "language": "en",
        "honorifics": False,
        "closing": "Best regards,",
        "signature_format": "AJIN Industrial (JOON INC)\n{name}, {position}\nTel: {phone}\nEmail: {email}",
        "guidelines": [
            "Formal business English, no contractions",
            "Use IATF 16949 / PPAP / 8D terminology",
            "Reference part numbers and lot numbers explicitly",
            "Include action items with clear deadlines",
            "Sign off with full company name (AJIN Industrial / JOON INC)",
        ],
    },
    "HMGMA (국영문)": {
        "formality": "formal",
        "language": "ko_en",
        "honorifics": True,
        "closing": "감사합니다. / Best regards,",
        "signature_format": "아진산업(주) / AJIN Industrial\n{name} {position}\nTEL: {phone}",
        "guidelines": [
            "한국어 먼저, 영문 번역 아래 배치",
            "'--- English Version ---' 구분선 사용",
            "기술 용어는 영문 그대로 (PPAP, EWP, CCH 등)",
        ],
    },
    "2차 협력사": {
        "formality": "formal",
        "language": "ko",
        "honorifics": True,
        "closing": "감사합니다.",
        "signature_format": "아진산업(주) {department}\n{name} {position}",
        "guidelines": [
            "명확한 요구사항 전달 ('~까지 제출 바랍니다')",
            "납기/수량/규격 등 숫자 명확히 기재",
            "필요 시 첨부파일 언급",
        ],
    },
    "해외법인": {
        "formality": "formal",
        "language": "en",
        "honorifics": False,
        "closing": "Best regards,",
        "signature_format": "AJIN Industrial HQ\n{name}, {position}\nTel: {phone}",
        "guidelines": [
            "Formal business English for US/Vietnam subsidiaries",
            "Chinese subsidiaries: Korean or bilingual acceptable",
            "Include specific plant names (JOON INC, AJIN USA, etc.)",
        ],
    },
    "사내": {
        "formality": "semi_formal",
        "language": "ko",
        "honorifics": True,
        "closing": "감사합니다.",
        "signature_format": "{department} {name} {position}",
        "guidelines": [
            "존댓말 유지하되 간결하게",
            "불필요한 서두 생략 가능",
            "핵심 내용 위주로 작성",
        ],
    },
}


def get_tone_config(recipient: str) -> dict:
    """수신처에 맞는 톤/스타일 설정을 반환한다."""
    return TONE_CONFIGS.get(recipient, TONE_CONFIGS["사내"])


def get_tone_guidelines_text(recipient: str) -> str:
    """수신처에 맞는 작성 가이드라인을 텍스트로 반환한다."""
    config = get_tone_config(recipient)
    lines = [f"- {g}" for g in config.get("guidelines", [])]
    return "\n".join(lines)
