# 06. OCR 파이프라인 진단 — "텍스트를 못 뽑는다" 원인

> 브랜치 성격: 진단 (코드 변경 없음)
> 대응 커밋: 없음 (조사 기록)
> 핵심 파일(읽기): `src/ocr/providers/paddle.py`, `src/ocr/factory.py`, `src/services/supplement_parser.py`

---

## 1. 사용자 증상

기능 테스트 중 "PaddleOCR이 아무런 텍스트를 못 뽑아온다"고 보고. 분석 결과가 "성분 0개 / 섹션 0개"로 표시.

---

## 2. 진단 과정 (단계별, 추측 배제)

| 가설 | 검증 방법 | 결과 |
|---|---|---|
| PaddleOCR 미설치 | 컨테이너 `pip show` + import | ❌ 오진 — 3.6.0 설치·import OK |
| Ollama 파서 모델 불일치 | `/api/tags` 모델 목록 | ❌ 오진 — `qwen3.5:9b` 존재(목록 잘림 착시) |
| OCR이 텍스트를 못 읽음 | 라벨 이미지로 raw `predict` 직접 실행 | ✅ **정상** — 22개 텍스트 추출 |
| 파서/섹션 검출 실패 | DB `parsed_snapshot` 직접 조회 | ✅ **확정 원인** |

---

## 3. 결정적 증거

### 3.1 raw PaddleOCR (스피루리나 라벨)

```
NUM_TEXTS=22
누리나 / 스피루리나 / SPIRULINA / 도움을줄수있음
량당총엽록소 14mg함유 / 600 mg×300정(총 180 g) / 1,182 mg a day ...
```

OCR은 **정상 작동**. (일부 조각 잘림: "DQUALITY", "RULINA" → 문서 04 autocontrast로 보조 개선)

### 3.2 DB ground-truth (최신 run)

```
09:31 | clova_ocr | OCR신뢰도 0.9578 | 성분후보 0개
       잡힌 섹션 타입 = "intake_method"(섭취방법)
       missing = ["supplement_facts"]
       action = "additional_label_image_required"
```

---

## 4. 결론

- **OCR/모델 버그 아님.** OCR은 신뢰도 0.96으로 정상.
- 원인: **촬영한 이미지에 영양정보(성분표) 표가 없었다.** 파서는 보이는 패널을 "섭취방법"으로 분류 + "성분표 없음"으로 판정 → 설계대로 성분 0개 + 재촬영 요청.
- 이 진단이 후속 작업의 방향을 결정함:
  - 문서 01: 원재료명만으로도 성분명 추출(성분표 없는 이미지 대응)
  - 문서 04: autocontrast로 인식 품질 보조 개선

---

## 5. 진단 중 환경 이슈 (참고)

- 컨테이너 이름 혼동: 이미지명 `lemon-aid-team-backend:dev` ≠ 컨테이너명 `lemon-aid-backend-1`
- 파일 권한: docker cp한 파일이 root 소유라 컨테이너 `lemon` 유저가 못 읽음 → chmod 644로 해결
- 모델 목록 출력 잘림으로 두 차례 오진 → 전체 목록 재확인으로 정정
