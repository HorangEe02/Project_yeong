# 이미지 수집·재사용·학습 동의 계획

## 1. 검토 목적

본 문서는 다음 세 가지 기능 도입을 전제로, 사용자 영양제 이미지의 수집·저장·재사용·학습 단계에서 적용해야 하는 동의 매트릭스, 가명화 절차, 보유·파기 정책, 의료기기법 회피 조항, 발주처 리뷰 게이트를 정리한다.

- 기능 A: 영양제 라벨 인식 비전 모델 (YOLO 기반, Phase 3 게이트)
- 기능 B: Ollama 멀티모달 LLM 보조 채널 (Gemma 4 등, Phase 2 게이트)
- 기능 C: 사용자 영양제 이미지 → 벡터 임베딩 → 학습 데이터 적재 (pgvector, Phase 4 게이트)

위 세 기능은 [docs/14 §2.4](./14-pre-implementation-scope-and-rules.md)의 "규제 게이트가 필요한 기능 범위"와 [docs/15 §3](./15-regulated-feature-feasibility-and-compliance-plan.md)의 "규제 안에서 가능한 범위로 기능을 쪼개는 방식"을 그대로 따른다.

## 2. 적용 범위 및 비적용 범위

본 문서가 적용되는 이미지:

- 영양제 라벨, 포장, 박스, 정보지(라벨 면에 한정)

본 문서가 적용되지 않는 이미지(별도 문서로 분리):

- 처방전, 진료기록, 검사표 등 의료 문서 → [docs/15 §3.2, §3.3](./15-regulated-feature-feasibility-and-compliance-plan.md) 적용
- 식단 음식 사진 → Phase 3 음식 인식 결정 시 별도 보강
- 사용자 신체 사진, 얼굴, 신분증 등 식별 가능 이미지 → 수집 자체를 금지

## 3. 수집 시점별 동의 매트릭스

| 수집 시점 | 데이터 분류 | 별도 동의 | 기본값 | 보유 | 학습 재사용 |
| --- | --- | --- | --- | --- | --- |
| 1) 분석용 임시 처리 | 일반 개인정보 | 불필요(서비스 이용 동의 포함) | 자동 처리 | 분석 직후 즉시 삭제 | 불가 |
| 2) 사용자 히스토리 저장 | 일반 개인정보 + 사용 맥락 | 필요 | OFF | 사용자 지정(기본 90일) | 불가 |
| 3) 발주처 공유 | 가명화 데이터 | 별도 화면·별도 토글 | OFF | 발주처 계약 명시 | 발주처 계약 범위 내 |
| 4) AI 학습용 재사용 | 가명화 데이터 + 라벨링 결과 | **별도 화면·별도 토글·철회 가능** | OFF | 동의 시점 + 최대 24개월 | 본 항목 동의 시 한정 |

기본 정책 요약:

- 1)은 [docs/14 §3](./14-pre-implementation-scope-and-rules.md) "원본 이미지는 기본적으로 분석 후 삭제"를 그대로 따른다.
- 2)~4)는 [docs/10 §5.2~5.3](./10-compliance-checklist.md)의 "민감 건강정보 별도 동의" 기준을 준수하며, 1차 서비스 동의와 분리된 별도 동의 화면으로 받는다.
- 4)의 동의는 1)~3)과 독립적으로 ON/OFF 가능하며, 어느 하나의 동의가 다른 동의를 자동 활성화하지 않는다.
- 모든 동의는 사용자 마이페이지에서 1탭으로 철회 가능하며, 철회 시 §6 파기 절차가 적용된다.

## 4. 가명화 절차

[docs/10 §5.3](./10-compliance-checklist.md), [docs/15 §3.1](./15-regulated-feature-feasibility-and-compliance-plan.md), 개인정보보호위원회 「보건의료데이터 활용 가이드라인」 기준을 따른다.

### 4.1 직접식별자 제거

- 이미지 EXIF에서 GPS, 카메라 시리얼, 촬영일시 분 단위 이하 정밀도, 사용자 이름 메타데이터 제거
- 파일명에 포함된 사용자 식별 가능 문자열(이메일, 닉네임 등) 무작위 UUID로 대체
- 라벨 이미지에 우연히 포함된 사용자 얼굴, 손가락, 손글씨 메모는 인식 검출 후 자동 모자이크

### 4.2 간접식별자 일반화

학습 적재 시 동반 메타데이터(사용자 프로필 일부)는 다음과 같이 일반화한다.

- 생년월일 → 연령대 10세 단위(예: 50대)
- 주소 → 시·도 단위(예: 서울특별시)
- 만성질환 코드 → 대분류만 보관(예: I10 → 고혈압)
- 복용 영양제 목록 → 성분 카테고리만 보관(상품명·제조사 제거)
- 촬영 시각 → 일 단위까지만 보관

### 4.3 결합 위험 평가 체크리스트

학습 데이터셋을 외부에 공유하거나 모델 학습에 투입하기 직전, 다음 항목을 모두 점검한다.

- [ ] 데이터셋 내 동일 사용자 식별 가능 행 수가 k≥5를 만족한다.
- [ ] 외부 공개 데이터(예: 통계청 인구 통계)와 결합 시 재식별 위험이 q≥1/100 미만이다.
- [ ] 라벨 이미지에 보이는 영양제 시리얼 번호, 처방 스티커, 보관 메모는 마스킹되었다.
- [ ] 사용자 단말 식별자(IDFA, AAID, IP, 단말 모델)는 데이터셋에 포함되지 않는다.
- [ ] 학습 종료 후 원본 이미지 보관 기간이 §6의 보유 기간을 초과하지 않는다.

체크 결과는 게이트별 리뷰 산출물(§8)에 첨부한다.

## 5. 보유·삭제·파기 정책

| 데이터 유형 | 기본 보유 | 최대 보유 | 사용자 철회 시 |
| --- | --- | --- | --- |
| 분석용 임시 이미지(1번) | 처리 종료 직후 삭제 | 24시간(장애 복구 백업 한정) | 즉시 삭제 |
| 사용자 히스토리(2번) | 90일 | 사용자 설정 최대 24개월 | 7일 이내 삭제 + 로그 |
| 발주처 공유(3번) | 발주처 계약 명시 | 24개월 | 발주처 측 삭제 요청 송부 + 로그 |
| 학습 데이터셋(4번) | 12개월 | 24개월 | 다음 학습 사이클 진입 전 제외 + 가능 시 모델 재학습 |

물리 파기:

- DB 컬럼은 AES-256 키 폐기 또는 컬럼 NULL화 후 VACUUM
- 객체 스토리지는 KMS 키 폐기 + 30일 내 영구 삭제 정책
- 백업은 보유 기간 만료 시 자동 만료(파기 일정과 동기)

## 6. 암호화 및 안전조치 표준

[docs/10 §6.3](./10-compliance-checklist.md), 「ISMS-P 인증 기준」을 따른다.

- 전송 구간: TLS 1.3 강제, HSTS 적용
- 저장: 이미지 객체 스토리지는 KMS 관리형 키로 SSE-KMS 적용
- DB 컬럼 암호화: PostgreSQL `pgcrypto`로 AES-256, 키는 외부 KMS(예: AWS KMS, NCP KMS)에서 관리
- 키 회전: 최소 365일 주기, 키 폐기 이력은 6년 보관
- 접근 통제: 학습 데이터 접근 권한은 발주처 승인 + 별도 IAM 역할에 한정, 모든 접근은 감사 로그 기록
- 가명화 매핑 테이블은 별도 네트워크 세그먼트에 보관, 학습 환경과 격리

## 7. 의료기기법·약사법 회피 조항

기능 A/B/C 모두 [docs/15 §2](./15-regulated-feature-feasibility-and-compliance-plan.md)의 표현 규칙을 준수한다.

- 비전 분류 결과는 "영양제 라벨 영역 검출", "성분 텍스트 추출" 정보 제공에 한정한다.
- "이 조합은 위험합니다", "복용량을 변경하세요" 같은 의료 판단 출력 금지.
- 위험 신호는 규칙 기반 검증(출처 명시 + 임상 가이드 인용)으로만 노출하며, 모델 추론 결과만으로 노출하지 않는다.
- 모든 화면에 [docs/10 §2.3](./10-compliance-checklist.md)의 면책 고지("진단·처방·치료가 아닌 영양 정보 제공") 위젯을 표시한다.
- LLM 멀티모달 출력에는 [docs/12 §6](./12-local-llm-ollama-migration.md)의 금지 표현 필터를 동일하게 적용한다.

## 8. 발주처 리뷰 게이트

세 기능은 각 단계 진입 직전 발주처((주)레몬헬스케어)의 컴플라이언스 담당 + 학생 팀 PM 공동 리뷰를 거친다. 리뷰 입력으로는 다음 산출물을 한 묶음으로 제출한다.

| 게이트 | 시점 | 대상 기능 | 필수 산출물 |
| --- | --- | --- | --- |
| 게이트 #1 | Phase 2 후반 | 기능 B(멀티모달 LLM) | PoC 정확도·응답시간 리포트, 표현 검수 결과, 환경변수 표 |
| 게이트 #2 | Phase 3 초반 | 기능 A(YOLO 검출) | 검출 IoU·OCR 정확도 향상치, 데이터 출처 확인서, 의료법 검토 메모 |
| 게이트 #3 | Phase 4 이후 | 기능 C(벡터 DB 학습 적재) | §4.3 결합 위험 체크리스트, 동의 UI 와이어프레임, 데이터 소유권 합의서 |

리뷰 결과는 본 문서의 §10 변경 이력에 누적하고, GitHub Issue 라벨 `compliance/gate-N`으로 추적한다. 게이트 통과 전에는 해당 기능의 게이트 플래그를 운영 환경에서 활성화하지 않는다.

## 9. 게이트 플래그 매핑

[docs/06 §2.3](./06-tech-stack.md)와 `backend/src/config.py` 의 `Settings` 클래스에 정의된 게이트 플래그는 본 문서의 동의·게이트 통과 여부와 1:1 매핑된다. 운영 환경(`ENVIRONMENT=production`)에서 게이트 플래그를 `true` 로 설정하면 `Settings.validate_production_security` 가 ValueError 를 발생시키므로, 반드시 발주처 리뷰 게이트 통과 후 환경 변수를 변경한다.

| 플래그 | 기본값 | 게이트 통과 조건 | 적용 기능 |
| --- | --- | --- | --- |
| `enable_multimodal_llm` | `false` | 게이트 #1 통과 | 기능 B(Gemma 4 보조 채널) |
| `enable_vision_classifier` | `false` | 게이트 #2 통과 | 기능 A(YOLO 라벨 검출) |
| `vision_classifier_model` | `"yolo26n.pt"` | `enable_vision_classifier` 와 동시 운용 | 기능 A YOLO 모델 태그 |
| `enable_image_learning_pipeline` | `false` | 게이트 #3 통과 + 동의 UI 출시 | 기능 C(학습 적재) |
| `enable_pgvector_storage` | `false` | 게이트 #3 통과 | 기능 C 부속 인프라 |
| `embedding_model` | `"clip-ViT-B-32"` | `enable_image_learning_pipeline` 와 동시 운용 | 기능 C 임베딩 모델 태그 |
| `image_retention_days` | `0` | 동의 매트릭스 §3에 따라 운영자가 설정 | 보유 기간 제어(0 = 즉시 삭제) |
| `enable_learning_auto_filter` | `true` | 사용자 opt-in 후 raw key·PII-like text·성분 signal 자동 필터 통과 | unsafe/low-signal metadata 차단 |
| `require_learning_manual_review` | `true` | 자동 필터 통과 후 operator 검수 통과 전까지 유지 | 학습 embedding job 생성 차단 |

학습 재사용은 `image_learning_dataset` 별도 동의, `ocr_image_processing`, `data_retention` 세 동의가 모두 활성화된 경우에만 `src/learning/consent_gate.py` 를 통과한다.
기존 Supabase Storage를 사용할 때는 public bucket을 금지하고, S3-compatible private bucket 또는 동등한 private object storage만 허용한다. DB에는 object URI, hash, 보유 기한, 자동 필터/검수 상태만 저장하고 raw OCR text와 provider raw payload는 저장하지 않는다. 자동 필터를 운영상 사용할 수 없는 경우에도 `require_learning_manual_review=true` 를 유지해 수동 검수 장벽을 둔다.

플래그를 운영 환경에서 변경하는 경우 변경 이력을 본 문서 §10에 추가한다.

## 10. 변경 이력

| 날짜 | 변경 내용 | 작성자 |
| --- | --- | --- |
| 2026-05-13 | 최초 작성. 동의 매트릭스, 가명화 절차, 게이트 플래그 매핑 정의. | @HorangEe02 |

## 11. 관련 문서

- [docs/Nutrition-docs/10-compliance-checklist.md](./10-compliance-checklist.md)
- [docs/Nutrition-docs/14-pre-implementation-scope-and-rules.md](./14-pre-implementation-scope-and-rules.md)
- [docs/Nutrition-docs/15-regulated-feature-feasibility-and-compliance-plan.md](./15-regulated-feature-feasibility-and-compliance-plan.md)
- [docs/Nutrition-docs/12-local-llm-ollama-migration.md](./12-local-llm-ollama-migration.md)
- [docs/Nutrition-docs/30-multimodal-yolo-experiment-plan.md](./30-multimodal-yolo-experiment-plan.md)
- [docs/Nutrition-docs/06-tech-stack.md](./06-tech-stack.md)
