# 04. OCR 전처리 기본값 변경 (none → autocontrast)

> 브랜치 성격: feat(ocr) / config
> 대응 커밋: `6e1b42c` (일부)
> 핵심 파일: `backend/Nutrition-backend/src/config.py`, `docker-compose.yml`, `tests/unit/ocr/test_preprocess_default_invocation.py`

---

## 1. 배경

OCR 진단(문서 06) 결과 PaddleOCR 자체는 정상이었으나, 저대비 한국어 라벨에서 일부 텍스트 조각이 잘리거나 깨지는 경향(예: "DQUALITY", "RULINA")이 관찰됐다.

`local_ocr_preprocess_mode`의 기본값이 `none`이라 전처리가 비활성 상태였다.

---

## 2. 변경

- `config.py`: `local_ocr_preprocess_mode` 기본값 `none → autocontrast`
- `docker-compose.yml`: 동일 기본값 반영
- autocontrast = full dynamic range 대비 보정
  - 클린 이미지에는 near-identity(거의 영향 없음)
  - 디코드 실패 시 수동 입력 경로로 graceful degradation
  - `env override` 유지(운영자가 `none`/다른 모드로 되돌릴 수 있음)

---

## 3. 검증 ✅

- 신규 `test_preprocess_default_invocation.py`: 기본 전처리 호출 검증
- 기존 `paddle_provider` 테스트 7건은 autocontrast 디코딩에 맞춰 `preprocess_mode="none"` 명시로 보정
- `test_config.py`: 기본값 단언 `autocontrast`로 갱신
- 배포 컨테이너 런타임 확인: `settings.local_ocr_preprocess_mode = autocontrast`

---

## 4. 주의

- 이번 "텍스트 0개" 증상의 **직접 원인은 아니었다**(원인은 문서 06 — 이미지에 영양정보 표 없음).
- autocontrast는 인식 품질 개선용 보조 변경이며, 추론 지연이 미세하게 증가할 수 있는 트레이드오프가 있다.
