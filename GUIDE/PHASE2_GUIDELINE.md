# MediWay Phase 2 — iOS 앱 MVP 구현 가이드라인

> Claude Code를 활용한 단계별 구현 지침서
> 예상 기간: 8~12주 (3개월) | 난이도: ★★★☆☆

---

## 목차

1. [Phase 2 목표 및 범위](#1-phase-2-목표-및-범위)
2. [Phase 1 대비 변경점 및 확장점](#2-phase-1-대비-변경점-및-확장점)
3. [기술 스택 및 의존성](#3-기술-스택-및-의존성)
4. [개발 환경 요구사항](#4-개발-환경-요구사항)
5. [프로젝트 구조](#5-프로젝트-구조)
6. [Month 1: SwiftUI 네이티브 앱 — Phase 1 기능 이식](#6-month-1-swiftui-네이티브-앱--phase-1-기능-이식)
7. [Month 2: ARKit + RoomPlan 3D 스캔 프로토타입](#7-month-2-arkit--roomplan-3d-스캔-프로토타입)
8. [Month 3: CoreBluetooth BLE 비콘 프로토타입 및 UI 고도화](#8-month-3-corebluetooth-ble-비콘-프로토타입-및-ui-고도화)
9. [데이터 모델 — Swift 구현](#9-데이터-모델--swift-구현)
10. [Firebase iOS SDK 연동](#10-firebase-ios-sdk-연동)
11. [실내 지도 — 네이티브 구현](#11-실내-지도--네이티브-구현)
12. [경로 탐색 알고리즘 — Swift 이식](#12-경로-탐색-알고리즘--swift-이식)
13. [ARKit 3D 스캔 상세 가이드](#13-arkit-3d-스캔-상세-가이드)
14. [BLE 비콘 측위 상세 가이드](#14-ble-비콘-측위-상세-가이드)
15. [보안 및 권한 관리](#15-보안-및-권한-관리)
16. [테스트 전략](#16-테스트-전략)
17. [빌드 및 배포](#17-빌드-및-배포)
18. [Phase 3 연계 고려사항](#18-phase-3-연계-고려사항)

---

## 1. Phase 2 목표 및 범위

### 1.1 핵심 목표

Phase 2는 Phase 1의 웹 데모를 **SwiftUI 네이티브 iOS 앱**으로 이식하면서, 웹에서는 불가능했던 **디바이스 네이티브 기능**(카메라 AR, BLE, LiDAR)을 활용한 프로토타입을 추가하는 단계입니다.

세 가지 핵심 목표가 있습니다.

```
목표 1: Phase 1 기능 완전 이식
  — 의료진 앱, 환자 앱의 모든 기능을 iOS 네이티브로 구현

목표 2: ARKit + RoomPlan 3D 스캔 프로토타입
  — iPhone LiDAR를 이용해 실내 공간을 3D로 캡처
  — 경북대 캠퍼스 건물에서 실제 테스트

목표 3: BLE 비콘 기반 실내 측위 프로토타입
  — CoreBluetooth로 비콘 신호를 수신하여 위치 추정
  — 실시간 블루닷 네비게이션의 기초 구현
```

### 1.2 구현 범위 (In-Scope)

```
Month 1 — 네이티브 앱 이식:
  ✅ 환자 앱: QR 표시, 동선 수신, 2D 실내 지도, 경로 표시, 도착 확인
  ✅ 의료진 앱: QR 스캔, 동선 템플릿 선택, 커스텀 경로, 전송
  ✅ Firebase 연동: Anonymous Auth, Realtime DB, FCM → APNs
  ✅ 네이티브 QR 스캔 (AVFoundation)
  ✅ 네이티브 푸시 알림 (APNs + FCM)
  ✅ 2D 실내 지도 (커스텀 UIScrollView 또는 MapKit 오버레이)

Month 2 — 3D 스캔 프로토타입:
  ✅ RoomPlan API로 방/복도 3D 구조 캡처
  ✅ ARKit LiDAR Point Cloud 수집
  ✅ USDZ/OBJ 내보내기 및 뷰어
  ✅ 스캔 데이터 → 2D 평면도 변환 프로토타입
  ✅ 경북대 캠퍼스 건물 실제 스캔 테스트

Month 3 — BLE 비콘 프로토타입:
  ✅ CoreBluetooth iBeacon 수신
  ✅ RSSI 기반 거리 추정 (삼변측량)
  ✅ 칼만 필터로 위치 노이즈 제거
  ✅ 실시간 블루닷 지도 위 표시
  ✅ UI 고도화 및 애니메이션 개선
```

### 1.3 구현 범위 밖 (Out-of-Scope)

```
  ❌ 턴바이턴 음성 안내 (Phase 3)
  ❌ AR 카메라 뷰 화살표 오버레이 네비게이션 (Phase 4)
  ❌ 실제 병원 데이터 연동 (Phase 3)
  ❌ 주차 위치 기록 및 정산
  ❌ Android 앱
  ❌ 다국어 지원
  ❌ App Store 배포 (TestFlight까지만)
  ❌ Wi-Fi 핑거프린팅 (CoreLocation의 기본 Wi-Fi 측위만 사용)
```

### 1.4 네비게이션 레벨 목표

```
Phase 1에서 달성: Level 1 — 정적 경로 안내

Phase 2에서 달성 목표:
  Level 1 유지 — 정적 경로 안내 (네이티브 지도 위)
  Level 2 시작 — 대략적 위치 감지 (CoreLocation 기본 + BLE 프로토타입)
  Level 3 준비 — BLE 비콘 프로토타입 (제한된 공간에서)

Phase 2 종료 시점:
  - 네이티브 앱에서 Phase 1의 모든 기능이 동작
  - LiDAR로 실내 공간 스캔 → 3D 모델 확보 가능
  - BLE 비콘 3~4개 환경에서 1~3m 정확도 위치 추정 가능
```

---

## 2. Phase 1 대비 변경점 및 확장점

### 2.1 기능 매핑 — Phase 1(웹) → Phase 2(iOS)

```
기능                    Phase 1 (웹)              Phase 2 (iOS)
───────────────────────────────────────────────────────────────
QR 코드 생성            qrcode.react              CoreImage CIFilter
QR 코드 스캔            html5-qrcode              AVFoundation AVCaptureSession
실시간 통신             Firebase JS SDK           Firebase iOS SDK
인증                    Firebase Auth (JS)        Firebase Auth (iOS)
푸시 알림               FCM + Service Worker      APNs + FCM iOS SDK
실내 지도               Leaflet.js + SVG          커스텀 MapView (UIScrollView)
경로 표시               Leaflet Polyline          Core Graphics / SwiftUI Path
상태 관리               Zustand                   @Observable (Swift 5.9+)
라우팅                  React Router              NavigationStack (SwiftUI)
데이터 모델             TypeScript interfaces     Swift structs + Codable
경로 탐색               pathfinding.ts            Pathfinding.swift (동일 알고리즘)
```

### 2.2 Phase 2에서 새로 추가되는 기능

```
기능                    기술                       설명
───────────────────────────────────────────────────────────────
3D 실내 스캔            RoomPlan API              방 단위 3D 구조 자동 캡처
Point Cloud 수집        ARKit LiDAR               밀집 포인트 클라우드 생성
3D 모델 내보내기        ModelIO / SceneKit        USDZ, OBJ 포맷 내보내기
BLE 비콘 수신           CoreBluetooth             iBeacon RSSI 수신
위치 추정               삼변측량 알고리즘          3+ 비콘 RSSI → 좌표 계산
노이즈 필터             칼만 필터                  RSSI 변동 평활화
실시간 블루닷           Core Animation            지도 위 현재 위치 표시
햅틱 피드백             UIImpactFeedbackGenerator  도착 시 진동 피드백
```

### 2.3 Firebase 백엔드 공유

```
Phase 1과 Phase 2는 동일한 Firebase 프로젝트를 공유합니다.

공유 리소스:
  ✅ Firebase Realtime Database (동일한 세션/QR 토큰 구조)
  ✅ Firebase Authentication (익명 인증 — iOS에서도 동일)
  ✅ Firebase Cloud Messaging (iOS 앱 등록 추가)

추가 설정:
  ⚠️ Firebase 프로젝트에 iOS 앱 등록
  ⚠️ GoogleService-Info.plist 다운로드
  ⚠️ APNs 인증 키 업로드 (FCM → APNs 연동)
  ⚠️ Realtime DB 보안 규칙은 변경 불필요 (auth.uid 기반)

호환성:
  웹(Phase 1) 의료진 → iOS(Phase 2) 환자: 동작해야 함
  iOS(Phase 2) 의료진 → 웹(Phase 1) 환자: 동작해야 함
  iOS(Phase 2) 의료진 → iOS(Phase 2) 환자: 동작해야 함
```

---

## 3. 기술 스택 및 의존성

### 3.1 핵심 기술 스택

```
영역              기술                      최소 버전
─────────────────────────────────────────────────────
언어              Swift                     5.9+
UI 프레임워크      SwiftUI                   iOS 17+
앱 아키텍처       MVVM + @Observable         Swift 5.9 Observation
네비게이션        NavigationStack            iOS 16+
비동기 처리       Swift Concurrency          async/await, Actor
네트워킹          URLSession + Combine       기본 포함
Firebase          Firebase iOS SDK           10.x
QR 스캔           AVFoundation               기본 포함
QR 생성           CoreImage (CIQRCodeGenerator) 기본 포함
3D 스캔           ARKit + RoomPlan           iOS 16+, LiDAR 필수
BLE               CoreBluetooth              기본 포함
위치              CoreLocation               기본 포함
푸시 알림          UserNotifications + APNs   기본 포함
3D 렌더링         SceneKit / RealityKit      기본 포함
테스트            XCTest + XCUITest          기본 포함
```

### 3.2 Swift Package Dependencies

```swift
// Package.swift 또는 Xcode SPM 설정

dependencies: [
    // Firebase iOS SDK
    .package(url: "https://github.com/firebase/firebase-ios-sdk.git", from: "10.19.0"),
]

// 사용할 Firebase 제품
targets: [
    .target(
        name: "MediWay",
        dependencies: [
            .product(name: "FirebaseAuth", package: "firebase-ios-sdk"),
            .product(name: "FirebaseDatabase", package: "firebase-ios-sdk"),
            .product(name: "FirebaseMessaging", package: "firebase-ios-sdk"),
        ]
    )
]
```

### 3.3 추가 고려 라이브러리

```
라이브러리          용도                      필수 여부
─────────────────────────────────────────────────────
없음 (자체 구현)    실내 지도 뷰              필수 (커스텀)
없음 (자체 구현)    칼만 필터                 Month 3
없음 (자체 구현)    Dijkstra 경로 탐색        필수
없음 (자체 구현)    삼변측량                  Month 3

Phase 2는 가능한 한 Apple 기본 프레임워크만 사용하여
외부 의존성을 최소화합니다. Firebase iOS SDK가 유일한 외부 의존성입니다.
```

---

## 4. 개발 환경 요구사항

### 4.1 하드웨어

```
필수:
  □ Mac (Apple Silicon 또는 Intel) — Xcode 실행용
  □ iPhone (iOS 16+) — 실기기 테스트 필수

LiDAR 스캔 (Month 2):
  □ iPhone 12 Pro 이상 (LiDAR 탑재 모델)
    - iPhone 12 Pro / Pro Max
    - iPhone 13 Pro / Pro Max
    - iPhone 14 Pro / Pro Max
    - iPhone 15 Pro / Pro Max
    - iPad Pro (2020 이후)

BLE 비콘 (Month 3):
  □ BLE 비콘 3~4개 (다음 중 택 1)
    - Estimote Proximity Beacons (추천, 개발자 키트)
    - Kontakt.io Beacon Pro
    - Raspberry Pi 4 + BLE 모듈 (저비용 대안)
    - 또는 추가 iPhone을 비콘 에뮬레이터로 활용
```

### 4.2 소프트웨어

```
필수:
  □ macOS Sonoma 14.0+ (또는 최신)
  □ Xcode 15.0+ (Swift 5.9, iOS 17 SDK)
  □ Apple Developer Account (무료도 가능, 실기기 설치용)
      → TestFlight 배포 시 유료 계정 필요 ($99/년)
  □ CocoaPods 또는 SPM (Firebase 설치용, SPM 권장)

권장:
  □ SF Symbols 앱 (아이콘 탐색)
  □ Reality Composer (3D 모델 미리보기)
  □ Instruments (성능 프로파일링)
  □ Charles Proxy (네트워크 디버깅)
```

### 4.3 Firebase iOS 설정 순서

```
1. Firebase Console → 프로젝트 설정 → 앱 추가 → iOS
2. Bundle ID 입력: com.mediway.app
3. GoogleService-Info.plist 다운로드 → Xcode 프로젝트에 추가
4. SPM으로 Firebase SDK 추가 (Auth, Database, Messaging)
5. AppDelegate에서 FirebaseApp.configure() 호출
6. APNs 설정:
   a. Apple Developer → Keys → APNs 인증 키 생성
   b. Firebase Console → Cloud Messaging → APNs 인증 키 업로드
   c. Xcode → Signing & Capabilities → Push Notifications 추가
   d. Xcode → Signing & Capabilities → Background Modes → Remote Notifications
```

---

## 5. 프로젝트 구조

### 5.1 Xcode 프로젝트 구조

```
MediWay/
├── MediWay.xcodeproj
├── MediWayApp.swift                    # @main 앱 진입점
├── GoogleService-Info.plist            # Firebase 설정 (Git 제외)
├── Info.plist                          # 앱 설정
│
├── Config/
│   ├── FirebaseConfig.swift            # Firebase 초기화
│   └── AppConstants.swift              # 상수 정의
│
├── Models/
│   ├── Hospital.swift                  # Hospital, Building, Floor, POI
│   ├── Session.swift                   # Session, Waypoint
│   ├── Navigation.swift                # NavEdge, NavigationGraph, PathResult
│   ├── RouteTemplate.swift             # 동선 템플릿
│   └── BeaconData.swift                # BLE 비콘 데이터 (Month 3)
│
├── Data/
│   ├── DemoHospital.swift              # 가상 병원 시드 데이터
│   ├── DemoRouteTemplates.swift        # 동선 템플릿 시드 데이터
│   └── DemoNavigationGraph.swift       # 네비게이션 그래프 시드 데이터
│
├── Services/
│   ├── AuthService.swift               # Firebase Anonymous Auth
│   ├── SessionService.swift            # 세션 CRUD (Realtime DB)
│   ├── NotificationService.swift       # APNs + FCM 푸시
│   ├── PathfindingService.swift        # Dijkstra 최단 경로
│   ├── QRService.swift                 # QR 생성 및 스캔
│   ├── RoomScanService.swift           # RoomPlan 3D 스캔 (Month 2)
│   └── BeaconService.swift             # BLE 비콘 측위 (Month 3)
│
├── ViewModels/
│   ├── PatientViewModel.swift          # 환자 화면 상태 관리
│   ├── StaffViewModel.swift            # 의료진 화면 상태 관리
│   ├── MapViewModel.swift              # 지도 상태 관리
│   ├── ScanViewModel.swift             # 3D 스캔 상태 관리 (Month 2)
│   └── BeaconViewModel.swift           # BLE 상태 관리 (Month 3)
│
├── Views/
│   ├── Launch/
│   │   └── RoleSelectionView.swift     # 역할 선택 (의료진/환자)
│   │
│   ├── Patient/
│   │   ├── PatientMainView.swift       # 환자 메인 (탭 컨테이너)
│   │   ├── QRDisplayView.swift         # QR 코드 표시
│   │   ├── NavigationGuideView.swift   # 동선 안내 메인 화면
│   │   ├── DestinationCardView.swift   # 다음 목적지 카드
│   │   ├── RouteProgressView.swift     # 동선 진행률 바
│   │   ├── ArrivalConfirmView.swift    # 도착 확인 시트
│   │   └── CompletionView.swift        # 모든 동선 완료 화면
│   │
│   ├── Staff/
│   │   ├── StaffMainView.swift         # 의료진 메인 화면
│   │   ├── QRScannerView.swift         # QR 스캐너 (AVFoundation)
│   │   ├── RouteTemplateListView.swift # 동선 템플릿 목록
│   │   ├── RouteBuilderView.swift      # 커스텀 동선 편집기
│   │   └── SendConfirmView.swift       # 전송 확인 시트
│   │
│   ├── Map/
│   │   ├── IndoorMapView.swift         # 실내 지도 컨테이너
│   │   ├── FloorPlanView.swift         # SVG/이미지 평면도 렌더링
│   │   ├── PathOverlayView.swift       # 경로 오버레이
│   │   ├── POIMarkerView.swift         # POI 마커
│   │   ├── BlueDotView.swift           # 현재 위치 블루닷 (Month 3)
│   │   └── FloorSelectorView.swift     # 층 선택 탭
│   │
│   ├── Scan/                           # Month 2
│   │   ├── RoomScanView.swift          # RoomPlan 스캔 화면
│   │   ├── ScanResultView.swift        # 스캔 결과 3D 뷰어
│   │   └── ScanExportView.swift        # USDZ/OBJ 내보내기
│   │
│   └── Common/
│       ├── LoadingView.swift           # 로딩 인디케이터
│       ├── ToastView.swift             # 토스트 알림
│       └── ErrorView.swift             # 에러 표시
│
├── Utilities/
│   ├── CoordinateConverter.swift       # SVG ↔ 뷰 좌표 변환
│   ├── KalmanFilter.swift              # 칼만 필터 (Month 3)
│   ├── Trilateration.swift             # 삼변측량 (Month 3)
│   └── HapticManager.swift             # 햅틱 피드백 관리
│
├── Extensions/
│   ├── Color+MediWay.swift             # 앱 컬러 팔레트
│   ├── View+Toast.swift                # 토스트 수정자
│   └── Date+Formatting.swift           # 날짜 포맷
│
├── Resources/
│   ├── Assets.xcassets/                # 앱 아이콘, 이미지
│   ├── HospitalMaps/                   # 병원 평면도 이미지/SVG
│   │   ├── demo-hospital-1F.svg
│   │   ├── demo-hospital-2F.svg
│   │   ├── demo-hospital-3F.svg
│   │   └── demo-hospital-4F.svg
│   └── Localizable.strings             # (향후 다국어)
│
├── Preview Content/
│   └── PreviewData.swift               # SwiftUI 프리뷰용 목 데이터
│
└── Tests/
    ├── MediWayTests/
    │   ├── PathfindingTests.swift       # 경로 탐색 단위 테스트
    │   ├── SessionServiceTests.swift    # 세션 서비스 테스트
    │   ├── TrilaterationTests.swift     # 삼변측량 테스트
    │   └── KalmanFilterTests.swift      # 칼만 필터 테스트
    └── MediWayUITests/
        └── NavigationFlowTests.swift   # UI 통합 테스트
```

---

## 6. Month 1: SwiftUI 네이티브 앱 — Phase 1 기능 이식

### 6.1 Task 목록

```
M1-W1: 프로젝트 셋업 및 기본 구조
  □ Xcode 프로젝트 생성 (MediWay, iOS 17+, SwiftUI)
  □ Firebase iOS SDK SPM 추가 (Auth, Database, Messaging)
  □ GoogleService-Info.plist 설정
  □ 디렉토리 구조 생성
  □ AppConstants, Color+MediWay 작성
  □ NavigationStack 기반 라우팅 설정
  □ RoleSelectionView 구현 (의료진/환자 선택)
  □ Firebase Anonymous Auth 연동 테스트

M1-W2: 데이터 모델 및 서비스 이식
  □ Swift 데이터 모델 작성 (Hospital, Session, Navigation 등)
  □ 가상 병원 시드 데이터 Swift로 변환
  □ 동선 템플릿 시드 데이터 Swift로 변환
  □ 네비게이션 그래프 시드 데이터 Swift로 변환
  □ AuthService 구현 (signInAnonymously)
  □ SessionService 구현 (Realtime DB CRUD)
  □ PathfindingService 구현 (Dijkstra 알고리즘 Swift 이식)
  □ QRService 구현 (CIQRCodeGenerator, AVCaptureSession)

M1-W3: 의료진 앱 UI
  □ StaffMainView — 상태 머신 기반 메인 화면
  □ QRScannerView — AVFoundation 카메라 QR 스캔
  □ RouteTemplateListView — 동선 템플릿 카드 목록
  □ RouteBuilderView — POI 검색 + 순서 편집
  □ SendConfirmView — 전송 확인 시트
  □ StaffViewModel — 전체 상태 관리
  □ 세션 생성 → Realtime DB 쓰기 → 전송 완료 토스트

M1-W4: 환자 앱 UI + 실내 지도
  □ QRDisplayView — CoreImage QR 코드 생성 및 표시
  □ IndoorMapView — 커스텀 ScrollView + 줌/팬
  □ FloorPlanView — 평면도 이미지 렌더링
  □ PathOverlayView — SwiftUI Path로 경로 그리기
  □ POIMarkerView — 마커 아이콘 + 라벨
  □ FloorSelectorView — 층 선택 Picker
  □ DestinationCardView — 다음 목적지 정보
  □ RouteProgressView — 진행률 바
  □ ArrivalConfirmView — "도착" 확인 버튼
  □ CompletionView — 완료 화면
  □ PatientViewModel — 세션 실시간 구독 + 상태 관리
  □ 동선 수신 → 지도 경로 표시 → 도착 → 다음 경유지 전환

M1-W4 (병행): 푸시 알림
  □ APNs 설정 (Capabilities, Entitlements)
  □ NotificationService — FCM 토큰 획득, 푸시 수신 처리
  □ AppDelegate에서 UNUserNotificationCenter 설정
  □ 포그라운드/백그라운드 알림 처리
  □ 동선 전송/전환/완료 시 알림 발송 테스트
```

### 6.2 QR 스캔 — AVFoundation 구현 가이드

```swift
// QRScannerView 구현 구조

// 1. UIViewControllerRepresentable로 AVCaptureSession 래핑
struct QRScannerView: UIViewControllerRepresentable {
    var onScanResult: (String) -> Void

    func makeUIViewController(context: Context) -> QRScannerController {
        let controller = QRScannerController()
        controller.onScanResult = onScanResult
        return controller
    }
}

// 2. UIViewController에서 카메라 세션 관리
class QRScannerController: UIViewController, AVCaptureMetadataOutputObjectsDelegate {
    var captureSession: AVCaptureSession?
    var onScanResult: ((String) -> Void)?

    // viewDidLoad:
    //   - AVCaptureDevice.default(.builtInWideAngleCamera, for: .video)
    //   - AVCaptureDeviceInput 생성
    //   - AVCaptureMetadataOutput 설정 (metadataObjectTypes: [.qr])
    //   - AVCaptureVideoPreviewLayer 표시
    //   - captureSession.startRunning()

    // metadataOutput 델리게이트:
    //   - QR 인식 시 onScanResult 콜백 호출
    //   - 중복 스캔 방지 (첫 인식 후 세션 일시 중지)

    // 권한 처리:
    //   - AVCaptureDevice.authorizationStatus(for: .video)
    //   - .notDetermined → requestAccess
    //   - .denied → 설정 앱 열기 안내
}

// 3. Info.plist 필수 키:
//   NSCameraUsageDescription: "QR 코드를 스캔하여 환자를 연결합니다"
```

### 6.3 QR 코드 생성 — CoreImage 구현 가이드

```swift
// QRService.swift

func generateQRCode(from string: String) -> UIImage? {
    let data = string.data(using: .utf8)
    guard let filter = CIFilter(name: "CIQRCodeGenerator") else { return nil }
    filter.setValue(data, forKey: "inputMessage")
    filter.setValue("M", forKey: "inputCorrectionLevel")  // 중간 오류 보정

    guard let ciImage = filter.outputImage else { return nil }

    // QR 코드 이미지 확대 (기본 크기가 매우 작음)
    let transform = CGAffineTransform(scaleX: 10, y: 10)
    let scaledImage = ciImage.transformed(by: transform)

    let context = CIContext()
    guard let cgImage = context.createCGImage(scaledImage, from: scaledImage.extent) else {
        return nil
    }
    return UIImage(cgImage: cgImage)
}
```

### 6.4 실내 지도 — 네이티브 구현 전략

```
Phase 1에서 Leaflet.js를 사용했던 실내 지도를
iOS에서는 두 가지 방식으로 구현할 수 있습니다.

방식 A: 커스텀 ScrollView (권장)
  - UIScrollView(또는 SwiftUI ScrollView) 위에 이미지/SVG 표시
  - 줌(pinch), 팬(drag) 기본 지원
  - Core Graphics로 경로 오버레이 그리기
  - 장점: 완전한 제어, 가벼움
  - 단점: 직접 구현해야 할 것이 많음

방식 B: MapKit 커스텀 오버레이
  - MKMapView에 커스텀 MKOverlay 추가
  - MKTileOverlay로 평면도 타일 서빙
  - MKPolyline으로 경로 표시
  - 장점: MapKit 인프라 활용
  - 단점: 비지리적 좌표계 사용이 까다로움

권장: 방식 A (커스텀 ScrollView)
  이유: 실내 지도는 GPS 좌표가 아닌 픽셀 좌표를 사용하므로,
       MapKit의 지리 좌표계를 우회하는 것보다
       ScrollView 위에 직접 그리는 것이 더 단순합니다.

구현 구조:
  IndoorMapView (SwiftUI)
    └── ZoomableScrollView (UIViewRepresentable, UIScrollView)
        ├── FloorPlanImageView (평면도 이미지)
        ├── PathOverlayLayer (경로 CAShapeLayer)
        ├── POIAnnotations (마커 서브뷰)
        └── BlueDotLayer (현재 위치, Month 3)
```

### 6.5 Firebase Realtime DB — iOS 리스너

```swift
// SessionService.swift — 세션 실시간 구독

import FirebaseDatabase

class SessionService {
    private let dbRef = Database.database().reference()
    private var sessionHandle: DatabaseHandle?

    /// 세션 실시간 구독 시작
    func observeSession(sessionId: String) -> AsyncStream<Session> {
        AsyncStream { continuation in
            let ref = dbRef.child("sessions").child(sessionId)
            let handle = ref.observe(.value) { snapshot in
                guard let dict = snapshot.value as? [String: Any],
                      let session = Session(from: dict) else {
                    return
                }
                continuation.yield(session)
            }
            self.sessionHandle = handle

            continuation.onTermination = { _ in
                ref.removeObserver(withHandle: handle)
            }
        }
    }

    /// QR 토큰 상태 관찰 (환자 → 매칭 대기)
    func observeQRToken(token: String) -> AsyncStream<QRTokenStatus> {
        AsyncStream { continuation in
            let ref = dbRef.child("qr_tokens").child(token).child("status")
            let handle = ref.observe(.value) { snapshot in
                guard let statusString = snapshot.value as? String,
                      let status = QRTokenStatus(rawValue: statusString) else {
                    return
                }
                continuation.yield(status)
            }
            continuation.onTermination = { _ in
                ref.removeObserver(withHandle: handle)
            }
        }
    }

    /// 세션 생성 (의료진이 호출)
    func createSession(_ session: Session) async throws {
        let ref = dbRef.child("sessions").child(session.sessionId)
        try await ref.setValue(session.toDictionary())
    }

    /// 도착 확인 (환자가 호출)
    func confirmArrival(sessionId: String, waypointIndex: Int) async throws {
        let ref = dbRef.child("sessions").child(sessionId)
        try await ref.updateChildValues([
            "waypoints/\(waypointIndex)/status": "completed",
            "waypoints/\(waypointIndex)/arrivedAt": ServerValue.timestamp(),
            "currentWaypointIndex": waypointIndex + 1,
        ])
    }
}
```

---

## 7. Month 2: ARKit + RoomPlan 3D 스캔 프로토타입

### 7.1 Task 목록

```
M2-W1: RoomPlan API 기본 구현
  □ RoomPlan 프레임워크 import 및 기능 확인
  □ RoomCaptureView 래핑 (UIViewRepresentable)
  □ RoomCaptureSession 설정 및 시작/중지
  □ RoomCaptureSessionDelegate 구현
  □ 캡처 결과 (CapturedRoom) 처리
  □ 기본 스캔 UI (시작/중지/저장 버튼)
  □ 실기기 테스트 (자신의 방 또는 교실)

M2-W2: 스캔 결과 처리 및 내보내기
  □ CapturedRoom → 3D 뷰어 (SceneKit 또는 RealityKit)
  □ USDZ 포맷 내보내기 (ModelIO)
  □ OBJ 포맷 내보내기 (옵션)
  □ 스캔 결과 목록 관리 (로컬 저장)
  □ 스캔 메타데이터 (위치 태그, 건물/층 정보)

M2-W3: 2D 평면도 변환 프로토타입
  □ CapturedRoom의 벽/문/창 데이터 → 2D 투영
  □ 3D 좌표 (x, y, z) → 2D 평면 좌표 (x, z) 변환
  □ 벽 윤곽선 추출 → SVG 또는 이미지 생성
  □ POI 자동 추출 시도 (문 위치 → 출입구 POI)
  □ 수동 POI 배치 UI (평면도 위 탭하여 POI 추가)

M2-W4: 현장 스캔 테스트
  □ 경북대 캠퍼스 건물 스캔 (접근 가능한 건물 선정)
  □ 복도, 로비, 개별 방 각각 스캔
  □ 스캔 품질 평가 (벽 인식률, 가구 오류 등)
  □ 여러 방 스캔 → 합치기 가능성 검토
  □ 스캔 결과 → 네비게이션 그래프 수동 연결 테스트
  □ 테스트 결과 문서화 (장단점, 한계)
```

### 7.2 RoomPlan API 핵심 구조

```swift
// RoomScanService.swift

import RoomPlan

@Observable
class RoomScanService: NSObject {
    var capturedRoom: CapturedRoom?
    var isScanning = false
    var scanError: Error?

    private var captureSession: RoomCaptureSession?

    /// LiDAR 지원 여부 확인
    static var isSupported: Bool {
        RoomCaptureSession.isSupported
    }

    /// 스캔 시작
    func startScan() {
        let session = RoomCaptureSession()
        session.delegate = self  // RoomCaptureSessionDelegate
        let config = RoomCaptureSession.Configuration()
        session.run(configuration: config)
        self.captureSession = session
        self.isScanning = true
    }

    /// 스캔 중지 및 결과 처리
    func stopScan() {
        captureSession?.stop()
        isScanning = false
    }

    /// USDZ 내보내기
    func exportUSDZ(room: CapturedRoom, to url: URL) throws {
        let exporter = RoomCaptureSession.USDZExporter()
        // ModelIO를 사용하여 USDZ 변환
        // ...
    }
}

extension RoomScanService: RoomCaptureSessionDelegate {
    func captureSession(
        _ session: RoomCaptureSession,
        didUpdate room: CapturedRoom
    ) {
        // 실시간 업데이트 (스캔 진행 중)
        self.capturedRoom = room
    }

    func captureSession(
        _ session: RoomCaptureSession,
        didEndWith data: CapturedRoomData,
        error: Error?
    ) {
        // 스캔 완료
        if let error {
            self.scanError = error
            return
        }
        // 최종 CapturedRoom 처리
        let finalRoom = try? CapturedRoom(from: data)
        self.capturedRoom = finalRoom
    }
}
```

### 7.3 CapturedRoom 데이터 구조

```
CapturedRoom이 제공하는 주요 데이터:

walls: [CapturedRoom.Surface]
  각 벽의 3D 치수 (dimensions), 변환 행렬 (transform)
  → 벽의 위치, 크기, 방향 파악 가능

doors: [CapturedRoom.Surface]
  문의 위치와 크기
  → 출입구 POI 자동 생성의 기초

windows: [CapturedRoom.Surface]
  창문 위치
  → 외벽 식별에 활용

objects: [CapturedRoom.Object]
  가구 등 인식된 객체 (table, chair, bed 등)
  → 병원 환경에서는 대기 의자, 접수 데스크 등

2D 평면도 변환 로직:
  1. walls 배열에서 각 벽의 transform.position 추출
  2. y축(높이) 제거 → (x, z) 2D 좌표로 투영
  3. 벽의 dimensions.x(너비)와 방향(rotation)으로 선분 생성
  4. 모든 벽 선분을 연결하여 방 윤곽선 구성
  5. doors 위치에 POI 앵커 포인트 자동 배치
```

### 7.4 3D → 2D 변환 핵심 알고리즘

```swift
// Utilities/FloorPlanExtractor.swift

struct FloorPlanExtractor {

    struct Wall2D {
        let start: CGPoint
        let end: CGPoint
        let thickness: CGFloat
    }

    struct DoorMarker {
        let position: CGPoint
        let width: CGFloat
    }

    /// CapturedRoom → 2D 평면도 데이터 변환
    static func extract(from room: CapturedRoom) -> FloorPlanData {
        var walls: [Wall2D] = []
        var doors: [DoorMarker] = []

        for surface in room.walls {
            let transform = surface.transform
            let width = surface.dimensions.x
            let position = CGPoint(
                x: CGFloat(transform.columns.3.x),
                y: CGFloat(transform.columns.3.z)  // z축 → 2D y축
            )
            // transform의 회전 행렬에서 방향(angle) 추출
            let angle = atan2(
                CGFloat(transform.columns.0.z),
                CGFloat(transform.columns.0.x)
            )
            let halfWidth = CGFloat(width) / 2
            let start = CGPoint(
                x: position.x - halfWidth * cos(angle),
                y: position.y - halfWidth * sin(angle)
            )
            let end = CGPoint(
                x: position.x + halfWidth * cos(angle),
                y: position.y + halfWidth * sin(angle)
            )
            walls.append(Wall2D(start: start, end: end, thickness: 0.15))
        }

        for surface in room.doors {
            let transform = surface.transform
            let pos = CGPoint(
                x: CGFloat(transform.columns.3.x),
                y: CGFloat(transform.columns.3.z)
            )
            doors.append(DoorMarker(
                position: pos,
                width: CGFloat(surface.dimensions.x)
            ))
        }

        return FloorPlanData(walls: walls, doors: doors)
    }
}
```

### 7.5 테스트 계획 — 경북대 캠퍼스

```
스캔 대상 후보 (접근 용이한 건물):

1순위: 학과 건물 (통계학과 소속 건물)
  - 1~2개 층 복도 + 교실 3~4개
  - 장점: 접근 자유, 반복 테스트 가능
  - 예상 시간: 층당 30~60분

2순위: 중앙도서관
  - 로비 + 열람실
  - 장점: 넓은 오픈 공간 테스트
  - 주의: 이용자 방해 최소화

3순위: 학생회관 / 편의시설
  - 식당, 매점 등 다양한 구조
  - 장점: 병원 내 편의시설과 유사한 구조

스캔 결과 평가 지표:
  □ 벽 인식 정확도 (실측 vs 스캔 오차)
  □ 문/출입구 인식률
  □ 긴 복도 스캔 품질 (드리프트 여부)
  □ 유리벽/유리문 인식 여부
  □ 스캔 소요 시간
  □ 파일 크기 (USDZ 기준)
```

---

## 8. Month 3: CoreBluetooth BLE 비콘 프로토타입 및 UI 고도화

### 8.1 Task 목록

```
M3-W1: BLE 비콘 기본 수신
  □ CoreBluetooth 프레임워크 설정
  □ Info.plist 권한 추가 (Bluetooth, Location)
  □ CBCentralManager 또는 CLLocationManager (iBeacon) 설정
  □ 비콘 스캔 시작/중지
  □ RSSI 값 실시간 수신 로깅
  □ 비콘 UUID/Major/Minor 식별
  □ 실기기 테스트 (비콘 1개 → 신호 강도 확인)

M3-W2: 삼변측량 위치 추정
  □ RSSI → 거리 변환 공식 구현
      distance = 10 ^ ((txPower - RSSI) / (10 * n))
  □ 삼변측량(trilateration) 알고리즘 구현
  □ 칼만 필터로 RSSI 노이즈 평활화
  □ 비콘 3~4개 배치 후 위치 추정 테스트
  □ 추정 정확도 측정 (실제 위치 vs 추정 위치)

M3-W3: 블루닷 + 지도 통합
  □ BlueDotView — 현재 위치 마커 (펄스 애니메이션)
  □ 추정 위치 → 지도 좌표 변환
  □ 실시간 블루닷 업데이트 (0.5초 간격)
  □ 위치 정확도 반경 표시 (파란 원)
  □ 경로 위 "현재 진행 구간" 하이라이트
  □ 도착 자동 감지 프로토타입
      (현재 위치가 목적지 POI 반경 3m 이내 → 도착 제안)

M3-W4: UI 고도화 및 마무리
  □ 전체 앱 애니메이션 개선
      - 화면 전환 트랜지션
      - 경로 그리기 애니메이션
      - 카드 표시/숨김 애니메이션
  □ 다크 모드 지원
  □ Dynamic Type (텍스트 크기 접근성)
  □ VoiceOver 기본 지원
  □ 햅틱 피드백 (도착 확인, 층 이동 시)
  □ 에러 상태 UI 정리
  □ 전체 앱 통합 테스트
  □ TestFlight 배포 준비
```

### 8.2 iBeacon 수신 — 두 가지 방식

```
방식 A: CLLocationManager (iBeacon 모니터링) — 권장
  장점: Apple의 공식 iBeacon API, 백그라운드 지원
  단점: 비콘이 iBeacon 프로토콜을 지원해야 함

  구현:
    let manager = CLLocationManager()
    let region = CLBeaconRegion(
        uuid: UUID(uuidString: "MEDIWAY-BEACON-UUID")!,
        identifier: "mediway-beacons"
    )
    manager.startMonitoring(for: region)
    manager.startRangingBeacons(satisfying: region.beaconIdentityConstraint)

    // 델리게이트:
    func locationManager(_ manager: CLLocationManager,
                         didRange beacons: [CLBeacon],
                         satisfying: CLBeaconIdentityConstraint) {
        for beacon in beacons {
            let major = beacon.major.intValue   // 층 번호 등
            let minor = beacon.minor.intValue   // 비콘 고유 ID
            let rssi = beacon.rssi              // 신호 강도
            let accuracy = beacon.accuracy      // Apple 추정 거리 (m)
            // → 삼변측량 입력으로 사용
        }
    }


방식 B: CBCentralManager (범용 BLE 스캔)
  장점: iBeacon 아닌 일반 BLE 장치도 스캔 가능
  단점: 백그라운드 제한, 더 많은 코드 필요

  구현:
    let central = CBCentralManager()
    central.scanForPeripherals(
        withServices: nil,
        options: [CBCentralManagerScanOptionAllowDuplicatesKey: true]
    )
    // RSSI 포함 디스커버리 콜백에서 처리


권장: 방식 A (CLLocationManager)
  이유: Apple의 iBeacon은 RSSI뿐 아니라 accuracy(추정 거리)도
       제공하므로, 삼변측량의 입력 품질이 더 높습니다.
       비콘 하드웨어도 iBeacon 호환 제품을 선택합니다.
```

### 8.3 RSSI → 거리 변환

```swift
// Utilities/Trilateration.swift

struct RSSIDistanceConverter {
    /// RSSI 값을 거리(미터)로 변환
    /// - Parameters:
    ///   - rssi: 수신 신호 강도 (dBm, 음수)
    ///   - txPower: 1m 거리에서의 기준 RSSI (보통 -59 ~ -65 dBm)
    ///   - n: 경로 손실 지수 (실내: 2.0 ~ 4.0, 일반적으로 2.5)
    static func distance(rssi: Int, txPower: Int = -59, n: Double = 2.5) -> Double {
        if rssi == 0 { return -1 }  // 유효하지 않은 RSSI
        let ratio = Double(txPower - rssi) / (10.0 * n)
        return pow(10.0, ratio)
    }
}
```

### 8.4 칼만 필터

```swift
// Utilities/KalmanFilter.swift

/// 1D 칼만 필터 — RSSI 값 평활화용
struct KalmanFilter {
    private var estimate: Double       // 현재 추정값
    private var estimateError: Double  // 추정 오차
    private let measurementError: Double  // 측정 노이즈 (RSSI 변동성)
    private let processNoise: Double      // 프로세스 노이즈

    init(
        initialEstimate: Double = -60.0,
        estimateError: Double = 5.0,
        measurementError: Double = 3.0,
        processNoise: Double = 0.5
    ) {
        self.estimate = initialEstimate
        self.estimateError = estimateError
        self.measurementError = measurementError
        self.processNoise = processNoise
    }

    /// 새 RSSI 측정값으로 추정값 업데이트
    mutating func update(measurement: Double) -> Double {
        // 칼만 이득 계산
        let kalmanGain = estimateError / (estimateError + measurementError)
        // 추정값 업데이트
        estimate = estimate + kalmanGain * (measurement - estimate)
        // 추정 오차 업데이트
        estimateError = (1 - kalmanGain) * estimateError + processNoise
        return estimate
    }
}


// 사용 예시 — 비콘별 칼만 필터 관리

class BeaconService {
    private var filters: [String: KalmanFilter] = [:]  // beaconId → filter

    func processRSSI(beaconId: String, rssi: Int) -> Double {
        if filters[beaconId] == nil {
            filters[beaconId] = KalmanFilter(initialEstimate: Double(rssi))
        }
        let smoothedRSSI = filters[beaconId]!.update(measurement: Double(rssi))
        let distance = RSSIDistanceConverter.distance(rssi: Int(smoothedRSSI))
        return distance
    }
}
```

### 8.5 삼변측량 알고리즘

```swift
// Utilities/Trilateration.swift

struct BeaconPosition {
    let id: String
    let x: Double       // 비콘의 알려진 x 좌표
    let y: Double       // 비콘의 알려진 y 좌표
    let distance: Double // RSSI로 추정한 거리
}

struct Trilateration {
    /// 3개 이상의 비콘 데이터로 위치 추정
    /// 최소 제곱법 기반 삼변측량
    static func estimate(beacons: [BeaconPosition]) -> CGPoint? {
        guard beacons.count >= 3 else { return nil }

        // 최소 제곱법으로 위치 추정
        // 기준점: 첫 번째 비콘
        let ref = beacons[0]
        var A: [[Double]] = []
        var b: [Double] = []

        for i in 1..<beacons.count {
            let beacon = beacons[i]
            // 선형화된 방정식:
            // 2(xi - x1) * x + 2(yi - y1) * y =
            //   (di^2 - d1^2) - (xi^2 - x1^2) - (yi^2 - y1^2)
            let row = [
                2 * (beacon.x - ref.x),
                2 * (beacon.y - ref.y)
            ]
            let val = (pow(ref.distance, 2) - pow(beacon.distance, 2))
                    - (pow(ref.x, 2) - pow(beacon.x, 2))
                    - (pow(ref.y, 2) - pow(beacon.y, 2))
            A.append(row)
            b.append(val)
        }

        // 최소 제곱법: x = (A^T * A)^-1 * A^T * b
        guard let result = leastSquares(A: A, b: b) else { return nil }
        return CGPoint(x: result[0], y: result[1])
    }

    /// 2x2 행렬 최소 제곱법 풀이
    private static func leastSquares(A: [[Double]], b: [Double]) -> [Double]? {
        // A^T * A
        let n = A[0].count  // 2
        var ATA = Array(repeating: Array(repeating: 0.0, count: n), count: n)
        var ATb = Array(repeating: 0.0, count: n)

        for i in 0..<A.count {
            for j in 0..<n {
                for k in 0..<n {
                    ATA[j][k] += A[i][j] * A[i][k]
                }
                ATb[j] += A[i][j] * b[i]
            }
        }

        // 2x2 역행렬
        let det = ATA[0][0] * ATA[1][1] - ATA[0][1] * ATA[1][0]
        guard abs(det) > 1e-10 else { return nil }

        let x = (ATA[1][1] * ATb[0] - ATA[0][1] * ATb[1]) / det
        let y = (ATA[0][0] * ATb[1] - ATA[1][0] * ATb[0]) / det
        return [x, y]
    }
}
```

### 8.6 비콘 배치 계획

```
BLE 비콘 프로토타입 테스트 배치:

테스트 공간: 약 15m × 10m 직사각형 구역 (강의실 또는 복도)

비콘 배치 (최소 3개, 권장 4개):

    B1 ──────────────────── B2
    │                        │
    │                        │
    │       테스트 구역       │
    │                        │
    │                        │
    B3 ──────────────────── B4

    B1: (0, 0) — 좌상단 구석
    B2: (15, 0) — 우상단 구석
    B3: (0, 10) — 좌하단 구석
    B4: (15, 10) — 우하단 구석 (옵션)

비콘 설정:
  UUID: "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX" (프로젝트 고유)
  Major: 층 번호 (예: 1, 2, 3, 4)
  Minor: 비콘 고유 ID (예: 1, 2, 3, 4)
  TX Power: -59 dBm (1m 거리 기준, 실측 캘리브레이션 권장)
  광고 간격: 100ms (빠른 업데이트)

캘리브레이션 순서:
  1. 각 비콘에서 1m 거리에서 RSSI 30회 측정
  2. 평균값 → txPower로 설정
  3. 2m, 3m, 5m 거리에서 추가 측정
  4. 경로 손실 지수(n) 피팅
  5. 환경별 n 값 기록 (오픈 공간 vs 벽 사이)

비콘 대안 — iPhone을 비콘으로 사용:
  추가 iPhone에서 CoreBluetooth Peripheral Manager로
  iBeacon 광고 패킷 송출 가능.
  비콘 구매 전 빠른 프로토타이핑에 유용.
```

### 8.7 블루닷 자동 도착 감지

```swift
// BeaconService.swift — 도착 자동 감지

/// 현재 추정 위치가 목적지 POI 반경 내인지 확인
func checkArrival(
    currentPosition: CGPoint,
    destinationPOI: POI,
    threshold: Double = 3.0  // 3미터 반경
) -> Bool {
    let dx = currentPosition.x - CGFloat(destinationPOI.coordinates.x)
    let dy = currentPosition.y - CGFloat(destinationPOI.coordinates.y)
    let distance = sqrt(dx * dx + dy * dy)

    // 좌표 단위가 미터인 경우
    return distance <= threshold
}

// 도착 판정 조건 (오탐 방지):
//   1. 목적지 반경 3m 이내 진입
//   2. 3초 이상 반경 내 체류
//   3. 위 조건 충족 시 → "도착하셨나요?" 확인 시트 표시
//   → 환자가 확인 시 다음 경유지로 전환
//   → Phase 1의 수동 "도착" 버튼도 여전히 사용 가능 (폴백)
```

---

## 9. 데이터 모델 — Swift 구현

### 9.1 핵심 모델 (Phase 1 TypeScript → Swift 변환)

```swift
// Models/Hospital.swift

import Foundation

enum POICategory: String, Codable, CaseIterable {
    case clinic, lab, imaging, pharmacy, admin
    case elevator, stairs, restroom, parking
    case entrance, convenience, lobby
}

struct Coordinate: Codable, Equatable {
    let x: Double
    let y: Double

    var cgPoint: CGPoint { CGPoint(x: x, y: y) }
}

struct POI: Codable, Identifiable, Equatable {
    let id: String
    let name: String
    let shortName: String
    let category: POICategory
    let buildingId: String
    let floorLevel: Int
    let coordinates: Coordinate
    var description: String?
    var iconName: String?  // SF Symbol name
}

struct Floor: Codable, Identifiable {
    var id: Int { level }
    let level: Int
    let name: String
    let mapImageName: String  // 평면도 이미지 에셋 이름
    let pois: [POI]
}

struct Building: Codable, Identifiable {
    let id: String
    let name: String
    let floors: [Floor]
}

struct Hospital: Codable, Identifiable {
    let id: String
    let name: String
    let buildings: [Building]
}


// Models/Session.swift

enum WaypointStatus: String, Codable {
    case pending, current, completed
}

struct Waypoint: Codable, Identifiable {
    var id: String { poiId }
    let poiId: String
    var status: WaypointStatus
    var arrivedAt: TimeInterval?
}

enum SessionStatus: String, Codable {
    case waiting, navigating, completed
}

struct Session: Codable, Identifiable {
    var id: String { sessionId }
    let sessionId: String
    let patientUid: String
    var staffUid: String?
    let qrToken: String
    var waypoints: [Waypoint]
    var currentWaypointIndex: Int
    var status: SessionStatus
    let createdAt: TimeInterval
    var completedAt: TimeInterval?
    let hospitalId: String

    /// Firebase Realtime DB 딕셔너리 변환
    func toDictionary() -> [String: Any] {
        var dict: [String: Any] = [
            "sessionId": sessionId,
            "patientUid": patientUid,
            "qrToken": qrToken,
            "currentWaypointIndex": currentWaypointIndex,
            "status": status.rawValue,
            "createdAt": createdAt,
            "hospitalId": hospitalId,
        ]
        if let staffUid { dict["staffUid"] = staffUid }
        if let completedAt { dict["completedAt"] = completedAt }

        var waypointsDict: [[String: Any]] = []
        for wp in waypoints {
            var wpDict: [String: Any] = [
                "poiId": wp.poiId,
                "status": wp.status.rawValue,
            ]
            if let arrivedAt = wp.arrivedAt { wpDict["arrivedAt"] = arrivedAt }
            waypointsDict.append(wpDict)
        }
        dict["waypoints"] = waypointsDict
        return dict
    }

    /// Firebase 딕셔너리 → Session
    init?(from dict: [String: Any]) {
        guard let sessionId = dict["sessionId"] as? String,
              let patientUid = dict["patientUid"] as? String,
              let qrToken = dict["qrToken"] as? String,
              let currentIdx = dict["currentWaypointIndex"] as? Int,
              let statusStr = dict["status"] as? String,
              let status = SessionStatus(rawValue: statusStr),
              let createdAt = dict["createdAt"] as? TimeInterval,
              let hospitalId = dict["hospitalId"] as? String
        else { return nil }

        self.sessionId = sessionId
        self.patientUid = patientUid
        self.staffUid = dict["staffUid"] as? String
        self.qrToken = qrToken
        self.currentWaypointIndex = currentIdx
        self.status = status
        self.createdAt = createdAt
        self.completedAt = dict["completedAt"] as? TimeInterval
        self.hospitalId = hospitalId

        // waypoints 파싱
        if let wpArray = dict["waypoints"] as? [[String: Any]] {
            self.waypoints = wpArray.compactMap { wpDict in
                guard let poiId = wpDict["poiId"] as? String,
                      let statusStr = wpDict["status"] as? String,
                      let wpStatus = WaypointStatus(rawValue: statusStr)
                else { return nil }
                return Waypoint(
                    poiId: poiId,
                    status: wpStatus,
                    arrivedAt: wpDict["arrivedAt"] as? TimeInterval
                )
            }
        } else {
            self.waypoints = []
        }
    }
}


// Models/Navigation.swift

struct FloorChange: Codable {
    let fromFloor: Int
    let toFloor: Int
    let via: TransportType

    enum TransportType: String, Codable {
        case elevator, stairs, escalator
    }
}

struct NavEdge: Codable, Identifiable {
    var id: String { "\(from)-\(to)" }
    let from: String
    let to: String
    let distance: Double        // 미터
    let estimatedTime: Double   // 초
    let pathCoordinates: [Coordinate]
    var floorChange: FloorChange?
}

struct NavigationGraph: Codable {
    let hospitalId: String
    let edges: [NavEdge]
}

struct PathSegment: Identifiable {
    let id = UUID()
    let floorLevel: Int
    let coordinates: [Coordinate]
    let distance: Double
    var instruction: String?
}

struct PathResult {
    let from: POI
    let to: POI
    let totalDistance: Double
    let totalTime: Double
    let segments: [PathSegment]
}


// Models/RouteTemplate.swift

struct RouteTemplate: Codable, Identifiable {
    let id: String
    let name: String
    let departmentTag: String
    let color: String
    let waypointPoiIds: [String]
    let estimatedTotalTime: Int  // 분
    let isDefault: Bool
}
```

---

## 10. Firebase iOS SDK 연동

### 10.1 초기화

```swift
// Config/FirebaseConfig.swift

import Firebase

class FirebaseConfig {
    static func configure() {
        FirebaseApp.configure()
    }
}

// MediWayApp.swift

@main
struct MediWayApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) var appDelegate

    var body: some Scene {
        WindowGroup {
            ContentView()
        }
    }
}

class AppDelegate: NSObject, UIApplicationDelegate {
    func application(
        _ application: UIApplication,
        didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?
    ) -> Bool {
        FirebaseConfig.configure()
        // 푸시 알림 설정
        UNUserNotificationCenter.current().delegate = self
        application.registerForRemoteNotifications()
        return true
    }

    func application(
        _ application: UIApplication,
        didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data
    ) {
        Messaging.messaging().apnsToken = deviceToken
    }
}

extension AppDelegate: UNUserNotificationCenterDelegate {
    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        willPresent notification: UNNotification
    ) async -> UNNotificationPresentationOptions {
        return [.banner, .sound, .badge]  // 포그라운드에서도 알림 표시
    }
}
```

### 10.2 익명 인증

```swift
// Services/AuthService.swift

import FirebaseAuth

actor AuthService {
    static let shared = AuthService()

    var currentUID: String? {
        Auth.auth().currentUser?.uid
    }

    func signInAnonymously() async throws -> String {
        if let uid = currentUID { return uid }
        let result = try await Auth.auth().signInAnonymously()
        return result.user.uid
    }
}
```

---

## 11. 실내 지도 — 네이티브 구현

### 11.1 ZoomableScrollView (핵심 컴포넌트)

```swift
// Views/Map/IndoorMapView.swift

struct IndoorMapView: View {
    let currentFloor: Int
    let path: [Coordinate]?
    let pois: [POI]
    let startPOI: POI?
    let endPOI: POI?
    var currentPosition: CGPoint?  // BLE 추정 위치 (Month 3)

    @State private var scale: CGFloat = 1.0
    @State private var offset: CGSize = .zero

    // 평면도 이미지 크기 (포인트)
    let mapSize = CGSize(width: 1200, height: 800)

    var body: some View {
        GeometryReader { geo in
            ZStack {
                // 1. 평면도 이미지
                Image("demo-hospital-\(currentFloor)F")
                    .resizable()
                    .aspectRatio(contentMode: .fit)

                // 2. 경로 오버레이
                if let path {
                    PathOverlayView(
                        coordinates: path,
                        mapSize: mapSize,
                        viewSize: geo.size
                    )
                }

                // 3. POI 마커
                ForEach(pois) { poi in
                    POIMarkerView(poi: poi, mapSize: mapSize, viewSize: geo.size)
                }

                // 4. 출발/도착 마커
                if let startPOI {
                    CircleMarker(
                        coordinate: startPOI.coordinates,
                        color: .blue,
                        mapSize: mapSize,
                        viewSize: geo.size
                    )
                }
                if let endPOI {
                    CircleMarker(
                        coordinate: endPOI.coordinates,
                        color: .red,
                        mapSize: mapSize,
                        viewSize: geo.size
                    )
                }

                // 5. 블루닷 (Month 3)
                if let pos = currentPosition {
                    BlueDotView(position: pos, mapSize: mapSize, viewSize: geo.size)
                }
            }
            .scaleEffect(scale)
            .offset(offset)
            .gesture(
                MagnificationGesture()
                    .onChanged { value in scale = value }
            )
            .gesture(
                DragGesture()
                    .onChanged { value in offset = value.translation }
            )
        }
    }
}
```

### 11.2 경로 오버레이

```swift
// Views/Map/PathOverlayView.swift

struct PathOverlayView: View {
    let coordinates: [Coordinate]
    let mapSize: CGSize
    let viewSize: CGSize

    var body: some View {
        Path { path in
            guard let first = coordinates.first else { return }
            let start = convertToViewPoint(first)
            path.move(to: start)

            for coord in coordinates.dropFirst() {
                path.addLine(to: convertToViewPoint(coord))
            }
        }
        .stroke(
            Color.blue,
            style: StrokeStyle(
                lineWidth: 4,
                lineCap: .round,
                lineJoin: .round,
                dash: [10, 5]  // 점선
            )
        )
    }

    private func convertToViewPoint(_ coord: Coordinate) -> CGPoint {
        // SVG 좌표 → 뷰 좌표 변환
        let scaleX = viewSize.width / mapSize.width
        let scaleY = viewSize.height / mapSize.height
        let scale = min(scaleX, scaleY)
        return CGPoint(
            x: coord.x * Double(scale),
            y: coord.y * Double(scale)
        )
    }
}
```

---

## 12. 경로 탐색 알고리즘 — Swift 이식

```swift
// Services/PathfindingService.swift

struct PathfindingService {

    /// Dijkstra 최단 경로 탐색
    static func findPath(
        from startId: String,
        to endId: String,
        graph: NavigationGraph,
        allPOIs: [POI]
    ) -> PathResult? {

        // 인접 리스트 구축
        var adjacency: [String: [(neighbor: String, edge: NavEdge)]] = [:]
        for edge in graph.edges {
            adjacency[edge.from, default: []].append((edge.to, edge))
            adjacency[edge.to, default: []].append((edge.from, edge))
        }

        // Dijkstra
        var distances: [String: Double] = [:]
        var previous: [String: (nodeId: String, edge: NavEdge)] = [:]
        var visited: Set<String> = []
        // (distance, nodeId)
        var queue: [(Double, String)] = [(0, startId)]
        distances[startId] = 0

        while !queue.isEmpty {
            queue.sort { $0.0 < $1.0 }
            let (currentDist, currentNode) = queue.removeFirst()

            if currentNode == endId { break }
            if visited.contains(currentNode) { continue }
            visited.insert(currentNode)

            for (neighbor, edge) in adjacency[currentNode] ?? [] {
                let newDist = currentDist + edge.estimatedTime
                if newDist < (distances[neighbor] ?? .infinity) {
                    distances[neighbor] = newDist
                    previous[neighbor] = (currentNode, edge)
                    queue.append((newDist, neighbor))
                }
            }
        }

        // 경로 역추적
        guard distances[endId] != nil else { return nil }

        var path: [NavEdge] = []
        var current = endId
        while let prev = previous[current] {
            path.insert(prev.edge, at: 0)
            current = prev.nodeId
        }

        // 세그먼트 분할 (층별)
        let segments = buildSegments(from: path, allPOIs: allPOIs)
        let totalDistance = path.reduce(0) { $0 + $1.distance }
        let totalTime = path.reduce(0) { $0 + $1.estimatedTime }

        guard let startPOI = allPOIs.first(where: { $0.id == startId }),
              let endPOI = allPOIs.first(where: { $0.id == endId })
        else { return nil }

        return PathResult(
            from: startPOI,
            to: endPOI,
            totalDistance: totalDistance,
            totalTime: totalTime,
            segments: segments
        )
    }

    private static func buildSegments(
        from edges: [NavEdge],
        allPOIs: [POI]
    ) -> [PathSegment] {
        var segments: [PathSegment] = []
        var currentCoords: [Coordinate] = []
        var currentFloor: Int?
        var currentDistance: Double = 0

        for edge in edges {
            if let floorChange = edge.floorChange {
                // 현재 층 세그먼트 마무리
                if !currentCoords.isEmpty, let floor = currentFloor {
                    segments.append(PathSegment(
                        floorLevel: floor,
                        coordinates: currentCoords,
                        distance: currentDistance
                    ))
                }
                // 층 이동 세그먼트
                let viaName = floorChange.via == .elevator ? "엘리베이터" : "계단"
                segments.append(PathSegment(
                    floorLevel: floorChange.fromFloor,
                    coordinates: [],
                    distance: 0,
                    instruction: "\(viaName)을(를) 타고 \(floorChange.toFloor)층으로 이동하세요"
                ))
                currentCoords = []
                currentDistance = 0
                currentFloor = floorChange.toFloor
            } else {
                if currentFloor == nil {
                    // 출발 층 결정
                    let fromPOI = allPOIs.first { $0.id == edge.from }
                    currentFloor = fromPOI?.floorLevel
                }
                currentCoords.append(contentsOf: edge.pathCoordinates)
                currentDistance += edge.distance
            }
        }

        // 마지막 세그먼트
        if !currentCoords.isEmpty, let floor = currentFloor {
            segments.append(PathSegment(
                floorLevel: floor,
                coordinates: currentCoords,
                distance: currentDistance
            ))
        }

        return segments
    }
}
```

---

## 13. ARKit 3D 스캔 상세 가이드

### 13.1 RoomPlan 사용 제약사항

```
하드웨어 요구사항:
  - LiDAR 센서 탑재 기기 필수
  - iPhone 12 Pro 이상 또는 iPad Pro (2020+)
  - iOS 16.0 이상

RoomPlan의 한계:
  - 한 번에 하나의 방만 스캔 가능
  - 긴 복도(10m+)는 정확도가 떨어질 수 있음
  - 유리벽, 거울은 LiDAR 반사로 인해 인식 오류 발생
  - 움직이는 사람/물체가 있으면 정확도 저하
  - 방 연결(복도 ↔ 방)은 자동으로 이루어지지 않음

대응 전략:
  1. 방/복도를 각각 개별 스캔
  2. 각 스캔에 위치 태그 부여 (건물/층/구역)
  3. 수동으로 스캔 결과 간 연결 포인트 지정
  4. 복도는 구간을 나누어 여러 번 스캔
  5. Phase 3에서 실제 병원 적용 시 직원 부재 시간에 스캔
```

### 13.2 RoomCaptureView SwiftUI 래핑

```swift
// Views/Scan/RoomScanView.swift

import RoomPlan

struct RoomScanView: View {
    @State private var scanService = RoomScanService()
    @State private var showResult = false

    var body: some View {
        ZStack {
            if scanService.isScanning {
                RoomCaptureViewRepresentable(service: scanService)
                    .ignoresSafeArea()

                VStack {
                    Spacer()
                    Button("스캔 완료") {
                        scanService.stopScan()
                        showResult = true
                    }
                    .buttonStyle(.borderedProminent)
                    .padding(.bottom, 40)
                }
            } else {
                VStack(spacing: 20) {
                    if RoomScanService.isSupported {
                        Image(systemName: "cube.transparent")
                            .font(.system(size: 60))
                        Text("3D 실내 스캔")
                            .font(.title)
                        Text("iPhone을 천천히 움직여 공간을 스캔하세요")
                            .foregroundStyle(.secondary)
                        Button("스캔 시작") {
                            scanService.startScan()
                        }
                        .buttonStyle(.borderedProminent)
                    } else {
                        Image(systemName: "exclamationmark.triangle")
                            .font(.system(size: 60))
                            .foregroundStyle(.orange)
                        Text("LiDAR 미지원 기기")
                        Text("3D 스캔에는 iPhone 12 Pro 이상이 필요합니다")
                            .foregroundStyle(.secondary)
                    }
                }
            }
        }
        .sheet(isPresented: $showResult) {
            if let room = scanService.capturedRoom {
                ScanResultView(capturedRoom: room)
            }
        }
    }
}

struct RoomCaptureViewRepresentable: UIViewRepresentable {
    let service: RoomScanService

    func makeUIView(context: Context) -> RoomCaptureView {
        let view = RoomCaptureView()
        // RoomCaptureView 설정
        return view
    }

    func updateUIView(_ uiView: RoomCaptureView, context: Context) {}
}
```

---

## 14. BLE 비콘 측위 상세 가이드

### 14.1 비콘 하드웨어 옵션

```
옵션 1: Estimote Proximity Beacons (권장)
  - 가격: 개발자 키트 약 $99 (3개)
  - 장점: iOS SDK 제공, iBeacon 호환, 설정 앱 제공
  - 배터리: CR2477, 약 2년 수명
  - 구매: estimote.com

옵션 2: Kontakt.io Beacon Pro
  - 가격: 개당 약 $20~30
  - 장점: 높은 신뢰성, 기업용 관리 플랫폼
  - 구매: kontakt.io

옵션 3: Raspberry Pi 4 + nRF52840 Dongle (저비용)
  - 가격: 약 ₩60,000 (Pi 4 + 동글)
  - 장점: 가장 저렴, 커스터마이징 자유
  - 단점: 전원 필요, 설정 복잡
  - 설정: BlueZ로 iBeacon 광고 패킷 송출

옵션 4: 추가 iPhone을 비콘으로 (무비용 테스트)
  - CoreBluetooth Peripheral Manager로 BLE 광고
  - 장점: 추가 비용 없음, 빠른 프로토타이핑
  - 단점: 항상 앱이 실행 중이어야 함
```

### 14.2 Info.plist 권한 설정

```xml
<!-- Info.plist에 추가할 키 -->

<!-- BLE 사용 -->
<key>NSBluetoothAlwaysUsageDescription</key>
<string>실내 위치를 파악하여 경로를 안내하기 위해 블루투스를 사용합니다</string>

<!-- 위치 (iBeacon 모니터링에 필요) -->
<key>NSLocationWhenInUseUsageDescription</key>
<string>병원 내 현재 위치를 파악하여 경로를 안내합니다</string>

<key>NSLocationAlwaysAndWhenInUseUsageDescription</key>
<string>백그라운드에서도 도착 알림을 제공하기 위해 위치 권한이 필요합니다</string>

<!-- 카메라 (QR 스캔) -->
<key>NSCameraUsageDescription</key>
<string>QR 코드를 스캔하여 환자를 연결합니다</string>

<!-- Background Modes (Capabilities에서도 설정) -->
<key>UIBackgroundModes</key>
<array>
    <string>bluetooth-central</string>
    <string>location</string>
    <string>remote-notification</string>
</array>
```

---

## 15. 보안 및 권한 관리

### 15.1 iOS 권한 요청 전략

```
Phase 2에서 사용하는 시스템 권한:

필수 권한:
  1. 카메라 — QR 스캔 (의료진 앱)
  2. 푸시 알림 — 동선 안내 알림

Month 2 추가:
  3. 카메라 — AR/3D 스캔 (LiDAR)

Month 3 추가:
  4. Bluetooth — BLE 비콘 수신
  5. 위치 (When In Use) — iBeacon 모니터링

권한 요청 타이밍:
  - 앱 최초 실행 시 모든 권한을 한꺼번에 요청하지 않음
  - 각 기능을 처음 사용할 때 해당 권한만 요청
  - 예: QR 스캔 버튼 탭 → 카메라 권한 요청
  - 예: 동선 수신 시 → 푸시 알림 권한 요청
  - 예: 3D 스캔 메뉴 진입 → 카메라(AR) 권한 요청
  - 예: BLE 측위 시작 → Bluetooth + 위치 권한 요청

권한 거부 시 처리:
  - 거부된 권한에 대한 안내 메시지 표시
  - "설정에서 권한을 변경할 수 있습니다" + 설정 앱 열기 버튼
  - 핵심 기능 불가 시에도 앱이 크래시되지 않도록 graceful degradation
```

### 15.2 데이터 보안 (Phase 1과 동일 원칙)

```
Phase 1과 동일한 보안 원칙을 iOS에서도 유지합니다.

1. 의료 정보 비접촉
2. 데이터 최소 수집
3. 실시간 처리 후 삭제
4. Firebase TLS 보안

iOS 추가 고려:
  - Keychain에 민감 데이터 저장 (Firebase UID 등)
  - UserDefaults에는 비민감 설정만 저장
  - BLE 위치 데이터는 메모리에서만 처리, 디스크 미저장
  - 3D 스캔 데이터는 로컬 저장 (서버 전송 없음)
  - App Transport Security (ATS) 활성화 유지
```

---

## 16. 테스트 전략

### 16.1 단위 테스트 (XCTest)

```
테스트 대상:

1. PathfindingService
   - 같은 층 최단 경로
   - 층 이동 포함 경로
   - 연결되지 않은 노드 예외
   - 출발지 == 목적지

2. Session 모델
   - toDictionary() → init(from:) 라운드트립
   - 상태 전환 로직

3. Trilateration (Month 3)
   - 3개 비콘 정삼각형 배치 → 중심점 추정
   - 비콘 2개 (부족) → nil 반환
   - 극단적 RSSI 값 처리

4. KalmanFilter (Month 3)
   - 안정적 입력 → 빠른 수렴
   - 갑작스러운 변화 → 점진적 추종
   - 노이즈 제거 효과 검증

5. RSSIDistanceConverter
   - 알려진 입력/출력 쌍 검증
   - RSSI = 0 예외 처리
```

### 16.2 UI 테스트 (XCUITest)

```
시나리오 1: 의료진 전체 플로우
  1. 앱 실행 → 의료진 역할 선택
  2. QR 스캔 화면 진입 (카메라 권한)
  3. 시뮬레이터에서는 수동 토큰 입력 테스트
  4. 템플릿 선택 → 전송 확인 → 완료

시나리오 2: 환자 전체 플로우
  1. 앱 실행 → 환자 역할 선택
  2. QR 코드 표시 확인
  3. (백그라운드에서 세션 생성 시뮬레이션)
  4. 동선 수신 → 지도 표시 → 도착 버튼 → 다음 경유지

시나리오 3: 3D 스캔 (실기기만)
  1. 스캔 메뉴 진입
  2. LiDAR 미지원 시 안내 메시지 확인
  3. (LiDAR 기기) 스캔 시작 → 중지 → 결과 뷰어
```

### 16.3 실기기 테스트 체크리스트

```
□ iPhone SE (비 LiDAR) — 기본 기능 동작 확인
□ iPhone 12 Pro+ (LiDAR) — 3D 스캔 동작 확인
□ iPad — 레이아웃 적응 확인 (선택)
□ iOS 16 — 최소 지원 버전 동작 확인
□ iOS 17 — 최신 버전 동작 확인
□ 다크 모드 — 모든 화면 가독성
□ Dynamic Type (큰 텍스트) — 레이아웃 깨짐 없음
□ 저전력 모드 — BLE 스캔 영향 확인
□ 비행기 모드 → 해제 — Firebase 재연결
```

---

## 17. 빌드 및 배포

### 17.1 Xcode 프로젝트 설정

```
General:
  Display Name: MediWay
  Bundle Identifier: com.mediway.app
  Deployment Target: iOS 16.0
  Devices: iPhone

Signing & Capabilities:
  □ Push Notifications
  □ Background Modes
      ☑ Remote notifications
      ☑ Uses Bluetooth LE accessories
      ☑ Location updates
  □ (자동 서명 설정)

Build Settings:
  Swift Language Version: Swift 5.9
  Build Active Architecture Only: Debug=Yes, Release=No
```

### 17.2 TestFlight 배포

```
배포 순서:
  1. Apple Developer Program 가입 ($99/년)
  2. Xcode → Archive → Distribute App → App Store Connect
  3. App Store Connect에서 TestFlight 탭
  4. 빌드 처리 완료 대기 (약 30분)
  5. 내부 테스터 그룹 생성 (최대 100명)
  6. 테스터 초대 (이메일)
  7. 테스터가 TestFlight 앱에서 설치

무료 대안 (Developer Account 없이):
  - Xcode → 실기기 직접 설치 (개인 팀 서명)
  - 제한: 7일마다 재설치 필요, 3대까지
  - 프로토타입 단계에서는 충분
```

---

## 18. Phase 3 연계 고려사항

### 18.1 Phase 3에서 재사용할 요소

```
재사용 대상:
  ✅ iOS 앱 전체 코드베이스
  ✅ Firebase 백엔드 (Auth, Realtime DB, FCM)
  ✅ 데이터 모델 (Hospital, Session, Navigation)
  ✅ PathfindingService
  ✅ BLE 비콘 수신 + 삼변측량 로직
  ✅ 실내 지도 뷰 컴포넌트

Phase 3에서 확장 필요:
  ⚠️ 실제 병원 평면도 교체 (가상 → 실제 CAD 변환)
  ⚠️ 비콘 수 증가 대응 (4개 → 20~50개)
  ⚠️ 비콘 캘리브레이션 도구 (현장 RSSI 측정 → 자동 n값 피팅)
  ⚠️ 관리자 대시보드 (비콘 상태, 배터리 모니터링)
  ⚠️ 의료진 앱 고도화 (EMR 시스템 연동 가능성)
```

### 18.2 코드 확장성 설계 포인트

```
1. PositionProvider 프로토콜
   Phase 2에서 BeaconService가 직접 위치를 제공하지만,
   Phase 3에서는 Wi-Fi 핑거프린팅, PDR 등 복합 측위로 전환할 수 있으므로
   위치 제공자를 프로토콜로 추상화합니다.

   protocol PositionProvider {
       var currentPosition: AsyncStream<CGPoint> { get }
       var accuracy: Double { get }
       func start()
       func stop()
   }

   class BLEPositionProvider: PositionProvider { ... }
   // Phase 3: class HybridPositionProvider: PositionProvider { ... }

2. MapDataProvider 프로토콜
   Phase 2에서는 번들 내 가상 병원 데이터를 사용하지만,
   Phase 3에서는 서버에서 실제 병원 지도를 다운로드해야 하므로
   데이터 소스를 프로토콜로 추상화합니다.

   protocol MapDataProvider {
       func getHospital(id: String) async throws -> Hospital
       func getFloorMap(hospitalId: String, floor: Int) async throws -> UIImage
       func getNavigationGraph(hospitalId: String) async throws -> NavigationGraph
   }

   class BundledMapDataProvider: MapDataProvider { ... }
   // Phase 3: class RemoteMapDataProvider: MapDataProvider { ... }

3. 동선 전송 채널 추상화
   Phase 2에서는 Firebase Realtime DB 직접 사용이지만,
   Phase 3에서는 REST API 서버를 도입할 수 있으므로
   세션 서비스 인터페이스를 유지합니다.

   현재: SessionService → Firebase Realtime DB
   향후: SessionService → REST API → Firebase (또는 자체 DB)
```

---

## 부록: Claude Code 사용 팁

### 프롬프트 예시 — Xcode 프로젝트 초기화

```
"SwiftUI iOS 17 프로젝트를 만들어줘. 
Firebase iOS SDK를 SPM으로 추가하고 (Auth, Database, Messaging),
위 가이드라인의 디렉토리 구조대로 그룹과 Swift 파일을 생성해줘.
AppDelegate에서 Firebase 초기화와 APNs 등록 코드를 작성해."
```

### 프롬프트 예시 — Phase 1 → Swift 모델 변환

```
"Phase 1 가이드라인의 TypeScript 타입 정의(Hospital, Session, Navigation)를
Swift struct + Codable로 변환해줘. 
Firebase Realtime DB 딕셔너리와의 변환 메서드(toDictionary, init(from:))도 포함해."
```

### 프롬프트 예시 — QR 스캐너

```
"AVFoundation을 사용한 QR 코드 스캐너를 SwiftUI에서 구현해줘.
UIViewControllerRepresentable로 래핑하고,
스캔 성공 시 콜백으로 토큰 문자열을 반환해.
카메라 권한 처리와 에러 핸들링도 포함해줘."
```

### 프롬프트 예시 — 실내 지도

```
"UIScrollView 기반 줌/팬 가능한 실내 지도 뷰를 만들어줘.
평면도 이미지를 배경으로 표시하고,
SwiftUI Path로 경로 좌표 배열을 점선으로 그려.
POI 마커와 출발/도착 원형 마커도 추가해."
```

### 프롬프트 예시 — RoomPlan 3D 스캔

```
"RoomPlan API를 사용한 3D 실내 스캔 기능을 구현해줘.
RoomCaptureView를 SwiftUI로 래핑하고,
스캔 시작/중지/결과 확인 UI를 만들어.
스캔 결과에서 벽 데이터를 추출해 2D 평면도로 변환하는 로직도 작성해."
```

### 프롬프트 예시 — BLE 비콘 측위

```
"CLLocationManager의 iBeacon 모니터링으로 BLE 비콘을 수신하고,
칼만 필터로 RSSI를 평활화한 뒤,
삼변측량으로 현재 위치를 추정하는 BeaconService를 구현해줘.
추정된 위치를 블루닷으로 지도 위에 표시하는 것까지."
```

---

> **이 가이드라인은 Phase 2 iOS 앱 MVP의 전체 구현 청사진입니다.**
> Month 1(기능 이식), Month 2(3D 스캔), Month 3(BLE 비콘)의 Task 체크리스트를 따르고,
> Swift 코드 명세와 알고리즘 구현을 참조하여 일관된 품질을 유지하세요.
> Phase 1의 Firebase 백엔드를 공유하므로, 웹-iOS 간 호환성을 항상 확인하세요.
