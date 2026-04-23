import { FileText } from 'lucide-react';

/**
 * 최근 검사 결과 — 시안 PlusUltra SaaS 1의 우측 하단 Recent Results.
 *
 * P5 "검사 결과 무기한 보관"(v2 MOAT #3) 착수 전 placeholder.
 */
export function RecentResultsStub() {
  return (
    <article
      className="rounded-xl border border-outline-variant bg-surface-container-lowest p-4"
      aria-labelledby="recent-results-title"
    >
      <header className="mb-2 flex items-center gap-2">
        <FileText className="h-5 w-5 text-primary" aria-hidden />
        <h3
          id="recent-results-title"
          className="text-base font-semibold"
        >
          최근 검사 결과
        </h3>
      </header>
      <p className="text-sm text-on-surface-variant">
        검사 결과는 P5에서 무기한 보관 형태로 제공됩니다.
      </p>
      <p className="mt-2 text-xs text-on-surface-variant">
        <span className="rounded-full bg-surface-container px-2 py-0.5">
          준비 중 (P5)
        </span>
      </p>
    </article>
  );
}
