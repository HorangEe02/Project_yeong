# MediWay Phase 4 — 확장 및 상용화 구현 가이드라인

> Claude Code를 활용한 단계별 구현 지침서
> 예상 기간: 6개월~ (지속 확장) | 난이도: ★★★★★

---

## 목차

1. [Phase 4 목표 및 범위](#1-phase-4-목표-및-범위)
2. [Phase 3 파일럿 결과 기반 진입 조건](#2-phase-3-파일럿-결과-기반-진입-조건)
3. [Track A — AR 네비게이션 고도화](#3-track-a--ar-네비게이션-고도화)
4. [Track B — 다병원 SaaS 플랫폼](#4-track-b--다병원-saas-플랫폼)
5. [Track C — 동선 데이터 분석 및 AI](#5-track-c--동선-데이터-분석-및-ai)
6. [Track D — 주차·결제·예약 연동](#6-track-d--주차결제예약-연동)
7. [Track E — 접근성 및 다국어](#7-track-e--접근성-및-다국어)
8. [Track F — Android 앱](#8-track-f--android-앱)
9. [시스템 아키텍처 — 최종 형태](#9-시스템-아키텍처--최종-형태)
10. [데이터 파이프라인 설계](#10-데이터-파이프라인-설계)
11. [비즈니스 모델 및 과금 설계](#11-비즈니스-모델-및-과금-설계)
12. [App Store 정식 배포](#12-app-store-정식-배포)
13. [보안 및 컴플라이언스 — 상용 수준](#13-보안-및-컴플라이언스--상용-수준)
14. [팀 빌딩 및 운영 체계](#14-팀-빌딩-및-운영-체계)
15. [타임라인 및 우선순위](#15-타임라인-및-우선순위)
16. [KPI 및 성과 측정](#16-kpi-및-성과-측정)
17. [장기 비전 — 타 시설 확장](#17-장기-비전--타-시설-확장)

---

## 1. Phase 4 목표 및 범위

### 1.1 핵심 목표

Phase 4는 MediWay를 **단일 병원 파일럿에서 상용 SaaS 플랫폼으로** 전환하는 단계입니다.
Phase 3의 검증 결과를 기반으로, 기술 고도화와 비즈니스 확장을 동시에 추진합니다.

```
목표 1: AR 네비게이션 실현 (Level 4)
  — ARKit 카메라 뷰에 3D 화살표 오버레이
  — LiDAR 사전 스캔 맵과 실시간 위치 매칭
  — "구글 맵 실내 AR 내비"와 유사한 경험

목표 2: 다병원 SaaS 전환
  — 멀티테넌시 아키텍처
  — 병원 셀프 온보딩 도구 (지도 업로드 → POI 등록 → 비콘 매핑)
  — 과금 체계 설계 및 적용

목표 3: 데이터 기반 가치 창출
  — 환자 동선 패턴 분석 대시보드
  — AI 최적 동선 추천
  — 혼잡도 실시간 예측

목표 4: 생태계 연동
  — 주차 정산 시스템 연동
  — 원무과 결제 연동
  — EMR/HIS 예약 시스템 → 자동 동선 생성
  — 나의건강기록 API 연계

목표 5: 시장 확장 기반 마련
  — App Store 정식 배포 (iOS)
  — Android 앱 출시
  — 다국어 지원 (영/중/일)
  — 접근성 강화 (시각장애, 휠체어)
```

### 1.2 6개 트랙 병렬 구조

```
Phase 4는 단일 선형 로드맵이 아닌 6개 트랙의 병렬 개발입니다.
각 트랙은 독립적으로 진행 가능하며, 우선순위에 따라 순차 또는 동시 착수합니다.

Track A: AR 네비게이션 고도화          ★★★★★  (기술 난이도 최고)
Track B: 다병원 SaaS 플랫폼            ★★★★☆  (비즈니스 핵심)
Track C: 동선 데이터 분석 및 AI        ★★★☆☆  (차별화 가치)
Track D: 주차·결제·예약 연동           ★★★☆☆  (병원 협업 필요)
Track E: 접근성 및 다국어              ★★☆☆☆  (사회적 가치)
Track F: Android 앱                    ★★★☆☆  (시장 확대)

권장 착수 순서:
  Phase 4a (Month 1~3): Track B + Track C (SaaS 기반 + 분석)
  Phase 4b (Month 3~6): Track A + Track E (AR + 접근성)
  Phase 4c (Month 4~8): Track D + Track F (연동 + Android)
```

### 1.3 네비게이션 레벨 최종 목표

```
Phase 3까지 달성:
  Level 1 ✅ — 정적 경로 안내
  Level 2 ✅ — 대략적 위치 감지
  Level 3 ✅ — BLE 실시간 블루닷 네비게이션

Phase 4에서 달성 목표:
  Level 4 ✅ — AR + 3D 네비게이션
    • ARKit 카메라 뷰에 3D 화살표/경로 오버레이
    • LiDAR 사전 스캔 맵 기반 위치 인식
    • Visual Inertial Odometry(VIO) 활용
    • 실내 3D 뷰 (Street View 유사)
```

---

## 2. Phase 3 파일럿 결과 기반 진입 조건

### 2.1 Phase 4 Go/No-Go 기준

```
Phase 4 착수를 위한 최소 조건:

필수 조건 (모두 충족):
  ✅ BLE 측위 정확도 평균 3m 이하 달성
  ✅ 앱 크래시율 1% 미만
  ✅ SUS 점수 65점 이상 (최소 "OK" 등급)
  ✅ 동선 완료율 80% 이상
  ✅ 이동 시간 단축률 15% 이상 (통계적 유의)

권장 조건 (2개 이상 충족):
  △ SUS 점수 75점 이상 ("Good" 등급)
  △ 이동 시간 단축률 25% 이상
  △ 환자 "재사용 의향" 80% 이상
  △ 의료진 "업무 도움" 긍정 평가 70% 이상
  △ 추가 병원 관심 표명 1곳 이상

중단 조건 (하나라도 해당):
  ❌ BLE 측위 정확도 평균 5m 초과
  ❌ 앱 크래시율 5% 초과
  ❌ SUS 점수 50점 미만
  ❌ 환자 참여 거부율 50% 이상
  ❌ 병원 측 파일럿 중도 중단 요청
```

### 2.2 파일럿 결과별 Phase 4 방향 조정

```
시나리오 1: 우수 결과 (권장 조건 3개 이상 충족)
  → 전체 Track 병렬 추진
  → 파일럿 병원을 첫 상용 고객으로 전환
  → 추가 병원 영업 즉시 시작

시나리오 2: 양호 결과 (필수 조건 충족, 권장 2개 미만)
  → Track B(SaaS) + Track C(분석) 우선 추진
  → Track A(AR)는 보류, BLE 측위 고도화에 집중
  → Phase 3 병원에서 확장 파일럿 지속

시나리오 3: 미흡 결과 (필수 조건 일부 미충족)
  → Phase 4 진입 보류
  → Phase 3 연장하여 핵심 문제 해결
  → BLE 측위 정확도 또는 UX 집중 개선
  → 3개월 후 재평가

시나리오 4: 부정적 결과 (중단 조건 해당)
  → 기술 방향 재검토 (BLE → UWB 전환 고려 등)
  → 대상 시설 변경 검토 (병원 → 대학 캠퍼스 등)
  → 피봇 또는 프로젝트 종료 판단
```

---

## 3. Track A — AR 네비게이션 고도화

### 3.1 목표 및 범위

```
목표:
  환자가 카메라를 들면 화면에 3D 화살표/경로가 표시되어
  직관적으로 목적지까지 이동할 수 있는 AR 네비게이션

구현 범위:
  ✅ ARKit 카메라 뷰에 3D 화살표 오버레이
  ✅ 바닥에 경로 선 렌더링 (AR)
  ✅ 목적지 방향 표시 (화살표 + 거리 라벨)
  ✅ 층 이동 시 AR → 2D 전환 (엘리베이터 안에서는 AR 불가)
  ✅ 사전 스캔 3D 맵 기반 위치 재인식 (ARWorldMap)
  ❌ 완전한 실시간 SLAM (너무 고비용, 사전 맵 방식 채택)

기술 핵심:
  ARKit의 ARWorldMap을 사전에 병원 구역별로 저장해두고,
  환자가 AR 모드를 켜면 현재 환경을 ARWorldMap과 매칭하여
  카메라의 정확한 위치/방향을 파악합니다.
```

### 3.2 AR 네비게이션 아키텍처

```
구성 요소:

1. AR Map Manager (사전 준비 단계)
   - 병원 구역별 ARWorldMap 생성 및 저장
   - 각 WorldMap에 앵커 포인트 배치 (POI 위치)
   - WorldMap → 서버 업로드 (또는 앱 번들)
   - 관리자 도구로 WorldMap 관리

2. AR Localizer (런타임)
   - 앱 시작 시 BLE로 대략적 위치 파악 → 해당 구역 WorldMap 로드
   - ARWorldMap relocalization으로 정밀 위치 인식
   - VIO (Visual Inertial Odometry)로 카메라 트래킹 유지

3. AR Renderer (시각화)
   - RealityKit으로 3D 화살표/경로 렌더링
   - 바닥 평면에 경로 선 그리기 (ARPlaneAnchor 활용)
   - 목적지 방향에 떠다니는 라벨 표시
   - 분기점에 회전 화살표 표시

4. AR Session Manager (세션 관리)
   - 2D 지도 ↔ AR 뷰 전환
   - AR 트래킹 상태 모니터링 (limited, normal, notAvailable)
   - 트래킹 불안정 시 2D 지도로 자동 폴백
   - 배터리 절약 모드 (AR 자동 해제)
```

### 3.3 ARWorldMap 기반 위치 인식

```swift
// Services/ARNavigationService.swift — 핵심 구조

import ARKit
import RealityKit

class ARNavigationService: NSObject, ObservableObject {
    private var arSession: ARSession?
    @Published var trackingState: ARCamera.TrackingState = .notAvailable
    @Published var isLocalized = false

    // 사전 저장된 WorldMap 로드
    func loadWorldMap(for zone: String) throws -> ARWorldMap {
        // 서버 또는 로컬에서 zone별 WorldMap 파일 로드
        let url = worldMapURL(for: zone)
        let data = try Data(contentsOf: url)
        let worldMap = try NSKeyedUnarchiver
            .unarchivedObject(ofClass: ARWorldMap.self, from: data)
        return worldMap!
    }

    // AR 세션 시작 (WorldMap으로 relocalization)
    func startARSession(worldMap: ARWorldMap) {
        let config = ARWorldTrackingConfiguration()
        config.initialWorldMap = worldMap
        config.planeDetection = [.horizontal]
        config.environmentTexturing = .automatic

        let session = ARSession()
        session.delegate = self
        session.run(config, options: [.resetTracking])
        self.arSession = session
    }

    // 경로 화살표 배치
    func placeRouteArrows(
        path: [Coordinate3D],
        in arView: ARView
    ) {
        // 경로 좌표를 AR 월드 좌표로 변환
        for i in 0..<path.count - 1 {
            let from = path[i].simdPosition
            let to = path[i + 1].simdPosition

            // 화살표 엔티티 생성
            let arrow = createArrowEntity(from: from, to: to)
            let anchor = AnchorEntity(world: from)
            anchor.addChild(arrow)
            arView.scene.addAnchor(anchor)
        }

        // 바닥 경로 선 렌더링
        let pathLine = createPathLineEntity(points: path.map { $0.simdPosition })
        let lineAnchor = AnchorEntity(world: .zero)
        lineAnchor.addChild(pathLine)
        arView.scene.addAnchor(lineAnchor)
    }

    private func createArrowEntity(
        from: SIMD3<Float>,
        to: SIMD3<Float>
    ) -> ModelEntity {
        // RealityKit으로 3D 화살표 생성
        let mesh = MeshResource.generateCone(height: 0.3, radius: 0.1)
        let material = SimpleMaterial(color: .systemBlue, isMetallic: false)
        let entity = ModelEntity(mesh: mesh, materials: [material])

        // 화살표 방향을 다음 경유지로 향하도록 회전
        let direction = normalize(to - from)
        entity.look(at: to, from: from, relativeTo: nil)

        return entity
    }
}

extension ARNavigationService: ARSessionDelegate {
    func session(_ session: ARSession, cameraDidChangeTrackingState camera: ARCamera) {
        trackingState = camera.trackingState
        if case .normal = camera.trackingState {
            isLocalized = true
        }
    }
}
```

### 3.4 ARWorldMap 생성 도구

```
병원 AR 맵 구축 프로세스:

1단계: 구역 분할
  - 병원을 8~15m 단위 구역으로 분할
  - 각 구역에 고유 ID 부여 (예: "2F-corridor-A", "2F-lobby")
  - 구역 간 오버랩 영역 확보 (2~3m)

2단계: WorldMap 캡처 (관리자 앱)
  - 관리자가 ARKit 앱으로 구역을 천천히 둘러보기 (약 2~3분/구역)
  - 특징점(feature points)이 충분히 수집되면 WorldMap 저장
  - 구역 내 POI 위치에 ARanchor 배치

3단계: WorldMap 서버 업로드
  - 각 구역의 WorldMap 파일 (수 MB~수십 MB)
  - 메타데이터: 구역 ID, 층, 포함 POI, 파일 크기

4단계: 클라이언트 다운로드 전략
  - BLE로 현재 구역 감지 → 해당 구역 WorldMap만 다운로드
  - 인접 구역 1~2개 미리 다운로드 (prefetch)
  - 총 다운로드량 최소화

WorldMap 한계:
  - 조명 변화에 민감 (낮/밤, 형광등 on/off)
  - 가구 배치 변경 시 재캡처 필요
  - 복도 같은 반복적 구조에서 인식률 저하
  - 해결: BLE 위치와 교차 검증, 정기적 맵 업데이트
```

### 3.5 AR 뷰 UI 설계

```
AR 네비게이션 화면 구성:

┌─────────────────────────────────────────┐
│  [카메라 뷰 — AR 오버레이]               │
│                                         │
│       ← 3D 화살표 (파란색, 반투명)        │
│                                         │
│    ═══════════ (바닥 경로 선, 파란 점선)   │
│                                         │
│       [채혈실 →]  (떠다니는 라벨)          │
│       23m                               │
│                                         │
│                                         │
├─────────────────────────────────────────┤
│  하단 카드:                              │
│  ┌───────────────────────────────────┐  │
│  │ ↗️  직진 23m → 오른쪽 채혈실       │  │
│  │    ━━━━━━━━░░░░  약 1분           │  │
│  └───────────────────────────────────┘  │
│                                         │
│  [🗺 2D 지도]  [📷 AR]  [도착]          │
└─────────────────────────────────────────┘

전환 동작:
  - "2D 지도" 탭 → 기존 2D 실내 지도 화면
  - "AR" 탭 → 카메라 AR 뷰 (현재 화면)
  - "도착" 탭 → 수동 도착 확인
  - 엘리베이터 진입 감지 → 자동으로 2D 전환 (AR 불가 구역)

AR 트래킹 상태 표시:
  정상: 상단에 "AR 네비게이션 활성" (초록 뱃지)
  제한: "AR 불안정 — 폰을 천천히 움직여주세요" (주황 뱃지)
  불가: 자동으로 2D 지도 전환 + "AR을 사용할 수 없는 구역입니다"
```

---

## 4. Track B — 다병원 SaaS 플랫폼

### 4.1 멀티테넌시 아키텍처

```
멀티테넌시 = 하나의 시스템으로 여러 병원을 독립적으로 서비스

데이터 격리 전략:

옵션 A: 단일 DB + 테넌트 컬럼 (권장)
  - 모든 병원 데이터를 하나의 DB에 저장
  - 각 테이블/컬렉션에 hospitalId 필드로 격리
  - 장점: 관리 단순, 비용 효율적
  - 단점: 쿼리마다 hospitalId 필터 필수
  - 적합: 초기 10~20개 병원 규모

옵션 B: 병원별 별도 DB (대규모 시)
  - 각 병원에 독립 Firebase 프로젝트 또는 DB 인스턴스
  - 장점: 완전한 격리, 병원별 백업/삭제 용이
  - 단점: 관리 복잡도 증가
  - 적합: 50개 이상 병원

Phase 4 초기에는 옵션 A를 채택하고,
병원 수 증가에 따라 옵션 B로 마이그레이션합니다.
```

### 4.2 병원 온보딩 셀프서비스 도구

```
병원이 스스로 MediWay를 설정할 수 있는 관리자 포털:

기능:

1. 병원 등록
   - 병원 기본 정보 입력 (이름, 주소, 건물 수)
   - 관리자 계정 생성
   - 서비스 약관 동의

2. 지도 업로드
   - 층별 평면도 이미지/SVG 업로드
   - 드래그앤드롭 업로더
   - 자동 크기 조정 및 viewBox 설정
   - 미리보기 기능

3. POI 등록 도구
   - 업로드된 평면도 위에 클릭하여 POI 마커 배치
   - POI 이름, 카테고리, 층 정보 입력
   - 일괄 CSV 업로드 옵션
   - POI 목록 편집 (수정/삭제)

4. 네비게이션 그래프 편집기
   - POI 간 통로(엣지) 클릭-드래그로 연결
   - 엣지 가중치(거리) 자동 계산 (좌표 기반)
   - 층 간 연결 설정 (엘리베이터/계단)
   - 경로 미리보기 및 검증

5. 비콘 매핑
   - 비콘 UUID/Major/Minor 일괄 등록
   - 평면도 위에 비콘 위치 배치
   - 캘리브레이션 데이터 업로드
   - 비콘 상태 모니터링

6. 동선 템플릿 관리
   - 진료과별 동선 템플릿 생성
   - 기존 POI에서 경유지 선택
   - 사용 빈도 통계

7. 의료진 계정 관리
   - 직원 계정 생성/비활성화
   - 진료과 배정
   - 권한 설정

기술 스택:
  - React + TypeScript + Tailwind
  - Recharts (통계 차트)
  - Konva.js 또는 Fabric.js (평면도 위 인터랙티브 편집)
  - API 서버와 통신
```

### 4.3 병원 온보딩 프로세스

```
셀프서비스 온보딩 플로우 (목표: 2~4주 내 서비스 시작):

Week 1: 초기 설정
  1. 관리자 포털 접속 → 병원 등록
  2. 서비스 약관 동의 및 개인정보 처리 방침 확인
  3. 관리자 계정 생성
  4. 건물/층 구조 입력

Week 2: 지도 및 POI
  5. 층별 평면도 업로드 (CAD → SVG 변환 가이드 제공)
  6. POI 마커 배치 (온라인 에디터)
  7. 네비게이션 그래프 연결

Week 3: 비콘 설치
  8. 비콘 하드웨어 수령 (택배 배송 또는 자체 구매)
  9. 비콘 설치 가이드에 따라 현장 설치
  10. 비콘 매핑 및 캘리브레이션 (캘리브레이션 앱 제공)
  11. 전체 구역 테스트

Week 4: 운영 시작
  12. 동선 템플릿 등록
  13. 의료진 계정 생성 및 교육 자료 제공
  14. 파일럿 테스트 (직원 대상)
  15. 정식 서비스 시작
```

---

## 5. Track C — 동선 데이터 분석 및 AI

### 5.1 분석 대시보드

```
병원 관리자를 위한 운영 인사이트 대시보드:

1. 실시간 현황
   - 현재 네비게이션 중인 환자 수
   - 구역별 체류 인원 히트맵 (층별)
   - 실시간 혼잡도 (색상: 녹→황→적)

2. 이동 분석
   - 구간별 평균 이동 시간 (실측 vs 예상)
   - 시간대별 이동량 그래프 (오전/오후 피크)
   - 가장 혼잡한 구간 TOP 5
   - 가장 긴 대기 발생 구간

3. 동선 패턴
   - 빈도 높은 동선 조합 (상키 다이어그램)
   - 진료과별 후속 방문 확률 (내과 → 채혈 80%, 영상 15%, 원무 5%)
   - 요일별/시간대별 진료과 방문 패턴

4. 서비스 품질
   - 동선 완료율 추이 (일별/주별)
   - 앱 사용 만족도 추이
   - 경로 이탈률
   - 수동 도착 vs 자동 도착 비율

5. 공간 최적화 제안
   - 병목 구간 식별 및 대안 경로 제안
   - 안내 표지판 추가 필요 지점
   - 비콘 음영 구역 식별
```

### 5.2 데이터 파이프라인

```
데이터 수집 → 익명화 → 저장 → 분석 파이프라인:

수집 (앱 → API):
  - 경유지 도착 이벤트 (waypointId, timestamp)
  - 구간 이동 시간 (fromPOI, toPOI, duration)
  - BLE 위치 로그 (x, y, floor, accuracy) — opt-in
  - 만족도 응답

익명화 (API 서버):
  - 세션 ID → SHA-256 해시
  - 타임스탬프 → 시간대 단위 절삭 (분/초 제거)
  - k-익명성 검증 (k ≥ 5)
  - 진료과 조합 → 일반화 (3개 이상 방문 시 세부 순서 제거)

저장:
  - BigQuery (Google Cloud) 또는 Firebase Firestore
  - 원본 이벤트 테이블 (분석용, 30일 보관)
  - 집계 테이블 (구간별 일별 통계, 영구 보관)

분석:
  - 배치 분석: 일 1회 집계 (Cloud Functions 스케줄)
  - 실시간 분석: 현재 혼잡도 (Realtime DB 업데이트)
```

### 5.3 AI 최적 동선 추천

```
기능: 과거 데이터를 기반으로 환자에게 최적의 방문 순서를 추천

문제 정의:
  환자가 [채혈, 영상의학, 원무과, 약국] 4곳을 방문해야 할 때,
  가장 빠르게 모두 방문할 수 있는 순서를 추천

접근 방식:

Level 1: 규칙 기반 (Phase 4 초기)
  - 현재 위치에서 가장 가까운 곳 먼저 (그리디 최근접)
  - 대기 시간이 긴 곳은 후순위
  - 원무과 → 약국 순서 강제 (의료 프로세스 제약)

Level 2: 데이터 기반 (Phase 4 중기)
  - 과거 이동 시간 데이터로 구간별 예상 시간 갱신
  - 시간대별 혼잡도 반영 (오전 채혈실 혼잡 → 영상 먼저)
  - TSP(Traveling Salesman Problem) 변형으로 최적 순서 계산

Level 3: ML 기반 (장기)
  - 환자 방문 패턴 클러스터링
  - 클러스터별 최적 동선 사전 계산
  - 실시간 혼잡도 예측 모델 (시계열)
  - 강화학습 기반 동적 경로 최적화

구현 (Level 1-2):
  Python + scikit-learn (분석 서버)
  또는 Swift (앱 내 경량 추론)

API:
  POST /api/ai/optimal-route
    Input: { hospitalId, startPOI, destinations: [poiId] }
    Output: { optimizedOrder: [poiId], estimatedTime, reasoning }
```

### 5.4 혼잡도 실시간 예측

```
혼잡도 = 특정 구역의 현재 체류 인원 추정

수집:
  - BLE 비콘에서 수신된 디바이스 수 (비콘이 스캔하는 게 아니라,
    앱이 비콘을 수신 → 서버에 위치 보고 → 구역별 인원 집계)
  - 실시간 활성 세션의 현재 위치

계산:
  - 구역별 현재 앱 사용자 수 카운트
  - 앱 미사용 환자 추정 (앱 사용자 × 보정 계수)
  - 혼잡도 등급: 여유(1~3명) / 보통(4~7명) / 혼잡(8명+)

표시:
  - 평면도 위 구역별 색상 오버레이 (녹→황→적)
  - "현재 채혈실 대기: 약 15분"
  - 동선 추천 시 혼잡 구역 회피
```

---

## 6. Track D — 주차·결제·예약 연동

### 6.1 주차 시스템 연동

```
주차 관련 기능 3단계:

Level 1: 수동 주차 위치 기록 (Phase 3에서 시작)
  - 환자가 주차 층/구역을 수동 입력
  - 진료 완료 후 주차 위치까지 네비게이션
  - 추가 인프라 불필요

Level 2: BLE 비콘 주차 위치 자동 감지
  - 주차장에도 BLE 비콘 설치
  - 주차 시 비콘 기반 자동 위치 기록
  - 출차 시 주차 위치까지 네비게이션

Level 3: 주차 관제 시스템 API 연동
  - 병원 주차 관제 시스템 API와 연동
  - 입차/출차 시간 자동 기록
  - 진료 시간 기반 주차 할인 자동 적용
  - 주차비 앱 내 결제 (간편결제 연동)

병원 주차 시스템 연동 대상:
  - 차량번호 인식(LPR) 시스템 API
  - 주차 정산기 API (REST 또는 SOAP)
  - 주차 할인 정책 API (진료 확인 → 할인 코드 발급)

주의사항:
  - 주차 시스템은 병원마다 벤더가 다름
  - API 연동은 병원 IT팀과 긴밀한 협의 필요
  - 개인정보(차량번호) 처리 추가 동의 필요
```

### 6.2 원무과 결제 연동

```
진료비 결제 관련 기능:

기능:
  - 원무과 도착 시 "결제 대기" 알림
  - 예상 진료비 표시 (병원 시스템 연동 시)
  - 간편결제로 앱 내 결제 (대기 없이)
  - 결제 완료 후 다음 동선(약국) 자동 전환

결제 연동 기술:
  - PG사 연동: 토스페이먼츠, NHN KCP, 나이스페이먼츠
  - 결제 모듈: 아임포트(포트원) SDK — 다중 PG 통합
  - Apple Pay 지원 (PassKit)
  - 인앱 결제가 아닌 PG 결제 (Apple 30% 수수료 회피)

EMR/HIS 연동:
  - 병원 EMR(전자의무기록) 또는 HIS(병원정보시스템)에서
    진료비 정보를 API로 조회
  - 연동 프로토콜: HL7 FHIR (표준), REST API (비표준)
  - 각 병원 EMR 벤더와 개별 연동 필요 (표준화 미흡)

현실적 접근:
  Phase 4 초기에는 결제 연동보다
  "원무과 도착 → 번호표 자동 발급" 같은 경량 연동부터 시작.
  결제 연동은 병원 IT 환경 확인 후 점진적 추진.
```

### 6.3 예약 시스템 → 자동 동선 생성

```
궁극적 자동화 시나리오:

  1. 환자가 병원 앱 또는 콜센터로 진료 예약
  2. EMR/HIS에 예약 정보 등록
  3. MediWay API가 예약 정보를 수신 (webhook 또는 폴링)
  4. 예약 내역 분석:
     - 예약 진료과: 내과
     - 사전 검사 필요: 채혈
     - 예상 동선 자동 생성: 접수 → 채혈 → 내과 → 원무과 → 약국
  5. 내원 당일 아침 푸시 알림:
     "오늘 내과 진료가 예약되어 있습니다.
      도착하시면 앱을 열어주세요."
  6. 병원 도착 → 앱 실행 → 자동으로 동선 표시

구현 요소:
  - EMR 예약 데이터 연동 API (병원별)
  - 진료과 → 필요 검사/절차 매핑 규칙 (간호사 협의)
  - 동선 자동 생성 엔진 (규칙 기반)
  - 예약 변경 시 동선 실시간 업데이트

주의: 이 기능은 병원 EMR 시스템과의 깊은 연동이 필요하며,
     병원별 EMR 벤더(유비케어, 인성정보, 이지케어텍 등)와
     개별 협의가 필요합니다.
     Phase 4 후반부 또는 Phase 5로 분류할 수도 있습니다.
```

---

## 7. Track E — 접근성 및 다국어

### 7.1 다국어 지원

```
지원 언어 (우선순위 순):
  1. 한국어 (기본)
  2. 영어
  3. 중국어 (간체)
  4. 일본어

구현:

iOS:
  - Localizable.strings 파일 언어별 작성
  - String Catalog (Xcode 15+ .xcstrings)
  - 앱 설정에서 언어 선택 (또는 시스템 언어 자동 감지)

웹:
  - react-intl 또는 i18next 라이브러리
  - JSON 번역 파일 관리

번역 대상:
  - 앱 UI 텍스트 (버튼, 라벨, 안내 문구)
  - 턴바이턴 안내 텍스트 ("Turn right in 10m")
  - 동선 완료 메시지
  - 푸시 알림 텍스트
  - 오류 메시지

번역하지 않는 항목:
  - 진료과 이름 (한국어 고유, 영문 병기)
  - 의사 이름
  - 병원 고유 명칭

POI 다국어:
  POI 모델에 localizedNames 필드 추가:
  {
    "name": "채혈실",
    "localizedNames": {
      "en": "Blood Collection Room",
      "zh": "采血室",
      "ja": "採血室"
    }
  }
```

### 7.2 접근성 강화

```
1. 시각장애인 — 음성 안내
  - VoiceOver 완전 지원 (모든 UI 요소에 accessibilityLabel)
  - 턴바이턴 안내를 TTS(Text-to-Speech)로 자동 읽기
  - AVSpeechSynthesizer 활용
  - 음성 안내 전용 모드 (지도 없이 음성만으로 네비게이션)
  - "10미터 앞에서 오른쪽으로 돌아가세요" 자동 음성 출력

2. 휠체어 사용자 — 배리어프리 경로
  - 네비게이션 그래프에 접근성 속성 추가:
    NavEdge에 wheelchair_accessible: Bool 필드
  - 계단 경로 제외, 엘리베이터/경사로 우선
  - 문 너비, 경사도 정보 추가 (고급)
  - 사용자 설정: "휠체어 경로 우선" 토글
  - Dijkstra에서 비접근 엣지 필터링 또는 가중치 증가

3. 고령자 — 큰 글씨/큰 버튼
  - Dynamic Type 완전 지원 (iOS 시스템 설정 연동)
  - 고대비 모드 (배경-전경 대비율 4.5:1 이상)
  - 최소 터치 영역 44×44pt (Apple HIG 준수)
  - 단순화 모드: 지도 없이 텍스트 + 화살표만 표시
  - "다음: 3층 채혈실 ↑" 대형 텍스트

4. 청각장애인
  - 모든 음성 안내에 텍스트 대안 제공 (기본 탑재)
  - 진동 패턴으로 방향 전환 알림
    좌회전: 짧-짧
    우회전: 긴-짧
    도착: 긴-긴-긴
```

### 7.3 나의건강기록 API 연계

```
나의건강기록 앱 (건강정보 고속도로):
  - 정부 제공 PHR(개인건강기록) 플랫폼
  - 1,004개 의료기관 진료기록 통합 조회
  - 투약정보, 진료이력, 건강검진, 예방접종 등 12종

MediWay와의 연계 가능성:
  1. 환자의 진료 예약 일정 조회 → 동선 자동 생성 보조
  2. 과거 방문 병원 정보 → 해당 병원 지도 자동 제안
  3. 투약 정보 → 약국 방문 필요 여부 자동 판단

기술 연동:
  - 건강정보 고속도로 API (FHIR 기반)
  - MyData 인증 (본인인증 + 동의 기반)
  - 연동 범위: 진료 예약 정보만 사용 (의료 데이터 비접촉 원칙 유지)

주의:
  - PHR 데이터 접근은 환자 명시적 동의 필수
  - MediWay는 PHR 데이터를 저장하지 않음 (실시간 조회만)
  - API 접근 권한 확보 절차 확인 필요 (정부 인가)
```

---

## 8. Track F — Android 앱

### 8.1 기술 스택 선택

```
옵션 A: Kotlin + Jetpack Compose (네이티브)
  장점: 최고 성능, 네이티브 API 직접 접근
  단점: iOS와 별도 코드베이스 유지
  AR 지원: ARCore

옵션 B: Kotlin Multiplatform (KMP, 공유 로직)
  장점: 비즈니스 로직(모델, 서비스) iOS와 공유
  단점: UI는 별도, 러닝 커브
  AR 지원: ARCore (플랫폼별 구현)

옵션 C: Flutter (크로스 플랫폼)
  장점: 단일 코드베이스로 iOS/Android 동시
  단점: 기존 iOS 코드 재작성 필요, AR 제약
  AR 지원: ar_flutter_plugin (제한적)

옵션 D: React Native (크로스 플랫폼)
  장점: Phase 1 웹 코드 일부 공유 가능
  단점: 네이티브 기능(AR, BLE) 브릿지 필요
  AR 지원: ViroReact (유지보수 불확실)

권장: 옵션 A (Kotlin + Jetpack Compose)
  이유:
  - AR 네비게이션에 ARCore 네이티브 접근 필수
  - BLE 비콘에 Android Bluetooth API 직접 접근
  - 병원 환경에서 성능과 안정성이 최우선
  - iOS 앱과 서버 API가 동일하므로 프론트엔드만 별도 구현
  - Jetpack Compose는 SwiftUI와 패러다임이 유사하여 전환 용이
```

### 8.2 Android 앱 구조

```
MediWay-Android/
├── app/src/main/
│   ├── java/com/mediway/
│   │   ├── MediWayApp.kt
│   │   ├── di/                          # Hilt DI
│   │   ├── model/                       # 데이터 모델 (iOS와 동일 구조)
│   │   ├── data/
│   │   │   ├── repository/              # Repository 패턴
│   │   │   ├── remote/                  # API 통신 (Retrofit)
│   │   │   └── local/                   # 로컬 캐시 (Room)
│   │   ├── service/
│   │   │   ├── AuthService.kt
│   │   │   ├── SessionService.kt
│   │   │   ├── PathfindingService.kt
│   │   │   ├── BeaconService.kt         # Android BLE
│   │   │   └── ARNavigationService.kt   # ARCore
│   │   ├── ui/
│   │   │   ├── patient/                 # Compose 화면
│   │   │   ├── staff/
│   │   │   ├── map/
│   │   │   ├── ar/
│   │   │   └── common/
│   │   └── util/
│   ├── res/
│   └── AndroidManifest.xml
├── build.gradle.kts
└── gradle/

핵심 라이브러리:
  - Jetpack Compose (UI)
  - Hilt (DI)
  - Retrofit + OkHttp (네트워킹)
  - Firebase Android SDK (Auth, Realtime DB, FCM)
  - Google ARCore (AR)
  - Android BLE API (비콘)
  - CameraX (QR 스캔)
  - ML Kit Barcode Scanning (QR 디코딩)
  - Room (로컬 캐시)
```

### 8.3 iOS → Android 기능 매핑

```
기능              iOS                          Android
────────────────────────────────────────────────────────────
QR 스캔          AVFoundation                  CameraX + ML Kit
QR 생성          CoreImage CIFilter            ZXing 라이브러리
실시간 통신       Firebase iOS SDK              Firebase Android SDK
인증             Firebase Auth (iOS)           Firebase Auth (Android)
푸시 알림         APNs + FCM                    FCM (네이티브)
실내 지도         커스텀 UIScrollView            커스텀 ComposeScrollable
경로 그리기       SwiftUI Path / CAShapeLayer    Compose Canvas / Path
BLE 비콘         CoreBluetooth / CLBeacon       Android BLE API
AR 네비게이션     ARKit + RealityKit             ARCore + Sceneform
3D 스캔          RoomPlan API                   ❌ (Android 대안 없음)
위치             CoreLocation                   FusedLocationProvider
기압계           CMAltimeter                    SensorManager (Pressure)
햅틱             UIImpactFeedbackGenerator       Vibrator
음성 안내         AVSpeechSynthesizer            TextToSpeech
```

---

## 9. 시스템 아키텍처 — 최종 형태

### 9.1 전체 아키텍처

```
┌─ Client Layer ──────────────────────────────────────────────────┐
│                                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐   │
│  │ iOS 앱   │  │ Android  │  │ 웹 앱    │  │ 관리자 포털   │   │
│  │ (환자)   │  │ 앱(환자) │  │ (환자)   │  │ (병원 관리)   │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └──────┬───────┘   │
│       └──────────────┴──────────────┴───────────────┘            │
│                              │                                   │
└──────────────────────────────┼───────────────────────────────────┘
                               │  HTTPS / WebSocket
                               ▼
┌─ API Gateway ───────────────────────────────────────────────────┐
│  Cloud Run / API Gateway                                        │
│  • Rate Limiting  • Auth Middleware  • Request Routing           │
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌─ Service Layer ──────────────┼──────────────────────────────────┐
│                              │                                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐   │
│  │ Session  │  │ Map      │  │ Push     │  │ Analytics    │   │
│  │ Service  │  │ Service  │  │ Service  │  │ Service      │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └──────┬───────┘   │
│       │              │              │               │            │
└───────┼──────────────┼──────────────┼───────────────┼────────────┘
        │              │              │               │
┌─ Data Layer ─────────┼──────────────┼───────────────┼────────────┐
│                      │              │               │            │
│  ┌──────────┐  ┌─────┴────┐  ┌─────┴────┐  ┌──────┴──────┐   │
│  │ Firebase │  │ Cloud    │  │ FCM /    │  │ BigQuery    │   │
│  │ RTDB     │  │ Storage  │  │ APNs    │  │ (분석)      │   │
│  │ (세션)   │  │ (지도)   │  │ (푸시)   │  │             │   │
│  └──────────┘  └──────────┘  └──────────┘  └─────────────┘   │
│                                                                │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ PostgreSQL / Firestore (병원 메타데이터, 계정, 설정)      │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

### 9.2 서비스 분리 전략

```
Phase 3: 모놀리식 Cloud Functions
Phase 4: 마이크로서비스 또는 모듈형 모놀리스

Phase 4 초기 (10개 병원 이하): 모듈형 모놀리스
  - 단일 Cloud Run 서비스에 모듈화된 코드
  - Session 모듈, Map 모듈, Push 모듈, Analytics 모듈
  - 장점: 배포/관리 단순, 모듈 간 호출 빠름

Phase 4 후기 (10개 병원 이상): 마이크로서비스 전환
  - Session Service: 세션 생성/관리
  - Map Service: 지도 데이터 서빙/캐싱
  - Push Service: 알림 발송 큐
  - Analytics Service: 데이터 수집/분석
  - 각 서비스 독립 배포, 독립 스케일링

전환 기준:
  모놀리스 유지: 개발자 1~2명, 병원 10개 이하
  마이크로서비스: 개발자 3명 이상, 병원 10개 이상
```

---

## 10. 데이터 파이프라인 설계

### 10.1 실시간 파이프라인

```
앱 → API → Realtime DB → 클라이언트 (기존 세션 플로우)
앱 → API → Pub/Sub → Cloud Functions → BigQuery (분석 이벤트)

실시간 혼잡도:
  1. 앱이 30초마다 현재 위치(구역)를 API에 보고
  2. API가 구역별 카운터 업데이트 (Realtime DB)
  3. 관리자 대시보드가 Realtime DB 구독 → 히트맵 갱신
  4. 환자 앱도 혼잡도 참조 (동선 추천 시)
```

### 10.2 배치 파이프라인

```
일별 집계:
  Cloud Scheduler (00:00) → Cloud Functions → BigQuery 쿼리
  → 집계 테이블 업데이트 → 대시보드 데이터 갱신

집계 항목:
  - 구간별 일평균 이동 시간
  - 시간대별 구역 체류 인원 (히스토그램)
  - 동선 패턴 빈도 (상위 20개)
  - 서비스 지표 (완료율, 만족도, 오류율)

데이터 보관:
  - 원본 이벤트: 30일
  - 일별 집계: 1년
  - 월별 집계: 영구
  - 개인 식별 가능 데이터: 즉시 삭제 (수집 안 함)
```

---

## 11. 비즈니스 모델 및 과금 설계

### 11.1 과금 모델 옵션

```
옵션 A: 비콘 수 기반 월정액
  비콘 50개 이하: ₩500,000/월
  비콘 100개 이하: ₩900,000/월
  비콘 200개 이하: ₩1,500,000/월
  비콘 200개 초과: 별도 협의

옵션 B: 월 활성 세션 수 기반
  세션 1,000건 이하: ₩300,000/월
  세션 5,000건 이하: ₩800,000/월
  세션 10,000건 이하: ₩1,500,000/월

옵션 C: 하이브리드 (기본료 + 사용량)
  기본료: ₩300,000/월 (비콘 50개, 세션 1,000건 포함)
  추가 비콘: ₩5,000/개/월
  추가 세션: ₩100/건

권장: 옵션 C (하이브리드)
  이유: 소규모 병원의 진입 장벽을 낮추면서,
       대규모 병원에서 적절한 수익 확보

추가 수익원:
  - 병원 온보딩 서비스 (유료): CAD 변환 + 비콘 설치 대행
  - 데이터 분석 프리미엄 리포트
  - AR 맵 구축 서비스 (LiDAR 스캔 대행)
  - 연동 API 커스터마이징
```

### 11.2 무료 티어 (Free Tier)

```
신규 병원 확보를 위한 무료 체험:

무료 제공:
  - 비콘 20개 이하
  - 월 세션 500건 이하
  - 1개 건물, 2개 층 이하
  - 기본 분석 대시보드
  - 기간: 3개월

제한:
  - AR 네비게이션 미제공
  - AI 동선 추천 미제공
  - 프리미엄 분석 리포트 미제공
  - 기술 지원: 이메일만

전환 전략:
  무료 기간 종료 1개월 전 → 사용 통계 리포트 발송
  "이 기간 동안 MediWay를 통해 환자 이동 시간이 X% 단축되었습니다.
   유료 플랜으로 전환하시면 AR 네비게이션, AI 추천 등을 이용하실 수 있습니다."
```

---

## 12. App Store 정식 배포

### 12.1 App Store 심사 준비

```
Apple App Store 심사 체크리스트:

메타데이터:
  □ 앱 이름: MediWay — 병원 내비게이션
  □ 카테고리: Medical (의료)
  □ 부제: 병원 내 동선 안내
  □ 스크린샷: iPhone 6.7", 6.5", 5.5" 각 최소 3장
  □ 앱 설명 (한국어/영어)
  □ 개인정보 처리 방침 URL
  □ 지원 URL
  □ 연령 등급: 4+ (의료 정보 미포함)

기술 요구:
  □ iOS 16.0+ 최소 지원
  □ IPv6 네트워크 호환
  □ App Transport Security (HTTPS)
  □ 최신 Xcode로 빌드

심사 포인트:
  □ 카메라 권한 사용 목적 명시 (QR 스캔, AR)
  □ 위치 권한 사용 목적 명시 (실내 네비게이션)
  □ Bluetooth 권한 사용 목적 명시 (BLE 비콘)
  □ Background Modes 정당성 설명
  □ 개인정보 수집 질문 응답 (App Privacy 라벨)
  □ 로그인/인증 방식 설명 (익명 + 직원 코드)
  □ 데모 계정 제공 (심사자용)

Medical 카테고리 특이사항:
  □ 이 앱은 의료 정보를 제공하지 않음 (네비게이션만) 명시
  □ 의료 기기 해당 여부: 비해당 (길 안내 앱)
  □ HIPAA/의료법 관련 Disclaimer (필요 시)
```

### 12.2 Google Play Store 배포

```
Google Play Store 체크리스트:

  □ 개발자 등록비: $25 (1회)
  □ 앱 서명 키 생성 (Google Play App Signing)
  □ 스크린샷: 최소 2장 (Phone), 태블릿 선택
  □ 기능 그래픽: 1024×500 배너
  □ 앱 설명 (한국어/영어)
  □ 개인정보 처리 방침
  □ 데이터 보안 양식 작성 (Data Safety)
  □ 내부 테스트 트랙 → 비공개 테스트 → 프로덕션

Android 특수 고려:
  □ Android 12+ 블루투스 권한 (BLUETOOTH_SCAN, BLUETOOTH_CONNECT)
  □ 정확한 위치 권한 (ACCESS_FINE_LOCATION) 정당성
  □ 백그라운드 위치 접근 정당성 (Play 정책 강화)
  □ ARCore 필수 여부 설정 (uses-feature android.hardware.camera.ar)
```

---

## 13. 보안 및 컴플라이언스 — 상용 수준

### 13.1 보안 강화 항목

```
Phase 3 대비 Phase 4 보안 강화:

1. API 보안
   □ OAuth 2.0 / JWT 기반 인증 표준화
   □ Rate Limiting (IP별, 계정별)
   □ API 키 관리 (병원별 API 키 발급)
   □ CORS 정책 강화 (허용 도메인 화이트리스트)
   □ SQL Injection / XSS 방어 (입력 검증)

2. 데이터 암호화
   □ 저장 시 암호화: AES-256 (서버 측)
   □ 전송 시 암호화: TLS 1.3
   □ Certificate Pinning (iOS/Android)
   □ 비콘 UUID 주기적 회전 (비인가 추적 방지)

3. 접근 통제
   □ RBAC (Role-Based Access Control)
     - Super Admin: MediWay 관리자
     - Hospital Admin: 병원 관리자
     - Staff: 의료진
     - Patient: 환자 (최소 권한)
   □ 병원별 데이터 격리 검증
   □ 관리자 2FA (Two-Factor Authentication)

4. 감사 로그
   □ 관리자 행동 로그 (설정 변경, 계정 관리)
   □ API 접근 로그 (누가 어떤 데이터에 접근했는지)
   □ 로그 보관: 1년
   □ 로그 접근: Super Admin만

5. 침해 대응
   □ 보안 사고 대응 매뉴얼 작성
   □ 데이터 유출 시 통지 절차 (72시간 이내, GDPR 기준)
   □ 정기 취약점 점검 (분기 1회)
```

### 13.2 의료 소프트웨어 규제

```
MediWay가 의료기기에 해당하는지:

판단 기준 (식약처 디지털 헬스케어 가이드라인):
  - 질병의 진단, 치료, 예방에 사용? → NO
  - 환자의 건강 상태를 모니터링? → NO
  - 의료 데이터를 분석하여 의사결정 지원? → NO

MediWay의 기능:
  - 병원 내 길 안내 (네비게이션)
  - 시설 이용 안내 ("원무과 3층으로 이동하세요")

결론: 의료기기 비해당
  → 식약처 인허가 불필요
  → 다만, "의료" 앱 카테고리이므로 면책 고지 포함 권장

면책 고지 문구:
  "MediWay는 병원 내 이동 경로 안내를 위한 앱이며,
   의료 진단, 치료, 처방에 관한 정보를 제공하지 않습니다.
   의료 관련 문의는 담당 의료진에게 문의하세요."
```

---

## 14. 팀 빌딩 및 운영 체계

### 14.1 Phase 4 팀 구성 (이상적)

```
Phase 1~3: 1인 개발
Phase 4: 확장에 따라 팀 구성 필요

최소 팀 (Phase 4 초기):
  - iOS 개발자 1명 (본인)
  - 웹/백엔드 개발자 1명
  - 총 2명

이상적 팀 (Phase 4 중후기):
  - PM/기획 1명
  - iOS 개발 1명
  - Android 개발 1명
  - 백엔드/인프라 1명
  - 프론트엔드(관리자 포털) 1명
  - 디자이너 1명 (UX/UI)
  - 데이터 분석 1명
  - 총 7명

채용 우선순위:
  1순위: 백엔드/인프라 (SaaS 기반 구축)
  2순위: Android 개발 (시장 확대)
  3순위: 디자이너 (상용 품질 UI/UX)
  4순위: 데이터 분석 (Track C)
```

### 14.2 운영 체계

```
개발 프로세스:
  - 2주 스프린트 (Scrum)
  - GitHub Flow (feature branch → PR → review → merge)
  - CI/CD: GitHub Actions → TestFlight / Play Internal Testing
  - 코드 리뷰: 1명 이상 승인 필수

커뮤니케이션:
  - Slack (일상 소통)
  - Notion (문서, 로드맵, 이슈 트래킹)
  - 주간 스탠드업 (15분)
  - 스프린트 리뷰/회고 (격주)

품질 관리:
  - 단위 테스트 커버리지 목표: 70%
  - 크래시율 목표: 0.5% 미만
  - API 응답 시간 목표: p99 < 500ms
  - 앱 사이즈 목표: 50MB 이하
```

---

## 15. 타임라인 및 우선순위

### 15.1 Phase 4 로드맵

```
Phase 4a: Month 1~3 (기반 구축)
  ─────────────────────────────────────────
  [Track B] 멀티테넌시 아키텍처 구현
  [Track B] 관리자 포털 v1 (병원 등록, 지도 업로드, POI)
  [Track C] 분석 파이프라인 구축 (BigQuery)
  [Track C] 운영 대시보드 v1 (기본 통계)
  [공통]    API 서버 리팩토링 (Cloud Functions → Cloud Run)

Phase 4b: Month 3~6 (기능 고도화)
  ─────────────────────────────────────────
  [Track A] ARWorldMap 생성 도구 개발
  [Track A] AR 네비게이션 v1 (화살표 오버레이)
  [Track E] 다국어 지원 (영/중/일)
  [Track E] 접근성 강화 (VoiceOver, 휠체어 경로)
  [Track B] 관리자 포털 v2 (비콘 매핑, 동선 편집)
  [공통]    App Store 정식 배포

Phase 4c: Month 4~8 (시장 확대)
  ─────────────────────────────────────────
  [Track F] Android 앱 개발 (Kotlin + Compose)
  [Track D] 주차 위치 BLE 자동 감지
  [Track C] AI 최적 동선 추천 (Level 1~2)
  [Track C] 혼잡도 실시간 예측
  [Track D] 원무과 결제 연동 (시범)
  [Track F] Google Play Store 배포

Phase 4d: Month 6~12+ (확장)
  ─────────────────────────────────────────
  [Track A] AR 네비게이션 v2 (바닥 경로, 실내 3D 뷰)
  [Track D] EMR 예약 → 자동 동선 생성
  [Track E] 나의건강기록 API 연계
  [Track B] 2~5번째 병원 온보딩
  [공통]    비즈니스 모델 검증 및 최적화
  [공통]    타 시설 확장 가능성 검토
```

---

## 16. KPI 및 성과 측정

### 16.1 핵심 KPI

```
비즈니스 KPI:
  - 서비스 도입 병원 수: 3개 (6개월 목표), 10개 (12개월 목표)
  - 월간 활성 세션 수 (MAS): 1,000+ (병원당)
  - 월간 활성 사용자 수 (MAU): 500+ (병원당)
  - 병원 이탈률: 10% 미만

사용자 KPI:
  - 동선 완료율: 90% 이상
  - 이동 시간 단축률: 30% 이상 (vs 미사용)
  - SUS 점수: 75점 이상 ("Good")
  - NPS (Net Promoter Score): +30 이상

기술 KPI:
  - 앱 크래시율: 0.5% 미만
  - API p99 응답 시간: 500ms 미만
  - BLE 측위 정확도: 평균 2m 이하
  - 앱 설치 → 첫 사용 전환율: 70% 이상
  - AR relocalization 성공률: 80% 이상

재무 KPI:
  - MRR (Monthly Recurring Revenue): 목표 ₩3,000,000 (12개월)
  - CAC (Customer Acquisition Cost): 병원당 < ₩1,000,000
  - Payback Period: 6개월 이내
```

---

## 17. 장기 비전 — 타 시설 확장

### 17.1 확장 가능 시설

```
MediWay의 핵심 가치(실내 네비게이션 + 동선 안내)는
병원 외 복잡한 실내 환경에도 적용 가능합니다.

1순위 확장 대상:
  - 대학 캠퍼스: 신입생/방문자 건물 찾기
  - 대형 쇼핑몰: 매장 찾기, 주차 위치
  - 공항: 탑승구, 라운지, 면세점 네비게이션

2순위 확장 대상:
  - 전시장/컨벤션센터: 부스 찾기
  - 정부 청사: 민원 동선 안내
  - 대형 오피스 빌딩: 방문자 안내

확장 시 고려:
  - 병원 특화 기능(동선 전송, 진료 완료)은 범용 모듈과 분리
  - 도메인별 모듈: MediWay-Hospital, MediWay-Campus, MediWay-Mall
  - 코어 엔진 공유: BLE 측위, 경로 탐색, AR 네비게이션, 지도 렌더링
  - 도메인별 커스텀: UI 테마, 용어, 동선 로직, 연동 시스템
```

### 17.2 플랫폼화 전략

```
장기 비전: MediWay → 범용 실내 네비게이션 플랫폼

단계:
  1단계: 병원 전용 (현재~Phase 4)
  2단계: 의료 시설 확대 (요양원, 재활원)
  3단계: 교육/공공 시설 (대학, 관공서)
  4단계: 상업 시설 (쇼핑몰, 공항)
  5단계: SDK/API 제공 (타사 앱에 MediWay 엔진 내장)

SDK 제공 시:
  - MediWaySDK for iOS / Android
  - API: 지도 데이터, 경로 탐색, BLE 측위, AR 네비게이션
  - 커스터마이징: UI 테마, 도메인 로직
  - 과금: API 호출 수 기반

이 비전의 가치:
  병원에서 검증된 정밀 실내 네비게이션 기술을
  범용 플랫폼으로 확장하여, "실내의 구글 맵"을 목표로 합니다.
```

---

## 부록: Claude Code 사용 팁

### 프롬프트 예시 — AR 네비게이션

```
"ARKit ARWorldMap을 이용해 사전 스캔된 3D 맵에서 
현재 위치를 인식하고, RealityKit으로 바닥에 경로 선과 
방향 화살표를 AR 오버레이하는 ARNavigationService를 구현해줘.
BLE 위치와 ARWorldMap relocalization을 결합하는 구조로."
```

### 프롬프트 예시 — 관리자 포털

```
"React + Tailwind + Konva.js로 병원 관리자 포털을 만들어줘.
기능: 평면도 이미지 업로드, 이미지 위 클릭하여 POI 배치,
POI 간 드래그로 네비게이션 엣지 연결, 비콘 위치 마커 배치.
REST API 연동으로 데이터 저장."
```

### 프롬프트 예시 — 동선 분석 대시보드

```
"React + Recharts로 동선 분석 대시보드를 만들어줘.
구역별 체류 인원 히트맵, 시간대별 이동량 라인 차트,
빈도 높은 동선 패턴 상키 다이어그램,
구간별 평균 이동 시간 바 차트를 포함해."
```

### 프롬프트 예시 — Android 앱 기초

```
"Kotlin + Jetpack Compose + Hilt로 MediWay Android 앱의
기본 프로젝트를 생성해줘. Firebase SDK(Auth, Realtime DB, FCM) 연동,
CameraX + ML Kit으로 QR 스캔, Compose Canvas로 실내 지도 경로 그리기,
Android BLE API로 iBeacon 수신을 포함하는 구조로."
```

### 프롬프트 예시 — AI 동선 추천

```
"Python으로 환자 동선 최적화 엔진을 구현해줘.
입력: 현재 위치, 방문 필요 POI 목록, 구간별 이동 시간, 구간별 혼잡도.
출력: 총 소요 시간을 최소화하는 방문 순서.
의료 프로세스 제약(원무과→약국 순서 고정 등)을 반영하고,
혼잡도를 가중치로 적용하는 TSP 변형 알고리즘으로 구현해."
```

---

> **이 가이드라인은 Phase 4 확장 및 상용화의 전체 청사진입니다.**
> Phase 4는 6개 트랙의 병렬 개발이므로, 비즈니스 우선순위에 따라
> 트랙 착수 순서와 깊이를 조절하세요.
> Phase 3 파일럿 결과가 Phase 4의 방향을 결정하는 핵심 입력이며,
> Go/No-Go 기준을 반드시 사전에 합의하세요.
> 궁극적으로 MediWay는 병원을 넘어 "실내의 구글 맵"을 지향합니다.
