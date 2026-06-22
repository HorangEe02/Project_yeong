"""식단 인식 예외 계층.

Reference:
    docs/dev-guides/16-meal-recognition.md
"""

from __future__ import annotations


class MealRecognitionError(Exception):
    """식단 인식 실패의 베이스 예외."""


class MealApiError(MealRecognitionError):
    """외부 API(YOLO/GCV) 호출 실패."""


class MealParseError(MealRecognitionError):
    """응답·입력 구조 파싱 실패."""
