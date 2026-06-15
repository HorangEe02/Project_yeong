// profile-llm.tsx — H1 v4.0 · 전체 LLM 모델 비교 페이지.
// 9개 모델 카드 그리드 + 필터 (전체/빠름/한국어/비전/고품질) + 휴리스틱 추천.
// 디자인 시스템 v3.5: lg-page + lg-hero + lg-tabs + lg-card.

import { useEffect, useMemo, useState } from 'react';
import { ArrowLeft, Sparkles, Building2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '@store/auth';
import { ModelComparisonCard } from '@components/common/ModelComparisonCard';
import {
  fetchModelCatalogCached,
  recommendModel,
  type ModelCatalogItem,
  type ModelRecommendResponse,
} from '@api/models';

type FilterKey = 'all' | 'fast' | 'korean' | 'vision' | 'high_quality';

const FILTERS: { key: FilterKey; label_en: string; label_ko: string }[] = [
  { key: 'all',          label_en: 'ALL',          label_ko: '전체' },
  { key: 'fast',         label_en: 'FAST',         label_ko: '빠름' },
  { key: 'korean',       label_en: 'KOREAN',       label_ko: '한국어 특화' },
  { key: 'vision',       label_en: 'VISION',       label_ko: '비전' },
  { key: 'high_quality', label_en: 'HIGH-QUALITY', label_ko: '고품질' },
];

const FEATURES = [
  { id: 'draft',       label: '문서 초안' },
  { id: 'onboarding',  label: 'AI 도우미' },
  { id: 'search',      label: '문서 검색' },
  { id: 'compliance',  label: '법규 모니터' },
  { id: 'equipment',   label: '설비 SPC' },
];

function passesFilter(m: ModelCatalogItem, f: FilterKey): boolean {
  switch (f) {
    case 'all':
      return true;
    case 'fast':
      return m.speed === 'fast';
    case 'korean':
      return m.lang === 'korean';
    case 'vision':
      return m.vision;
    case 'high_quality':
      return m.quality === 'very_high';
    default:
      return true;
  }
}

export function ProfileLLM() {
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);

  const [models, setModels] = useState<ModelCatalogItem[] | null>(null);
  const [filter, setFilter] = useState<FilterKey>('all');

  // 추천 입력 상태
  const [recFeature, setRecFeature] = useState<string>('draft');
  const [needsVision, setNeedsVision] = useState(false);
  const [prefersSpeed, setPrefersSpeed] = useState(false);
  const [recBusy, setRecBusy] = useState(false);
  const [recommendation, setRecommendation] = useState<ModelRecommendResponse | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchModelCatalogCached()
      .then((d) => {
        if (!cancelled) setModels(d.items);
      })
      .catch(() => !cancelled && setModels([]));
    return () => {
      cancelled = true;
    };
  }, []);

  const filtered = useMemo(
    () => (models ?? []).filter((m) => passesFilter(m, filter)),
    [models, filter],
  );

  const handleRecommend = async () => {
    setRecBusy(true);
    try {
      const r = await recommendModel({
        feature: recFeature,
        department: user?.department ?? '',
        needs_vision: needsVision,
        prefers_speed: prefersSpeed,
      });
      setRecommendation(r);
    } finally {
      setRecBusy(false);
    }
  };

  return (
    <div className="page lg-page" data-screen-label="LLM Models">
      {/* HERO */}
      <section className="lg-hero">
        <div className="lg-hero-eyebrow">PROFILE · LLM CATALOG</div>
        <h1 className="lg-display">LLM 모델 비교</h1>
        <p className="lg-sub">
          9개 모델의 속도·품질·언어·비전 지원 여부를 한눈에 비교하세요. 부서와 작업 유형에 맞는
          모델을 추천 받을 수 있습니다.
        </p>
      </section>

      {/* BACK + FILTERS */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          marginBottom: 14,
          flexWrap: 'wrap',
        }}
      >
        <button
          type="button"
          className="lg-btn ghost sm"
          onClick={() => navigate('/profile')}
          style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}
        >
          <ArrowLeft size={12} strokeWidth={2} /> 프로필로
        </button>

        <div className="lg-tabs" style={{ marginLeft: 'auto' }}>
          {FILTERS.map((f) => (
            <button
              key={f.key}
              type="button"
              className={'lg-tab' + (filter === f.key ? ' on' : '')}
              onClick={() => setFilter(f.key)}
            >
              <span className="en">{f.label_en}</span>
              <span className="ko">{f.label_ko}</span>
            </button>
          ))}
        </div>
      </div>

      {/* RECOMMEND */}
      <section className="lg-card" style={{ marginBottom: 18 }}>
        <div className="lg-card-h">
          <div>
            <div
              className="lg-eyebrow"
              style={{ display: 'flex', alignItems: 'center', gap: 6 }}
            >
              <Sparkles size={12} strokeWidth={2} /> RECOMMEND · 내 업무에 맞는 모델
            </div>
            <h2 className="lg-h2">부서·기능·요구를 입력하면 추천</h2>
          </div>
          <span
            className="lg-pill"
            title={user?.department ? `현재 부서: ${user.department}` : '비로그인'}
          >
            <Building2 size={11} strokeWidth={2} /> {user?.department ?? '게스트'}
          </span>
        </div>

        <div
          className="lg-filter-grid"
          style={{ gridTemplateColumns: '1fr 1fr 1fr auto', gap: 12, alignItems: 'flex-end' }}
        >
          <div className="lg-field">
            <label>기능 · FEATURE</label>
            <select value={recFeature} onChange={(e) => setRecFeature(e.target.value)}>
              {FEATURES.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.label}
                </option>
              ))}
            </select>
          </div>
          <div
            className="lg-field"
            style={{
              flexDirection: 'row',
              alignItems: 'center',
              gap: 6,
              padding: '10px 12px',
              border: '1px solid color-mix(in oklab, var(--hud-text) 12%, transparent)',
              borderRadius: 12,
              background: 'color-mix(in oklab, var(--hud-surface) 50%, transparent)',
            }}
          >
            <input
              id="vision-toggle"
              type="checkbox"
              checked={needsVision}
              onChange={(e) => setNeedsVision(e.target.checked)}
              style={{ accentColor: 'var(--hud-primary)' }}
            />
            <label htmlFor="vision-toggle" style={{ fontSize: 13, cursor: 'pointer' }}>
              이미지 입력 필요
            </label>
          </div>
          <div
            className="lg-field"
            style={{
              flexDirection: 'row',
              alignItems: 'center',
              gap: 6,
              padding: '10px 12px',
              border: '1px solid color-mix(in oklab, var(--hud-text) 12%, transparent)',
              borderRadius: 12,
              background: 'color-mix(in oklab, var(--hud-surface) 50%, transparent)',
            }}
          >
            <input
              id="speed-toggle"
              type="checkbox"
              checked={prefersSpeed}
              onChange={(e) => setPrefersSpeed(e.target.checked)}
              style={{ accentColor: 'var(--hud-primary)' }}
            />
            <label htmlFor="speed-toggle" style={{ fontSize: 13, cursor: 'pointer' }}>
              속도 우선
            </label>
          </div>
          <button
            type="button"
            className="lg-btn"
            onClick={handleRecommend}
            disabled={recBusy}
          >
            {recBusy ? '분석 중…' : '추천 받기'}
          </button>
        </div>

        {recommendation && (
          <div
            style={{
              marginTop: 14,
              padding: 14,
              borderRadius: 12,
              border: '1px solid var(--hud-primary)',
              background: 'color-mix(in oklab, var(--hud-primary) 8%, transparent)',
            }}
          >
            <div className="lg-eyebrow" style={{ marginBottom: 6 }}>
              RECOMMENDATION · 추천 모델
            </div>
            <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 4 }}>
              {recommendation.display}{' '}
              <span
                className="mono"
                style={{
                  fontFamily: 'var(--hud-font-mono)',
                  fontSize: 11,
                  color: 'var(--hud-text-muted)',
                  marginLeft: 6,
                }}
              >
                {recommendation.recommended_model_id}
              </span>
            </div>
            <div style={{ fontSize: 13, color: 'var(--hud-text-dim)', lineHeight: 1.6 }}>
              {recommendation.reason}
            </div>
          </div>
        )}
      </section>

      {/* CARD GRID */}
      <section className="lg-card">
        <div className="lg-card-h">
          <div>
            <div className="lg-eyebrow">CATALOG · 모델 카탈로그</div>
            <h2 className="lg-h2">
              {filter === 'all' ? '전체' : FILTERS.find((f) => f.key === filter)?.label_ko}{' '}
              <span className="lg-h2-sub">({filtered.length}/{models?.length ?? 0})</span>
            </h2>
          </div>
        </div>

        {!models ? (
          <div
            className="dim"
            style={{ padding: 24, textAlign: 'center', fontSize: 13 }}
          >
            카탈로그 불러오는 중…
          </div>
        ) : filtered.length === 0 ? (
          <div className="lg-empty" style={{ padding: 32, textAlign: 'center' }}>
            현재 필터에 매칭되는 모델이 없습니다. 다른 필터를 선택해 보세요.
          </div>
        ) : (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
              gap: 14,
            }}
          >
            {filtered.map((m) => (
              <ModelComparisonCard
                key={m.id}
                model={m}
                recommended={
                  recommendation?.recommended_model_id === m.id
                }
              />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
