# 후속 작업 TODO — 별도 PR 분리 권장

> 본 세션에서 식별된 작업 중 별도 PR 로 진행할 항목 목록.
> 우선순위 (P0 즉시, P1 단기, P2 중기, P3 장기).

---

## P0 — 운영 적용 (즉시)

### F-1. Production 환경에 lightweight pipeline 활성

- **변경**: 운영 `.env` 또는 settings 기본값에 `PADDLEOCR_USE_LIGHTWEIGHT_PIPELINE=true` 추가
- **근거**: v3-B 측정 결과 합성에서 CER 8.03% → 7.19% + exact_match 10% → 28.33%
- **위험**: 회전된 라벨 정확도 약간↓ (모바일 가이드로 정면 촬영 안내 시 영향 작음)
- **예상 작업**: 1 LOC + .env.example 갱신
- **참조**: [docs/ocr_baseline_reports/v3/final_summary.md §5](v3/final_summary.md)

### F-2. Production 도메인 확정 후 SPKI 핀 주입

- **변경**:
  - `mobile/android/app/src/main/res/xml/network_security_config.xml` placeholder pins 교체
  - iOS `Info.plist` NSExceptionDomains 의 placeholder 호스트 교체
  - Dart `Env.certificatePins` 값 `--dart-define` 으로 주입 (CI/CD 파이프라인)
- **근거**: PR-B/PR-C 가 placeholder 핀으로 머지된 상태
- **명령**: `./scripts/extract_spki_pin.sh <production-host>`
- **예상 작업**: 30 분 (도메인 확정 + 핀 추출 + 4파일 갱신)

---

## P1 — 단기 (1-2주)

### F-3. 모바일 촬영 가이드 UX

- **목적**: 실사 CER 38% → 15-20% 수준으로 (가설)
- **변경**:
  - 모바일 카메라 화면에 라벨 정면 정렬 가이드 오버레이
  - 흐림(blur) 자동 검출 → 재촬영 요청 휴리스틱
  - 박스가 아닌 라벨만 보이는 frame 권장
- **예상 작업**: Flutter UI ~200 LOC + 휴리스틱 ~80 LOC
- **참조**: [docs/ocr_baseline_reports/v3/final_summary.md §4-실사](v3/final_summary.md)

### F-4. 실사 데이터셋 라벨링 확대 (7장 → 30-50장)

- **목적**: 통계적 신뢰도 향상 + outlier 영향 감소 + 도메인 fine-tuning 데이터 마련
- **변경**:
  - `scripts/bootstrap_real_labels.py` 으로 추가 pseudo-label
  - 사람 검수 — Claude 멀티모달 시각 확인 또는 외부 라벨러
  - `data/ocr_eval/real_manifest.json` 의 `labeled=true` 항목 확대
- **예상 작업**: 라벨링 자체 4-8시간 (장 수 기준)

### F-5. PR-M1 follow-up — /predictions, /activity 라우터 검토

- **상황**: 현재 워크트리에 두 라우터 없음. 향후 추가 시 [`test_route_auth_contract.py`](../../backend/tests/integration/api/test_route_auth_contract.py) 가드가 자동 검출
- **변경**: 새 라우터 추가 PR 에서 `Depends(get_current_user)` 부착 확인
- **예상 작업**: 라우터 추가 PR 내에서 동시 처리

### F-6. 통합 테스트 80% 커버리지 게이트 복귀

- **상황**: 현재 게이트 70%, 측정 73.88%
- **변경**: `backend/pyproject.toml` `--cov-fail-under=80` 으로 상향
- **선행**: integration / e2e 테스트 추가로 커버리지 ~80% 도달 후
- **예상 작업**: 4-5일 (테스트 보강 후 게이트 변경 1줄)

---

## P2 — 중기 (1-2개월)

### F-7. YOLO ROI 별도 프로세스화 (segfault 회피)

- **문제**: PaddleOCR + YOLO 동시 실행 시 macOS 에서 segfault (paddle + torch 충돌)
- **해결**: 사전 크롭 모듈을 별도 프로세스/스크립트로 분리
  - `scripts/precrop_real_dataset.py` — 실사 manifest 의 모든 이미지를 YOLO ROI 크롭
  - 결과: `data/ocr_eval/real_samples_cropped/` + `real_cropped_manifest.json`
  - 측정 시 cropped manifest 사용 → PaddleOCR 만 실행되므로 충돌 없음
- **예상 효과**: 실사 정확도 향상 + segfault 회피
- **예상 작업**: ~150 LOC + 실사 60-100장 사전 크롭

### F-8. `text_det_limit_side_len` 조정 실험

- **변경**: PaddleOCRAdapter 에 `text_det_limit_side_len` 옵션 추가, 1280/960/768 비교
- **목적**: detection 입력 크기 → 추론 속도 + 정확도 trade-off 파라미터 최적화
- **예상 작업**: ~30 LOC + 합성 60장 × 3 값 측정

### F-9. ROI smoke segfault 정밀 진단

- **문제**: 합성 6장에서는 ROI smoke 정상, 60장에서는 segfault
- **변경**: 어떤 시점에 fail 하는지 reproducer 작성 + ultralytics/paddlepaddle 환경 격리 옵션 평가

### F-10. PaddleOCRAdapter 의 `text_det_*` thresh 자동 튜닝

- **변경**: bayesian 또는 grid search 로 `text_det_thresh`, `text_det_box_thresh`, `text_det_unclip_ratio` 최적값 찾기
- **목적**: 합성 데이터셋에서 best CER 추가 1-2%p 감소

---

## P3 — 장기 (3개월+)

### F-11. 도메인 fine-tuning

- **목적**: 한국어 영양제 라벨 데이터셋으로 PP-OCRv5_server_rec 재학습
- **선행**: F-4 (실사 라벨링 확대) 200-500장 규모
- **예상 효과**: ko/mixed CER 3-5%p 감소
- **예상 작업**: 데이터 준비 + GPU 학습 환경 + 평가 — **별도 트랙**

### F-12. ONNX 변환 + CoreML Execution Provider

- **목적**: macOS Apple Silicon 가속 (현재 paddlepaddle GPU 불가)
- **변경**:
  - PaddleOCR det/rec 모델을 ONNX 로 변환
  - `onnxruntime` + CoreML EP 어댑터 작성
  - PaddleOCRAdapter 와 동일한 인터페이스로 plug-in
- **예상 효과**: macOS 에서 2-3x 가속
- **예상 작업**: 변환 검증 + 신규 어댑터 ~300 LOC + 단위 테스트

### F-13. 합성 데이터셋 다양화

- **현재**: 60장 (ko/en/mixed 각 20장), 깨끗한 인쇄체
- **확장**: 회전/perspective 왜곡/노이즈 추가/색상 변동 — 실사와 더 가까운 분포로
- **예상 효과**: 합성 측정이 실사 정확도 예측에 더 유용해짐

---

## Cleanup / Hygiene

### F-14. `.omc/` 디렉터리 gitignore 추가

- 현재 변경에서 `.omc/`, `backend/.omc/`, `yeong-Vision-Nutrition/.omc/` 가 untracked 로 남아 있음 (OMC 도구 생성물)
- 변경: 저장소 루트 `.gitignore` 에 `.omc/` 패턴 추가

### F-15. `data/ocr_eval/real_samples/` 라이선스 검토

- 외장 드라이브에서 복사한 실제 영양제 라벨 사진들
- 저작권/라이선스 검토 필요 — git 커밋 적합한지, 외부 스토리지로 옮길지

### F-16. `data/ocr_eval/synthetic_small_manifest.json` 임시 데이터 정리

- 6장 smoke test용 임시 데이터셋 — 합성 60장 본 manifest 와 중복
- 정리: 60장 manifest만 유지, small 은 제거

---

## 작업 진척 추적

| ID | 항목 | 우선순위 | 상태 | 담당 |
|----|------|---------|------|------|
| F-1 | lightweight 운영 활성 | P0 | TODO | — |
| F-2 | Production SPKI 핀 주입 | P0 | TODO (도메인 확정 대기) | — |
| F-3 | 모바일 촬영 가이드 UX | P1 | TODO | — |
| F-4 | 실사 라벨링 확대 | P1 | TODO | — |
| F-5 | predictions/activity 라우터 (필요 시) | P1 | 가드 작동 중 | — |
| F-6 | 80% 커버리지 게이트 복귀 | P1 | TODO | — |
| F-7 | YOLO ROI 별도 프로세스 | P2 | TODO | — |
| F-8 | text_det_limit_side_len 튜닝 | P2 | TODO | — |
| F-9 | ROI segfault 진단 | P2 | TODO | — |
| F-10 | det thresh 자동 튜닝 | P2 | TODO | — |
| F-11 | 도메인 fine-tuning | P3 | 선행 작업 대기 (F-4) | — |
| F-12 | ONNX + CoreML | P3 | TODO | — |
| F-13 | 합성 데이터셋 다양화 | P3 | TODO | — |
| F-14 | .omc gitignore | hygiene | TODO | — |
| F-15 | 실사 라이선스 검토 | hygiene | TODO | — |
| F-16 | synthetic_small 정리 | hygiene | TODO | — |
