"""전사(ASR) Provider.

계약: transcribe(audio_path, language, hotwords, duration_ms) -> list[dict]
반환 dict 필드: speaker_label, start_ms, end_ms, text, confidence

- StubTranscriptionProvider: 모델 없이 고정 스크립트를 오디오 길이에 배치(데모 기본)
- FasterFasterWhisper...: faster-whisper 실제 전사 + (선택) pyannote 화자 구분
"""
import math
from typing import List, Optional

from .. import config
from . import diarization

# 무거운 모델 객체는 프로세스에 1회만 로드하도록 캐시
_WHISPER_CACHE = {}


# ----------------------------------------------------------------------------
# 데모용 고정 한국어 회의 스크립트 (3인 화자)
# ----------------------------------------------------------------------------
_SCRIPT = [
    ("Speaker 1", "자, 오늘 제품 MVP 회의 시작하겠습니다. 먼저 이번 분기 일정부터 확인하죠."),
    ("Speaker 2", "네, 저는 녹음과 업로드 흐름을 맡고 있는데 이번 주 안에 프로토타입이 가능합니다."),
    ("Speaker 1", "좋습니다. 전사는 우선 Mac 로컬에서 처리하는 방향으로 가는 게 맞을까요?"),
    ("Speaker 3", "네, 초기에는 서버 비용이 없으니 로컬 Worker로 시작하고 나중에 서버로 옮기는 게 안전합니다."),
    ("Speaker 2", "요약은 로컬 LLM으로 뽑고, 사용자가 검토해서 수정하는 구조면 될 것 같아요."),
    ("Speaker 1", "그럼 원본 음성은 절대 덮어쓰지 않고 보존하는 원칙을 지킵시다."),
    ("Speaker 3", "동의합니다. 요약본만 별도 버전으로 저장하고 원본 전사는 그대로 두죠."),
    ("Speaker 1", "일정 후보는 자동 등록하지 말고 반드시 사용자가 확인한 뒤 등록하도록 합시다."),
    ("Speaker 2", "Slack 공유는 우선 Webhook으로 지정 채널에 요약만 보내는 걸로 시작하겠습니다."),
    ("Speaker 3", "다음 점검 회의는 다음 주 수요일 오전 10시로 잡으면 어떨까요?"),
    ("Speaker 1", "좋아요. 그때까지 각자 맡은 프로토타입 상태를 공유합시다."),
    ("Speaker 2", "네, 홍길동 님이 Mac 로컬 Worker 프로토타입을, 저는 웹 녹음 UI를 준비하겠습니다."),
]


class StubTranscriptionProvider:
    name = "stub"

    def transcribe(self, audio_path: Optional[str], language: str = "ko",
                   hotwords: Optional[List[str]] = None,
                   duration_ms: Optional[int] = None) -> List[dict]:
        total = int(duration_ms or 180_000)
        if total < 4_000:
            total = 180_000
        n = len(_SCRIPT)
        weights = [max(len(t), 8) for _, t in _SCRIPT]
        total_w = sum(weights)
        speak_budget = int(total * 0.88)
        gap = max(150, (total - speak_budget) // (n + 1))

        segments = []
        cur = gap
        for (label, text), w in zip(_SCRIPT, weights):
            dur = max(1500, int(speak_budget * w / total_w))
            start = cur
            end = min(total - 50, start + dur)
            if end <= start:
                end = min(total - 1, start + 1000)
            segments.append({
                "speaker_label": label, "start_ms": start, "end_ms": end,
                "text": text, "confidence": round(0.88 + (w % 6) * 0.02, 3),
            })
            cur = end + gap
            if cur >= total:
                cur = max(start + 500, total - 2000)
        return segments


class FasterWhisperTranscriptionProvider:
    """faster-whisper 실제 전사. ASR_PROVIDER=faster_whisper 로 활성화.

    - PyAV로 오디오를 디코딩하므로 별도 ffmpeg 설치 불필요(webm/opus/wav/m4a 등).
    - HF_TOKEN 이 설정되고 pyannote.audio 가 설치되면 화자 구분을 적용한다.
    - 앱 API·DB 스키마는 그대로. Provider 구현체만 바뀐다.
    """

    name = "faster_whisper"

    def _get_model(self):
        key = (config.WHISPER_MODEL, config.WHISPER_DEVICE, config.WHISPER_COMPUTE)
        if key not in _WHISPER_CACHE:
            from faster_whisper import WhisperModel
            _WHISPER_CACHE[key] = WhisperModel(
                config.WHISPER_MODEL, device=config.WHISPER_DEVICE,
                compute_type=config.WHISPER_COMPUTE,
            )
        return _WHISPER_CACHE[key]

    def transcribe(self, audio_path, language="ko", hotwords=None, duration_ms=None):
        if not audio_path:
            raise RuntimeError("전사할 오디오 경로가 없습니다.")
        model = self._get_model()
        seg_iter, _info = model.transcribe(
            audio_path, language=language,
            initial_prompt=(", ".join(hotwords) if hotwords else None),
            vad_filter=True,
            word_timestamps=False,
        )
        raw = []
        for s in seg_iter:
            text = (s.text or "").strip()
            if not text:
                continue
            # avg_logprob(≤0) → 0~1 대략적 신뢰도
            conf = round(math.exp(s.avg_logprob), 3) if s.avg_logprob is not None else None
            raw.append({
                "start_ms": int(s.start * 1000), "end_ms": int(s.end * 1000),
                "text": text, "confidence": conf,
            })

        turns = diarization.diarize(audio_path)
        if turns:
            for seg in raw:
                seg["speaker_label"] = self._assign_speaker(seg, turns)
        else:
            for seg in raw:
                seg["speaker_label"] = "Speaker 1"
        return raw

    @staticmethod
    def _assign_speaker(seg, turns):
        """세그먼트와 시간 겹침이 가장 큰 화자 턴을 할당."""
        best, best_ov = "Speaker 1", -1
        for t in turns:
            ov = min(seg["end_ms"], t["end_ms"]) - max(seg["start_ms"], t["start_ms"])
            if ov > best_ov:
                best_ov, best = ov, t["label"]
        return best
