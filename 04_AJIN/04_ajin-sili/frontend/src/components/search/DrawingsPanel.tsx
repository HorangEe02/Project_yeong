// P2 (Weakness #3) — 도면 메타 + Vision 캡션 통합 검색 패널.
// search.tsx 의 'drawings' 탭에서 렌더링.

import { useEffect, useMemo, useState } from 'react';
import { Image as ImageIcon, FileSearch, Sparkles, Layers, Calendar } from 'lucide-react';
import {
  searchDrawings,
  searchDrawingCaptions,
  drawingThumbnail,
  type DrawingItem,
  type DrawingCaptionItem,
} from '@api/drawings';

type AssetType = 'all' | 'drawing' | 'caption';

export function DrawingsPanel() {
  const [q, setQ] = useState('');
  const [assetType, setAssetType] = useState<AssetType>('all');
  const [drawings, setDrawings] = useState<DrawingItem[]>([]);
  const [captions, setCaptions] = useState<DrawingCaptionItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);

  const onSubmit = async (e?: React.FormEvent) => {
    e?.preventDefault();
    setLoading(true);
    setError(null);
    setSubmitted(true);
    try {
      const tasks: Promise<unknown>[] = [];
      if (assetType !== 'caption') {
        tasks.push(searchDrawings(q).then((r) => setDrawings(r.items)));
      } else {
        setDrawings([]);
      }
      if (assetType !== 'drawing') {
        tasks.push(searchDrawingCaptions(q).then((r) => setCaptions(r.items)));
      } else {
        setCaptions([]);
      }
      await Promise.all(tasks);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  // 초기 로드 시 전체 도면 메타 노출 (q 비어있음)
  useEffect(() => {
    void onSubmit();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const totalCount = drawings.length + captions.length;

  return (
    <section className="lg-card" style={{ padding: 20 }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
        <div>
          <div style={{ fontSize: 10, opacity: 0.55, letterSpacing: '0.06em' }}>
            <Sparkles size={10} style={{ verticalAlign: 'middle', marginRight: 4 }} />
            DRAWINGS · VISION CAPTIONS
          </div>
          <h2 style={{ margin: '4px 0 0', fontSize: 18, fontWeight: 700 }}>
            도면 / 부품 자산 검색
          </h2>
          <div style={{ fontSize: 12, opacity: 0.65, marginTop: 4 }}>
            도면 메타 15건(EWP/CCH/OBC/BMS 등) + 신입 가이드 Vision Q&A 에서 인덱싱된 캡션.
            정식 CAD 파일(DWG/STEP/DXF) 파싱은 v2.0 로드맵.
          </div>
        </div>
        <div
          style={{
            padding: '6px 10px',
            borderRadius: 999,
            border: '1px solid var(--hud-border)',
            fontSize: 11,
            opacity: 0.75,
          }}
        >
          PoC
        </div>
      </header>

      <form onSubmit={onSubmit} style={{ marginTop: 16, display: 'flex', gap: 8 }}>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="예: EWP, AL6061, 프레스, DWG-CCH-001, 임펠러"
          style={{
            flex: 1,
            padding: '10px 14px',
            borderRadius: 8,
            border: '1px solid var(--hud-border)',
            background: 'var(--hud-surface-2)',
            fontSize: 13,
            color: 'var(--hud-text)',
          }}
        />
        <select
          value={assetType}
          onChange={(e) => setAssetType(e.target.value as AssetType)}
          style={{
            padding: '0 12px',
            borderRadius: 8,
            border: '1px solid var(--hud-border)',
            background: 'var(--hud-surface-2)',
            fontSize: 13,
            color: 'var(--hud-text)',
          }}
        >
          <option value="all">전체</option>
          <option value="drawing">도면 메타</option>
          <option value="caption">Vision 캡션</option>
        </select>
        <button
          type="submit"
          className="lg-btn primary"
          disabled={loading}
          style={{ padding: '0 18px' }}
        >
          {loading ? '검색 중…' : '검색'}
        </button>
      </form>

      {error && (
        <div
          style={{
            marginTop: 14,
            padding: '8px 12px',
            borderRadius: 8,
            border: '1px solid color-mix(in oklab, #dc2626 35%, transparent)',
            background: 'color-mix(in oklab, #dc2626 8%, transparent)',
            fontSize: 12,
          }}
        >
          ⚠️ {error}
        </div>
      )}

      {submitted && !loading && totalCount === 0 && !error && (
        <div style={{ marginTop: 16, fontSize: 12, opacity: 0.65 }}>
          매칭된 자산이 없습니다. 키워드를 바꿔 다시 시도하거나, 신입 가이드 → Vision Q&A 에서 도면 사진을 업로드해 인덱스를 늘릴 수 있습니다.
        </div>
      )}

      {(drawings.length > 0 || captions.length > 0) && (
        <div style={{ marginTop: 16, fontSize: 11, opacity: 0.6 }}>
          도면 메타 {drawings.length} · Vision 캡션 {captions.length}
        </div>
      )}

      <div
        style={{
          marginTop: 12,
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
          gap: 12,
        }}
      >
        {drawings.map((d) => <DrawingCard key={`drawing-${d.id}`} item={d} />)}
        {captions.map((c) => <CaptionCard key={`caption-${c.id}`} item={c} />)}
      </div>
    </section>
  );
}

function DrawingCard({ item }: { item: DrawingItem }) {
  return (
    <article
      style={{
        padding: 14,
        borderRadius: 10,
        border: '1px solid var(--hud-border)',
        background: 'var(--hud-surface-2)',
        display: 'flex',
        gap: 12,
      }}
    >
      <div
        style={{
          width: 64,
          height: 64,
          borderRadius: 8,
          background: 'color-mix(in oklab, var(--hud-primary) 12%, transparent)',
          display: 'grid',
          placeItems: 'center',
          flexShrink: 0,
        }}
      >
        <img
          src={drawingThumbnail(item.equipment_type)}
          alt={item.part_name}
          width={48}
          height={48}
          style={{ opacity: 0.85 }}
          onError={(e) => {
            (e.currentTarget as HTMLImageElement).style.display = 'none';
          }}
        />
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: 10, opacity: 0.6 }}>
            {item.drawing_number} · Rev {item.revision}
          </span>
          <Badge label="도면" tone="primary" />
        </div>
        <div style={{ fontSize: 14, fontWeight: 600, marginTop: 2 }}>{item.part_name}</div>
        <div style={{ fontSize: 11, opacity: 0.65, marginTop: 4, lineHeight: 1.5 }}>
          {item.description}
        </div>
        <MetaRow icon={<Layers size={10} />} text={`${item.material} · ${item.process_type}`} />
        <MetaRow icon={<FileSearch size={10} />} text={`${item.department} · ${item.part_number}`} />
      </div>
    </article>
  );
}

function CaptionCard({ item }: { item: DrawingCaptionItem }) {
  const dateOnly = useMemo(() => (item.created_at || '').slice(0, 10), [item.created_at]);
  return (
    <article
      style={{
        padding: 14,
        borderRadius: 10,
        border: '1px solid color-mix(in oklab, #16a34a 30%, transparent)',
        background: 'color-mix(in oklab, #16a34a 5%, transparent)',
        display: 'flex',
        gap: 12,
      }}
    >
      <div
        style={{
          width: 64,
          height: 64,
          borderRadius: 8,
          background: 'color-mix(in oklab, #16a34a 15%, transparent)',
          display: 'grid',
          placeItems: 'center',
          flexShrink: 0,
        }}
      >
        <ImageIcon size={28} style={{ opacity: 0.7 }} />
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: 10, opacity: 0.6 }}>
            #{item.id} · {item.file_name || 'vision-upload'}
          </span>
          <Badge label="Vision 캡션" tone="ok" />
        </div>
        <div style={{ fontSize: 13, lineHeight: 1.5, marginTop: 4, whiteSpace: 'pre-wrap' }}>
          {item.caption}
        </div>
        {item.keywords && (
          <MetaRow icon={<Sparkles size={10} />} text={item.keywords} />
        )}
        <MetaRow
          icon={<Calendar size={10} />}
          text={`${dateOnly} · ${item.uploader || 'unknown'} · ${item.source_model || 'vision'}`}
        />
      </div>
    </article>
  );
}

function Badge({ label, tone }: { label: string; tone: 'primary' | 'ok' }) {
  const color =
    tone === 'ok'
      ? 'color-mix(in oklab, #16a34a 60%, transparent)'
      : 'color-mix(in oklab, var(--hud-primary) 60%, transparent)';
  return (
    <span
      style={{
        fontSize: 9,
        padding: '2px 6px',
        borderRadius: 999,
        border: `1px solid ${color}`,
        color: color,
        letterSpacing: '0.04em',
      }}
    >
      {label.toUpperCase()}
    </span>
  );
}

function MetaRow({ icon, text }: { icon: React.ReactNode; text: string }) {
  return (
    <div style={{ marginTop: 6, fontSize: 11, opacity: 0.6, display: 'flex', alignItems: 'center', gap: 4 }}>
      {icon}
      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{text}</span>
    </div>
  );
}
