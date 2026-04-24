# 📱 iPhone LiDAR 3D 스캔 → 3D 맵 → 2D 평면도 변환 가이드

> 본 문서는 MediWay 프로젝트에서 iPhone Pro의 LiDAR 스캐너를 활용하여
> 건물 내부를 3D 스캔하고, 이를 3D 맵 및 2D 평면도로 변환하는 방법을 정리한 것입니다.

---

## 목차

1. [개요](#1-개요)
2. [iPhone 3D 스캔 → 3D 맵 생성](#2-iphone-3d-스캔--3d-맵-생성)
3. [3D 맵 → 2D 평면도 변환](#3-3d-맵--2d-평면도-변환)
4. [서드파티 앱 활용](#4-서드파티-앱-활용)
5. [MediWay 프로젝트 적용 워크플로우](#5-mediway-프로젝트-적용-워크플로우)
6. [제약 사항 및 대응 전략](#6-제약-사항-및-대응-전략)
7. [참고 자료](#7-참고-자료)

---

## 1. 개요

iPhone Pro(12 Pro 이상)에 탑재된 LiDAR 스캐너와 Apple의 RoomPlan API를 활용하면, **3D 스캔 → 3D 맵 생성 → 2D 평면도 추출**까지의 전체 파이프라인을 iPhone 1대로 처리할 수 있습니다.

| 단계 | 입력 | 출력 | 핵심 기술 |
|------|------|------|----------|
| 3D 스캔 | 실제 건물 공간 | CapturedRoom 데이터 | RoomPlan API + LiDAR |
| 3D 맵 생성 | CapturedRoom 데이터 | USDZ/USD 3D 모델 | StructureBuilder (MultiRoom 병합) |
| 2D 평면도 추출 | CapturedRoom 좌표 데이터 | SVG/PNG/PDF 평면도 | simd_float4x4 → XZ 투영 |

---

## 2. iPhone 3D 스캔 → 3D 맵 생성

### 2.1 Apple RoomPlan API (권장)

RoomPlan은 ARKit과 RealityKit 기반의 Swift API로, iPhone/iPad의 카메라와 LiDAR 스캐너를 사용하여 방의 3D 모델(벽, 문, 창문, 가구 포함)을 자동 생성합니다.

#### 작동 원리

RoomPlan은 두 개의 뉴럴 네트워크를 활용합니다.

- **벽/개구부 감지 네트워크**: Point Cloud와 시맨틱 라벨을 입력받아 bird's-eye view에서 2D 벽과 개구부를 예측한 뒤, 벽 높이를 이용해 3D로 리프팅
- **문/창문 감지 네트워크**: 2D 벽면 위에서 문과 창문을 탐지

Apple의 평가에 따르면, 벽과 창문 카테고리에서 95% 정밀도/재현율, 문 카테고리에서 90% 정밀도/재현율을 달성했습니다.

#### 스캔 과정

1. iPhone Pro를 들고 방 안에서 천천히 걸어다닙니다
2. RoomPlan이 실시간으로 벽, 문, 창문, 가구를 인식하고 3D 모델을 구축합니다
3. 조명이 부족하거나, 너무 빠르거나, 너무 가까울 경우 자동으로 안내 메시지를 표시합니다
4. 스캔이 완료되면 `CapturedRoom` 객체가 생성됩니다

#### 출력 형식

RoomPlan은 다음 형식으로 내보낼 수 있습니다.

- **USDZ/USD**: 3D 모델 파일 (AR Quick Look, Blender, SketchUp 등에서 열기 가능)
- **JSON/Plist**: CapturedRoom 구조체의 직렬화 데이터 (벽, 문, 창문, 가구의 좌표, 크기, 유형 정보 포함)

#### 정밀도

실제 측정값과 비교했을 때 오차가 보통 5% 이하로, 전문적 용도(인테리어 설계, 부동산 문서화)에도 충분한 수준입니다. 전문 레이저 측정기(Bosch)와 비교했을 때 1~2cm 차이 수준이라는 사용자 리뷰도 있습니다.

#### 핵심 코드 구조 (Swift)

```swift
// 1. RoomCaptureSession 설정
let roomCaptureView = RoomCaptureView(frame: .zero)
let roomBuilder = RoomBuilder(options: [.beautifyObjects])
roomCaptureView.captureSession.delegate = self

// 2. 스캔 완료 후 CapturedRoom 생성
let room = try await roomBuilder.capturedRoom(from: capturedData)

// 3. USDZ로 내보내기
try room.export(to: outputURL)

// 4. CapturedRoom의 주요 데이터
room.walls      // [CapturedRoom.Surface] — 벽 목록
room.doors      // [CapturedRoom.Surface] — 문 목록
room.windows    // [CapturedRoom.Surface] — 창문 목록
room.objects     // [CapturedRoom.Object]  — 가구/설비 목록
// 각 surface/object는 transform(4x4 행렬), dimensions(크기), category(유형) 포함
```

### 2.2 다중 방 스캔 (MultiRoom) — iOS 17+

iOS 17부터 추가된 `StructureBuilder` API를 사용하면 여러 방의 개별 스캔을 하나의 3D 구조로 병합할 수 있습니다.

```swift
// 1. StructureBuilder 인스턴스 생성
let structureBuilder = StructureBuilder(options: [.beautifyObjects])

// 2. 여러 CapturedRoom을 배열로 로드
let rooms: [CapturedRoom] = [room1, room2, room3]

// 3. 병합하여 CapturedStructure 생성
let capturedStructure = try await structureBuilder.capturedStructure(from: rooms)

// 4. 병합된 구조를 USDZ로 내보내기
try capturedStructure.export(to: outputURL)
```

`CapturedStructure`는 다음을 포함합니다.

- `rooms`: 개별 CapturedRoom 인스턴스 배열
- 병합된 벽, 문, 창문, 개구부, 객체 목록
- USDZ 내보내기 함수

이 기능을 활용하면 병원 한 개 층의 여러 방/복도를 개별 스캔한 뒤 하나의 통합 3D 맵으로 병합할 수 있습니다.

### 2.3 대안: ARKit Depth API + Point Cloud

RoomPlan이 "방" 단위의 구조화된 모델을 만든다면, ARKit Depth API는 더 원시적인 Point Cloud(점군) 데이터를 제공합니다.

- **용도**: 복도, 대형 로비 등 RoomPlan이 "방"으로 인식하기 어려운 개방 공간
- **출력**: PLY, OBJ, XYZ 형식의 Point Cloud
- **후처리**: Blender, CloudCompare, Open3D(Python) 등에서 메시 생성 및 편집
- **참고 프로젝트**: [LiDAR-Map-App (GitHub)](https://github.com/minsangKang/LiDAR-Map-App) — Apple LiDAR로 Point Cloud 측정 후 서버 업로드하는 iOS 앱

---

## 3. 3D 맵 → 2D 평면도 변환

### 3.1 방법 1: CapturedRoom 데이터에서 프로그래밍 방식으로 변환

RoomPlan의 `CapturedRoom`에 포함된 각 벽(surface)의 3D 좌표에서 **Y축(높이)을 무시하고 X, Z 좌표만 추출**하면 bird's-eye view 2D 평면도가 됩니다.

#### 핵심 원리

각 surface의 `transform` 속성은 `simd_float4x4` 행렬입니다. 이 행렬에서 위치(translation)와 회전(rotation) 정보를 추출하고, 높이 축을 제거하면 2D 좌표를 얻습니다.

```swift
// simd_float4x4에서 2D 좌표 추출 (Y축 무시)
extension simd_float4x4 {
    var position2D: CGPoint {
        // columns.3은 translation 벡터
        // x = 3D의 x좌표, y = 3D의 z좌표 (bird's-eye view)
        return CGPoint(x: CGFloat(columns.3.x), y: CGFloat(columns.3.z))
    }
    
    var rotationAngle2D: CGFloat {
        // Y축 기준 회전각 추출
        return CGFloat(atan2(columns.0.z, columns.0.x))
    }
}

// 벽을 2D SpriteKit 노드로 변환
for wall in capturedRoom.walls {
    let position = wall.transform.position2D
    let angle = wall.transform.rotationAngle2D
    let width = CGFloat(wall.dimensions.x)  // 벽의 너비
    let thickness = 0.1  // 벽 두께 (시각적 표현용)
    
    let wallNode = SKShapeNode(rectOf: CGSize(width: width, height: thickness))
    wallNode.position = position
    wallNode.zRotation = angle
    wallNode.fillColor = .darkGray
    scene.addChild(wallNode)
}
```

#### 오픈소스 참고 프로젝트

**RoomPlanDemo** (GitHub: BaidetskyiYurii/RoomPlanDemo)

- LiDAR 스캔 → 인터랙티브 2D 평면도 생성을 완전히 구현한 프로젝트
- 기술 스택: RoomPlan + SpriteKit + SwiftUI
- 주요 기능:
  - 벽, 문, 창문, 가구를 2D로 렌더링
  - 탭하여 상세 정보 확인 및 편집
  - 커스텀 가구 추가, 어노테이션 추가
  - PNG, JPEG, PDF로 내보내기
  - USDZ 3D 모델 내보내기
  - Demo Mode (LiDAR 없이도 미리 로드된 데이터로 테스트 가능)
- 링크: https://github.com/BaidetskyiYurii/RoomPlanDemo

**RoomPlan-2D** (GitHub: denniswave/RoomPlan-2D)

- Apple Developer Forums에서 공유된 솔루션의 전체 구현
- CapturedRoom 데이터를 SpriteKit 기반 2D 맵으로 변환
- 링크: https://github.com/denniswave/RoomPlan-2D

### 3.2 방법 2: USDZ 파일에서 변환

RoomPlan으로 내보낸 USDZ 파일을 Blender, SketchUp 등의 3D 소프트웨어에서 열고, 상단 뷰(Top View)로 전환하여 2D 이미지로 렌더링하는 방법입니다.

```
iPhone 스캔 → USDZ 내보내기 → Blender에서 열기 → Top View → PNG/SVG 렌더링
```

이 방법은 프로그래밍 없이 수동으로 처리할 수 있지만, 자동화가 어렵고 MediWay처럼 앱 내에서 실시간으로 평면도를 생성해야 하는 경우에는 적합하지 않습니다.

---

## 4. 서드파티 앱 활용

iPhone LiDAR 스캔 → 2D 평면도 자동 변환을 지원하는 앱들입니다. 직접 코딩 없이 빠르게 평면도를 얻고 싶을 때 유용합니다.

| 앱 | 3D 스캔 | 2D 평면도 | 내보내기 형식 | 가격 | 비고 |
|----|:-------:|:--------:|------------|------|------|
| **magicplan** | ✅ | ✅ | PDF, PNG, DXF, SVG, IFC | 월 $24~ | Apple RoomPlan 기반 Auto-Scan, 다중 방 한 번에 스캔 |
| **RoomScan Pro** | ✅ | ✅ | PDF, PNG, DXF, IFC, OBJ, PLY | 구독/1회 구매 | 가장 빠른 스캔 속도, Point Cloud 통합 내보내기 |
| **Polycam** | ✅ | ✅ | OBJ, DAE, FBX, STL, DXF, PLY | 월 $12~ | AI 기반 빈 영역 자동 채움, 360° 파노라마 |
| **Metaroom** | ✅ | ✅ | IFC, DXF, GLB 등 30+ | 구독 | CAD-ready 출력, 전문가용 정밀도 |
| **Live Home 3D** | ✅ | ✅ | 자체 포맷 | 앱 구매 | RoomPlan 기반, 2D 평면도에서 벽 위치 수동 조정 가능 |

---

## 5. MediWay 프로젝트 적용 워크플로우

### Phase 1 — 웹 데모 (LiDAR 불필요)

웹 데모에서는 LiDAR 스캔에 의존하지 않고, **가상의 병원 평면도를 SVG/Figma로 직접 제작**하는 것이 가장 빠르고 안정적입니다.

```
Figma/Illustrator → 병원 평면도 SVG 제작 → Leaflet.js 오버레이 → 경로 하이라이트
```

### Phase 2 — iOS 앱 (LiDAR 활용)

```
Step 1: 3D 스캔
├── 경북대 캠퍼스 건물 1개 층을 대상으로 선정
├── 각 방/복도를 RoomPlan으로 개별 스캔 (방당 2~5분)
├── iOS 17 StructureBuilder로 여러 스캔을 CapturedStructure로 병합
└── USDZ로 내보내기 → 3D 맵 완성

Step 2: 2D 평면도 추출
├── CapturedRoom의 surface 좌표에서 Y축 제거 → XZ 2D 투영
├── RoomPlanDemo 오픈소스 참고하여 SpriteKit/SwiftUI로 렌더링
├── SVG로 변환하여 웹 데모에도 활용 가능
└── PNG/PDF로도 내보내기 가능

Step 3: 네비게이션 그래프 생성
├── 2D 평면도 위에 통로 중심선을 따라 노드(교차점, POI) 정의
├── 노드 간 엣지(통로) 정의 및 거리 계산
├── Dijkstra/A* 알고리즘으로 최단 경로 탐색
└── 경로를 2D 맵 위에 하이라이트하여 표시

Step 4: 3D 네비게이션 (고급, 선택)
├── 스캔한 USDZ 모델을 ARKit에서 로드
├── 사용자의 현재 위치를 3D 공간에 매핑
├── AR 카메라 뷰에 화살표 오버레이로 방향 안내
└── Google Street View와 유사한 실내 3D 뷰 제공
```

### 데이터 흐름 요약

```
[iPhone Pro LiDAR]
       │
       ▼
[RoomPlan API] ──── CapturedRoom ────┬──── USDZ (3D 맵)
                                     │
                                     ├──── JSON (구조화 데이터)
                                     │
                                     └──── XZ 투영 (2D 평면도)
                                              │
                                              ├── SVG (웹 데모용)
                                              ├── PNG/PDF (문서용)
                                              └── 네비게이션 그래프 (경로 탐색용)
```

---

## 6. 제약 사항 및 대응 전략

### 6.1 대형 공간의 한계

RoomPlan의 MultiRoom은 일반적인 단층 주택(1~4개 침실) 규모에서 가장 잘 작동합니다. 병원의 넓은 로비나 긴 복도에서는 인식률이 떨어질 수 있습니다.

**대응**: 대형 공간은 구역별로 나눠서 스캔하고, StructureBuilder로 병합합니다. 병합이 잘 되지 않는 경우 수동으로 좌표를 보정하는 후처리 코드를 작성합니다.

### 6.2 유리벽/개방 구조

개방형 구조, 계단실, 유리벽, 공사 중인 공간은 Auto-Scan으로 캡처하기 어렵습니다. LiDAR는 투명한 유리를 통과하거나 반사되어 정확한 깊이 측정이 어려울 수 있습니다.

**대응**: 유리벽이 있는 구간은 수동으로 벽 위치를 추가/보정합니다. 또는 해당 구간만 ARKit Point Cloud 방식으로 별도 캡처합니다.

### 6.3 복도 인식 문제

RoomPlan은 "방" 단위로 인식하도록 설계되어 있어, 긴 복도를 하나의 방으로 인식하지 못할 수 있습니다.

**대응**: 복도는 일정 간격(5~10m)으로 분할하여 개별 스캔하고, 후처리에서 연결합니다. 또는 복도는 RoomPlan 대신 수동으로 SVG 위에 직접 그려 넣습니다.

### 6.4 데모 전략

Phase 1 웹 데모에서는 LiDAR 스캔 결과에 의존하기보다, **가상의 병원 평면도를 직접 제작**하는 것이 더 안정적입니다. LiDAR 3D 스캔은 Phase 2에서 "기술 시연(tech demo)"으로 포트폴리오 가치를 보여주는 용도로 활용하고, 실제 네비게이션은 수동 제작한 2D 맵 기반으로 동작하게 하는 이중 전략이 현실적입니다.

---

## 7. 참고 자료

### Apple 공식 문서
- RoomPlan Overview: https://developer.apple.com/augmented-reality/roomplan/
- RoomPlan Documentation: https://developer.apple.com/documentation/roomplan/
- RoomPlan ML Research: https://machinelearning.apple.com/research/roomplan
- WWDC23 — Explore enhancements to RoomPlan: https://developer.apple.com/videos/play/wwdc2023/10192/
- Custom Models for CapturedRoom Export: https://developer.apple.com/documentation/RoomPlan/providing-custom-models-for-captured-rooms-and-structure-exports

### 오픈소스 프로젝트
- RoomPlanDemo (3D 스캔 → 2D 평면도): https://github.com/BaidetskyiYurii/RoomPlanDemo
- RoomPlan-2D (CapturedRoom → 2D 변환): https://github.com/denniswave/RoomPlan-2D
- LiDAR-Map-App (Point Cloud 측정/업로드): https://github.com/minsangKang/LiDAR-Map-App
- ARKit-Scanner (RGB-D 스캔): https://github.com/xiongyiheng/ARKit-Scanner
- SwiftUI-LiDAR (3D 메시 생성/내보내기): https://github.com/cedanmisquith/SwiftUI-LiDAR
- ARKitScenes (Apple 공식 실내 씬 데이터셋): https://github.com/apple/ARKitScenes

### 서드파티 앱
- magicplan: https://www.magicplan.app/
- RoomScan Pro LiDAR: https://www.locometric.com/lidar
- Polycam: https://poly.cam/
- Metaroom: https://amrax.ai/3d-room-scan/
- Live Home 3D: https://www.livehome3d.com/
- Mappedin (실내 지도 플랫폼): https://www.mappedin.com/

### 관련 논문
- ARKitScenes: A Diverse Real-World Dataset for 3D Indoor Scene Understanding (2021): https://arxiv.org/pdf/2111.08897
- 3D Parametric Room Representation with RoomPlan (Apple ML Research): https://machinelearning.apple.com/research/roomplan

---

*최종 업데이트: 2026년 4월*
