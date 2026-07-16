"""화자 구분(diarization) Provider — 오디오에서 화자별 발화 구간을 추출.

반환: list[{"start_ms", "end_ms", "label"}]  (label = "Speaker 1" ...)  또는 None(비활성)

두 가지 백엔드:
- sherpa-onnx: 오픈 모델(HF 토큰 불필요). models/diarization/ 에 모델 필요.
- pyannote.audio: HF_TOKEN + 게이트 모델 약관 동의 필요.
무거운 객체는 프로세스에 1회만 로드하도록 캐시한다.
"""
import os

from .. import config

_SHERPA = {}
_PYANNOTE = {}


def _resolve_mode() -> str:
    d = config.DIARIZER
    if d in ("sherpa", "pyannote", "none"):
        return d
    # auto
    if os.path.exists(config.SHERPA_SEG_MODEL) and os.path.exists(config.SHERPA_EMB_MODEL):
        return "sherpa"
    if config.HF_TOKEN:
        return "pyannote"
    return "none"


def diarize(audio_path):
    """오디오 → 화자 턴 리스트. 실패/비활성 시 None."""
    mode = _resolve_mode()
    try:
        if mode == "sherpa":
            return _sherpa(audio_path)
        if mode == "pyannote":
            return _pyannote(audio_path)
    except Exception as e:  # noqa: BLE001
        print(f"[diarization:{mode}] 실패, 단일 화자로 진행: {e}")
    return None


def _decode_16k(audio_path):
    """어떤 포맷이든 16kHz mono float32 numpy로 디코딩(PyAV 경유, ffmpeg 불필요)."""
    from faster_whisper.audio import decode_audio
    return decode_audio(audio_path, sampling_rate=16000)


def _sherpa(audio_path):
    if "sd" not in _SHERPA:
        import sherpa_onnx
        num = config.DIAR_NUM_SPEAKERS if config.DIAR_NUM_SPEAKERS > 0 else -1
        cfg = sherpa_onnx.OfflineSpeakerDiarizationConfig(
            segmentation=sherpa_onnx.OfflineSpeakerSegmentationModelConfig(
                pyannote=sherpa_onnx.OfflineSpeakerSegmentationPyannoteModelConfig(
                    model=config.SHERPA_SEG_MODEL)),
            embedding=sherpa_onnx.SpeakerEmbeddingExtractorConfig(
                model=config.SHERPA_EMB_MODEL),
            clustering=sherpa_onnx.FastClusteringConfig(
                num_clusters=num, threshold=config.DIAR_THRESHOLD),
            min_duration_on=0.2, min_duration_off=0.4,
        )
        _SHERPA["sd"] = sherpa_onnx.OfflineSpeakerDiarization(cfg)
    sd = _SHERPA["sd"]
    samples = _decode_16k(audio_path)
    result = sd.process(samples).sort_by_start_time()
    turns = [{"start_ms": int(r.start * 1000), "end_ms": int(r.end * 1000),
              "label": f"Speaker {r.speaker + 1}"} for r in result]
    return turns or None


def _pyannote(audio_path):
    if "pipe" not in _PYANNOTE:
        from pyannote.audio import Pipeline
        _PYANNOTE["pipe"] = Pipeline.from_pretrained(
            config.DIARIZATION_MODEL, use_auth_token=config.HF_TOKEN)
    annotation = _PYANNOTE["pipe"](audio_path)
    turns, label_map = [], {}
    for turn, _track, speaker in annotation.itertracks(yield_label=True):
        if speaker not in label_map:
            label_map[speaker] = f"Speaker {len(label_map) + 1}"
        turns.append({"start_ms": int(turn.start * 1000),
                      "end_ms": int(turn.end * 1000),
                      "label": label_map[speaker]})
    return turns or None
