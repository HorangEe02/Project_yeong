"""Provider 팩토리.

문서(local-worker-project-structure.md)의 핵심 설계 원칙:
처리 위치/모델을 바꿀 때 앱 API·스키마는 그대로 두고 Provider 구현체만 교체한다.
데모는 stub 기본. 환경변수로 실제 로컬 모델 구현체로 전환한다.
"""
from .. import config
from .transcription import StubTranscriptionProvider, FasterWhisperTranscriptionProvider
from .summary import StubSummaryProvider, OllamaSummaryProvider


def get_transcription_provider():
    if config.ASR_PROVIDER == "faster_whisper":
        return FasterWhisperTranscriptionProvider()
    return StubTranscriptionProvider()


def get_summary_provider():
    if config.SUMMARY_PROVIDER == "ollama":
        return OllamaSummaryProvider()
    return StubSummaryProvider()
