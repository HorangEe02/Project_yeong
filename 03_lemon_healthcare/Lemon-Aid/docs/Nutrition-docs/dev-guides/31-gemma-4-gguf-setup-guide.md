# dev-guides/31 - Gemma 4 26B A4B GGUF Ollama 적용 가이드

작성일: 2026-05-21

이 문서는 `unsloth/gemma-4-26B-A4B-it-GGUF`를 Lemon Aid 백엔드의 로컬
Ollama 텍스트 구조화 파서 후보로 적용하는 절차를 고정한다. 적용 범위는
`OLLAMA_MODEL` 텍스트 파서이며, `OLLAMA_VISION_MODEL`은 별도 멀티모달 gate가
통과하기 전까지 기존 `gemma4:e4b`를 유지한다.

공식 근거:

- Unsloth Gemma 4 GGUF 모델 페이지: https://huggingface.co/unsloth/gemma-4-26B-A4B-it-GGUF
- Hugging Face Ollama GGUF 사용 문서: https://huggingface.co/docs/hub/en/ollama
- Hugging Face GGUF 문서: https://huggingface.co/docs/hub/gguf
- Ollama Chat API: https://docs.ollama.com/api/chat
- Ollama Structured Outputs: https://docs.ollama.com/capabilities/structured-outputs
- Ollama Importing a GGUF file: https://docs.ollama.com/import
- Ollama context length: https://docs.ollama.com/context-length

## 1. 현재 로컬 관찰값

2026-05-21 로컬 확인 후 2026-05-24 경로 보정 기준:

- `ollama list`와 `/api/tags`에서
  `hf.co/unsloth/gemma-4-26B-A4B-it-GGUF:UD-Q4_K_M`가 확인됐다.
- `/api/tags` 표시 크기는 `18 GB`, family는 `gemma4`, parameter size는
  `25.2B`였다.
- `/api/show`는 모델과 vision projector 메타데이터를 읽었다.
- 그러나 `/api/chat` 생성 smoke는 외장 Ollama model cache의 blob 로드 실패로
  실패했다. 현재 확인된 모델 저장소는
  `/Volumes/Corsair EX400U Media/.ollama/models` 이다.
- 같은 Ollama API에서 `qwen3.5:9b` structured smoke는 성공했다.

따라서 현재 상태는 **설치/메타데이터 인식 OK, Gemma 4 Q4 추론 로드 NG**다.
운영 또는 팀 데모에서 `OLLAMA_MODEL`을 바꾸기 전 반드시 §5 smoke gate를 통과해야
한다.

## 2. 모델 선택 기준

Hugging Face 파일 목록 기준 권장 순서는 다음과 같다.

| 우선순위 | Ollama/HF 태그 | HF 파일명 | HF 표시 크기 | 용도 |
| --- | --- | --- | --- | --- |
| 1 | `hf.co/unsloth/gemma-4-26B-A4B-it-GGUF:UD-Q4_K_M` | `gemma-4-26B-A4B-it-UD-Q4_K_M.gguf` | 16.9 GB | 기본 목표. 텍스트 구조화 파서 정확도 후보 |
| 2 | `hf.co/unsloth/gemma-4-26B-A4B-it-GGUF:UD-Q3_K_M` | `gemma-4-26B-A4B-it-UD-Q3_K_M.gguf` | 12.7 GB | Q4 로드 실패, OOM, swap 과다 시 fallback |
| 3 | `hf.co/unsloth/gemma-4-26B-A4B-it-GGUF:UD-Q2_K_XL` | `gemma-4-26B-A4B-it-UD-Q2_K_XL.gguf` | 10.5 GB | 로컬 장비에서 Q3도 불안정할 때만 사용 |

주의:

- 파일 크기는 모델 파일 기준이다. 실제 실행 메모리는 context length, vision
  projector, 동시 요청, OS/IDE 메모리 사용량에 따라 증가한다.
- Ollama 공식 context 문서는 VRAM 구간에 따라 기본 context가 달라지고, context를
  키우면 메모리 사용량도 증가한다고 안내한다. 본 프로젝트 smoke는 먼저
  `num_ctx=4096`으로 시작한다.
- 성능 수치, schema-valid rate, OCR 개선율은 fixture 평가 전에는 확정값으로 쓰지
  않는다.

## 3. 설치와 모델 태그

우선 Hugging Face Hub의 GGUF 모델을 Ollama가 직접 가져오게 한다.

```bash
ollama run hf.co/unsloth/gemma-4-26B-A4B-it-GGUF:UD-Q4_K_M
```

설치와 태그 확인:

```bash
ollama list

curl -sS http://127.0.0.1:11434/api/tags
```

Q4가 로드되지 않으면 같은 방식으로 Q3, Q2 순서로만 낮춘다.

```bash
ollama run hf.co/unsloth/gemma-4-26B-A4B-it-GGUF:UD-Q3_K_M
ollama run hf.co/unsloth/gemma-4-26B-A4B-it-GGUF:UD-Q2_K_XL
```

수동 GGUF 다운로드와 `Modelfile` import는 보조 경로다. Ollama 공식 import 문서는
GGUF 모델 import 시 `Modelfile`에 `FROM /path/to/file.gguf`를 두고
`ollama create my-model`을 실행하는 방식을 안내한다. 이 경로를 쓸 때는 임의 chat
template을 만들지 말고, 모델 페이지 또는 `ollama show --modelfile` 결과와
동일한 template/stop token을 확인한 뒤 적용한다.

## 4. 백엔드 설정

실제 비밀값이 있는 `backend/.env`는 저장소에 기록하지 않는다. smoke gate가
통과한 로컬 개발 장비에서만 다음처럼 override한다.

```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=hf.co/unsloth/gemma-4-26B-A4B-it-GGUF:UD-Q4_K_M
OLLAMA_VISION_MODEL=gemma4:e4b
OLLAMA_TIMEOUT_SEC=60
OLLAMA_TEMPERATURE=0
ALLOW_EXTERNAL_LLM=false
ENABLE_MULTIMODAL_LLM=false
MULTIMODAL_OCR_ASSIST_POLICY=disabled
ENABLE_MULTIMODAL_VERIFICATION=false
```

경계:

- `OLLAMA_MODEL`만 Gemma 4 Q4 후보로 바꾼다.
- `OLLAMA_VISION_MODEL`은 아직 바꾸지 않는다.
- `ENABLE_MULTIMODAL_LLM=false`를 유지한다.
- OCR-first, preview-first, user-confirmation 흐름을 유지한다.
- raw OCR text, prompt, raw model response는 저장하지 않는다.

## 5. Smoke gate

### 5.1 설치 확인

```bash
curl -sS http://127.0.0.1:11434/api/tags
```

성공 조건:

- `models[].name` 또는 `models[].model`에
  `hf.co/unsloth/gemma-4-26B-A4B-it-GGUF:UD-Q4_K_M`가 있어야 한다.

### 5.2 최소 structured output

```bash
curl -sS --max-time 180 http://127.0.0.1:11434/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "model": "hf.co/unsloth/gemma-4-26B-A4B-it-GGUF:UD-Q4_K_M",
    "stream": false,
    "messages": [
      {
        "role": "user",
        "content": "Return exactly JSON {\"ok\": true, \"model_ready\": true}"
      }
    ],
    "format": {
      "type": "object",
      "properties": {
        "ok": {"type": "boolean"},
        "model_ready": {"type": "boolean"}
      },
      "required": ["ok", "model_ready"]
    },
    "options": {
      "temperature": 0,
      "num_ctx": 4096
    }
  }'
```

성공 조건:

- HTTP response가 JSON object여야 한다.
- `message.content`가 JSON 문자열이어야 한다.
- `message.content`를 Pydantic 또는 `json.loads()`로 파싱했을 때 `ok=true`,
  `model_ready=true`여야 한다.
- 실패 시 실제 응답 error 문자열을 보고서에 그대로 남긴다. 원인을 추정 수치로
  대체하지 않는다.

### 5.3 backend parser smoke

smoke가 통과한 뒤에만 backend 환경에서 실제 parser를 호출한다.

```bash
cd /Users/yeong/99_me/00_github/03_lemon_healthcare/yeong-Lemon-Aid/backend

OLLAMA_MODEL=hf.co/unsloth/gemma-4-26B-A4B-it-GGUF:UD-Q4_K_M \
  .venv/bin/python -m pytest \
  Nutrition-backend/tests/unit/llm/test_ollama_parser.py \
  Nutrition-backend/tests/unit/services/test_supplement_parser.py
```

## 6. 현재 load 실패 복구 순서

현재 로컬에서 관찰한 실패 범주:

```text
unable to load model: /Volumes/Corsair EX400U Media/.ollama/models/blobs/...
```

복구는 아래 순서로 진행한다.

1. Ollama 버전과 서버 상태를 확인한다.

   ```bash
   ollama --version
   curl -sS http://127.0.0.1:11434/api/version
   ```

2. 모델 blob 경로와 외장 볼륨 상태를 확인한다.

   ```bash
   df -h "/Volumes/Corsair EX400U Media"
   ls -lh "/Volumes/Corsair EX400U Media/.ollama/models/blobs"
   ```

3. Ollama 앱 또는 서비스 재시작 후 Q4 smoke를 다시 실행한다.

4. 계속 실패하면 Q4를 재 pull한다.

   ```bash
   ollama pull hf.co/unsloth/gemma-4-26B-A4B-it-GGUF:UD-Q4_K_M
   ```

5. 외장 볼륨 blob 로드가 반복 실패하면 내부 SSD의 Ollama model cache에서 Q4를
   다시 pull하는 경로를 우선 검토한다.

6. Q4가 계속 실패하면 Q3 fallback으로 같은 smoke gate를 실행한다.

   ```bash
   ollama run hf.co/unsloth/gemma-4-26B-A4B-it-GGUF:UD-Q3_K_M
   ```

7. Q3도 불안정하면 Q2 fallback을 검토하되, schema 준수율과 파싱 정확도 저하는
   fixture report에 별도로 남긴다.

## 7. 프로젝트 검증 기준

Gemma 4 Q4를 프로젝트 기본 파서 후보로 인정하려면 다음을 모두 통과해야 한다.

- `/api/tags` 설치 확인
- `/api/chat` 최소 JSON Schema smoke 통과
- `test_ollama_parser.py` 통과
- `test_ollama_vision_assist.py`에서 vision gate 비활성 경계 유지
- `test_ocr_factory.py`에서 multimodal policy가 gate 없이 켜지지 않음
- `test_supplement_parser.py`와 `test_supplement_image_analysis.py` 통과
- 기존 fixture/manifest로 Qwen 3.5 9B 대비 Gemma 4 Q4의 schema-valid rate,
  timeout, low-confidence fields, 금지 표현 발생 여부를 기록

fixture 평가 전까지는 Gemma 4 Q4가 Qwen 3.5 9B보다 우수하다고 표현하지 않는다.
