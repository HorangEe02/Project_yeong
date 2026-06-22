# dev-guides/08 — Ollama Supplement Parsing Current Status

작성일: 2026-05-13

이 문서는 현재 코드에 존재하는 로컬 Ollama OCR text parsing 구현만 설명한다. 과거 adapter 분리 설계 예시는 `docs/Nutrition-docs/previous-version/dev-guide-08-llm-supplement-parsing-design-example.md`로 이동했다.

Ollama 로컬 LLM 연결 안정화의 상세 구현 플랜은 `docs/Nutrition-docs/28-ollama-local-llm-connection-implementation-plan.md`를 기준으로 한다.

공식 문서 확인:

- Ollama Chat API: <https://docs.ollama.com/api/chat>
- Ollama structured outputs: <https://docs.ollama.com/capabilities/structured-outputs>

## 현재 구현

현행 구현체는 `backend/src/llm/ollama.py`의 `OllamaSupplementParser`다.

| 구간 | 현재 파일 | 상태 |
| --- | --- | --- |
| Parser entrypoint | `backend/src/services/supplement_parser.py` | 연결됨 |
| Local Ollama adapter | `backend/src/llm/ollama.py` | 구현됨 |
| Ollama transport/readiness | `backend/src/llm/ollama.py` | `OllamaChatClient`, `check_ollama_readiness` 구현됨 |
| Output schema | `backend/src/models/schemas/supplement_parser.py` | 구현됨 |
| API orchestration | `backend/src/services/supplement_image_analysis.py` | OCR text가 있을 때만 호출 |
| OCR text parse API | `backend/src/api/v1/supplements.py` | `POST /api/v1/supplements/analyses/{analysis_id}/ocr-text` 연결됨 |

`parse_supplement_analysis_ocr_text`는 parser가 명시 주입되지 않으면 `OllamaSupplementParser(settings)`를 사용한다. 이 함수는 OCR text를 normalize하고 HMAC-SHA256 hash를 저장한 뒤, raw OCR text는 저장하지 않는다.

API에서는 `SupplementOCRTextParseRequest`로 `ocr_text`, `ocr_provider`, `ocr_confidence`를 검증한 뒤 이 service를 호출한다. 성공 응답은 확정 저장이 아니라 `requires_confirmation` preview이며, 최종 저장은 기존 `POST /api/v1/supplements` 사용자 확인 payload로만 진행한다.

## Ollama 호출 계약

현재 parser는 local Ollama `/api/chat` endpoint를 사용한다. 요청 payload는 다음 구조를 따른다.

- `model`: `Settings.ollama_model`
- `messages`: system prompt와 OCR text prompt
- `stream`: `false`
- `think`: `false`
- `format`: `SupplementStructuredParseResult.model_json_schema()`
- `options.temperature`: `Settings.ollama_temperature`

공식 Ollama 문서 기준으로 `format`에는 `json` 또는 JSON Schema를 전달할 수 있고, structured output 사용 시 Pydantic schema를 전달한 뒤 응답을 검증하는 패턴을 사용할 수 있다. 현재 코드는 응답의 `message.content`를 `SupplementStructuredParseResult.model_validate_json`으로 다시 검증한다.

`check_ollama_readiness`는 `/api/tags`를 사용해 configured model 존재 여부를 확인한다. 이 check는 기본 CI나 public health endpoint에 강제로 연결하지 않고, 운영 preflight 또는 opt-in smoke test에서 사용한다.

## Local-Only Guard

`ALLOW_EXTERNAL_LLM=false`일 때 `OLLAMA_BASE_URL`은 다음 host만 허용한다.

- `localhost`
- `127.0.0.1`
- `::1`
- `host.docker.internal` (`development` only, for Docker Desktop containers
  calling a Mac-hosted Ollama server)

`LLM_PROVIDER`는 `ollama`만 지원한다. 외부 LLM provider로 확장하려면 별도 보안 검토와 설정 gate가 필요하다.

## 연결되지 않은 항목

- 이미지 파일을 직접 vision model로 보내는 multimodal parser
- `ENABLE_MULTIMODAL_LLM=true` 전용 runtime adapter
- 외부 LLM provider
- model performance metric 수집

## 검증 포인트

- `tests/unit/llm/test_ollama_parser.py`
- `tests/unit/services/test_supplement_parser.py`
- `tests/integration/api/test_supplement_ocr_text_api.py`
- OCR text가 빈 문자열, 과도한 길이, 다른 hash 충돌, 만료 preview 상태일 때의 실패 경로
