# Lemon Healthcare — Static Data Catalog

본 디렉터리는 영양 분석에 사용하는 **정적·반정적 데이터**를 보관합니다. 사용자 데이터 / 이미지는 절대 보관하지 않습니다.

---

## 📂 구조

```
data/
├── CLAUDE.md                           # 데이터 작업 규칙 (Tier 2)
├── README.md                           # 이 파일 (출처·라이선스)
├── reference/
│   ├── nutrient_codes.json             # 30종 표준 영양소 코드
│   └── disease_codes.json              # 5종 만성질환 + ICD-10 + v4 가중치
├── kdris/
│   ├── kdris_2020.csv                  # PoC 시드 (≈76 row)
│   └── kdris_metadata.json
├── mfds/
│   ├── functional_ingredients.csv      # 식약처 건기식 인정 원료 ↔ nutrient_code 매핑
│   └── unit_conversions.json           # vit A/D/E IU↔질량
└── sample/                             # 테스트용 작은 익명 데이터
```

---

## 📚 출처·라이선스

| 자원 | 출처 | 라이선스 | 의무 |
|------|------|---------|------|
| KDRIs 2020 | 한국영양학회 + 보건복지부 | 공공저작물 자유이용 (KOGL Type 1) | 출처 표시 |
| 식약처 건강기능식품 원료 | 식품의약품안전처 | 공공데이터 | 출처 표시 + API 키 (외부 API 사용 시) |
| 만성질환 코드 매핑 | 보건복지부 / WHO ICD-10 | 공공저작물 | 출처 표시 |
| 단위 환산 (IU↔질량) | USP / 식약처 환산 기준 | 일반 공중 영역 | — |

---

## ⚠️ PoC 시드 한계

**`kdris/kdris_2020.csv` 는 PoC 시드 데이터입니다.** 정확한 KDRIs 2020 표를 그대로 옮긴 자료가 아니며, 정식 출시 전 영양사 검수 후 갱신해야 합니다.

자세한 한계는 `kdris/kdris_metadata.json#limitations` 참조.

---

## 🔄 데이터 갱신 정책

| 데이터 | 갱신 빈도 | 트리거 |
|--------|---------|-------|
| KDRIs | 개정 발표 시 즉시 | 한국영양학회 알림 (수동) |
| 식약처 건기식 원료 | 변경 알림 시 수동 | 식약처 보도자료 모니터링 |
| nutrient_codes / disease_codes | 영양 분석 로직 변경 시 | 코드 변경 시 동반 |

---

## 🧪 검증

데이터 무결성은 `backend/scripts/validate_data.py` 가 Pydantic 으로 검증합니다. CI에 통합되어 데이터 변경 시 자동 실행됩니다.

```bash
cd backend
python scripts/validate_data.py
```

---

## 🔐 보안 / 컴플라이언스

- 사용자 개인정보 / 이미지는 **절대** 본 디렉터리에 보관하지 않습니다.
- AI Hub 데이터셋 같이 재배포 금지인 자원은 메타만 보관하고 실제 데이터는 외부 스토리지에 둡니다.
- 가명처리된 데이터라도 결합 위험을 평가합니다 (`CLAUDE.md` §가명정보 처리).

---

## 🔗 관련 문서

- [`data/CLAUDE.md`](./CLAUDE.md) — 데이터 작업 절차
- [`docs/09-data-catalog.md`](../docs/09-data-catalog.md) — 전체 데이터·API 카탈로그
- [`docs/10-compliance-checklist.md`](../docs/10-compliance-checklist.md) — 개인정보 / 가명정보 처리
