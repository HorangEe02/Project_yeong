# 기능 구현 문서: 전사, 화자 구분, 발화 클릭 재생

## 목표

Mac 로컬 Worker가 원본 음성을 ASR 처리용 파일로 변환하고, VibeVoice-ASR Provider를 통해 화자, 타임스탬프, 발화 텍스트를 segment 단위로 생성한다. 앱은 segment 목록을 표시하고 사용자가 발화를 클릭하면 해당 구간을 재생한다.

## 처리 파이프라인

```text
uploaded
  -> normalizing_audio
  -> transcribing
  -> summarizing
```

1. 원본 파일을 `ffmpeg`로 `normalized.wav`로 변환한다.
2. 변환된 파일의 샘플레이트, 채널, 길이를 기록한다.
3. `TranscriptionProvider.transcribe(audio_path, hotwords)`를 호출한다.
4. Provider 결과를 내부 `transcript_segments` 스키마로 정규화한다.
5. segment 순서, 시간 범위, 빈 텍스트를 검증한다.
6. DB에 segment를 저장한다.
7. 요약 작업을 enqueue한다.

## Segment 스키마

```json
{
  "id": "seg_001",
  "meeting_id": "meeting_001",
  "speaker_label": "Speaker 1",
  "speaker_name": null,
  "start_ms": 12000,
  "end_ms": 18500,
  "text": "이번 분기 일정부터 확인하겠습니다.",
  "confidence": 0.91,
  "source": "asr"
}
```

## 시간 검증 규칙

- `start_ms`는 0 이상이어야 한다.
- `end_ms`는 `start_ms`보다 커야 한다.
- segment는 `start_ms` 오름차순으로 저장한다.
- 겹치는 구간은 허용하되, 같은 화자의 완전 중복 구간은 제거한다.
- 음성 길이보다 뒤에 있는 timestamp는 파일 길이로 clamp한다.

## 화자 처리

ASR 결과의 기본 화자명은 `Speaker 1`, `Speaker 2`처럼 저장한다. 사용자가 화자명을 바꾸면 원본 ASR label은 보존하고, 별도 alias를 적용한다.

예시:

```text
speaker_label = Speaker 1
speaker_name = 김민수
display_name = 김민수
```

화자명 변경은 동일 회의 안에서 같은 `speaker_label`을 가진 모든 segment에 적용한다.

## 발화 클릭 재생

클라이언트는 `<audio>` 또는 네이티브 오디오 플레이어를 사용한다.

1. 사용자가 segment를 클릭한다.
2. 플레이어 `currentTime`을 `start_ms / 1000`으로 이동한다.
3. 재생을 시작한다.
4. `end_ms`를 지나면 자동 정지하거나 다음 segment로 넘어간다.
5. 재생 중인 segment를 하이라이트한다.

## 검색 및 북마크

MVP에서는 클라이언트 또는 API 기반 단순 텍스트 검색을 제공한다.

- 검색 대상: `text`, `corrected_text`, `speaker_name`
- 검색 결과 클릭 시 해당 timestamp로 이동
- 중요 발화는 `bookmarked = true`로 저장

## 수정 정책

- 원본 ASR 텍스트는 `text`에 보존한다.
- 사용자가 수정한 텍스트는 `corrected_text`에 저장한다.
- 화면에는 `corrected_text`가 있으면 이를 우선 표시한다.
- 요약 재생성 시에는 `corrected_text`를 우선 사용한다.

## 완료 조건

- 업로드된 음성이 `normalized.wav`로 변환된다.
- ASR Provider 결과가 segment 단위로 저장된다.
- 회의 상세에서 speaker, timestamp, text가 표시된다.
- segment 클릭 시 해당 음성 구간부터 재생된다.
- 화자명 수정, 텍스트 보정, 북마크가 저장된다.
