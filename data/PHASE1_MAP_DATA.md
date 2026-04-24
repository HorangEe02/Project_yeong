# 🗺️ MediWay Phase 1 웹 데모 — 활용 가능 지도 데이터 및 리소스

> 본 문서는 MediWay Phase 1 웹 데모 구현에 필요한 병원 평면도 데이터, 실내 네비게이션 오픈소스 프로젝트,
> 평면도 제작 도구/템플릿을 정리한 것입니다.

---

## 목차

1. [실제 건물 실내 지도 데이터](#1-실제-건물-실내-지도-데이터)
2. [오픈소스 실내 네비게이션 프로젝트](#2-오픈소스-실내-네비게이션-프로젝트)
3. [병원 평면도 템플릿 및 제작 도구](#3-병원-평면도-템플릿-및-제작-도구)
4. [Phase 1 실전 추천 전략](#4-phase-1-실전-추천-전략)

---

## 1. 실제 건물 실내 지도 데이터

### 1.1 OpenStreetMap 실내 매핑 데이터

OpenStreetMap(OSM)에는 `indoor=room`, `level=`, `room=`, `building:part` 등의 태그 체계를 통해 공항, 기차역, 대학, 병원 등의 내부 구조가 상세하게 매핑되어 있습니다. 미국 콜로라도 덴버의 병원을 포함하여, 전 세계 다수의 건물이 방, 복도, 화장실, 벽, 엘리베이터까지 OSM 실내 태깅 모델로 매핑되어 있습니다.

Overpass API를 사용하면 특정 건물의 실내 지도 데이터를 GeoJSON 형태로 즉시 추출하여 Leaflet.js 위에 오버레이할 수 있습니다.

| 리소스 | 링크 | 설명 |
|--------|------|------|
| Overpass Turbo (데이터 추출) | https://overpass-turbo.eu/ | OSM 데이터를 쿼리하여 GeoJSON으로 다운로드 |
| Simple Indoor Tagging 스키마 | https://wiki.openstreetmap.org/wiki/Simple_Indoor_Tagging | OSM 실내 매핑 태그 체계 문서 |
| Indoor Mapping 위키 | https://wiki.openstreetmap.org/wiki/Indoor_Mapping | OSM 실내 매핑 관련 프로젝트 및 아이디어 모음 |
| Indoor Projects 목록 | https://wiki.openstreetmap.org/wiki/Indoor/Projects | IndoorGML, IMDF 등 실내 매핑 표준 및 프로젝트 |
| Indoor Use Cases | https://wiki.openstreetmap.org/wiki/Indoor/use_cases | 병원, 쇼핑몰, 대학 등 실내 매핑 유스케이스 |
| OpenLevelUp (실내 지도 뷰어) | https://openlevelup.net/ | OSM 실내 데이터를 시각화하는 웹 뷰어 |

#### Overpass API 쿼리 예시

Overpass Turbo(https://overpass-turbo.eu/)에서 아래 쿼리를 실행하면 특정 영역의 실내 매핑 데이터를 GeoJSON으로 추출할 수 있습니다.

```
// 특정 바운딩 박스 내 실내 매핑 데이터 추출
[out:json][timeout:25];
(
  way["indoor"]({{bbox}});
  way["room"]({{bbox}});
  relation["indoor"]({{bbox}});
);
out body;
>;
out skel qt;
```

```
// 특정 병원 주변의 실내 데이터 추출 (덴버 병원 예시)
[out:json][timeout:25];
(
  way["indoor"]["level"](39.738,-104.985,39.742,-104.980);
  relation["indoor"]["level"](39.738,-104.985,39.742,-104.980);
);
out body;
>;
out skel qt;
```

#### 활용 방법

1. Overpass Turbo에서 쿼리 실행 후 "Export → GeoJSON" 다운로드
2. Leaflet.js에서 `L.geoJSON(data)` 로 로드하여 실내 지도 오버레이
3. `level` 속성으로 층별 필터링, `room` 속성으로 방 유형별 색상 구분
4. 각 방에 POI 마커(내과, 약국, 원무과 등) 추가

### 1.2 OSM → Apple IMDF 변환 도구

| 리소스 | 링크 | 설명 |
|--------|------|------|
| osmtoimdf | https://github.com/danielrotaermel/osmtoimdf | OSM XML → Apple Indoor Mapping Data Format 변환 |

OSM 데이터를 Apple의 IMDF(Indoor Mapping Data Format)으로 변환하는 도구입니다. 생성된 IMDF 아카이브는 Apple MapKit에서 사용할 수 있어, Phase 2 iOS 앱에서도 동일한 지도 데이터를 활용할 수 있습니다.

---

## 2. 오픈소스 실내 네비게이션 프로젝트

아래 프로젝트들은 소스 코드와 함께 **샘플 지도 데이터**가 포함되어 있어, fork 후 병원 평면도로 교체하면 빠르게 데모를 구현할 수 있습니다.

### 2.1 Pathpal / indoor-wayfinder ⭐ (가장 추천)

| 항목 | 내용 |
|------|------|
| **링크** | https://github.com/KnotzerIO/indoor-wayfinder |
| **기술 스택** | React + SVG + Dijkstra 알고리즘 |
| **라이선스** | MIT |
| **포함 데이터** | SVG 맵 파일 + POI/경로 정의 JSON |

React 기반의 인터랙티브 SVG 맵으로 실내 경로 탐색을 구현한 프로젝트입니다. MediWay의 기술 스택(React + TypeScript)과 완벽히 호환됩니다.

주요 기능:
- 인터랙티브 SVG 맵 (줌, 패닝, 핀치 줌)
- Dijkstra 알고리즘 기반 최단 경로 계산
- POI(관심 지점) 커스터마이즈
- 반응형 디자인 (모바일 최적화)
- 모든 데이터가 JSON 파일에 저장 (백엔드 불필요)

MediWay 활용 방법:
1. 프로젝트를 fork
2. 내장된 SVG 맵을 가상 병원 평면도로 교체
3. JSON에 POI(내과, 채혈실, 원무과, 약국 등) 정의
4. Dijkstra 경로 탐색 기능 그대로 활용
5. QR 매칭 + 푸시 알림 기능 추가

### 2.2 OpenIndoorMaps

| 항목 | 내용 |
|------|------|
| **링크** | https://github.com/openindoormaps/openindoormaps |
| **기술 스택** | OpenStreetMap 기반, 웹 |
| **라이선스** | 오픈소스 |
| **포함 데이터** | OSM 기반 실내 지도 데이터 |

쇼핑몰, 공항, 병원, 대학 등 복잡한 실내 공간의 네비게이션을 위한 오픈소스 프로젝트입니다.

주요 기능:
- 다층(Multi-Floor) 지원
- 커스터마이즈 가능한 관리 패널
- 오픈 API
- QR 코드 기반 위치 식별 (MediWay 컨셉과 동일)

MediWay의 QR 기반 동선 안내 컨셉과 구조적으로 매우 유사하여 아키텍처 참고에 적합합니다.

### 2.3 simpleroutingsvg (가장 심플)

| 항목 | 내용 |
|------|------|
| **링크** | https://github.com/kisimita/simpleroutingsvg |
| **기술 스택** | 순수 JavaScript + SVG |
| **라이선스** | 오픈소스 |
| **포함 데이터** | `floormap_route.svg` 샘플 평면도 |

SVG 파일을 실내 지도로 사용하고, Dijkstra 최단 경로 알고리즘으로 두 방 사이의 경로를 계산하여 맵 위에 표시하는 가장 단순한 구현체입니다.

구조가 매우 간단하여 Phase 1 프로토타입의 최소 기능 구현 출발점으로 적합합니다. 프로젝트 내 `/assets/floormap_route.svg` 파일에 샘플 평면도가 포함되어 있습니다.

### 2.4 SvgNaviMap (SVG + 네비게이션 그래프 + WiFi)

| 항목 | 내용 |
|------|------|
| **링크** | https://github.com/LukeOwlclaw/SvgNaviMap |
| **기술 스택** | Node.js + SVG + XML 그래프 |
| **라이선스** | 비상업적 무료, 상업용 라이선스 별도 |
| **포함 데이터** | 건물 층별 SVG + XML 네비게이션 그래프 |

건물의 층별 SVG 파일 위에 라우팅 그래프를 생성하는 프로젝트입니다. 그래프는 XML로 저장되며 SVG 원본은 유지됩니다.

주요 기능:
- 방(room), 진입점(door, lift, stairs), 복도(hallway) 노드 정의
- 엣지에 one-way, wheelchair-accessible 등 파라미터 설정
- 두 노드 간 경로 계산 및 시각화
- WiFi 핑거프린트 데이터베이스 생성 (Phase 2~3 활용 가능)
- Android 앱 내보내기

### 2.5 OpenLayers Indoor Map (GeoJSON 실내 지도)

| 항목 | 내용 |
|------|------|
| **링크** | https://github.com/arcataroger/openlayers_indoor_map |
| **기술 스택** | OpenLayers + QGIS + GeoJSON |
| **라이선스** | Creative Commons (지도 데이터), MIT (코드) |
| **포함 데이터** | GeoJSON 층별 레이어 + SVG 아이콘 |

실제 박물관(Field Museum)의 디지털 지도를 OpenLayers로 구현한 프로젝트입니다. `layers/` 폴더에 GeoJSON 형태의 실내 지도 데이터와 SVG 아이콘이 Creative Commons 라이선스로 포함되어 있습니다.

주요 기능:
- 층별 레이어 전환 (Layer Switcher)
- 전시 공간, 편의시설, 라벨, 장식 아이콘 등 다중 레이어
- 클릭 가능한 영역 + 사이드바 정보 표시

### 2.6 Graphmapper Demo (네비게이션 그래프 생성기)

| 항목 | 내용 |
|------|------|
| **링크** | https://github.com/klingerko/graphmapper_demo |
| **기술 스택** | Android (Tango) + Point Cloud |
| **라이선스** | 오픈소스 |
| **포함 데이터** | 네비게이션 그래프 + 2D 평면도 JPG |

실내 환경의 네비게이션 그래프와 2D 평면도를 생성할 수 있는 데모 앱입니다. 복도(hallway), 방(room), 진입점(door, lift, stairs) 등의 POI를 마킹하고 복도 네트워크를 구성할 수 있습니다. 그래프 구조가 IndoorGML과 호환되도록 설계되었습니다.

---

## 3. 병원 평면도 템플릿 및 제작 도구

실제 병원 데이터를 구하기 어려운 경우, 아래 도구/템플릿으로 가상의 병원 평면도를 직접 제작할 수 있습니다.

### 3.1 EdrawMax 병원 평면도 템플릿 (무료)

| 항목 | 내용 |
|------|------|
| **템플릿 갤러리** | https://edrawmax.wondershare.com/examples/hospital-floor-plan.html |
| **개별 템플릿** | https://edrawmax.wondershare.com/templates/hospital-floor-plan.html |
| **내보내기 형식** | JPG, PNG, SVG, PDF, PPTX |
| **가격** | 무료 (기본 편집), 유료 (고급 기능) |

수술실, 회복실, 진료실, 검사실, 약국, 입원 병동, 응급실, ICU 등이 포함된 다양한 유형의 병원 평면도 템플릿을 제공합니다. EdrawMax 온라인 에디터에서 무료로 편집한 후 SVG로 내보내면 Leaflet.js에서 바로 사용할 수 있습니다.

포함된 템플릿 유형:
- 종합병원 전체 평면도
- 응급실(Emergency Room) 레이아웃
- ICU(중환자실) 레이아웃
- 외래 클리닉 레이아웃
- 의료센터 평면도
- 의과대학 평면도

### 3.2 Freepik 병원 평면도 벡터 (무료, 상업용 가능)

| 항목 | 내용 |
|------|------|
| **링크** | https://www.freepik.com/free-photos-vectors/hospital-floor-plan |
| **벡터 전용** | https://www.freepik.com/vectors/hospital-floor-plan |
| **형식** | SVG, AI, EPS, PNG |
| **라이선스** | Free License (출처 표기 시 상업용 가능) |

병원 평면도 벡터, 스톡 사진, PSD 파일을 무료로 다운로드할 수 있습니다. SVG/AI 포맷의 벡터 파일을 다운로드하여 Leaflet.js 오버레이 소스로 직접 활용 가능합니다.

### 3.3 Vecteezy 병원 평면도 벡터 (무료)

| 항목 | 내용 |
|------|------|
| **링크** | https://www.vecteezy.com/free-vector/hospital-floor-plan |
| **형식** | SVG, PNG |
| **라이선스** | Free License (출처 표기 시 상업용 가능) |

다양한 병원 평면도 벡터 아트를 무료로 다운로드할 수 있습니다.

### 3.4 SmartDraw 병원 레이아웃 템플릿

| 항목 | 내용 |
|------|------|
| **링크** | https://www.smartdraw.com/floor-plan/hospital-floor-plan-creator.htm |
| **내보내기 형식** | PDF, PNG, SVG |
| **가격** | 무료 체험 후 유료 |

의료 시설, 클리닉, 외래 시설 등의 템플릿이 제공됩니다. 실시간 협업과 Microsoft Teams/Slack 통합이 가능합니다.

### 3.5 homeRoughEditor (SVG 평면도 에디터, 오픈소스)

| 항목 | 내용 |
|------|------|
| **링크** | https://github.com/ekymo/homeRoughEditor |
| **기술 스택** | 순수 JavaScript + Bootstrap 5 |
| **라이선스** | 오픈소스 |
| **특징** | 외부 라이브러리 없이 브라우저에서 동작 |

순수 JavaScript로 구현된 SVG 평면도 에디터로, 브라우저에서 직접 평면도를 그리고 SVG로 저장할 수 있습니다. `index.html`을 열기만 하면 바로 사용 가능합니다. 직접 병원 평면도를 SVG로 제작할 때 편리합니다.

---

## 4. Phase 1 실전 추천 전략

### 방법 A — 오픈소스 프로젝트 활용 (가장 빠름, 1~2일)

```
Pathpal(indoor-wayfinder) fork
  → 내장 SVG 맵을 가상 병원 평면도로 교체
  → JSON에 POI 정의 (내과, 채혈실, 원무과, 약국 등)
  → Dijkstra 경로 탐색 기능 그대로 활용
  → Firebase 연동하여 QR 매칭 + 푸시 알림 추가
```

**장점**: React 기반으로 MediWay 기술 스택과 동일, 경로 탐색 이미 구현됨, MIT 라이선스
**적합 상황**: 빠른 프로토타입이 필요할 때

### 방법 B — OSM 실제 병원 데이터 활용 (가장 현실적, 3~5일)

```
Overpass API로 실제 병원 실내 데이터 GeoJSON 추출
  → Leaflet.js에 오버레이
  → 방 유형별 색상 구분 (room= 태그 활용)
  → POI 마커 추가
  → 네비게이션 그래프 수동 구성
  → 경로 하이라이트 구현
```

**장점**: 실제 건물 데이터 사용으로 데모 설득력 높음, 무료
**적합 상황**: 현실감 있는 데모가 필요할 때, 발표/포트폴리오용

### 방법 C — 직접 제작 (가장 맞춤, 5~7일)

```
EdrawMax/Freepik에서 병원 평면도 템플릿 다운로드
  → SVG 편집 (Figma, Illustrator, 또는 homeRoughEditor)
  → 한국 대형 병원 구조 반영 (내과, 외과, 영상의학과, 채혈실, 원무과, 약국 등)
  → Leaflet.js에 SVG 오버레이
  → 네비게이션 그래프 직접 정의
  → 경로 하이라이트 + 턴바이턴 텍스트 안내
```

**장점**: 한국어 라벨, 한국 병원 특유의 구조를 정확히 반영 가능
**적합 상황**: 완성도 높은 한국 병원 맞춤 데모가 필요할 때

### 추천 조합

| 우선순위 | 방법 | 소요 시간 | 결과물 |
|---------|------|----------|--------|
| 1순위 | A + C 조합 | 3~5일 | Pathpal fork + 한국어 병원 SVG 직접 제작 |
| 2순위 | B 단독 | 3~5일 | OSM 실제 병원 데이터 기반 데모 |
| 3순위 | C 단독 | 5~7일 | 완전 맞춤 제작 (가장 높은 완성도) |

**1순위 조합(A+C)을 가장 추천합니다.** Pathpal의 React 코드베이스와 Dijkstra 경로 탐색 로직을 활용하되, 지도만 한국 병원 구조에 맞게 SVG로 직접 제작하면 개발 시간과 완성도를 모두 잡을 수 있습니다.

---

## 참고: 데이터 형식별 활용 도구

| 데이터 형식 | 활용 도구 | 용도 |
|------------|----------|------|
| SVG | Leaflet.js `L.svgOverlay()`, React SVG 컴포넌트 | 정적 평면도 오버레이 |
| GeoJSON | Leaflet.js `L.geoJSON()`, OpenLayers | 실내 지도 + 속성 데이터 |
| PNG/JPG | Leaflet.js `L.imageOverlay()` | 이미지 기반 평면도 |
| IMDF | Apple MapKit (iOS) | Phase 2 iOS 앱용 |
| IndoorGML | OGC 표준 파서 | 네비게이션 그래프 표준 |

---

*최종 업데이트: 2026년 4월*
