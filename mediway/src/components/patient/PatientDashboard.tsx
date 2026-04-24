import { useState, useCallback, useMemo, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { QRDisplay } from './QRDisplay';
import { RouteProgress } from './RouteProgress';
import { DestinationCard } from './DestinationCard';
import { ArrivalButton } from './ArrivalButton';
import { CompletionScreen } from './CompletionScreen';
import { Loading } from '@/components/common/Loading';
import { HospitalMapContainer } from '@/components/map/HospitalMapContainer';
import { computeRoute } from '@/services/pathfinding';
import { createQRToken, markWaypointArrived } from '@/services/session';
import { getCurrentUid, initAnonymousAuth } from '@/services/auth';
import { isFirebaseConfigured } from '@/config/firebase';
import { useSession } from '@/hooks/useSession';
import { NotificationMessages } from '@/services/notification';
import { navigationGraph, getPOIById } from '@/data/hospital';
import { useMapStore } from '@/stores/mapStore';
import type { Waypoint, WaypointStatus } from '@/types/session';
import type { MapHighlights } from '@/types/map-renderer';
import type { RouteResult } from '@/types/navigation';

// localStorage 키
const LS_QR_TOKEN = 'mediway_qr_token';
const LS_SESSION_ID = 'mediway_session_id';

/** 데모용 시뮬레이션 경유지 (Firebase 미설정 시 폴백) */
const DEMO_WAYPOINT_IDS = ['lab_blood', 'admin_billing', 'pharmacy_main', 'entrance_main'];

export function PatientDashboard() {
  const { sessionId: _urlSessionId } = useParams<{ sessionId?: string }>();

  // QR 토큰 — localStorage에서 복원 시도
  const [qrToken, setQrToken] = useState<string | null>(() => {
    return localStorage.getItem(LS_QR_TOKEN);
  });

  // Firebase 실시간 구독
  const { session, qrTokenData, isConnected } = useSession(qrToken);

  // 로컬 폴백 상태 (Firebase 미설정 시)
  const [localWaypoints, setLocalWaypoints] = useState<Waypoint[]>([]);
  const [localCurrentIndex, setLocalCurrentIndex] = useState(0);
  const [routeResult, setRouteResult] = useState<RouteResult | null>(null);
  const [isLocalMode, setIsLocalMode] = useState(!isFirebaseConfigured());

  const setCurrentFloor = useMapStore((s) => s.setCurrentFloor);

  // === Firebase 세션 데이터에서 파생 ===
  const waypoints: Waypoint[] = useMemo(() => {
    if (isLocalMode) return localWaypoints;
    if (!session?.waypoints) return [];
    // Firebase에서 배열이 객체로 저장될 수 있으므로 정규화
    return Array.isArray(session.waypoints)
      ? session.waypoints
      : Object.values(session.waypoints);
  }, [isLocalMode, localWaypoints, session?.waypoints]);

  const currentIndex: number = useMemo(() => {
    if (isLocalMode) return localCurrentIndex;
    return session?.currentWaypointIndex ?? 0;
  }, [isLocalMode, localCurrentIndex, session?.currentWaypointIndex]);

  const sessionStatus = useMemo(() => {
    if (isLocalMode) {
      if (localWaypoints.length === 0) return 'waiting';
      if (localWaypoints.every((wp) => wp.status === 'completed')) return 'completed';
      return 'navigating';
    }
    return session?.status ?? 'waiting';
  }, [isLocalMode, localWaypoints, session?.status]);

  // === 상태 머신 파생 ===
  const state: 'qr_display' | 'navigating' | 'completed' = useMemo(() => {
    if (sessionStatus === 'completed') return 'completed';
    if (sessionStatus === 'navigating' && waypoints.length > 0) return 'navigating';
    return 'qr_display';
  }, [sessionStatus, waypoints]);

  // === QR 토큰 생성 + Firebase 등록 ===
  const handleTokenGenerated = useCallback(
    async (token: string) => {
      setQrToken(token);
      localStorage.setItem(LS_QR_TOKEN, token);

      if (isFirebaseConfigured()) {
        // 인증 완료 보장 — 아직 uid가 없으면 인증 재시도
        let uid = getCurrentUid();
        if (!uid) {
          const user = await initAnonymousAuth();
          uid = user?.uid ?? null;
        }
        if (uid) {
          await createQRToken(token, uid);
        }
      }
    },
    [],
  );

  // === Firebase 세션 수신 시 경로 계산 ===
  useEffect(() => {
    if (state !== 'navigating' || waypoints.length === 0) return;

    const poiIds = waypoints.map((wp) => wp.poiId);
    const route = computeRoute(navigationGraph, poiIds);
    if (route) {
      setRouteResult(route);
      // sessionId를 localStorage에 저장 (복원용)
      if (session?.sessionId) {
        localStorage.setItem(LS_SESSION_ID, session.sessionId);
      }
    }
  }, [state, waypoints, session?.sessionId]);

  // === 세션 수신 시 알림 + 자동 층 전환 ===
  useEffect(() => {
    if (state === 'navigating' && waypoints.length > 0 && routeResult) {
      const currentPoi = getPOIById(waypoints[currentIndex]?.poiId);
      if (currentPoi) {
        setCurrentFloor(currentPoi.floorLevel);
      }
    }
  }, [state, currentIndex, waypoints, routeResult, setCurrentFloor]);

  // === 세션 상태 변경 시 알림 ===
  useEffect(() => {
    if (!isLocalMode && session?.status === 'navigating' && routeResult && currentIndex === 0) {
      NotificationMessages.routeReceived();
    }
  }, [isLocalMode, session?.status, routeResult, currentIndex]);

  // === "도착" 버튼 처리 ===
  const handleArrival = useCallback(async () => {
    if (isLocalMode) {
      // 로컬 폴백
      setLocalWaypoints((prev) =>
        prev.map((wp, i) => {
          if (i === localCurrentIndex)
            return { ...wp, status: 'completed' as WaypointStatus, arrivedAt: Date.now() };
          if (i === localCurrentIndex + 1)
            return { ...wp, status: 'current' as WaypointStatus };
          return wp;
        }),
      );
      const nextIdx = localCurrentIndex + 1;
      setLocalCurrentIndex(nextIdx);
      if (nextIdx < localWaypoints.length) {
        const nextPoi = getPOIById(localWaypoints[nextIdx].poiId);
        if (nextPoi) setCurrentFloor(nextPoi.floorLevel);
        NotificationMessages.nextDestination(nextPoi?.name ?? '');
      } else {
        NotificationMessages.allCompleted();
      }
    } else if (session) {
      // Firebase 연동
      await markWaypointArrived(
        session.sessionId,
        currentIndex,
        waypoints.length,
      );
      const nextIdx = currentIndex + 1;
      if (nextIdx < waypoints.length) {
        NotificationMessages.nextDestination(
          getPOIById(waypoints[nextIdx].poiId)?.name ?? '',
        );
      } else {
        NotificationMessages.allCompleted();
      }
    }
  }, [isLocalMode, localCurrentIndex, localWaypoints, session, currentIndex, waypoints, setCurrentFloor]);

  // === 초기화 (새 동선 받기) ===
  const handleReset = useCallback(() => {
    setQrToken(null);
    setLocalWaypoints([]);
    setLocalCurrentIndex(0);
    setRouteResult(null);
    setCurrentFloor(1);
    localStorage.removeItem(LS_QR_TOKEN);
    localStorage.removeItem(LS_SESSION_ID);
  }, [setCurrentFloor]);

  // === 로컬 폴백: 시뮬레이션 ===
  const handleSimulateReceive = useCallback(() => {
    const route = computeRoute(navigationGraph, DEMO_WAYPOINT_IDS);
    if (!route) return;
    setLocalWaypoints(
      DEMO_WAYPOINT_IDS.map((poiId, i) => ({
        poiId,
        status: (i === 0 ? 'current' : 'pending') as WaypointStatus,
      })),
    );
    setLocalCurrentIndex(0);
    setRouteResult(route);
    setIsLocalMode(true);
    const firstPoi = getPOIById(DEMO_WAYPOINT_IDS[0]);
    if (firstPoi) setCurrentFloor(firstPoi.floorLevel);
    NotificationMessages.routeReceived();
  }, [setCurrentFloor]);

  // === 경로 세그먼트 계산 ===
  const currentSegments = useMemo(() => {
    if (!routeResult || currentIndex >= routeResult.legs.length) return null;
    return routeResult.legs[currentIndex];
  }, [routeResult, currentIndex]);

  const currentDestination = useMemo(() => {
    if (currentIndex >= waypoints.length) return null;
    return getPOIById(waypoints[currentIndex].poiId);
  }, [waypoints, currentIndex]);

  const floorInstruction = useMemo(() => {
    if (!currentSegments) return undefined;
    const transition = currentSegments.segments.find((s) => s.floorTransition);
    return transition?.floorTransition?.instruction;
  }, [currentSegments]);

  const highlights: MapHighlights | undefined = useMemo(() => {
    if (state !== 'navigating' || waypoints.length === 0) return undefined;
    return {
      currentPoiId: waypoints[currentIndex]?.poiId,
      completedPoiIds: waypoints.filter((wp) => wp.status === 'completed').map((wp) => wp.poiId),
      endPoiId: waypoints[waypoints.length - 1]?.poiId,
    };
  }, [state, waypoints, currentIndex]);

  const currentFloor = useMapStore((s) => s.currentFloor);
  const currentFloorSegment = useMemo(() => {
    if (!currentSegments) return undefined;
    return currentSegments.segments.find(
      (s) => s.floorLevel === currentFloor && s.coordinates.length > 0,
    );
  }, [currentSegments, currentFloor]);

  // === 렌더링 ===

  if (state === 'completed') {
    return <CompletionScreen totalSteps={waypoints.length} onReset={handleReset} />;
  }

  if (state === 'qr_display') {
    // QR 토큰이 matched 상태인데 세션 로딩 중
    if (qrTokenData?.status === 'matched' && !session) {
      return <Loading message="동선 정보를 불러오는 중..." />;
    }

    return (
      <div className="flex flex-col gap-6">
        <QRDisplay onTokenGenerated={handleTokenGenerated} />

        {/* Firebase 미설정 시 로컬 시뮬레이션 폴백 */}
        {!isFirebaseConfigured() && (
          <div className="rounded-xl bg-surface-container-low p-4 text-center">
            <p className="mb-2 text-xs text-on-surface-variant">
              Firebase 미설정 — 로컬 데모 모드
            </p>
            <button
              onClick={handleSimulateReceive}
              className="rounded-xl bg-gradient-to-r from-primary to-primary-container px-6 py-3 text-sm font-semibold text-white transition-transform active:scale-[0.97]"
            >
              동선 수신 시뮬레이션
            </button>
          </div>
        )}

        {/* Firebase 연결 상태 표시 */}
        {isFirebaseConfigured() && (
          <div className="flex items-center justify-center gap-2 text-xs text-on-surface-variant">
            <div className={`h-2 w-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-amber-500'}`} />
            {isConnected ? '서버 연결됨 — 의료진 스캔 대기 중' : '서버 연결 중...'}
          </div>
        )}
      </div>
    );
  }

  // state === 'navigating'
  return (
    <div className="flex flex-col gap-4">
      <RouteProgress waypoints={waypoints} currentIndex={currentIndex} />

      {currentDestination && currentSegments && (
        <DestinationCard
          destination={currentDestination}
          segmentTime={currentSegments.totalTime}
          segmentDistance={currentSegments.totalDistance}
          floorInstruction={floorInstruction}
          currentLeg={currentIndex}
          totalLegs={waypoints.length}
        />
      )}

      <div className="rounded-2xl bg-surface-container-lowest shadow-ambient">
        <div className="flex items-center justify-between px-4 pt-4">
          <h3 className="flex items-center gap-2 text-sm font-semibold text-on-surface">
            <span className="text-primary">▶</span> Current Indoor View
          </h3>
        </div>
        <div className="p-2">
          <HospitalMapContainer pathSegment={currentFloorSegment} highlights={highlights} />
        </div>
      </div>

      {currentDestination && <ArrivalButton onArrival={handleArrival} />}
    </div>
  );
}
