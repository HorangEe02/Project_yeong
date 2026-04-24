# MediWay Phase 1: 웹 데모 기술 명세서 (Technical Specification)

본 문서는 MediWay Phase 1 웹 데모 구현을 위한 핵심 기술 사양과 데이터 구조를 정의합니다.

## 1. 프로젝트 개요
- **목표**: 의료진의 동선 전송과 환자의 실시간 경로 확인 기능을 검증하는 MVP 구현
- **주요 사용자**: 의료진(간호사), 환자 및 보호자
- **플랫폼**: 반응형 웹 (Mobile/Desktop)

## 2. 기술 스택 (Core Stack)
- **Frontend**: React 18, TypeScript, Vite
- **Styling**: Tailwind CSS, Lucide React (Icons)
- **State Management**: Zustand
- **Backend & Realtime**: Firebase (Auth, Realtime DB, FCM)
- **Maps**: Leaflet.js (CRS.Simple)
- **Utilities**: html5-qrcode (Scan), qrcode.react (Gen)

## 3. 핵심 데이터 모델 (Types)

### POI (Point of Interest)
```typescript
interface POI {
  id: string;
  name: string;
  category: 'clinic' | 'lab' | 'imaging' | 'pharmacy' | 'admin' | 'elevator' | 'stairs' | 'restroom' | 'parking' | 'entrance' | 'convenience' | 'lobby';
  floorLevel: number;
  coordinates: { x: number; y: number }; // SVG 좌표계 (1200x800)
}
```

### Session
```typescript
interface Session {
  sessionId: string;
  patientUid: string;
  qrToken: string;
  status: 'waiting' | 'navigating' | 'completed';
  waypoints: {
    poiId: string;
    status: 'pending' | 'current' | 'completed';
  }[];
  currentWaypointIndex: number;
}
```

## 4. 실시간 동기화 플로우
1. **환자**: 익명 로그인 후 QR 토큰 생성 및 DB 등록 (`/qr_tokens/{token}`)
2. **의료진**: QR 스캔 후 토큰을 통해 환자 매칭, 동선 선택 후 세션 생성 (`/sessions/{sessionId}`)
3. **연결**: 환자 웹에서 상태 변화 감지 후 네비게이션 화면으로 자동 전환

## 5. 실내 지도 구현 가이드 (Leaflet)
- **좌표계**: `L.CRS.Simple` 사용
- **레이어**: 병원 층별 SVG를 `ImageOverlay`로 렌더링
- **경로**: POI 간 연결 그래프를 기반으로 Dijkstra 알고리즘을 통해 최단 경로 산출 및 Polyline 렌더링

## 6. 구현 로드맵 (Checklist)
- [ ] **Week 1-2**: Firebase 환경 설정 및 익명 인증, QR 매칭 로직 구현
- [ ] **Week 3-4**: 의료진용 QR 스캐너 및 동선 템플릿 UI 개발
- [ ] **Week 4-5**: 환자용 2D 실내 지도(Leaflet) 및 경로 안내 UI 개발
- [ ] **Week 5-6**: FCM 푸시 알림 통합 및 Vercel 배포

---
*본 명세서는 공유된 가이드라인을 기반으로 작성되었습니다.*