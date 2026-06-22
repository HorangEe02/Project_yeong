'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import {
  analyzeImage,
  buildSamplePayload,
  getWebReadiness,
  runApiReadinessSmoke,
  runDeploymentStatusSmoke,
  runSupabaseRuntimeSmoke,
} from '@/lib/api';
import type { AnalysisMode, ApiResult, TabKey } from '@/lib/types';

const shellTabs: Array<{ key: Exclude<TabKey, 'camera' | 'result'>; icon: string; label: string }> = [
  { key: 'home', icon: '♥', label: '홈' },
  { key: 'chat', icon: '●', label: '챗' },
  { key: 'score', icon: '◆', label: '점수' },
  { key: 'settings', icon: '⚙', label: '설정' },
];

type CameraFacingMode = 'environment' | 'user';
type StageStatus = 'success' | 'warning' | 'failed' | 'skipped' | 'unknown';

interface ResultSectionCard {
  key: string;
  title: string;
  body: string;
  items: string[];
  missing: boolean;
}

interface ResultStage {
  key: string;
  label: string;
  status: StageStatus;
}

interface ResultViewModel {
  summary: Array<[string, string]>;
  sections: ResultSectionCard[];
  stages: ResultStage[];
  notice: string;
}

/**
 * Interactive React version of the current Lemon-Aid mobile demo flow.
 *
 * Returns:
 *   A mobile-first OCR/YOLO/Ollama feature-test surface for Vercel.
 */
export function LemonWebApp() {
  const [tab, setTab] = useState<TabKey>('camera');
  const [mode, setMode] = useState<AnalysisMode>('supplement');
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [bearerToken, setBearerToken] = useState('');
  const [ocrProvider, setOcrProvider] = useState('configured');
  const [mealType, setMealType] = useState('unknown');
  const [busy, setBusy] = useState(false);
  const [cameraRunning, setCameraRunning] = useState(false);
  const [cameraFacing, setCameraFacing] = useState<CameraFacingMode>('environment');
  const [cameraMessage, setCameraMessage] = useState('웹 카메라 프리뷰를 시작하거나 이미지를 선택하세요.');
  const [result, setResult] = useState<ApiResult | null>(null);
  const [apiStatus, setApiStatus] = useState('아직 확인하지 않았습니다.');
  const [deploymentStatus, setDeploymentStatus] = useState('아직 확인하지 않았습니다.');
  const [supabaseStatus, setSupabaseStatus] = useState('아직 확인하지 않았습니다.');
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const autoCameraStartAttemptedRef = useRef(false);

  const readiness = useMemo(() => getWebReadiness(), []);
  const resultView = useMemo(() => buildResultViewModel(result?.payload, mode), [result, mode]);

  useEffect(() => {
    return () => {
      stopCameraStream(streamRef.current);
    };
  }, []);

  useEffect(() => {
    return () => {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
    };
  }, [previewUrl]);

  useEffect(() => {
    const stream = streamRef.current;
    const video = videoRef.current;
    if (!cameraRunning || !stream || !video) {
      return;
    }
    video.srcObject = stream;
    void video.play().catch((error: unknown) => {
      setCameraMessage(
        error instanceof Error
          ? `카메라 프리뷰 재생을 시작하지 못했습니다: ${error.message}`
          : '카메라 프리뷰 재생을 시작하지 못했습니다.',
      );
    });
  }, [cameraRunning]);

  useEffect(() => {
    if (
      tab !== 'camera' ||
      cameraRunning ||
      previewUrl ||
      streamRef.current ||
      autoCameraStartAttemptedRef.current
    ) {
      return;
    }
    autoCameraStartAttemptedRef.current = true;
    void startCamera(cameraFacing);
  }, [tab, cameraRunning, previewUrl, cameraFacing]);

  useEffect(() => {
    if (tab === 'camera') {
      return;
    }
    autoCameraStartAttemptedRef.current = false;
    stopCameraStream(streamRef.current);
    streamRef.current = null;
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setCameraRunning(false);
  }, [tab]);

  async function startCamera(nextFacing: CameraFacingMode = cameraFacing) {
    try {
      if (!navigator.mediaDevices?.getUserMedia) {
        setCameraMessage('현재 브라우저에서 카메라 프리뷰를 사용할 수 없습니다.');
        return;
      }
      setCameraMessage('카메라를 준비하고 있어요.');
      stopCameraStream(streamRef.current);
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: nextFacing } },
        audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setCameraRunning(true);
      setCameraMessage('실시간 프리뷰가 켜져 있습니다. 라벨을 가이드 안에 맞춘 뒤 캡처하세요.');
    } catch (error) {
      streamRef.current = null;
      setCameraRunning(false);
      setCameraMessage(
        error instanceof Error
          ? `카메라를 시작하지 못했습니다: ${error.message}`
          : '카메라를 시작하지 못했습니다.',
      );
    }
  }

  function stopCamera() {
    stopCameraStream(streamRef.current);
    streamRef.current = null;
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setCameraRunning(false);
    setCameraMessage('카메라 프리뷰가 중지되었습니다.');
  }

  async function toggleCameraFacing() {
    const nextFacing = cameraFacing === 'environment' ? 'user' : 'environment';
    setCameraFacing(nextFacing);
    if (cameraRunning) {
      await startCamera(nextFacing);
    }
  }

  function closeCamera() {
    stopCamera();
    setTab('home');
  }

  async function captureFrame() {
    const video = videoRef.current;
    if (!video || video.videoWidth === 0 || video.videoHeight === 0) {
      setCameraMessage('캡처할 프레임이 아직 준비되지 않았습니다.');
      return;
    }
    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const context = canvas.getContext('2d');
    if (!context) {
      setCameraMessage('브라우저 캔버스 초기화에 실패했습니다.');
      return;
    }
    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise<Blob | null>((resolve) => {
      canvas.toBlob(resolve, 'image/jpeg', 0.9);
    });
    if (!blob) {
      setCameraMessage('프레임을 이미지로 변환하지 못했습니다.');
      return;
    }
    const nextFile = new File([blob], `lemon-aid-web-${Date.now()}.jpg`, {
      type: 'image/jpeg',
    });
    setSelectedFile(nextFile);
    stopCameraStream(streamRef.current);
    streamRef.current = null;
    video.srcObject = null;
    setCameraRunning(false);
    setCameraMessage('프레임을 캡처했습니다. 분석하기를 눌러 API 흐름을 테스트하세요.');
  }

  function setSelectedFile(nextFile: File) {
    setFile(nextFile);
    setPreviewUrl((current) => {
      if (current) {
        URL.revokeObjectURL(current);
      }
      return URL.createObjectURL(nextFile);
    });
  }

  async function submitAnalysis() {
    if (!file) {
      setResult({ ok: false, message: '먼저 촬영하거나 이미지를 선택하세요.' });
      setTab('result');
      return;
    }
    setBusy(true);
    const response = await analyzeImage({
      mode,
      file,
      bearerToken,
      ocrProvider,
      imageRole: 'unknown',
      mealType,
    });
    setResult(response);
    setBusy(false);
    setTab('result');
  }

  function loadSample() {
    setResult({ ok: true, status: 200, payload: buildSamplePayload(mode) });
    setTab('result');
  }

  async function checkSupabase() {
    setSupabaseStatus('Supabase runtime 연결을 확인하는 중입니다.');
    setSupabaseStatus(await runSupabaseRuntimeSmoke());
  }

  async function checkApiReadiness() {
    setApiStatus('API readiness를 확인하는 중입니다.');
    setApiStatus(await runApiReadinessSmoke());
  }

  async function checkDeploymentStatus() {
    setDeploymentStatus('배포 준비 상태를 확인하는 중입니다.');
    setDeploymentStatus(await runDeploymentStatusSmoke());
  }

  return (
    <main className={`page ${tab === 'camera' ? 'page-camera' : ''}`}>
      <div className="stage">
        <section className="phone" aria-label="Lemon AID mobile web app">
          <div className={`phone-screen ${tab === 'camera' ? 'phone-screen-camera' : ''}`}>
            {tab !== 'camera' && tab !== 'home' && (
              <header className="mobile-top">
                <div className="brand">
                  <span>레몬</span>
                  <i aria-hidden="true" />
                  에이드
                </div>
                <div className="status-pill">Web</div>
              </header>
            )}
            <div
              className={`mobile-content ${tab === 'camera' ? 'mobile-content-camera' : ''} ${
                tab === 'home' ? 'mobile-content-home' : ''
              }`}
            >
              {tab === 'home' && <HomePanel onOpenCamera={() => setTab('camera')} />}
              {tab === 'chat' && <ChatPanel />}
              {tab === 'camera' && (
                <CameraPanel
                  mode={mode}
                  setMode={setMode}
                  previewUrl={previewUrl}
                  videoRef={videoRef}
                  cameraRunning={cameraRunning}
                  cameraFacing={cameraFacing}
                  cameraMessage={cameraMessage}
                  ocrProvider={ocrProvider}
                  setOcrProvider={setOcrProvider}
                  mealType={mealType}
                  setMealType={setMealType}
                  busy={busy}
                  hasSelectedFile={file !== null}
                  onFileSelected={setSelectedFile}
                  onStartCamera={startCamera}
                  onStopCamera={stopCamera}
                  onCaptureFrame={captureFrame}
                  onToggleFacing={toggleCameraFacing}
                  onClose={closeCamera}
                  onSubmit={submitAnalysis}
                  onSample={loadSample}
                />
              )}
              {tab === 'result' && (
                <ResultPanel result={result} viewModel={resultView} mode={mode} />
              )}
              {tab === 'score' && <ScorePanel />}
              {tab === 'settings' && (
                <SettingsPanel
                  apiBaseUrl={readiness.apiBaseUrl}
                  supabaseConfigured={readiness.supabaseConfigured}
                  bearerToken={bearerToken}
                  setBearerToken={setBearerToken}
                  apiStatus={apiStatus}
                  onCheckApiReadiness={checkApiReadiness}
                  deploymentStatus={deploymentStatus}
                  onCheckDeploymentStatus={checkDeploymentStatus}
                  supabaseStatus={supabaseStatus}
                  onCheckSupabase={checkSupabase}
                />
              )}
            </div>
            {tab !== 'camera' && (
              <ShellNav activeTab={tab} onTabChange={setTab} onCameraTap={() => setTab('camera')} />
            )}
          </div>
        </section>
      </div>
    </main>
  );
}

function HomePanel({ onOpenCamera }: { onOpenCamera: () => void }) {
  const today = new Intl.DateTimeFormat('ko-KR', {
    month: 'long',
    day: 'numeric',
    weekday: 'short',
  }).format(new Date());

  return (
    <section className="home-screen">
      <div className="home-brand-header">
        <div className="home-wordmark">
          레몬<span />에이드
        </div>
        <div className="home-icons" aria-label="홈 바로가기">
          <button type="button" aria-label="캘린더">
            ◷
          </button>
          <button type="button" aria-label="알림">
            ●
          </button>
          <button type="button" aria-label="설정">
            ♙
          </button>
        </div>
      </div>

      <div className="home-body">
        <div className="health-card">
          <div className="date-row">
            <button type="button" aria-label="이전 날">
              ‹
            </button>
            <strong>{today}</strong>
            <button type="button" aria-label="다음 날">
              ›
            </button>
          </div>
          <div className="health-main">
            <div>
              <span className="eyebrow">오늘의 건강 점수</span>
              <h1>78점</h1>
              <p>영양제와 식단 이미지를 촬영해 개인별 권장·주의 사항을 확인하세요.</p>
            </div>
            <button type="button" onClick={onOpenCamera}>
              촬영
            </button>
          </div>
        </div>

        <div className="output-grid">
          <InfoTile value="OCR" label="성분·함량" />
          <InfoTile value="YOLO" label="식단 인식" />
          <InfoTile value="LLM" label="권장·경고" />
          <InfoTile value="DB" label="복용 이력" />
        </div>

        <div className="schedule-card">
          <div>
            <b>복용 알림</b>
            <span>오늘 저녁 · 오메가3 확인 필요</span>
          </div>
          <strong>대기</strong>
        </div>

        <div className="recent-card">
          <b>최근 분석</b>
          <p>샘플 결과 또는 실제 OCR/YOLO 분석 후 결과 카드에서 확인합니다.</p>
        </div>
      </div>
    </section>
  );
}

function ChatPanel() {
  return (
    <section className="panel grid">
      <div className="result-card">
        <h2 className="section-title">AI 상담</h2>
        <p>OCR/YOLO 분석 결과를 LLM WIKI와 사용자 정보 DB에 연결하는 상담 탭입니다.</p>
      </div>
      <div className="chat-bubble">비타민 D와 칼슘을 같이 먹어도 될까요?</div>
      <div className="chat-bubble assistant">
        현재 복용 이력과 함량을 먼저 확인한 뒤 권장, 주의, 의사 상담 필요 여부를 분리해 안내합니다.
      </div>
    </section>
  );
}

function ScorePanel() {
  return (
    <section className="panel grid">
      <div className="score-hero">
        <span>건강 루틴 점수</span>
        <strong>78</strong>
        <p>식단 기록, 영양제 복용, 주의 성분 확인 여부를 통합한 웹 검증 카드입니다.</p>
      </div>
      <div className="metric-grid">
        <InfoTile value="2" label="주의 성분" />
        <InfoTile value="4" label="확인된 영양소" />
      </div>
    </section>
  );
}

function CameraPanel(props: {
  mode: AnalysisMode;
  setMode: (mode: AnalysisMode) => void;
  previewUrl: string | null;
  videoRef: React.RefObject<HTMLVideoElement | null>;
  cameraRunning: boolean;
  cameraFacing: CameraFacingMode;
  cameraMessage: string;
  ocrProvider: string;
  setOcrProvider: (value: string) => void;
  mealType: string;
  setMealType: (value: string) => void;
  busy: boolean;
  hasSelectedFile: boolean;
  onFileSelected: (file: File) => void;
  onStartCamera: () => void;
  onStopCamera: () => void;
  onCaptureFrame: () => void;
  onToggleFacing: () => void;
  onClose: () => void;
  onSubmit: () => void;
  onSample: () => void;
}) {
  const isSupplement = props.mode === 'supplement';
  const title = isSupplement ? '영양제 촬영' : '식단 촬영';
  const hint = isSupplement
    ? '성분표를 테두리 안에 맞춰주세요'
    : '음식이 테두리 안에 들어오게 맞춰주세요';
  const emptyMessage = props.previewUrl
    ? '선택한 이미지를 확인한 뒤 분석하세요.'
    : props.cameraMessage;

  return (
    <section className="camera-capture" aria-label={title}>
      <div className="camera-live">
        {props.cameraRunning ? (
          <video ref={props.videoRef} playsInline muted />
        ) : props.previewUrl ? (
          <img src={props.previewUrl} alt="선택된 분석 이미지 미리보기" />
        ) : (
          <div className="camera-empty">
            <div className="camera-empty-icon" aria-hidden="true" />
            <p>{emptyMessage}</p>
            <span>{props.cameraMessage}</span>
          </div>
        )}
      </div>

      <div className="camera-shade" aria-hidden="true" />

      <div className="camera-statusbar" aria-hidden="true">
        <span>9:49</span>
        <span className="camera-status-icons">
          <i />
          <i />
          <i />
        </span>
      </div>

      <div className="capture-topbar">
        <button className="round-icon" type="button" aria-label="닫기" onClick={props.onClose}>
          ×
        </button>
        <h1>{title}</h1>
        <button
          className="round-icon"
          type="button"
          aria-label={props.cameraFacing === 'environment' ? '전면 카메라로 전환' : '후면 카메라로 전환'}
          onClick={props.onToggleFacing}
        >
          ↻
        </button>
      </div>

      <div className="guide-area" aria-hidden="true">
        <div className={`guide-frame ${isSupplement ? 'guide-supplement' : 'guide-meal'}`}>
          <span className="guide-corner tl" />
          <span className="guide-corner tr" />
          <span className="guide-corner bl" />
          <span className="guide-corner br" />
        </div>
      </div>

      <div className="capture-bottom">
        <div className="capture-hint">
          <span>▣</span>
          {hint}
        </div>

        <div className="mode-switch" role="tablist" aria-label="촬영 모드">
          <button
            type="button"
            role="tab"
            aria-selected={isSupplement}
            onClick={() => props.setMode('supplement')}
          >
            영양제
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={!isSupplement}
            onClick={() => props.setMode('meal')}
          >
            식단
          </button>
        </div>

        <div className="capture-actions">
          <label className="gallery-button" aria-label="이미지 선택">
            <span className="gallery-icon" aria-hidden="true" />
            <input
              hidden
              type="file"
              accept="image/*"
              capture="environment"
              onChange={(event) => {
                const selected = event.currentTarget.files?.[0];
                if (selected) props.onFileSelected(selected);
              }}
            />
          </label>

          <button
            className={`shutter-button ${props.cameraRunning ? 'is-running' : ''}`}
            type="button"
            aria-label={props.cameraRunning ? '프레임 캡처' : '프리뷰 시작'}
            onClick={props.cameraRunning ? props.onCaptureFrame : props.onStartCamera}
          >
            <span />
          </button>

          <button
            className="analysis-button"
            type="button"
            disabled={props.busy || !props.hasSelectedFile}
            onClick={props.onSubmit}
          >
            {props.busy ? '분석 중' : '분석'}
          </button>
        </div>
      </div>
    </section>
  );
}

function ResultPanel({
  result,
  viewModel,
  mode,
}: {
  result: ApiResult | null;
  viewModel: ResultViewModel;
  mode: AnalysisMode;
}) {
  if (!result) {
    return (
      <section className="panel result-card">
        <h2 className="section-title">분석 결과</h2>
        <p>아직 분석 결과가 없습니다. 촬영 탭에서 이미지를 분석하거나 샘플 결과를 확인하세요.</p>
      </section>
    );
  }
  return (
    <section className="panel grid">
      <div className="result-card">
        <h2 className="section-title">{mode === 'meal' ? '식단 분석 결과' : '영양제 분석 결과'}</h2>
        {!result.ok && <div className="banner">요청 실패: {result.message}</div>}
        <div className="status-list">
          {viewModel.summary.map(([label, value]) => (
            <div className="status-item" key={label}>
              <span>{label}</span>
              <b>{value}</b>
            </div>
          ))}
        </div>
      </div>
      <div className="result-card">
        <h2 className="section-title">파이프라인 상태</h2>
        <div className="pipeline-leds" aria-label="OCR YOLO Ollama status">
          {viewModel.stages.map((stage) => (
            <div className="pipeline-led" key={stage.key}>
              <span className={`led led-${stage.status}`} aria-hidden="true" />
              <b>{stage.label}</b>
              <em>{stage.status}</em>
            </div>
          ))}
        </div>
      </div>
      <div className="result-card">
        <h2 className="section-title">{mode === 'meal' ? '식단 정보' : '확인된 정보'}</h2>
        <div className="section-card-grid">
          {viewModel.sections.map((section) => (
            <article className={`section-card ${section.missing ? 'is-missing' : ''}`} key={section.key}>
              <div>
                <span>{section.missing ? '추가 촬영 필요' : '확인됨'}</span>
                <h3>{section.title}</h3>
              </div>
              <p>{section.body}</p>
              {section.items.length > 0 && (
                <ul>
                  {section.items.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              )}
            </article>
          ))}
        </div>
      </div>
      <div className="banner">{viewModel.notice}</div>
    </section>
  );
}

function SettingsPanel(props: {
  apiBaseUrl: string;
  supabaseConfigured: boolean;
  bearerToken: string;
  setBearerToken: (value: string) => void;
  apiStatus: string;
  onCheckApiReadiness: () => void;
  deploymentStatus: string;
  onCheckDeploymentStatus: () => void;
  supabaseStatus: string;
  onCheckSupabase: () => void;
}) {
  return (
    <section className="panel grid">
      <div className="result-card">
        <h2 className="section-title">Vercel / API 연결</h2>
        <div className="status-list">
          <div className="status-item">
            <span>Framework</span>
            <b>Next.js on Vercel</b>
          </div>
          <div className="status-item">
            <span>API Base</span>
            <b>{props.apiBaseUrl}</b>
          </div>
          <div className="status-item">
            <span>Readiness</span>
            <b>{props.apiStatus}</b>
          </div>
          <div className="status-item">
            <span>Deploy Check</span>
            <b>{props.deploymentStatus}</b>
          </div>
        </div>
        <div className="field">
          <label htmlFor="bearer-token">테스트용 Bearer token</label>
          <input
            id="bearer-token"
            type="password"
            value={props.bearerToken}
            autoComplete="off"
            placeholder="선택 사항"
            onChange={(event) => props.setBearerToken(event.target.value)}
          />
        </div>
        <div className="controls">
          <button className="button primary" type="button" onClick={props.onCheckApiReadiness}>
            API 확인
          </button>
          <button className="button secondary" type="button" onClick={props.onCheckDeploymentStatus}>
            배포 확인
          </button>
        </div>
      </div>
      <div className="result-card">
        <h2 className="section-title">Supabase 연결</h2>
        <div className="status-list">
          <div className="status-item">
            <span>환경변수</span>
            <b>{props.supabaseConfigured ? 'configured' : 'not set'}</b>
          </div>
          <div className="status-item">
            <span>Runtime Smoke</span>
            <b>{props.supabaseStatus}</b>
          </div>
        </div>
        <div className="controls">
          <button className="button primary" type="button" onClick={props.onCheckSupabase}>
            연결 확인
          </button>
        </div>
      </div>
    </section>
  );
}

function ShellNav({
  activeTab,
  onTabChange,
  onCameraTap,
}: {
  activeTab: TabKey;
  onTabChange: (tab: TabKey) => void;
  onCameraTap: () => void;
}) {
  const leftTabs = shellTabs.slice(0, 2);
  const rightTabs = shellTabs.slice(2);

  return (
    <nav className="shell-nav" aria-label="Lemon AID mobile shell tabs">
      <div className="shell-nav-row">
        {leftTabs.map((item) => (
          <ShellTabButton key={item.key} item={item} active={activeTab === item.key} onClick={onTabChange} />
        ))}
        <div className="camera-slot" aria-hidden="true" />
        {rightTabs.map((item) => (
          <ShellTabButton key={item.key} item={item} active={activeTab === item.key} onClick={onTabChange} />
        ))}
      </div>
      <button className="shell-camera-fab" type="button" aria-label="촬영 열기" onClick={onCameraTap}>
        +
      </button>
    </nav>
  );
}

function ShellTabButton({
  item,
  active,
  onClick,
}: {
  item: (typeof shellTabs)[number];
  active: boolean;
  onClick: (tab: TabKey) => void;
}) {
  return (
    <button type="button" aria-selected={active} onClick={() => onClick(item.key)}>
      <span>{item.icon}</span>
      <b>{item.label}</b>
    </button>
  );
}

function InfoTile({ value, label }: { value: string; label: string }) {
  return (
    <div className="tile">
      <b>{value}</b>
      <span>{label}</span>
    </div>
  );
}

function buildResultViewModel(payload: unknown, mode: AnalysisMode): ResultViewModel {
  if (mode === 'meal') {
    return buildMealResultViewModel(payload);
  }
  return buildSupplementResultViewModel(payload);
}

/**
 * Builds the supplement result cards shown to users after OCR analysis.
 *
 * Args:
 *   payload: Backend supplement analysis response.
 *
 * Returns:
 *   User-facing section cards, summary rows, and LED statuses.
 */
function buildSupplementResultViewModel(payload: unknown): ResultViewModel {
  if (!payload || typeof payload !== 'object') {
    return {
      summary: [['상태', '결과 없음']],
      sections: buildEmptySupplementSections([]),
      stages: buildPipelineStages(undefined),
      notice: '분석 결과가 없어요. 이미지를 촬영하거나 샘플 결과를 확인하세요.',
    };
  }
  const record = payload as Record<string, unknown>;
  const missingSections = readStringArray(record.missing_required_sections);
  const product = readNestedString(record, ['parsed_product', 'product_name'])
    ?? readNestedString(record, ['product_candidate', 'display_name']);
  const ingredientItems = readIngredientLines(record.ingredient_candidates);
  const intakeMethod = readNestedString(record, ['intake_method', 'text']);
  const precautions = readPrecautionLines(record.precautions);
  const warnings = readStringArray(record.warning_codes ?? record.warnings);
  const sections = [
    {
      key: 'product_name',
      title: '영양제명',
      body: product ?? '제품명이 보이게 한 장 더 촬영해주세요.',
      items: [],
      missing: !product || missingSections.includes('product_name'),
    },
    {
      key: 'supplement_facts',
      title: '상세 성분 및 함량',
      body: ingredientItems.length > 0
        ? '성분표에서 읽은 후보를 확인하세요.'
        : '성분표와 함량이 보이게 한 장 더 촬영해주세요.',
      items: ingredientItems,
      missing: ingredientItems.length === 0 || missingSections.includes('supplement_facts'),
    },
    {
      key: 'intake_method',
      title: '섭취 방법',
      body: intakeMethod ?? '섭취 방법 문구가 보이게 한 장 더 촬영해주세요.',
      items: [],
      missing: !intakeMethod || missingSections.includes('intake_method'),
    },
    {
      key: 'precautions',
      title: '섭취 시 주의사항',
      body: precautions.length > 0
        ? '라벨에 보이는 주의사항 문구입니다.'
        : '주의사항 문구가 보이게 한 장 더 촬영해주세요.',
      items: precautions,
      missing: precautions.length === 0 || missingSections.includes('precautions'),
    },
  ];

  const summary: Array<[string, string]> = [
    ['분석 ID', stringify(record.analysis_id ?? 'sample')],
    ['제품명', product ?? '확인 필요'],
    ['성분 후보', String(ingredientItems.length)],
    ['부족 섹션', missingSections.join(', ') || '없음'],
    ['Warning', warnings.join(', ') || '없음'],
  ];
  return {
    summary,
    sections,
    stages: buildPipelineStages(asRecord(record.pipeline_metadata)),
    notice: missingSections.length > 0
      ? '누락된 항목은 해당 카드 안의 안내대로 한 장 더 촬영하면 병합 분석에 사용할 수 있어요.'
      : '확인된 정보는 사용자 검토 후 복용 이력과 맞춤 판단에 반영됩니다.',
  };
}

/**
 * Builds result cards for the meal YOLO flow.
 *
 * Args:
 *   payload: Backend meal image analysis response.
 *
 * Returns:
 *   User-facing meal result view model.
 */
function buildMealResultViewModel(payload: unknown): ResultViewModel {
  if (!payload || typeof payload !== 'object') {
    return {
      summary: [['상태', '결과 없음']],
      sections: [
        {
          key: 'meal',
          title: '식단 후보',
          body: '음식 사진을 촬영하면 후보가 표시됩니다.',
          items: [],
          missing: true,
        },
      ],
      stages: buildPipelineStages(undefined),
      notice: '식단 분석 결과가 없어요. 이미지를 촬영하거나 샘플 결과를 확인하세요.',
    };
  }
  const record = payload as Record<string, unknown>;
  const foodItems = readFoodLines(record.food_candidates);
  return {
    summary: [
      ['분석 ID', stringify(record.analysis_id ?? 'sample')],
      ['음식 후보', String(foodItems.length)],
      ['Warning', readStringArray(record.warning_codes).join(', ') || '없음'],
    ],
    sections: [
      {
        key: 'meal_candidates',
        title: '식단 후보',
        body: foodItems.length > 0
          ? 'YOLO/분류 결과를 사용자 확인 후 식단 분석에 반영합니다.'
          : '음식이 선명하게 보이게 다시 촬영해주세요.',
        items: foodItems,
        missing: foodItems.length === 0,
      },
    ],
    stages: [
      {
        key: 'detector',
        label: 'YOLO',
        status: readNestedBoolean(record, ['pipeline_metadata', 'detector_used']) ? 'success' : 'skipped',
      },
      {
        key: 'classifier',
        label: 'Classifier',
        status: readNestedBoolean(record, ['pipeline_metadata', 'classifier_used']) ? 'success' : 'skipped',
      },
    ],
    notice: '식단 후보는 사용자 확인 후 영양 분석에 반영합니다.',
  };
}

function buildEmptySupplementSections(missingSections: string[]): ResultSectionCard[] {
  return [
    ['product_name', '영양제명', '제품명이 보이게 한 장 더 촬영해주세요.'],
    ['supplement_facts', '상세 성분 및 함량', '성분표와 함량이 보이게 한 장 더 촬영해주세요.'],
    ['intake_method', '섭취 방법', '섭취 방법 문구가 보이게 한 장 더 촬영해주세요.'],
    ['precautions', '섭취 시 주의사항', '주의사항 문구가 보이게 한 장 더 촬영해주세요.'],
  ].map(([key, title, body]) => ({
    key,
    title,
    body,
    items: [],
    missing: missingSections.length === 0 || missingSections.includes(key),
  }));
}

function buildPipelineStages(metadata: Record<string, unknown> | undefined): ResultStage[] {
  return [
    { key: 'ocr', label: 'OCR', status: readStageStatus(metadata?.ocr_status) },
    { key: 'vision', label: 'YOLO', status: readStageStatus(metadata?.vision_status) },
    { key: 'llm', label: 'Ollama', status: readStageStatus(metadata?.llm_status) },
  ];
}

function readStageStatus(value: unknown): StageStatus {
  return value === 'success' || value === 'warning' || value === 'failed' || value === 'skipped'
    ? value
    : 'unknown';
}

function readIngredientLines(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((item) => {
    if (!item || typeof item !== 'object') return [];
    const record = item as Record<string, unknown>;
    const name = stringify(record.display_name ?? record.name ?? record.ingredient_name);
    if (name === '-') return [];
    const amount = stringify(record.amount);
    const unit = stringify(record.unit);
    return [`${name}${amount === '-' ? '' : ` ${amount}`}${unit === '-' ? '' : ` ${unit}`}`];
  });
}

function readFoodLines(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((item) => {
    if (!item || typeof item !== 'object') return [];
    const record = item as Record<string, unknown>;
    const name = stringify(record.display_name ?? record.name);
    return name === '-' ? [] : [name];
  });
}

function readPrecautionLines(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((item) => {
    if (typeof item === 'string' && item.trim()) return [item.trim()];
    if (!item || typeof item !== 'object') return [];
    const text = (item as Record<string, unknown>).text;
    return typeof text === 'string' && text.trim() ? [text.trim()] : [];
  });
}

function readStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === 'string' && item.trim().length > 0);
}

function asRecord(value: unknown): Record<string, unknown> | undefined {
  return value && typeof value === 'object' ? value as Record<string, unknown> : undefined;
}

function readNestedString(record: Record<string, unknown>, path: string[]): string | undefined {
  let value: unknown = record;
  for (const key of path) {
    if (!value || typeof value !== 'object') {
      return undefined;
    }
    value = (value as Record<string, unknown>)[key];
  }
  return typeof value === 'string' ? value : undefined;
}

function readNestedBoolean(record: Record<string, unknown>, path: string[]): boolean | undefined {
  let value: unknown = record;
  for (const key of path) {
    if (!value || typeof value !== 'object') {
      return undefined;
    }
    value = (value as Record<string, unknown>)[key];
  }
  return typeof value === 'boolean' ? value : undefined;
}

function stringify(value: unknown): string {
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  return '-';
}

function stopCameraStream(stream: MediaStream | null) {
  stream?.getTracks().forEach((track) => track.stop());
}
