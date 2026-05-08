// hwp.ts — Phase 1: rhwp WASM 통합 HWP/HWPX 생성 라이브러리.
// 모든 모듈(B/D/F/E/A)에서 호출 가능. lazy import — 사용 시점에만 WASM 로드 (~3.9MB).
//
// 핵심 API: rhwp/core 0.7.7
//   - HwpDocument.createBlankDocument() / createEmpty()
//   - insertText(sec, para, offset, text)
//   - applyCharFormat / applyParaFormat
//   - exportHwp(): Uint8Array
//   - exportHwpx(): Uint8Array
//
// WASM 파일: public/rhwp_bg.wasm (vite copy 단계에서 자동 배포)

// ──────────────────────────────────────────────────────────
// 타입 (rhwp/core .d.ts 발췌 — 런타임 동적 로드라 import type 만 사용)
// ──────────────────────────────────────────────────────────

interface HwpDocumentLike {
  insertText(sec_idx: number, para_idx: number, char_offset: number, text: string): string;
  insertTextLogical(sec_idx: number, para_idx: number, logical_offset: number, text: string): string;
  applyCharFormat(sec_idx: number, para_idx: number, start: number, end: number, props_json: string): string;
  applyParaFormat(sec_idx: number, para_idx: number, props_json: string): string;
  exportHwp(): Uint8Array;
  exportHwpx(): Uint8Array;
  free(): void;
}

interface RhwpModule {
  default: (input?: { module_or_path: string }) => Promise<unknown>;
  HwpDocument: {
    createEmpty(): HwpDocumentLike;
    new (...args: unknown[]): HwpDocumentLike;
    prototype: { createBlankDocument(): string };
  };
}

// ──────────────────────────────────────────────────────────
// WASM 초기화 (1회만)
// ──────────────────────────────────────────────────────────

let _rhwpReady: Promise<RhwpModule> | null = null;

/**
 * rhwp WASM 모듈 lazy 초기화.
 * 첫 호출 시 ~3.9MB 다운로드 + 초기화.
 * canvas measureTextWidth 글로벌 함수 등록 (rhwp 내부 텍스트 폭 계산 의존).
 */
async function loadRhwp(): Promise<RhwpModule> {
  if (!_rhwpReady) {
    _rhwpReady = (async () => {
      // canvas 측정 함수 등록 (rhwp README 가이드)
      if (typeof window !== 'undefined' && !(globalThis as Record<string, unknown>).measureTextWidth) {
        let ctx: CanvasRenderingContext2D | null = null;
        let lastFont = '';
        (globalThis as Record<string, unknown>).measureTextWidth = (font: string, text: string): number => {
          if (!ctx) ctx = document.createElement('canvas').getContext('2d');
          if (!ctx) return 0;
          if (font !== lastFont) {
            ctx.font = font;
            lastFont = font;
          }
          return ctx.measureText(text).width;
        };
      }

      // 동적 import (Vite manualChunks → rhwp-wasm 청크)
      const mod = (await import('@rhwp/core')) as unknown as RhwpModule;

      // WASM 초기화 — public/ 경로
      await mod.default({ module_or_path: '/rhwp_bg.wasm' });

      if (import.meta.env.DEV) {
        console.info('[rhwp] WASM 초기화 완료 (~3.9MB)');
      }
      return mod;
    })();
  }
  return _rhwpReady;
}

// ──────────────────────────────────────────────────────────
// 마크다운 → HWP 콘텐츠 변환 (단순 파서)
// ──────────────────────────────────────────────────────────

/**
 * 마크다운을 단락 단위로 분해.
 * 지원: 제목(#~######), 단락, 목록(-), 인용(>) — 표/이미지는 추후 확장.
 */
function parseMarkdownLines(markdown: string): { type: 'h' | 'p' | 'li' | 'quote' | 'code'; level: number; text: string }[] {
  const lines = markdown.split(/\r?\n/);
  const out: { type: 'h' | 'p' | 'li' | 'quote' | 'code'; level: number; text: string }[] = [];
  let inCode = false;
  for (const raw of lines) {
    if (raw.startsWith('```')) {
      inCode = !inCode;
      continue;
    }
    if (inCode) {
      out.push({ type: 'code', level: 0, text: raw });
      continue;
    }
    const headingMatch = raw.match(/^(#{1,6})\s+(.+)$/);
    if (headingMatch) {
      out.push({ type: 'h', level: headingMatch[1].length, text: headingMatch[2] });
      continue;
    }
    if (raw.startsWith('> ')) {
      out.push({ type: 'quote', level: 0, text: raw.slice(2) });
      continue;
    }
    const liMatch = raw.match(/^[-*]\s+(.+)$/);
    if (liMatch) {
      out.push({ type: 'li', level: 0, text: liMatch[1] });
      continue;
    }
    if (raw.trim() === '') {
      out.push({ type: 'p', level: 0, text: '' });
      continue;
    }
    out.push({ type: 'p', level: 0, text: raw });
  }
  return out;
}

// ──────────────────────────────────────────────────────────
// 핵심 변환 함수
// ──────────────────────────────────────────────────────────

export interface HwpDocOptions {
  title?: string;
  author?: string;
}

interface BuildResult {
  bytes: Uint8Array;
  format: 'hwp' | 'hwpx';
}

/**
 * 마크다운 텍스트로 HwpDocument 를 빌드 (공통 로직).
 * 호출 후 caller 가 exportHwp() 또는 exportHwpx() 로 바이트 추출.
 */
async function buildHwpDocument(
  markdown: string,
  exportFormat: 'hwp' | 'hwpx',
  _options?: HwpDocOptions,
): Promise<BuildResult> {
  const mod = await loadRhwp();
  // createEmpty 또는 인스턴스 생성 후 createBlankDocument
  // rhwp/core 0.7.7 : HwpDocument.createEmpty() 정적 메서드 노출
  const doc = mod.HwpDocument.createEmpty();

  try {
    const parsed = parseMarkdownLines(markdown);
    let para = 0;
    let charOffset = 0;

    for (const block of parsed) {
      // 비어있는 단락 = 공백 라인
      if (block.text === '' && block.type === 'p') {
        // 빈 단락 추가 — 텍스트 미삽입
        para += 1;
        charOffset = 0;
        continue;
      }

      // 제목/인용/리스트 prefix 처리
      let text = block.text;
      if (block.type === 'li') {
        text = '• ' + text;
      } else if (block.type === 'quote') {
        text = '“ ' + text + ' ”';
      }

      // sec_idx=0 (단일 섹션 가정), para_idx=para, char_offset=0 부터
      doc.insertText(0, para, charOffset, text);

      // 제목 서식 적용 (h1=18pt bold, h2=15pt bold, ...)
      if (block.type === 'h') {
        const propsJson = JSON.stringify({
          fontSize: Math.max(20 - block.level * 2, 10) * 100,  // HWP 단위 1/100pt
          bold: block.level <= 3,
        });
        try {
          doc.applyCharFormat(0, para, 0, text.length, propsJson);
        } catch {
          // 서식 적용 실패 시 텍스트만 유지
        }
      }
      para += 1;
      charOffset = 0;
    }

    const bytes = exportFormat === 'hwp' ? doc.exportHwp() : doc.exportHwpx();
    return { bytes, format: exportFormat };
  } finally {
    try {
      doc.free();
    } catch {
      /* noop */
    }
  }
}

/**
 * 마크다운 → HWP (5.0 바이너리) blob.
 * 한컴오피스 표준 포맷.
 */
export async function markdownToHwp(markdown: string, options?: HwpDocOptions): Promise<Blob> {
  const { bytes } = await buildHwpDocument(markdown, 'hwp', options);
  return new Blob([new Uint8Array(bytes)], { type: 'application/x-hwp' });
}

/**
 * 마크다운 → HWPX (XML) blob.
 * HWPX 정식 — Hancom 신 포맷.
 */
export async function markdownToHwpx(markdown: string, options?: HwpDocOptions): Promise<Blob> {
  const { bytes } = await buildHwpDocument(markdown, 'hwpx', options);
  return new Blob([new Uint8Array(bytes)], { type: 'application/vnd.hancom.hwpx' });
}

/**
 * Blob → 브라우저 다운로드 트리거 (공통 헬퍼).
 */
export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// ──────────────────────────────────────────────────────────
// Phase 7: 백엔드 fallback (WASM 메모리 부족 / 모바일 / 보안 격리)
// ──────────────────────────────────────────────────────────

interface BackendFallbackPayload {
  content: string;
  title?: string;
  doc_type?: string;
  author?: string;
  source?: string;
}

/**
 * 백엔드 /api/export/{hwp|hwpx} 호출 → blob 응답.
 * 프론트 WASM 실패 또는 환경 미지원 시 fallback.
 */
async function backendExportHwp(
  format: 'hwp' | 'hwpx',
  payload: BackendFallbackPayload,
): Promise<Blob> {
  const res = await fetch(`/api/export/${format}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      content: payload.content,
      title: payload.title,
      doc_type: payload.doc_type ?? 'general',
      author: payload.author,
      source: payload.source ?? 'default',
    }),
  });
  if (!res.ok) {
    throw new Error(`백엔드 ${format.toUpperCase()} 변환 실패: HTTP ${res.status}`);
  }
  return res.blob();
}

/**
 * 통합 헬퍼: 마크다운 → HWP/HWPX 다운로드 1회 호출.
 *
 * v3.6 라우팅 정책:
 *   - HWPX → **백엔드 /api/export/hwpx 우선** (정식 OWPML 생성)
 *     rhwp v0.7.7 의 exportHwpx() 가 Contents/content.hpf 누락 버그가 있어
 *     "유효하지 않은 파일" 오류로 한컴오피스/rhwp 뷰어에서 거부됨.
 *     백엔드는 OWPML 1.4 사양 정식 패키지 생성 → 호환성 보장.
 *   - HWP  → 프론트엔드 WASM 우선 (한컴 5.0 바이너리, rhwp 안정적)
 *           실패 시 백엔드 fallback, 그것도 실패하면 HWPX 로 폴백.
 */
export async function downloadHwp(
  markdown: string,
  filename: string,
  format: 'hwp' | 'hwpx' = 'hwp',
  options?: HwpDocOptions,
): Promise<void> {
  // ── HWPX: 백엔드 1순위 (rhwp WASM 의 OWPML 결함 우회) ──────
  if (format === 'hwpx') {
    try {
      const blob = await backendExportHwp('hwpx', {
        content: markdown,
        title: options?.title,
        author: options?.author,
      });
      downloadBlob(blob, filename);
      return;
    } catch (backErr) {
      if (import.meta.env.DEV) {
        console.warn(
          '[hwp] 백엔드 HWPX 실패 → WASM fallback 시도:',
          backErr instanceof Error ? backErr.message : backErr,
        );
      }
      // 백엔드 실패 시 WASM 시도 (마지막 수단)
      try {
        const blob = await markdownToHwpx(markdown, options);
        downloadBlob(blob, filename);
        return;
      } catch (frontErr) {
        throw new Error(
          `HWPX 변환 실패 (backend + WASM): ${frontErr instanceof Error ? frontErr.message : String(frontErr)}`,
        );
      }
    }
  }

  // ── HWP (5.0 바이너리): 프론트엔드 WASM 우선 ──────────────
  try {
    const blob = await markdownToHwp(markdown, options);
    downloadBlob(blob, filename);
    return;
  } catch (frontErr) {
    if (import.meta.env.DEV) {
      console.warn(
        '[hwp] WASM HWP 실패 → 백엔드 fallback 시도:',
        frontErr instanceof Error ? frontErr.message : frontErr,
      );
    }
  }

  // HWP 백엔드 fallback
  try {
    const blob = await backendExportHwp('hwp', {
      content: markdown,
      title: options?.title,
      author: options?.author,
    });
    downloadBlob(blob, filename);
    return;
  } catch (backErr) {
    // 라스트-디치: HWP → HWPX 백엔드 (확장자 변경)
    try {
      const blob = await backendExportHwp('hwpx', {
        content: markdown,
        title: options?.title,
      });
      const altFilename = filename.replace(/\.hwp$/, '.hwpx');
      downloadBlob(blob, altFilename);
    } catch (e2) {
      throw new Error(
        `HWP/HWPX 모두 실패: ${e2 instanceof Error ? e2.message : String(e2)} (이전: ${backErr instanceof Error ? backErr.message : String(backErr)})`,
      );
    }
  }
}

// 개발 편의: window 에서 직접 호출 가능
if (typeof window !== 'undefined' && import.meta.env.DEV) {
  (window as unknown as { __testHwp: typeof downloadHwp }).__testHwp = downloadHwp;
}
