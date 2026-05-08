// CrawlResultsDrawer — Module D Phase 2.
// Feature A EmployeeDetailDrawer 동일 패턴. 우측 슬라이드 Drawer 에 크롤러 결과 항목 표시.
// 디자인 시스템 v3.5 (HUD): 2px radius, 골드 강조, 영문 eyebrow + 한글 본문.

import { useEffect, useState } from 'react';
import { ExternalLink, AlertCircle, FileText, RefreshCw, Download } from 'lucide-react';
import { Drawer } from '@components/ui/Drawer';
import { Button } from '@components/ui/Button';
import {
  fetchCrawlResultDetail,
  type CrawlResultDetailResponse,
  type CrawlResultItem,
} from '@api/compliance';
import { api } from '@api/client';
import { useToastStore } from '@store/toast';

type DownloadFormat = 'json' | 'csv' | 'xlsx' | 'docx' | 'pdf' | 'report';

const DOWNLOAD_FORMATS: { fmt: DownloadFormat; label: string; ext: string; tip?: string }[] = [
  { fmt: 'json', label: 'JSON', ext: 'json', tip: '원본 raw 데이터 (자동화/분석용)' },
  { fmt: 'csv', label: 'CSV', ext: 'csv', tip: '엑셀 호환 (UTF-8 BOM)' },
  { fmt: 'xlsx', label: 'XLSX', ext: 'xlsx', tip: '엑셀 — 헤더+자동 너비' },
  { fmt: 'docx', label: 'DOCX', ext: 'docx', tip: '워드 — 항목별 섹션' },
  { fmt: 'pdf', label: 'PDF', ext: 'pdf', tip: 'PDF — 한글 폰트 적용' },
  { fmt: 'report', label: '📑 회사 양식', ext: 'docx', tip: '회사 양식 보고서 — 표지+요약+본문+부록' },
];

interface Props {
  /** 선택된 크롤러 이름 (iso, apqp, msds 등). null 이면 닫힘. */
  crawlerName: string | null;
  /** 카드 헤더에 표시할 한국어 라벨 (옵션) */
  displayName?: string;
  isOpen: boolean;
  onClose: () => void;
}

const PAGE_SIZE = 20;

export function CrawlResultsDrawer({
  crawlerName,
  displayName,
  isOpen,
  onClose,
}: Props) {
  const [data, setData] = useState<CrawlResultDetailResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);

  const load = async (resetOffset = true) => {
    if (!crawlerName) return;
    setLoading(true);
    setError(null);
    try {
      const newOffset = resetOffset ? 0 : offset;
      const res = await fetchCrawlResultDetail(crawlerName, PAGE_SIZE, newOffset);
      if (resetOffset || !data) {
        setData(res);
      } else {
        // 더 보기 → 기존 items 에 append
        setData({
          ...res,
          items: [...data.items, ...res.items],
        });
      }
      if (resetOffset) setOffset(0);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  // crawlerName 변경 시 fetch
  useEffect(() => {
    if (!crawlerName || !isOpen) {
      setData(null);
      setError(null);
      setOffset(0);
      return;
    }
    void load(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [crawlerName, isOpen]);

  const handleLoadMore = async () => {
    if (!data || !crawlerName) return;
    const nextOffset = data.items.length;
    setOffset(nextOffset);
    setLoading(true);
    try {
      const res = await fetchCrawlResultDetail(crawlerName, PAGE_SIZE, nextOffset);
      setData({
        ...res,
        items: [...data.items, ...res.items],
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  // v3.6 Phase 4 — axios 기반 다운로드 (interceptor 의 auto auth + 401 refresh + 재시도 활용)
  const [downloadingFmt, setDownloadingFmt] = useState<DownloadFormat | null>(null);
  const addToast = useToastStore.getState().addToast;

  const handleDownload = async (fmt: DownloadFormat) => {
    if (!crawlerName) return;
    setDownloadingFmt(fmt);
    try {
      // axios 사용 — 자동으로 Authorization 헤더 첨부 + 401 시 refresh/exchange + 재시도
      const res = await api.get<Blob>(
        `/compliance/crawl/results/${encodeURIComponent(crawlerName)}/download`,
        { params: { format: fmt }, responseType: 'blob' },
      );
      const blob = res.data;
      const today = new Date().toISOString().slice(0, 10).replace(/-/g, '');
      const meta = DOWNLOAD_FORMATS.find((f) => f.fmt === fmt);
      const ext = meta?.ext ?? fmt;
      const suffix = fmt === 'report' ? '_report' : '';
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = `${crawlerName}_${today}${suffix}.${ext}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(() => URL.revokeObjectURL(a.href), 1000);
      addToast({
        type: 'success',
        message: `${fmt.toUpperCase()} 다운로드 완료`,
        duration: 2000,
      });
    } catch (e) {
      // axios interceptor 가 401 → /login 리다이렉트를 이미 처리.
      // 여기로 도달했다면 네트워크/서버 오류이거나 refresh 도 실패한 케이스.
      const status = (e as { response?: { status?: number } })?.response?.status;
      if (status === 401) {
        addToast({
          type: 'warning',
          message: '세션이 만료되었습니다. 다시 로그인해 주세요.',
          duration: 3500,
        });
      } else {
        const msg = e instanceof Error ? e.message : String(e);
        addToast({
          type: 'error',
          message: `${fmt.toUpperCase()} 다운로드 실패: ${msg}`,
          duration: 4000,
        });
      }
    } finally {
      setDownloadingFmt(null);
    }
  };

  const drawerTitle = `${displayName ?? crawlerName ?? '크롤러'} · 크롤링 결과`;

  return (
    <Drawer isOpen={isOpen} onClose={onClose} side="right" width={480} title={drawerTitle}>
      <div style={{ padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 14 }}>
        {/* ── 헤더: 크롤러 메타 ──────────────────────────────── */}
        <div
          style={{
            padding: 12,
            borderRadius: 2,
            border: '1px solid var(--hud-border, #2A2520)',
            background: 'var(--hud-surface, #111820)',
          }}
        >
          <div
            className="label-en"
            style={{ fontSize: 10, letterSpacing: '0.1em', color: 'var(--hud-text-muted)' }}
          >
            CRAWLER · {(crawlerName ?? '').toUpperCase()}
          </div>
          <div style={{ fontSize: 16, fontWeight: 700, marginTop: 2 }}>
            {displayName ?? crawlerName ?? '—'}
          </div>
          {data?.crawled_at && (
            <div style={{ fontSize: 11, color: 'var(--hud-text-dim)', marginTop: 4 }}>
              마지막 실행: {new Date(data.crawled_at).toLocaleString('ko-KR')}
            </div>
          )}
          {data?.source && (
            <a
              href={data.source}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                fontSize: 11,
                color: 'var(--hud-primary)',
                textDecoration: 'none',
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
                marginTop: 4,
              }}
            >
              <ExternalLink size={10} strokeWidth={1.5} />
              {data.source.replace(/^https?:\/\//, '').slice(0, 50)}
              {data.source.length > 50 ? '…' : ''}
            </a>
          )}
          {data && (
            <div
              style={{
                marginTop: 8,
                display: 'flex',
                gap: 14,
                fontSize: 11,
                color: 'var(--hud-text-muted)',
                fontFamily: 'var(--hud-font-mono)',
              }}
            >
              <span>총 {data.total}건</span>
              <span>표시 {data.items.length}건</span>
              {data.has_more && <span style={{ color: 'var(--hud-orange)' }}>+ 더 있음</span>}
            </div>
          )}
        </div>

        {/* ── 액션 버튼 (재실행 + 5 포맷 다운로드) ──────────── */}
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <Button variant="ghost" size="sm" onClick={() => load(true)} disabled={loading}>
            <RefreshCw size={12} strokeWidth={1.5} style={{ marginRight: 4 }} />
            새로고침
          </Button>
        </div>

        {/* v3.6 Phase 3 Item 2 — 다운로드 (JSON/CSV/XLSX/DOCX/PDF) */}
        {data && data.items.length > 0 && (
          <div
            style={{
              padding: 10,
              borderRadius: 2,
              border: '1px dashed var(--hud-border, #2A2520)',
              background: 'color-mix(in oklab, var(--hud-primary) 4%, transparent)',
            }}
          >
            <div
              className="label-en"
              style={{
                fontSize: 10,
                letterSpacing: '0.1em',
                color: 'var(--hud-text-muted)',
                marginBottom: 6,
                display: 'flex',
                alignItems: 'center',
                gap: 4,
              }}
            >
              <Download size={11} strokeWidth={1.5} />
              EXPORT · 5 포맷 다운로드
            </div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {DOWNLOAD_FORMATS.map(({ fmt, label, tip }) => (
                <button
                  key={fmt}
                  className="lg-btn ghost sm"
                  onClick={() => handleDownload(fmt)}
                  disabled={downloadingFmt !== null}
                  style={{
                    fontSize: 11,
                    padding: '4px 10px',
                    // 회사 양식 (6번째) 강조
                    ...(fmt === 'report' && {
                      background: 'color-mix(in oklab, var(--hud-primary) 14%, transparent)',
                      borderColor: 'var(--hud-primary)',
                      color: 'var(--hud-primary)',
                      fontWeight: 600,
                    }),
                  }}
                  title={tip ? `${label}: ${tip} (${data.total}건)` : `${label} (${data.total}건)`}
                >
                  {downloadingFmt === fmt ? '⏳' : '↓'} {label}
                </button>
              ))}
            </div>
            <div style={{ fontSize: 10, color: 'var(--hud-text-muted)', marginTop: 4 }}>
              항목 {data.total}건 · 출처 URL과 상세 내용 포함
            </div>
          </div>
        )}

        {/* ── 에러/로딩 ─────────────────────────────────────── */}
        {error && (
          <div
            style={{
              padding: 10,
              borderRadius: 2,
              background: 'rgba(232,163,23,0.10)',
              border: '1px solid var(--hud-orange)',
              color: 'var(--hud-orange)',
              fontSize: 12,
              display: 'flex',
              alignItems: 'center',
              gap: 6,
            }}
          >
            <AlertCircle size={14} strokeWidth={1.5} />
            {error}
          </div>
        )}

        {loading && !data && (
          <div style={{ padding: 16, textAlign: 'center', color: 'var(--hud-text-muted)', fontSize: 12 }}>
            ⏳ 결과 로딩 중...
          </div>
        )}

        {data && data.items.length === 0 && !loading && (
          <div
            style={{
              padding: 24,
              textAlign: 'center',
              color: 'var(--hud-text-muted)',
              fontSize: 13,
              border: '1px dashed var(--hud-border)',
              borderRadius: 2,
            }}
          >
            <FileText size={24} strokeWidth={1.2} style={{ margin: '0 auto 8px', opacity: 0.5 }} />
            아직 크롤링된 결과가 없습니다.
            <br />
            "RUN ALL" 버튼을 클릭해 크롤러를 실행해 주세요.
          </div>
        )}

        {/* ── 항목 리스트 ────────────────────────────────────── */}
        {data && data.items.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {data.items.map((item, i) => (
              <CrawlItemCard key={`${item.title}-${i}`} item={item} />
            ))}
          </div>
        )}

        {/* ── 더 보기 ────────────────────────────────────── */}
        {data && data.has_more && (
          <Button variant="ghost" size="sm" onClick={handleLoadMore} disabled={loading}>
            {loading ? '로딩 중...' : `더 보기 (+${Math.min(PAGE_SIZE, data.total - data.items.length)}건)`}
          </Button>
        )}
      </div>
    </Drawer>
  );
}

function CrawlItemCard({ item }: { item: CrawlResultItem }) {
  return (
    <div
      style={{
        padding: 10,
        borderRadius: 2,
        border: '1px solid var(--hud-border-light, #20262E)',
        background: 'color-mix(in oklab, var(--hud-text) 3%, transparent)',
      }}
    >
      <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--hud-text)', lineHeight: 1.4 }}>
        {item.title}
      </div>
      {item.summary && (
        <div
          style={{
            fontSize: 11,
            color: 'var(--hud-text-dim)',
            marginTop: 4,
            lineHeight: 1.5,
            display: '-webkit-box',
            WebkitLineClamp: 3,
            WebkitBoxOrient: 'vertical',
            overflow: 'hidden',
          }}
        >
          {item.summary}
        </div>
      )}
      {item.url && (
        <a
          href={item.url}
          target="_blank"
          rel="noopener noreferrer"
          style={{
            fontSize: 10,
            color: 'var(--hud-primary)',
            textDecoration: 'none',
            display: 'inline-flex',
            alignItems: 'center',
            gap: 4,
            marginTop: 6,
          }}
        >
          <ExternalLink size={10} strokeWidth={1.5} />
          원문 보기
        </a>
      )}
    </div>
  );
}
