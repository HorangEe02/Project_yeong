# One-shot 융합 — 실 라벨 end-to-end 검증 런북

- 작성일: 2026-06-15
- 대상: `merge_strategy=single_product` 한방 OCR 융합 경로(`analyze_fused_supplement_images`)
- 하네스: `backend/scripts/verify_oneshot_fusion_labels.py`
- 관련 설계: `docs/ocr_baseline_reports/2026-06-15-multi-image-single-supplement-merge-design-and-guideline.md`

## 0. 목적

원통형 영양제처럼 한 라벨이 여러 장에 쪼개져 찍힌 실제 묶음에서, **융합(single_product)**이
**레거시 이미지별(distinct_products)** 대비 4개 타깃 필드(제품명 / 성분·함량 / 한글병기 / 섭취·주의)를
실측으로 개선하는지 A/B로 확인한다.

## 1. 사전 준비 (필수)

1. **융합 플래그 ON** — 융합은 dark-launch(기본 False)다. 백엔드 프로세스/컨테이너 env에
   `SUPPLEMENT_ONE_SHOT_FUSION_ENABLED=true` 를 주입한다.
   - 로컬 docker 스택이면 `docker-compose.yml` backend env에 추가 후 **재빌드 불요·recreate**로 충분
     (이미지 코드는 그대로, env만 바뀜). 단 소스 변경(per-image 학습)을 반영하려면
     `docker compose build backend` 재빌드 필요(소스가 이미지에 baked — [[ai-agent-chatbot-import-state]]).
   - `docker system df` + `df -h /System/Volumes/Data`로 디스크 여유 확인 후 빌드(빌드가 시스템 디스크를 채워 데몬 hung 사고 이력).
2. **인증 토큰** — `supplement:write` 권한 보유 사용자의 bearer 토큰.
3. **동의(consent)** — 그 사용자가 외부 OCR 처리 / 데이터 보존 동의를 보유해야 한다.
   없으면 라우트가 `403 consent_required` 를 반환(하네스가 에러로 기록).
4. **이미지 레이아웃** — 제품 1개 = 서브폴더 1개, 그 안에 N장:
   ```
   labels/
     vitamin-d-cylinder/
       01-front.jpg
       02-facts.jpg
       03-intake.jpg
       roles.json        # 선택: {"01-front.jpg": "front_label", "02-facts.jpg": "supplement_facts", ...}
     omega-3/
       ...
   ```
   허용 역할: `unknown, front_label, supplement_facts, intake_method, ingredients, precautions, barcode, mixed`.
   `roles.json` 생략 시 전부 `unknown`(역할은 파서에 주는 약한 힌트일 뿐, 누락돼도 동작).

## 2. 실행

```bash
cd backend
.venv/bin/python scripts/verify_oneshot_fusion_labels.py \
  --base-url http://localhost:8000 \
  --token "$SUPPLEMENT_WRITE_TOKEN" \
  --images-root ./labels \
  --out outputs/oneshot-fusion-verification.md
```

- 각 제품 폴더를 `single_product`·`distinct_products` 두 전략으로 POST → markdown A/B 리포트 생성.
- **개인정보**: 리포트는 파싱된 라벨 내용(제품명·성분)을 담는다 = 검증 대상이므로 의도적. `outputs/`(gitignore)에
  쓰고 **커밋 금지**. 원문 OCR 텍스트는 요청·저장하지 않음(`raw_ocr_text_stored=False`).

## 3. 합격 기준 (A/B 해석)

`single_product`가 `distinct_products` 대비 다음을 만족하면 융합이 효과적:

| 지표 | 기대 |
|---|---|
| **결과 개수** | single=**1** (distinct는 보통 N) — "4개로 쪼개짐" 문제 해소의 1차 증거 |
| **성분 수 / recall** | 끊긴 표가 한 파싱으로 복원 → distinct 합집합 이상(누락↓) |
| **함량 채움률(w/ amount)** | 이름↔함량이 다른 이미지에 나뉜 경우 융합이 재결합 → 함량 보유 성분↑ |
| **한글병기 %** | `한글 (English)` 또는 display+original 동시 보유 비율 동등 이상 |
| **missing_required_sections** | 융합이 더 적게(제품명/성분/섭취/주의 누락↓) |

- 실패(융합이 동등/열위)면: 프롬프트 보강(설계문서 §5.3)·단위 정규화·노이즈 필터(§6.2)를 후속으로.
- 합격이면: 플래그를 `default=True`로 되돌리거나(또는 env로 운영 노출) 단계적 롤아웃 결정.

## 4. 후속 의사결정 연결

- 이 검증이 통과해야 **dark-launch → default-on** 플립을 정당화한다(`supplement_one_shot_fusion_enabled`).
- per-image 학습 아티팩트(이번 세션 구현)는 융합 경로에서도 이미지별 학습 이미지+섹션 주석을 적재하므로,
  검증 묶음 자체가 섹션 검출기 데이터셋에도 기여한다(동의 보유 시).
