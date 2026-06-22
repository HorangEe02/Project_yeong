# Lemon-Aid UI/UX 개편 + 엔드포인트 통합 상세 설계 플랜

> 작성: 2026-06-10 · 기준 브랜치: `feat/ai-agent-chat-import`
> 빌드 타깃: Android Studio — Pixel 10 Pro (Android 17, targetSdk 36) / Xcode — iPhone 17 Pro (iOS 26.5, deployment target 15.0)
> 근거 자료: `mobile/uiux/figma` 전수 판독(SoT·DS v2.0·UI 보드 21장·프로토타입), 현재 앱 코드(`mobile/lib`) 인벤토리, 백엔드 55개 라우트 전수 조사

---

## 0. 한눈에 보는 결론

1. **디자인 단일 출처는 Figma `01_Design_System`(DS v2.0) + `mobile/lib/utils/design_tokens_v2.dart`다.** SoT v1.1 §9.4/9.5가 명시. 현재 앱에 공존하는 4개 토큰 파일 중 v2만 살리고 나머지는 정리한다.
2. **탭 구조는 이미 거의 일치한다.** 디자인 보드: `홈 / 챗 / +FAB / 분석 / 설정` ↔ 현재 앱: `홈 / 챗 / 카메라FAB / 점수 / 설정`. **'점수' 탭을 '오늘의 분석'(S-09)으로 교체**하는 것이 유일한 구조 변경.
3. **화면 대부분이 "디자인은 LADS v2인데 데이터가 가짜"인 상태다.** 홈/챗/점수 탭이 하드코딩·mock. 반대로 카메라→분석→등록 플로우는 백엔드 실연동이 이미 탄탄하다. → **이번 개편의 본질은 "시안 적용 + mock을 실제 엔드포인트로 교체"**.
4. **백엔드는 55개 라우트가 준비돼 있고, 시안과의 매핑이 거의 1:1로 떨어진다.** 특히 `POST /supplements/analyze/comprehensive`(5카드 종합분석)와 `POST /ai-agent/chat`(레몬봇)이 핵심.
5. **공백 3가지**: ① 인증(`/auth/*`) 라우트가 백엔드에 없음(시안의 소셜/이메일 가입 플로우 블로커) ② 복약 관리용 `user_medications`/`food_records`/`notifications` 라우트 미등록(팀원 브랜치에 구현 존재 — 가져오면 됨) ③ 리워드/포인트 백엔드 전무.

---

## 1. figma 디자인 자산 인벤토리 (폴더별 파악 결과)

### 1.1 `figma/` 루트
| 파일 | 내용 |
|---|---|
| `LemonAid.fig` (4.2MB) | Figma 원본 파일 (file key `tabLE08wPC1EQ0XdfgCwII`) |
| `_frames_index.md/json` | 페이지·프레임 ID 전체 맵 (총 85+26 프레임) — Figma API 렌더 시 그대로 사용 가능 |
| `_manifest.json` | 내보내기 매니페스트 (frame_scale 3x) |

### 1.2 `00_Source_of_Truth/` — 제품 결정 문서 (1장)
`01_SoT_v1.0_Document.png` = **SoT v1.1** (2026-05-28). 디자인/개발 충돌 시 최종 권위.
- 제품 정의: "혈당 관리 기능을 제외한 음식·영양제 통합 AI 건강관리 앱"
- 5대 확정 결정: 5탭 유지 / 카메라 음식·영양제 2탭 분리 / 음식·영양제 결과 화면 분리 / 추천=분석·기록 기반 행동 가이드 허브 / 의료 면책 룰(금지·권장 워딩, 고정 푸터 "건강 참고용이며 진단·처방이 아닙니다")
- 시니어 접근성 최소치: 본문 15px+, 중요 안내 16px+, 버튼 높이 52px+, 터치 48px+, 색+아이콘+텍스트 병행
- 결과 카드 4요소 필수: 결과 / 확신도(높음·보통·직접확인) / 근거·출처 / 추천 행동
- 상태 매트릭스 9종(분석중/실패/건강정보없음/빈기록/권한없음/저신뢰/HC거부/AppleHealth미지원/네트워크오류)
- 스코프 제외: 혈당 추적·CGM·EMR·진단·처방. v2 이후: Apple Health, 가족 프로필, 장기 리포트

### 1.3 `01_Design_System/` — DS v2.0 (3장 + 풀페이지)
- **브랜드 4테마 × 5단계**: yellow(기본) `#FFC700/#E5B300/#C99100/#FFF6CC/#FFF0A8`, purple `#8B7EE8…`, green `#5FBF7A…`, blue `#4D9CFF…` → 코드 `brand_palette.dart` 구현 존재, 설정에서 사용자 선택(SoT §9.5)
- **시맨틱 20변수**: bg/surface `#FFFFFF`, sunken `#F7F8FA`, section `#F2F4F6`, border `#EEF1F6`, ink `#191F28`/`#4E5968`/`#8B95A1`/`#C5C8CE`, success `#22B07D`, warning `#FF9500`, danger `#EF4452`, review(확인필요) `#B86A00`, info `#2CA8E0` (+각 soft)
- **타이포 7단계 (AppText/*)**: display 32 / title 24 / subtitle 18 / bodyLg 17 / **body 15(시니어 최소)** / caption 13 / micro 11 — **폰트 단일 출처는 Pretendard** (Figma는 Inter 폴백 상태)
- **컴포넌트**: AppCard(Elevated/Outlined), AppPrimaryButton(4상태), AppSecondaryButton, AppTextField(4상태), ConfidenceBadge(High/Mid/Low), OutputCard(결과·확신·출처·다음행동), ResultListRow(충분/부족/과다/주의), SummaryRing
- `02_OutputCard_Concepts.png` 결과 카드 A/B/C 컨셉, `03_ResultList (A)` 영양소 목록 컴포넌트

### 1.4 `02_Wireframe/` — 비어 있음 (스킵)

### 1.5 `03_UI_Design/` — 본편 21장 보드 / 85프레임
| 보드 | 프레임 | 핵심 |
|---|---|---|
| 00 Splash | 1 | Lottie `lemonaid_gold` + 태그라인 |
| 01 Login | 3 | 카카오/구글/Apple + 이메일, "최근 로그인" 툴팁 3변형 |
| 02 Signup | 12 | 약관 바텀시트 → 9단계 위저드(프로필/생년월일 휠/이메일 인증/목적/관심사/신체/건강연동/확인/완료) |
| 03 Main(홈) | 1+2 | 노랑 헤더+주간 달력 스트립, 건강점수 78점 게이지, kcal/매크로 바, **상호작용 주의 카드 3상태**, AI 요약, 식단/복약/영양제 관리 섹션 |
| 04 분석 결과 | 4 | A/B 시안 + **C 하이브리드(채택)** + D 음식 상세. C = 링게이지 82점 → 주의성분 → 부족/과다 2열 → 목적별(GI) |
| 05 부가 화면 | 7 | **S-08 카메라 / S-09 오늘의 분석(84점+실천리스트+4주추이) / S-11 챗 레몬봇 / S-13 설정 / 알림 / 캘린더 / 건강 프로필(만성질환 칩 멀티선택)** |
| 06 음식 분석 플로우 | 2 | 3단계 파이프라인 로딩(검출→분류→후보) / 후보 선택(92%/88%/41% 일치) + 섭취량 칩 + 예상 영양소 |
| 07 영양제 분석 플로우 | 5 | 분석중(검출→OCR→LLM) / OCR 추출(1/2) / 확인·수정(2/2) / 최종 결과(기준치%·효능·주의·**개인화 코멘트**) / 저장 완료 |
| 08 온보딩·권한·캡처 | 7 | 온보딩 3장 / 카메라 권한 / 촬영 미리보기 / 카메라 오류 / 촬영 가이드 모달 |
| 09·14 상태 | 4+5 | 빈/동기화실패/권한없음/분석실패 + 알림빈/검색0건/워치미연동/**신뢰도 낮음(41%)**/응모완료 |
| 10 부가 플로우 | 4 | 건강 데이터(워치 메트릭 4종+주간차트) / 리워드 / 직접 입력(검색) / 복약 알림 설정(시간+요일) |
| 11·16 모달 | 3+4 | **상호작용 경고(소프트 블록)** / 삭제 확인 / 저장 축하 / 시간 휠 바텀시트 / 로그아웃 / 토스트(실행취소) / 섭취량 스테퍼 |
| 12 검출·기록 상세 | 5 | 음식 바운딩박스 검출(94%/81%) / OCR 라벨 검출 / **다중 촬영(앞면+성분표 2슬롯)** / 성분 상세(권장량·상한·효능·질환주의·함유식품) / 오늘의 기록(타임라인) |
| 13 인증 복구 | 4 | 비밀번호 찾기/재설정/완료/**계정 충돌(카카오 중복)** |
| 15 설정 상세 | 4 | 프로필 편집 / 알림 설정(토글 5종) / 약관·정책 / 회원 탈퇴 |
| 달력 시안 | 4 | 주간 위젯 A/B/C 비교 + 월 펼침 |
| 상태 Edge | 3 | 이메일 인증 실패/쿨다운/완료 |

### 1.6 `04_Clickable_Prototype/` — 26프레임 (5장)
로그인·가입 인터랙티브 프로토타입 + 컴포넌트(Checkbox/Switch/Chip/SegmentItem/CheckCircle/SelectCard). 모션 레퍼런스용.

### 1.7 형제 폴더 (참고)
- `Lemon Aid Design System/` — **구버전 리퀴드글래스 킷** (`#FFCE00`, 웜톤 canvas `#FBF8EC`). SoT 권위 체계상 **DS v2.0에 밀림** — radius/spacing/elevation 수치는 v2에 없는 값이라 보조 참조로만 사용
- `handoff/` — `02_FRONTEND_GUIDE.md`(LADS 규칙·auth 라우트 표·모션 가이드), `03_IOS_SETUP.md`(**한국어 권한 문구·카카오/구글 URL 스킴 — 현재 ios/에 미적용**), `OAuth.md`
- `screenshots/` — 현재 앱이 아니라 **'건강의신' 벤치마크 캡처** (구 블루 토큰의 출처)

### 1.8 판독 중 발견된 디자인 모순 (개편 전 결정 필요)
| # | 모순 | 권고 |
|---|---|---|
| D1 | '과다' 색: DS v2.0은 review 앰버 `#B86A00`, ResultList(A)는 danger 레드 | **DS v2.0을 따름** (과다=앰버, 주의=레드) — 색·아이콘·텍스트 병행 원칙으로 보완 |
| D2 | 확신도 % 노출: SoT §7 "% 직접 노출 금지(기본)" vs 모든 보드에 "확신 92%" 칩 | **등급(높음/보통/직접확인)을 기본, %는 상세 화면에서만** — SoT Need-Decision #1 기본값 존중하되 보드의 칩 형태 유지 |
| D3 | Figma 폰트가 Inter 폴백 | 코드는 이미 Pretendard 번들 — 코드 기준 진행 |
| D4 | SoT §2.1 탭(홈/분석/기록/추천/마이) vs UI 보드 탭(홈/챗/+/분석/설정) | **UI 보드를 따름** ("지금 만드는 게 최종" 원칙 + 현재 앱 구조와 일치) |

---

## 2. 현재 앱 진단 (Gap Analysis)

### 2.1 토큰/테마 — 4개 시스템 혼재
| 파일 | 상태 | 처리 |
|---|---|---|
| `utils/design_tokens_v2.dart` (LADS v2, `#FFC700`) | **모든 라우팅된 화면이 import — 사실상 표준** | **유지·단일 출처 확정** (DS v2.0과 값 일치 확인됨) |
| `shared/theme/lemon_design_tokens.dart` | 전역 ThemeData 소스인데 v2와 다른 웜톤/그린시드 | ThemeData를 v2 + `brand_palette` 기반으로 재작성 |
| `utils/design_tokens_v3.dart` | 사용처 거의 없음 (리퀴드글래스 지향) | deprecated 주석 후 점진 제거 |
| `utils/tokens.dart` | 구 '건강의신' 블루 — 폐기 선언됨 | 삭제 |

### 2.2 화면별 현황 ↔ 시안 갭
| 탭/화면 | 현재 | 시안 대비 갭 |
|---|---|---|
| 홈 (`screens/dashboard_screen.dart`, 1038줄) | LADS v2 스타일이나 **데이터 전부 하드코딩**(78점/600kcal 고정). 백엔드 연동된 `features/dashboard/dashboard_screen.dart`는 **라우터 미연결(고아)** | 시안 03 Main: 주간 달력 스트립, 상호작용 카드 3상태, 식단/복약/영양제 관리 섹션 — 데이터 연결 + 신규 섹션 3개 |
| 챗 (`screens/chat_screen.dart`, 600줄) | LADS v2 디자인 완성, **mock 응답** (`TODO: 영양제 팀원 API`) | 시안 S-11과 디자인 거의 일치 — **`/ai-agent/chat` 연동만 하면 됨** (이미 백엔드 통합 완료 상태) |
| 점수 (`screens/score_screen.dart`) | 정적 mock | **'오늘의 분석'(S-09)으로 교체**: 종합점수 링 + 실천 리스트 + 4주 추이 + 레몬봇 딥링크 |
| 카메라 (`screens/camera_screen.dart`, 2631줄) | **실연동 완성** (멀티샷 6장, OCR 4-프로바이더 레이스) | 시안 S-08/08보드: 영양제·식단 세그먼트 토글, 촬영 가이드 모달, 미리보기 품질 체크 UI 보강 |
| 분석 결과 (`screens/analysis_result_screen.dart`, 3473줄) | **실연동 완성** (preview→확인→등록→영향분석→설명) | 시안 04 C(채택) 레이아웃로 재구성 + 07 보드의 2단계 위저드·최종결과 카드 적용 |
| 설정 (`screens/settings_screen.dart`) | 동의 토글·토큰 관리는 실연동, 프로필 행은 정적 | 시안 S-13: 테마 4색 선택, 건강 프로필 서브화면, 워치 연동 상태, 15보드 서브화면 4종 |
| 캘린더/알림 | 명시적 placeholder | 시안 05보드 캘린더/알림 + 12보드 오늘의 기록 |
| 로그인 | Bearer 토큰 붙여넣기 화면 (dev용) | 시안 01/02/13: 소셜+이메일 가입 9단계 — **백엔드 `/auth/*` 부재로 P2** |
| 온보딩/상태화면 | 없음 | 시안 08/09/14 템플릿 신규 |

### 2.3 플랫폼 설정 갭
**Android (Pixel 10 Pro · Android 17)**
- `cleartextTrafficPermitted=false` 전역 차단인데 dev API가 `http://10.0.2.2:8000` → **디버그 빌드용 network_security_config debug-overrides 추가 필요** (현재 dev에서 HTTP 호출이 막힐 수 있는 실제 버그)
- Health Connect 권한/매니페스트/`health` 패키지 전무 (시안 10보드 워치 연동은 P1)
- targetSdk 36 유지, Android 17 대응은 예측형 뒤로가기·엣지투엣지 점검 수준

**iOS (iPhone 17 Pro · iOS 26.5)**
- 카메라/사진 권한 문구가 **영어** — `handoff/03_IOS_SETUP.md`의 한국어 문구로 교체 (심사 리스크)
- `UIUserInterfaceStyle=Light` 미적용 (디자인은 라이트 전용)
- 카카오/구글 URL 스킴 미적용 (auth P2 진행 시)
- HealthKit 엔타이틀먼트 없음 — SoT상 Apple Health는 v2 이후라 보류
- ATS `NSAllowsLocalNetworking=true`로 시뮬레이터 dev는 동작

---

## 3. 화면별 상세 설계 — 시안 적용 + 엔드포인트 배선

> 전 화면 공통: ① 모든 호출 전 동의 게이트(403 `consent_required` → 동의 재요청 플로우 기존 패턴 재사용) ② 결과 카드 4요소(결과/확신도/출처/다음행동) ③ 고정 면책 푸터 ④ 시니어 최소치(본문 15px+, 버튼 52px+)

### 3.1 홈 (03 Main) — P0
| 시안 요소 | 데이터 소스 (엔드포인트) | 비고 |
|---|---|---|
| 주간 달력 스트립 + 기록 점 | `GET /meals?from_eaten_at=&to_eaten_at=` + `GET /supplements` | 날짜별 기록 유무 → 점. 달력 시안 A(소프트 셀) 채택 권고 |
| 오늘의 건강 점수 78점 + 등급 | `GET /dashboard/summary` (activity.latest_activity_score) + `POST /supplements/analyze/comprehensive`의 `diet_score` | 점수 정의 결정 필요: 대시보드 활동점수 vs 식단점수 — **초기엔 diet_score 사용 권고** |
| kcal 섭취/목표/소모/잔여 + 매크로 3종 바 | `GET /meals` 당일 합산(`nutrition_summary`) + 목표는 프로필(`GET /health/profile-snapshots/latest` + KDRIs `GET /nutrition/kdris`) | 소모 kcal은 Health Connect 연동 전까지 숨김 |
| 상호작용 주의 카드 (3상태: 주의 N건/안심/약 미등록) | `GET /supplements/recommendations/latest`의 `excess_or_duplicate_risks` + (P1) `user_medications` 라우트 임포트 후 약 기준 점검 | 약 미등록 상태가 기본값이 됨 — 시안의 ③상태 |
| 오늘의 분석 AI 요약 카드 | `POST /ai-agent/daily-coaching` 응답 `message`/`findings` (또는 직전 결과 캐시) | 1일 1회 호출 + 로컬 캐시 |
| 식단 관리 섹션 (끼니별 기록) | `GET /meals` (meal_type별) + 기록하기 → 카메라 딥링크 | 이미 동작하는 meal confirm 플로우 재사용 |
| 복약/영양제 관리 섹션 (체크리스트) | 영양제: `GET /supplements` + `intake_schedule`. **복약: 백엔드 라우트 공백** → P1에서 팀원 브랜치 `user_medications.py` 라우트 임포트 | 복용 체크 상태는 우선 로컬 저장(P0), 서버 동기화는 P2 |

### 3.2 챗 — 레몬봇 (S-11) — P0 ★기존 Flutter 이식 계획과 동일 작업
- 시안과 현재 `chat_screen.dart` 디자인이 거의 일치 → **UI 변경 최소, 데이터만 교체**
- 배선 시퀀스: 앱 기동 시 `POST /me/privacy/consents/sensitive_health_analysis`(1회) → 메시지마다 `POST /ai-agent/chat` `{request_id, user_id, message, conversation[≤24], context{}}`
- 응답 처리: `message` 말풍선 / `answerability`≠answerable 시 안내 패널 / `sources[]` 출처 칩 / `ctas[≤3]` 추천 행동 버튼 / `requires_user_approval=true` + `approval_preview` → 승인 시트 → `context.analysis_run_approval={approved:true, analysis_kind}` 재전송
- 분석결과 화면의 "챗으로 설명 보내기"(현 로컬 드래프트)는 유지하되, 전송 시 실제 챗 API에 컨텍스트로 합류
- 팀원 레퍼런스: `mobile/flutter_app/lib/features/chat/` (chat_models.dart는 거의 그대로 이식, repository는 기존 http ApiClient 재작성 — **경로에서 `/api/v1` 접두사 제거**, 신규 pubspec 의존성 불필요)

### 3.3 분석 탭 — 오늘의 분석 (S-09, 점수 탭 대체) — P0
| 시안 요소 | 데이터 소스 |
|---|---|
| 종합 점수 84/100 링 + 등급 칩 + 코멘트 | `POST /ai-agent/daily-coaching` (`findings`→부족 영양소 언급, `message`→코멘트) |
| 실천 리스트 4개 + 체크 | daily-coaching `recommendations[]`/`actions[]` (체크 상태는 로컬) |
| 스마트 분석 — 4주 추이 라인차트 | `GET /analysis-results?analysis_type=nutrition_analysis` 시계열 (저장은 `POST /analysis-results/nutrition`) |
| "레몬봇에게 물어보기" | `/shell/chat` 딥링크 + 초기 질문 프리필 |

### 3.4 카메라/검출 플로우 (S-08, 06/07/08/12 보드) — P0~P1
- 기존 실연동 위에 시안 UI 보강: 영양제/식단 세그먼트 토글(현 액션시트 대체), 촬영 가이드 모달(`다시 보지 않기` 로컬 플래그), 미리보기 품질 체크 2종, 다중 촬영 2슬롯(앞면+성분표 — 기존 멀티샷 세션 `POST /supplements/analysis-sessions/*` 재사용)
- 분석 중 화면: 시안의 3단계 체크리스트(검출→OCR/분류→해석)를 `pipeline_metadata` + 잡 상태로 표현, "메인으로 이동"(백그라운드 계속) = 기존 AnalysisJobSnapshot 패턴 그대로
- 음식 후보 선택(06-②): `MealImageAnalysisPreview.food_candidates[]`의 `display_name/confidence` → 일치 % 칩(D2 결정 반영: 등급 표시), 섭취량 칩/스테퍼(16보드) → confirm payload의 `portion_amount` 조정, 후보 없음/저신뢰 → 직접 입력 검색(`GET /meals/foods?q=`) 폴백
- 음식 영역 검출 오버레이(12-①): preview 응답의 detected regions 활용(영양제는 `detected_product_regions[]` 존재; 음식은 백엔드 확장 필요 시 P2)

### 3.5 분석 결과 — C 하이브리드 채택안 (04 보드) — P0
**음식(식단) 결과**: 링게이지(diet_score) → 주의 성분 카드 → 부족/과다 2열 → 목적별(GI) 카드 → 면책 → [기록에 저장]
- 데이터: `POST /supplements/analyze/comprehensive` 응답이 5카드와 1:1 — `deficient_nutrients[]`(부족), `excessive_nutrients[]`(과다, 배수 계산 가능), `cautionary_components[]`(주의, severity/message), `diet_score`+label+message(점수), `purpose_targets[]`(목적별·당뇨 GI 등)
- 음식 상세(D 프레임): `MealRecordResponse.food_items[]` + `nutrition_summary` + `POST /meals/{id}/explain`(AI 영양소 분석 문단, source_citations)
- 저장: `POST /meals/{meal_id}/confirm` (기존 동작 유지)

**영양제 결과(07 보드 ④)**: 핵심 성분 기준치% 바(`ingredient_candidates`의 `daily_value_percent` 또는 `GET /nutrition/kdris` 대비 계산) + 기대 효능/주의(`POST /supplements/analyses/{id}/explain`의 bullets/citations) + **개인화 코멘트**(만성질환 기반 — comprehensive의 `chronic_disease_indications[]`) + 저장 `POST /supplements`
- 저장 완료(⑤): 응답 요약 + "복용 알림 설정하기" → 복약 알림 화면(3.7) / 상호작용 경고 모달(3.8) 조건부 표출

### 3.6 설정 (S-13 + 15 보드) — P1
| 시안 요소 | 배선 |
|---|---|
| 프로필 헤더/편집 | 로컬 + `POST /health/profile-snapshots` (이름·생년월일·성별·신체) |
| 만성질환·복약 정보 → 건강 프로필(05-⑦) | `POST /medical-records` + `/confirm` (만성질환 칩 멀티선택 → condition 레코드), 복약 탭은 user_medications 라우트 임포트 후 |
| 테마 색상 4스와치 | `brand_palette.dart` + `brandThemeNotifier` (코드 구현 존재 — UI만 연결) + SharedPreferences |
| 동의 관리 | `GET/POST/DELETE /me/privacy/consents` (기존 연동 확장) |
| 워치 연동 상태 칩 | Health Connect 연동(P1, Android 먼저) → `POST /health/sync` |
| 데이터 내보내기/회원 탈퇴 | 탈퇴: `POST /me/data-deletion-requests` (시안 15-④ 경고 카드 + 사유 수집은 로컬) |
| 알림 설정(15-②) | 로컬 알림 권한+스케줄(P1) — 백엔드 알림 라우트 공백(아래 §5) |

### 3.7 캘린더 / 오늘의 기록 / 알림 — P1
- 캘린더(05-⑥): 월 그리드 + 기록 점 = `GET /meals?from_eaten_at&to_eaten_at` + `GET /supplements` 날짜 집계; 일자 상세 행 → 기록 상세
- 오늘의 기록(12-⑤): 끼니/영양제 타임라인 = `GET /meals` + `GET /supplements`(등록일 기준) 병합 정렬, 합계 카드(kcal/끼니/영양제 수)
- 알림 센터(05-⑤): P1은 로컬 알림 이력(복약 리마인더), 서버 푸시·리포트 알림은 P2
- 복약 알림 설정(10-④ + 16-① 시간 휠): `flutter_local_notifications` 기반 로컬 스케줄(시간 배열+반복 요일). 백엔드 `reminder_preferences` 테이블은 존재하나 라우트 미등록 — 팀원 `notifications.py` 임포트 시 서버 동기화 가능

### 3.8 모달/상태 시스템 (09·11·14·16 보드) — P0 템플릿 + P1 적용
- 전역 상태 위젯 4종(빈/동기화실패/권한없음/분석실패) — 기존 `empty_state.dart`/`error_panel.dart`를 시안 레이아웃(마스코트+타이틀+설명+CTA)으로 교체, SoT §8 9종 메시지 매핑
- **상호작용 경고 모달(11-①)**: 영양제 저장 직전, comprehensive `cautionary_components[severity=high]` 또는 impact preview `excess_or_duplicate_risks` 검출 시 표출. 소프트 블록("그래도 저장할게요") + "안전 정보 자세히 보기" → 성분 상세. **의료법 워딩 준수**(상담 권고형)
- 삭제 확인(11-②): `DELETE /supplements/{id}`, `DELETE /analysis-results/{id}` 등 파괴적 액션 공통
- 토스트+실행취소(16-③): 저장 직후 — 실행취소는 soft-delete 즉시 호출로 구현
- 저신뢰 경고(14-④): confidence < 임계치(예: 0.6) 시 "추정" 라벨 + 직접 입력/재촬영 폴백 (SoT 확신도 가이드)

### 3.9 인증 (01/02/13 보드 + Edge states) — P2 (백엔드 블로커)
- **백엔드에 `/auth/*` 라우트가 없음** (현 인증 = AUTH_MODE=disabled dev 또는 외부 OIDC JWT). 시안의 카카오/구글/Apple/이메일 인증코드 플로우는 백엔드 신규 개발 필요: `POST /auth/signup|login|kakao|google|apple|email/send-code|email/verify-code|refresh|logout` (handoff 가이드의 라우트 표 준용)
- 다만 **가입 위저드의 수집 데이터는 기존 엔드포인트로 선반영 가능**: 약관 동의 시트 → `/me/privacy/consents/*`, 신체 정보 → `/health/profile-snapshots`, 목적/관심사 → 로컬+프로필, 건강연동 토글 → Health Connect 온보딩
- 권고 순서: P0~P1 동안 현 토큰 로그인 유지 → P2에서 auth 백엔드(Supabase Auth 또는 자체 OIDC) 결정 후 시안 적용. 결정 전에는 시안 02의 약관 동의 시트만 먼저 떼어 동의 게이트 UI로 사용(현 영문 ConsentGateScreen 대체)

### 3.10 리워드(10-②) — P2/보류
백엔드 전무(포인트/응모권/챌린지). SoT MoSCoW상 Could 이하 → 보드는 보존하되 이번 개편 범위 제외.

---

## 4. 엔드포인트 매핑 총괄표 (화면 → API)

| 화면/기능 | 엔드포인트 | 필요 동의 | 단계 |
|---|---|---|---|
| 챗 레몬봇 | `POST /ai-agent/chat` | sensitive_health_analysis | **P0** |
| 오늘의 분석 | `POST /ai-agent/daily-coaching` | sensitive_health_analysis | **P0** |
| 홈 요약 | `GET /dashboard/summary` | sensitive_health_analysis | **P0** |
| 식단 5카드/점수 | `POST /supplements/analyze/comprehensive` | (인증만) | **P0** |
| 식단 기록 목록/캘린더 | `GET /meals`, `GET /meals/cuisines`, `GET /meals/foods` | — | P0~P1 |
| 음식 분석/확정 | `POST /meals/analyze-image` → `POST /meals/{id}/confirm` → `POST /meals/{id}/explain` | food_image_processing | 기존 동작 |
| 영양제 분석/확정 | `POST /supplements/analyze`(+세션/멀티) → `/analyses/{id}/ocr-text|explain` → `POST /supplements` | ocr_image_processing, sensitive_health_analysis | 기존 동작 |
| 영양제 목록/상세/삭제 | `GET/DELETE /supplements*` | — | P0~P1 |
| 영향·상호작용 | `GET /supplements/recommendations/latest`, `POST .../explain` | sensitive_health_analysis | P0 |
| 영양 기준/분석 | `GET /nutrition/kdris`, `POST /nutrition/analyze`, `GET /nutrition/diagnosis/latest` | (kdris/analyze는 공개) | P1 |
| 추이 저장/조회 | `POST /analysis-results/*`, `GET /analysis-results` | sensitive_health_analysis | P1 |
| 건강 프로필 | `POST/GET /health/profile-snapshots*` | sensitive_health_analysis | P1 |
| 워치 동기화 | `POST /health/sync`, `GET /health/daily-summary` | health_device_data | P1 |
| 만성질환/복약 기록 | `POST/GET /medical-records*` | sensitive_health_analysis | P1 |
| 동의 관리 | `GET/POST/DELETE /me/privacy/consents*` | — | 기존 동작 |
| 탈퇴 | `POST /me/data-deletion-requests` | — | P1 |
| 활동/체중 예측 | `POST /activity/score`, `POST /predictions/weight` | sensitive_health_analysis | P1~P2 |
| 처방전/검사지 OCR | `POST /regulated-inputs/*` | +prescription/lab consents, feature flag | P2 |

**백엔드 공백(이번에 결정/처리할 것)**
1. `/auth/*` 전체 — P2 결정 사항 (Supabase Auth vs 자체 구현)
2. `user_medications`/`food_records`/`notifications` API 라우트 — **팀원 브랜치(`external/Lemon-sin-ai-agent-branch`)에 구현 존재**. 홈 복약 관리·복약 알림 서버 동기화에 필요 → P1에서 선별 임포트(직전 백엔드 통합과 동일한 방식)
3. 리워드/포인트 — 범위 외

---

## 5. 플랫폼별 작업 목록

### Android (Pixel 10 Pro · Android 17)
- [ ] `network_security_config.xml`에 debug-overrides 추가 (dev HTTP `10.0.2.2` 허용; release는 현행 차단 유지) — **P0, 현재 dev 연결 버그 가능성**
- [ ] 테마 4색·다이나믹 컬러 비간섭 확인, 엣지투엣지/예측형 뒤로가기 점검 — P0
- [ ] `flutter_local_notifications` + `POST_NOTIFICATIONS` 권한(복약 알림) — P1
- [ ] Health Connect: `health` 패키지 + 매니페스트 권한 + 온보딩 연동 플로우(10-①) — P1
- [ ] 빌드: `flutter build apk --debug --dart-define=LEMON_API_BASE_URL=http://10.0.2.2:8000/api/v1` (flavor dev)

### iOS (iPhone 17 Pro · iOS 26.5)
- [ ] Info.plist 한국어 권한 문구 교체(카메라/사진/마이크) — `handoff/03_IOS_SETUP.md` §3 그대로 — **P0, 심사 리스크**
- [ ] `UIUserInterfaceStyle = Light` 추가 — P0
- [ ] 로컬 알림 권한 + 복약 알림 — P1
- [ ] (P2, auth 진행 시) 카카오/구글 URL 스킴 + LSApplicationQueriesSchemes
- [ ] (v2 이후) HealthKit 엔타이틀먼트 — SoT상 보류
- [ ] 빌드: `flutter build ios --no-codesign` 검증, 시뮬레이터 `iPhone 17 Pro`, dev API `http://127.0.0.1:8000/api/v1` (ATS LocalNetworking 허용 확인됨)

### 공통/백엔드 dev 스택
- 백엔드 기동: `uvicorn src.main:app --port 8000` (PYTHONPATH에 `ai_agent_chat/src` 포함 — Dockerfile은 반영 완료, 베어메탈 실행 시 환경변수 필요)
- 최초 1회 `alembic upgrade head` (챗 테이블 0030~0041 미적용 상태)
- LLM: Ollama(`gemma4:e4b` 로컬 기본) 또는 SGLang — 미기동 시에도 챗은 결정론적 답변으로 동작(데모 가능)

---

## 6. 실행 로드맵

### P0 — 핵심 동작 (UI 정합 + mock 제거)
1. **토큰 통일**: ThemeData를 design_tokens_v2 + brand_palette 기반으로 재작성, v3/구토큰 정리, 설정 테마 선택 UI (D1·D2 결정 반영)
2. **챗 실연동**: consent → `/ai-agent/chat` (팀원 chat_models 이식 + repository 재작성, answerability/CTA/승인 루프)
3. **홈 실데이터**: dashboard/summary + meals/supplements 연결, 주간 스트립, 상호작용 카드(약 미등록 상태부터), AI 요약
4. **분석 결과 C 적용**: comprehensive 5카드 + 음식 상세(D) + 영양제 최종 결과 재구성
5. **분석 탭 전환**: 점수 → 오늘의 분석(S-09) + daily-coaching
6. **상태/모달 템플릿** + Android cleartext 디버그 픽스 + iOS 한국어 권한 문구
- 검증: `flutter analyze` + 위젯/골든 테스트 갱신, 양 플랫폼 디바이스 스모크(촬영→분석→저장→챗 질문 E2E)

### P1 — 흐름 완성
캘린더·오늘의 기록 / 설정 서브 4종 + 건강 프로필(medical-records) / 복약·영양제 체크리스트(라우트 임포트 포함) / 복약 알림(로컬) / 음식 후보 선택·섭취량 UI / 추이 차트(analysis-results) / Health Connect(Android)

### P2 — 인증·확장
auth 백엔드 결정 + 01/02/13 보드 구현 / 알림 센터 서버화 / 처방전·검사지 OCR 화면 / (보류) 리워드

---

## 7. 리스크 및 결정 대기 항목
| # | 항목 | 권고 |
|---|---|---|
| R1 | 홈 '건강 점수'의 정의 (활동점수 vs 식단점수 vs 합성) | 초기 diet_score, 합성 점수는 백엔드 협의 후 |
| R2 | 복용 체크 상태 저장 위치 | P0 로컬 → P1 user_medications 라우트 임포트 후 서버 |
| R3 | 인증 백엔드 방식 | Supabase Auth 우선 검토(이미 supabase 의존 존재) — 팀 결정 필요 |
| R4 | 음식 영역 바운딩박스 오버레이 | 백엔드 detected regions(음식) 미노출 시 P2로 |
| R5 | production 챗 fail-closed | 의료 소스 거버넌스 DB 시드 전까지 챗이 보수적 답변 — 데모 시 dev 환경 사용 |

---

*이 문서는 `mobile/uiux/figma` 전수 판독(에이전트 5개 병렬 분석, SoT·DS·85프레임·코드·55라우트)을 근거로 작성되었습니다. 프레임 ID가 필요한 경우 `figma/_frames_index.md`를 참조하세요.*
