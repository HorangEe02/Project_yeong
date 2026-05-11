# 규제 기능 구현 가능성 평가 및 반영 계획

## 1. 검토 목적

팀이 구현하고 싶은 기능은 다음 세 가지다.

- 실제 병원 데이터 연동
- 처방전 및 검사표 이미지 분석
- 복용량 변경 관련 안내

검토 결과, 세 기능 모두 기술적으로는 구현 가능하지만 공개 B2C 서비스에서 바로 제공하면 개인정보, 의료행위, 약사 업무, 의료기기 또는 디지털의료제품 규제에 걸릴 수 있다. 따라서 “규제 회피”가 아니라 “규제 안에서 가능한 범위로 기능을 쪼개는 방식”으로 구현해야 한다.

## 2. 공식 근거 요약

| 구분 | 확인 내용 | 구현 영향 | 공식 출처 |
| --- | --- | --- | --- |
| 개인정보 수집 | 개인정보 수집·이용은 동의, 목적, 수집 항목, 보유 기간, 거부권 고지가 필요하다. | 병원 데이터, 처방전, 검사표는 목적·항목·보유기간을 분리해 동의받아야 한다. | [개인정보 보호법 제15조](https://law.go.kr/LSW/lsLawLinkInfo.do?chrClsCd=010202&lsId=011357&lsJoLnkSeq=900078940&print=print) |
| 민감정보 | 건강 정보는 민감정보로 별도 동의 또는 법령 근거가 필요하고 안전조치가 필요하다. | 만성질환, 복약, 검사결과, OCR 결과는 일반 개인정보 동의와 분리한다. | [개인정보 보호법 제23조](https://www.law.go.kr/lsLawLinkInfo.do?chrClsCd=010202&lsJoLnkSeq=1000575255) |
| 진료기록 | 환자는 본인 기록 열람·사본 발급을 요청할 수 있고, 환자가 아닌 사람에게는 확인하게 하면 안 된다. | 병원 직접 조회는 사용자 본인 권한·동의·공식 연동 경로가 필요하다. | [의료법 제21조](https://www.law.go.kr/LSW/lsLinkCommonInfo.do?ancYnChk=&chrClsCd=010202&lsJoLnkSeq=1007235937) |
| 의료행위 | 의료인이 아니면 의료행위를 할 수 없다. | 진단, 치료, 처방, 복용량 변경 결정은 앱 단독 기능으로 제공하지 않는다. | [의료법 제27조](https://www.law.go.kr/lsLawLinkInfo.do?chrClsCd=010202&lsJoLnkSeq=900700904) |
| 원격의료 | 의료법상 원격의료는 의료인이 정보통신기술로 의료지식·기술을 지원하는 구조를 다룬다. | 의료인 판단이 필요한 기능은 파트너 의료기관·의료인 검토 워크플로로 분리한다. | [의료법 제34조](https://www.law.go.kr/lsLawLinkInfo.do?chrClsCd=010202&lsJoLnkSeq=900519517) |
| 의약품 조제·복약지도 | 약사는 처방전에 따라 조제하고, 조제 후 필요한 복약지도를 해야 한다. | 앱은 복용량 변경 지시를 하지 않고 약사/의사 상담 연결로 제한한다. | [약사법 제23조](https://www.law.go.kr/lsLawLinkInfo.do?chrClsCd=010202&lsJoLnkSeq=1000179918), [약사법 제24조](https://www.law.go.kr/LSW/lsLawLinkInfo.do?chrClsCd=010202&lsId=001783&lsJoLnkSeq=1000345151&print=print) |
| 의료기기 해당 가능성 | 질병의 진단·치료·경감·처치·예방 목적의 소프트웨어는 의료기기 해당 가능성이 있다. | 검사표를 해석해 질환을 판단하거나 치료 방향을 제안하면 인허가 검토 대상이 될 수 있다. | [의료기기법 제2조](https://www.law.go.kr/lsLawLinkInfo.do?chrClsCd=010202&lsJoLnkSeq=900516573) |
| 디지털의료제품 | 디지털의료기기는 질병 진단·치료·예후 관찰, 치료 반응·결과 예측, 부작용 모니터링 목적을 포함한다. 건강 유지·향상 목적 기기도 별도 범주가 있다. | AI 기반 검사표 해석, 치료 반응 예측, 복약 부작용 판단은 디지털의료제품 검토가 필요하다. | [디지털의료제품법 제2조](https://www.law.go.kr/LSW/lsSideInfoP.do?chrClsCd=010202&docCls=jo&joBrNo=00&joNo=0002&lsId=&lsiSeq=259299&urlMode=lsScJoRltInfoR), [MFDS 생성형 AI 의료기기 가이드라인](https://www.mfds.go.kr/brd/m_1060/view.do?seq=15628) |
| 병원 데이터 연동 표준 | 건강정보 고속도로는 활용서비스 연계 API와 데이터 조회, 동적 동의, 인증 API를 제공한다. | 직접 스크래핑이 아니라 공식 API 또는 FHIR adapter 구조로 설계한다. | [건강정보 고속도로 API](https://www.myhealthway.go.kr/portal/index?page=Organization%2FPortal%2FMediMyData%2FMydataApi) |
| 연동 데이터 범위 | 건강정보 고속도로는 Patient, Condition, MedicationRequest, Observation 등 12개 항목을 전송 가능한 데이터로 안내한다. | 병원 데이터 schema는 KR Core FHIR 리소스 기준으로 설계한다. | [건강정보 고속도로 데이터 종류](https://www.myhealthway.go.kr/portal/index?page=Organization%2FPortal%2FMediMyData%2FMydataType) |
| 보건의료데이터 활용 | 개인정보보호위원회는 보건의료데이터 활용 가이드라인 최신판을 제공한다. | 가명처리, 연구/통계/서비스 활용 구분, 데이터 최소화 기준을 별도 문서화한다. | [개인정보보호위원회 보건의료데이터 활용 가이드라인](https://www.pipc.go.kr/np/cop/bbs/selectBoardArticle.do?bbsId=BS217&mCode=G010030000&nttId=9901) |

## 3. 기능별 구현 가능성 평가

### 3.1 실제 병원 데이터 연동

구현 가능성: 조건부 가능

바로 구현하면 위험한 방식:

- 병원 홈페이지 또는 EMR 화면 직접 스크래핑
- 사용자의 병원 계정 정보를 앱이 보관
- 병원 또는 공공기관 동의 없이 제3자 데이터 조회
- 병원 원본 문서 전체를 장기 저장

구현 가능한 방식:

- 1단계: mock FHIR 서버와 샘플 환자 프로필로 화면, API, DB schema를 먼저 구현
- 2단계: 사용자가 직접 내려받은 진료요약, 처방내역, 검사결과를 업로드하는 수동 입력 기능 제공
- 3단계: 건강정보 고속도로, 병원 파트너 API, 공식 FHIR 연동 경로 검토
- 4단계: 동적 동의, 제공 범위 선택, 철회, 접근 로그, 데이터 삭제 기능 적용

구현 범위:

- Patient
- Condition
- MedicationRequest
- Observation
- DiagnosticReport
- AllergyIntolerance
- DocumentReference

서비스 문구:

- 허용: “사용자가 동의한 건강 기록을 바탕으로 영양·복약 관리 참고 정보를 제공합니다.”
- 금지: “병원 기록을 분석해 질병을 진단합니다.”

### 3.2 처방전 이미지 분석

구현 가능성: 제한 범위에서 가능

처방전 이미지는 민감 건강정보이며, 약품명과 용법·용량이 포함된다. 따라서 공개 B2C에서는 “처방을 새로 만들거나 바꾸는 기능”이 아니라 “사용자가 보유한 처방 정보를 구조화하는 OCR 입력 기능”으로 제한한다.

구현 가능한 방식:

- 이미지 업로드
- OCR 추출
- 약품명, 용법, 용량, 횟수, 기간, 처방일자 구조화
- OCR confidence score 표시
- 사용자가 직접 수정 및 확인
- 복약 알림 생성
- 영양제 또는 식품과의 주의 가능성 안내
- 원본 이미지는 분석 후 기본 삭제

금지 범위:

- “이 약은 줄이세요”
- “복용량을 1정에서 2정으로 바꾸세요”
- “이 약 대신 다른 약을 드세요”
- “현재 처방이 잘못되었습니다”

서비스 문구:

- 허용: “처방전에 적힌 내용을 읽어 복약 알림으로 정리합니다.”
- 허용: “영양제와 함께 복용 전 전문가 상담이 필요할 수 있습니다.”
- 금지: “복용량을 변경하세요.”

### 3.3 검사표 이미지 분석

구현 가능성: 제한 범위에서 가능

검사표 이미지는 진단으로 이어지기 쉬운 민감 정보다. 따라서 앱은 검사명, 수치, 단위, 참고범위, 검사일자 추출과 추세 표시까지만 담당한다.

구현 가능한 방식:

- 이미지 업로드
- OCR 추출
- 검사명, 수치, 단위, 참고범위, 검사일자 구조화
- 단위 변환 및 값 검증
- 사용자가 직접 수정 및 확인
- 과거 입력값 대비 추세 표시
- 참고범위 이탈 시 의료기관 상담 권장

금지 범위:

- 검사 수치 기반 질병 진단
- 질병 확률 예측
- 치료 방향 제안
- 약 복용량 변경 제안

서비스 문구:

- 허용: “입력된 검사 수치가 참고범위 밖에 있어 의료기관 상담을 권장합니다.”
- 금지: “당뇨입니다.”
- 금지: “이 수치면 약을 늘려야 합니다.”

### 3.4 복용량 변경 안내

구현 가능성: 공개 B2C 단독 기능으로는 불가에 가깝고, 전문가 검토 워크플로가 있으면 제한적으로 가능

앱이 직접 복용량 변경을 지시하면 의료행위 또는 약사 업무 영역에 들어갈 가능성이 높다. 따라서 Lemon Aid의 일반 공개 기능에서는 복용량 변경을 결정하지 않는다.

구현 가능한 대체 방식:

- 사용자가 “약을 줄여도 되나요?”라고 물으면 직접 답변하지 않음
- 처방된 용량을 임의로 변경하지 말라고 안내
- 부작용 의심, 상호작용 가능성, 과다 섭취 가능성만 알림
- 의사 또는 약사 상담 CTA 제공
- 파트너 파일럿에서는 의료인/약사 검토 대기열로 전달

서비스 문구:

- 허용: “복용량 변경은 담당 의료진 또는 약사와 상담해야 합니다.”
- 허용: “현재 입력된 약과 영양제 조합은 전문가 상담이 필요할 수 있습니다.”
- 금지: “오늘부터 절반만 드세요.”

## 4. 구현 구조 변경안

### 4.1 기능 플래그

설정 파일에 다음 방향으로 반영했다.

- `hospital_data_integration_design_enabled`: true
- `healthway_fhir_integration_pilot_enabled`: false
- `manual_hospital_record_upload_enabled`: true
- `prescription_ocr_intake_enabled`: true
- `prescription_original_image_storage_enabled`: false
- `clinical_test_sheet_ocr_intake_enabled`: true
- `clinical_test_sheet_original_image_storage_enabled`: false
- `dosage_change_recommendation_enabled`: false
- `medication_safety_alert_enabled`: true
- `clinician_review_queue_enabled`: false

핵심은 “입력·구조화·알림”은 구현하고, “의료 결정”은 막는 것이다.

### 4.2 API 설계 방향

권장 endpoint:

- `POST /api/regulated-inputs/prescriptions/ocr`
- `POST /api/regulated-inputs/lab-results/ocr`
- `POST /api/health-records/manual-import`
- `POST /api/health-records/fhir/mock-import`
- `GET /api/health-records/timeline`
- `POST /api/medication-safety/check`
- `POST /api/professional-review/requests`

반드시 막아야 할 endpoint:

- `POST /api/medications/change-dose`
- `POST /api/diagnosis/predict`
- `POST /api/treatment/recommend`
- `POST /api/prescriptions/create`

### 4.3 DB 설계 방향

권장 table:

- `regulated_documents`
- `ocr_extraction_jobs`
- `prescription_items`
- `lab_result_items`
- `health_record_imports`
- `consent_records`
- `access_audit_logs`
- `medication_safety_alerts`
- `professional_review_requests`

원본 이미지는 기본 저장하지 않는다. 저장이 필요한 경우에는 별도 동의, 암호화, 보유기간, 삭제 정책을 명시해야 한다.

## 5. 최종 판단

| 기능 | 공개 B2C 구현 | 파트너/인허가 이후 구현 | 권장 상태 |
| --- | --- | --- | --- |
| 실제 병원 데이터 연동 | mock FHIR, 수동 업로드, 공식 API adapter 설계 | 건강정보 고속도로 또는 병원 파트너 API | 단계형 구현 |
| 처방전 이미지 분석 | OCR 추출, 사용자 확인, 복약 알림 | 약사/의사 검토, 약국 연계 | 제한 구현 |
| 검사표 이미지 분석 | OCR 추출, 수치·단위·추세 표시 | 의료인 해석, 진단 보조 기능 | 제한 구현 |
| 복용량 변경 안내 | 직접 안내 금지, 위험 알림과 상담 연결 | 의료인/약사 검토 워크플로 | 제한 또는 보류 |

따라서 상세 구현은 다음 원칙으로 진행한다.

1. 병원 데이터는 공식 연동을 전제로 하되, 지금은 mock FHIR와 수동 업로드부터 구현한다.
2. 처방전과 검사표는 OCR intake 기능으로 구현하되, 원본 저장과 의료 판단을 막는다.
3. 복용량 변경은 앱이 직접 결정하지 않고 전문가 상담 또는 검토 큐로 보낸다.
4. 모든 민감 건강정보는 별도 동의, 접근 로그, 삭제 기능, 보유기간 설정을 갖춘다.
5. AI는 설명 보조 역할만 하며, 의료 판단은 규칙, 출처, 전문가 검토 게이트를 통과해야 한다.
