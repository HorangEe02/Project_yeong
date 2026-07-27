'use strict';
/* ============================================================================
   회의녹음챗 — 클라이언트 애플리케이션 (vanilla JS, 의존성 없음)
   Chat Web App UI Kit 레이아웃 적용: 아이콘 레일 + 회의 목록 + 전사(채팅 버블) + 참석자/요약
   구성:
     1. 상수 & 아이콘
     2. 유틸리티 (포맷터, 색상, 토스트, 다이얼로그)
     3. API 레이어
     4. 라우터 & 앱 셸 (레일 / 드로어)
     5. 회의 목록 컬럼 (ListColumn, 상시 마운트)
     6. 가운데 컬럼: 새 회의 (녹음 / 업로드)
     7. 가운데 컬럼: 빈 상태 / 오른쪽 컬럼: 안내 팁
     8. 가운데 + 오른쪽 컬럼: 회의 상세 (전사 버블 + 참석자/요약)
     9. 초기화
   ========================================================================= */

(function () {

  /* ==========================================================================
     1. 상수 & 아이콘
     ======================================================================= */

  var API_BASE = '/v1';

  var JOB_STAGES = ['uploaded', 'normalizing_audio', 'transcribing', 'summarizing', 'ready_for_review'];
  var STAGE_LABELS = {
    uploaded: '업로드',
    normalizing_audio: '오디오 정규화',
    transcribing: '전사',
    summarizing: '요약 생성',
    ready_for_review: '완료'
  };
  var STATUS_META = {
    uploaded: { label: '업로드됨' },
    normalizing_audio: { label: '정규화 중' },
    transcribing: { label: '전사 중' },
    summarizing: { label: '요약 생성 중' },
    ready_for_review: { label: '검토 대기' },
    failed: { label: '실패' }
  };
  var TODO_STATUS_OPTIONS = [['open', '열림'], ['done', '완료'], ['dismissed', '취소됨']];
  var CAL_STATUS_OPTIONS = [['pending', '대기'], ['approved', '승인됨'], ['dismissed', '취소됨']];
  var TAB_SLUGS = ['transcript', 'summary', 'todos', 'calendar', 'export'];
  var RIGHT_TAB_SLUGS = ['summary', 'todos', 'calendar', 'export'];

  // 옅은 배경 + 짙은 전경 쌍. 한 글자짜리 아바타라도 텍스트이므로 대비 4.5:1 을 넘긴다.
  var AVATAR_PALETTE = [
    { bg: '#FFF0A8', fg: '#7A4F00' },
    { bg: '#FDEAF0', fg: '#A81E55' },
    { bg: '#FCEEDB', fg: '#8F5C08' },
    { bg: '#E3F8EA', fg: '#1D6A40' },
    { bg: '#E7F3FE', fg: '#1B639F' },
    { bg: '#F1F2F4', fg: '#5F6672' }
  ];

  var ICONS = {
    search: '<svg width="15" height="15" viewBox="0 0 15 15" fill="none"><circle cx="6.5" cy="6.5" r="5" stroke="currentColor" stroke-width="1.5"/><path d="M10.5 10.5L14 14" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>',
    folderMove: '<svg width="16" height="16" viewBox="0 0 20 20" fill="none"><path d="M2.5 6A1.5 1.5 0 014 4.5h3l1.6 2h5.9A1.5 1.5 0 0116 8v6.5a1.5 1.5 0 01-1.5 1.5h-9A1.5 1.5 0 014 14.5V6z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/></svg>',
    share: '<svg width="16" height="16" viewBox="0 0 16 16" fill="none"><circle cx="12" cy="4" r="2" stroke="currentColor" stroke-width="1.5"/><circle cx="4" cy="8" r="2" stroke="currentColor" stroke-width="1.5"/><circle cx="12" cy="12" r="2" stroke="currentColor" stroke-width="1.5"/><path d="M5.7 7L10.3 5M5.7 9l4.6 2" stroke="currentColor" stroke-width="1.5"/></svg>',
    check: '<svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M2.5 7.2l3 3 6-6.4" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    star: '<svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><path d="M8 1.3l1.9 4.2 4.6.5-3.4 3.2.9 4.6L8 11.6l-4 2.2.9-4.6-3.4-3.2 4.6-.5L8 1.3z"/></svg>',
    edit: '<svg width="15" height="15" viewBox="0 0 15 15" fill="none"><path d="M9.8 2.3l2.9 2.9-7.3 7.3-3.3.4.4-3.3 7.3-7.3z" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round"/></svg>',
    trash: '<svg width="15" height="15" viewBox="0 0 15 15" fill="none"><path d="M2.5 4.2h10M5.8 4.2V2.8c0-.4.3-.7.7-.7h3c.4 0 .7.3.7.7v1.4M6 7v4M9 7v4M3.5 4.2l.6 8c0 .5.5.9 1 .9h5.8c.5 0 1-.4 1-.9l.6-8" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    play: '<svg width="17" height="17" viewBox="0 0 17 17" fill="currentColor"><path d="M5 3.2v10.6l9-5.3-9-5.3z"/></svg>',
    pause: '<svg width="17" height="17" viewBox="0 0 17 17" fill="currentColor"><rect x="4" y="3" width="3.2" height="11" rx="1"/><rect x="9.8" y="3" width="3.2" height="11" rx="1"/></svg>',
    // 되감기/빨리감기의 "10" 은 <text> 로 그리면 사용자 폰트에 따라 자리가 밀린다 → 패스로 직접 그린다.
    skipBack: '<svg width="17" height="17" viewBox="0 0 24 24" fill="none"><path d="M6.34 6.34A8 8 0 1 0 12 4" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"/><polyline points="6.34 2.9 6.34 6.34 9.78 6.34" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"/><path d="M8.3 12.2 9.3 11.2 9.3 16" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"/><ellipse cx="13.4" cy="13.6" rx="1.7" ry="2.4" stroke="currentColor" stroke-width="2.1"/></svg>',
    skipFwd: '<svg width="17" height="17" viewBox="0 0 24 24" fill="none"><path d="M17.66 6.34A8 8 0 1 1 12 4" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"/><polyline points="17.66 2.9 17.66 6.34 14.22 6.34" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"/><path d="M8.3 12.2 9.3 11.2 9.3 16" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"/><ellipse cx="13.4" cy="13.6" rx="1.7" ry="2.4" stroke="currentColor" stroke-width="2.1"/></svg>',
    close: '<svg width="14" height="14" viewBox="0 0 16 16" fill="none"><path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>',
    record: '<svg width="13" height="13" viewBox="0 0 16 16" fill="currentColor"><circle cx="8" cy="8" r="4.4"/></svg>',
    docEdit: '<svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M12.4 7.8v5a1.4 1.4 0 01-1.4 1.4H4.6a1.4 1.4 0 01-1.4-1.4V3.2a1.4 1.4 0 011.4-1.4h4" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/><path d="M11.3 1.5l2.4 2.4-4.7 4.7-2.9.5.5-2.9 4.7-4.7z" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/></svg>',
    docText: '<svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M9.3 1.8H4.6a1.4 1.4 0 00-1.4 1.4v9.6a1.4 1.4 0 001.4 1.4h6.8a1.4 1.4 0 001.4-1.4V5.3L9.3 1.8z" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/><path d="M9.2 2v3.3h3.5" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/><path d="M5.7 8.7h4.6M5.7 11.2h3.1" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/></svg>',
    empty: '<svg width="48" height="48" viewBox="0 0 52 52" fill="none"><rect x="6" y="6" width="40" height="40" rx="12" stroke="currentColor" stroke-width="2"/><path d="M26 16v14M20 26a6 6 0 0012 0" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
    plus: '<svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M8 2v12M2 8h12" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
    users: '<svg width="16" height="16" viewBox="0 0 16 16" fill="none"><circle cx="6" cy="5.5" r="2.3" stroke="currentColor" stroke-width="1.4"/><path d="M1.6 13c.5-2.4 2.3-3.8 4.4-3.8s3.9 1.4 4.4 3.8" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/><circle cx="12" cy="6" r="1.8" stroke="currentColor" stroke-width="1.3"/><path d="M10.6 9.6c1.7.2 3 1.4 3.4 3.4" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/></svg>',
    back: '<svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M10 3L4 8l6 5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    chevronRight: '<svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M6 3l5 5-5 5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    calendar: '<svg width="17" height="17" viewBox="0 0 19 19" fill="none"><rect x="2.5" y="4" width="14" height="12.5" rx="2.3" stroke="currentColor" stroke-width="1.5"/><path d="M2.5 7.8h14" stroke="currentColor" stroke-width="1.5"/><path d="M6.3 2.2v3M12.7 2.2v3" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><rect x="5.6" y="10.1" width="2.7" height="2.7" rx="0.6" fill="currentColor"/></svg>',
    bell: '<svg width="17" height="17" viewBox="0 0 19 19" fill="none" aria-hidden="true" focusable="false"><path d="M9.5 2.6a4.6 4.6 0 0 0-4.6 4.6c0 3.4-1.1 4.6-1.6 5.2-.2.2 0 .6.3.6h11.8c.3 0 .5-.4.3-.6-.5-.6-1.6-1.8-1.6-5.2A4.6 4.6 0 0 0 9.5 2.6z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/><path d="M7.9 15.4a1.7 1.7 0 0 0 3.2 0" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>'
  };

  /* ==========================================================================
     2. 유틸리티
     ======================================================================= */

  function esc(str) {
    if (str === null || str === undefined) return '';
    return String(str).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function cssEscapeId(id) {
    try {
      if (window.CSS && CSS.escape) return CSS.escape(id);
    } catch (e) {}
    return String(id).replace(/[^a-zA-Z0-9_-]/g, '\\$&');
  }

  function formatDuration(ms) {
    if (ms === null || ms === undefined || isNaN(ms) || ms < 0) return '--:--';
    var totalSec = Math.round(ms / 1000);
    var h = Math.floor(totalSec / 3600);
    var m = Math.floor((totalSec % 3600) / 60);
    var s = totalSec % 60;
    var pad = function (n) { return String(n).padStart(2, '0'); };
    return h > 0 ? (h + ':' + pad(m) + ':' + pad(s)) : (pad(m) + ':' + pad(s));
  }

  function formatFileSize(bytes) {
    if (bytes === null || bytes === undefined) return '-';
    if (bytes < 1024) return bytes + 'B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + 'KB';
    return (bytes / 1024 / 1024).toFixed(1) + 'MB';
  }

  var DOW = ['일', '월', '화', '수', '목', '금', '토'];
  function formatDateTime(iso, opts) {
    opts = opts || {};
    if (!iso) return '-';
    var d = new Date(iso);
    if (isNaN(d.getTime())) return String(iso);
    var yyyy = d.getFullYear();
    var mm = String(d.getMonth() + 1).padStart(2, '0');
    var dd = String(d.getDate()).padStart(2, '0');
    var dow = DOW[d.getDay()];
    var hh = d.getHours();
    var mi = String(d.getMinutes()).padStart(2, '0');
    if (opts.dateOnly) return yyyy + '.' + mm + '.' + dd + ' (' + dow + ')';
    var ampm = hh < 12 ? '오전' : '오후';
    var hh12 = String(hh % 12 === 0 ? 12 : hh % 12).padStart(2, '0');
    return yyyy + '.' + mm + '.' + dd + '(' + dow + ') ' + ampm + ' ' + hh12 + ':' + mi;
  }

  function shortDate(iso) {
    if (!iso) return '-';
    var d = new Date(iso);
    if (isNaN(d.getTime())) return '-';
    var mm = String(d.getMonth() + 1).padStart(2, '0');
    var dd = String(d.getDate()).padStart(2, '0');
    return mm + '.' + dd;
  }

  function toLocalInputValue(iso) {
    if (!iso) return '';
    var d = new Date(iso);
    if (isNaN(d.getTime())) return '';
    var pad = function (n) { return String(n).padStart(2, '0'); };
    return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()) + 'T' + pad(d.getHours()) + ':' + pad(d.getMinutes());
  }

  function fromLocalInputValue(val) {
    if (!val) return null;
    var d = new Date(val);
    if (isNaN(d.getTime())) return null;
    return d.toISOString();
  }

  function formatPercent(x) {
    if (x === null || x === undefined || isNaN(x)) return null;
    return Math.round(x * 100);
  }

  function shortId(id) {
    var s = String(id || '');
    return s.length > 8 ? s.slice(-6) : s;
  }

  function debounce(fn, wait) {
    var t;
    function debounced() {
      var args = arguments;
      clearTimeout(t);
      t = setTimeout(function () { fn.apply(null, args); }, wait);
    }
    /* Enter 로 즉시 실행할 때 대기 중인 타이머를 취소해 같은 질의가 두 번 나가지 않게 한다. */
    debounced.cancel = function () { clearTimeout(t); };
    return debounced;
  }

  /* 요청 순서 토큰. 같은 뷰에서 조회가 여러 번 겹칠 때(빠른 검색 입력·탭 전환·정렬 변경)
     늦게 도착한 옛 응답이 최신 화면을 덮어쓰는 것을 막는다.
     사용법: var my = seq.next(); ... .then(function(){ if (!seq.isCurrent(my)) return; ... })
     라우트 이탈용 `cancelled` 플래그와는 층이 다르다 — 저건 뷰 밖으로 나갈 때,
     이건 같은 뷰 안에서 조회끼리 경주할 때 쓴다. */
  function seqGuard() {
    var cur = 0;
    return {
      next: function () { cur += 1; return cur; },
      isCurrent: function (t) { return t === cur; }
    };
  }

  /* 같은 동작의 중복 발사를 막는다(버튼 연타 → 요청 2번). fn 이 promise 를 돌려주면
     그게 끝날 때까지 잠근다. 잠겨 있으면 false 를 돌려주고 fn 을 호출하지 않는다. */
  function inFlightLock() {
    var busy = false;
    return function (fn) {
      if (busy) return false;
      busy = true;
      var p;
      try {
        p = fn();
      } catch (e) {
        busy = false;
        throw e;
      }
      if (p && typeof p.then === 'function') {
        p.then(function () { busy = false; }, function () { busy = false; });
      } else {
        busy = false;
      }
      return true;
    };
  }

  function colorFromString(str) {
    var s = String(str || '');
    var h = 0;
    for (var i = 0; i < s.length; i++) { h = (h * 31 + s.charCodeAt(i)) >>> 0; }
    return AVATAR_PALETTE[h % AVATAR_PALETTE.length];
  }

  function statusChipClass(status) {
    if (status === 'ready_for_review') return 'chip-green';
    if (status === 'transcribing' || status === 'summarizing' || status === 'normalizing_audio') return 'chip-amber';
    if (status === 'failed') return 'chip-red';
    return 'chip-gray';
  }

  function statusChipHtml(status) {
    var meta = STATUS_META[status] || { label: status || '알 수 없음' };
    return '<span class="chip ' + statusChipClass(status) + '"><span class="chip-dot"></span>' + esc(meta.label) + '</span>';
  }

  function confidencePillHtml(c) {
    var pct = formatPercent(c);
    if (pct === null) return '<span class="text-muted text-sm">-</span>';
    var cls = pct >= 80 ? 'confidence-high' : (pct >= 50 ? 'confidence-mid' : 'confidence-low');
    return '<span class="confidence-pill ' + cls + '">신뢰도 ' + pct + '%</span>';
  }

  function statusOptionsHtml(options, current) {
    var opts = options.slice();
    if (current && !opts.some(function (o) { return o[0] === current; })) {
      opts = [[current, current]].concat(opts);
    }
    return opts.map(function (o) {
      return '<option value="' + esc(o[0]) + '"' + (o[0] === current ? ' selected' : '') + '>' + esc(o[1]) + '</option>';
    }).join('');
  }

  /* 원문에서 찾고 조각별로 이스케이프한다(raw in → 이스케이프된 HTML out).
     이스케이프 먼저 하면 esc 가 만든 엔티티 속을 검색어가 갈라버린다 —
     예: 제목 "A&B" 에서 'a' 검색 시 &amp; 의 a 까지 <mark> 로 감싸 "A&amp;B" 가 그대로 보이고,
     전사에서는 없던 매치가 생겨 1/131 카운트까지 부풀었다. */
  function highlightMatch(text, q) {
    var s = String(text == null ? '' : text);
    if (!q) return esc(s);
    var escQ = String(q).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    if (!escQ) return esc(s);
    try {
      var parts = s.split(new RegExp('(' + escQ + ')', 'ig'));
      return parts.map(function (part, i) {
        return i % 2 ? '<mark>' + esc(part) + '</mark>' : esc(part);
      }).join('');
    } catch (e) {
      return esc(s);
    }
  }

  function chipsRowHtml(ids) {
    if (!ids || !ids.length) return '';
    return '<div class="chip-row">' + ids.map(function (id) {
      return '<button type="button" class="source-chip" data-action="jump" data-seg="' + esc(id) + '">#' + esc(shortId(id)) + '</button>';
    }).join('') + '</div>';
  }

  function emptyStateHtml(title, body, ctaHtml) {
    return '<div class="list-empty">' + ICONS.empty + (title ? '<h3>' + esc(title) + '</h3>' : '') + (body ? '<p>' + esc(body) + '</p>' : '') + (ctaHtml || '') + '</div>';
  }

  /* 전사 화자를 좌/우로 나눌지 판단: 화자가 정확히 2명이면 1:1 대화처럼 좌/우로, 그 외엔 모두 왼쪽 + 색상 구분 */
  function computeSideMode(segments) {
    var order = [];
    (segments || []).forEach(function (s) { if (order.indexOf(s.speaker_label) === -1) order.push(s.speaker_label); });
    return { twoSpeaker: order.length === 2, order: order };
  }

  /* ---- 토스트 ---- */
  /* 범용 localStorage 헬퍼(서브프로젝트 G). ListColumn 안의 readRecents/writeRecents 는
     그 IIFE 밖에서 못 쓰므로 별도로 둔다(기존 것은 건드리지 않는다).
     프라이빗 모드에선 접근 자체가 예외라 전부 try/catch. */
  function lsGet(key, fallback) {
    try {
      var v = window.localStorage.getItem(key);
      return v === null ? fallback : v;
    } catch (e) { return fallback; }
  }
  function lsSet(key, value) {
    try { window.localStorage.setItem(key, value); return true; } catch (e) { return false; }
  }
  function lsRemove(key) {
    try { window.localStorage.removeItem(key); } catch (e) { /* noop */ }
  }

  function toast(message, type, opts) {
    type = type || 'info';
    opts = opts || {};
    var stack = document.getElementById('toast-stack');
    if (!stack) return;
    var el = document.createElement('div');
    el.className = 'toast toast-' + type;
    var iconSvg = {
      success: '<svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M3 8.5l3 3 7-7" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
      error: '<svg width="16" height="16" viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="6.5" stroke="currentColor" stroke-width="1.6"/><path d="M8 5v4M8 11h.01" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>',
      info: '<svg width="16" height="16" viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="6.5" stroke="currentColor" stroke-width="1.6"/><path d="M8 7.2v3.8M8 5.2h.01" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>'
    }[type] || '';
    el.innerHTML = '<span class="toast-icon">' + iconSvg + '</span><span>' + esc(message) + '</span><button type="button" class="toast-close" aria-label="닫기">' + ICONS.close + '</button>';
    stack.appendChild(el);
    var removed = false;
    function remove() {
      if (removed) return;
      removed = true;
      el.classList.add('is-leaving');
      setTimeout(function () { el.remove(); }, 200);
    }
    el.querySelector('.toast-close').addEventListener('click', remove);
    if (!opts.sticky) setTimeout(remove, opts.duration || 4200);
    return el;
  }

  /* ---- 확인 다이얼로그 ---- */
  function confirmDialog(message, opts) {
    opts = opts || {};
    var title = opts.title || '확인';
    var confirmLabel = opts.confirmLabel || '확인';
    var cancelLabel = opts.cancelLabel || '취소';
    var danger = opts.danger !== false;
    return new Promise(function (resolve) {
      var dlg = document.getElementById('confirm-dialog');
      dlg.querySelector('#confirm-dialog-title').textContent = title;
      dlg.querySelector('#confirm-dialog-body').textContent = message;
      var okBtn = dlg.querySelector('#confirm-dialog-ok');
      var cancelBtn = dlg.querySelector('#confirm-dialog-cancel');
      okBtn.textContent = confirmLabel;
      okBtn.className = 'btn ' + (danger ? 'btn-danger' : 'btn-primary');
      cancelBtn.textContent = cancelLabel;

      // close 이벤트는 큐잉되는 비동기 이벤트라 일부 환경(Electron 셸 등)에서 누락된다.
      // 버튼 핸들러에서 직접 확정하고, ESC/기타 경로만 close·cancel 이벤트로 받는다.
      var settled = false;
      function finish(ok) {
        if (settled) return;
        settled = true;
        okBtn.removeEventListener('click', onOk);
        cancelBtn.removeEventListener('click', onCancel);
        dlg.removeEventListener('close', onClose);
        dlg.removeEventListener('cancel', onEsc);
        resolve(ok);
      }
      function onOk() { dlg.returnValue = 'ok'; dlg.close(); finish(true); }
      function onCancel() { dlg.returnValue = 'cancel'; dlg.close(); finish(false); }
      function onEsc() { finish(false); }
      function onClose() { finish(dlg.returnValue === 'ok'); }
      okBtn.addEventListener('click', onOk);
      cancelBtn.addEventListener('click', onCancel);
      dlg.addEventListener('close', onClose);
      dlg.addEventListener('cancel', onEsc);
      dlg.returnValue = '';
      dlg.showModal();
    });
  }

  function triggerDownload(url) {
    var a = document.createElement('a');
    a.href = url;
    a.rel = 'noopener';
    document.body.appendChild(a);
    a.click();
    a.remove();
  }

  /* ==========================================================================
     3. API 레이어
     ======================================================================= */

  function ApiError(message, code, status, details) {
    var err = new Error(message);
    err.code = code;
    err.status = status;
    err.details = details || {};   // 서버 _err 의 details (예: 요약 충돌 시 current_version)
    return err;
  }

  function apiRequest(path, options) {
    options = options || {};
    return fetch(API_BASE + path, options).catch(function () {
      throw ApiError('서버에 연결할 수 없습니다. 로컬 Worker(localhost:8710)가 실행 중인지 확인해주세요.', 'network_error', 0);
    }).then(function (res) {
      if (res.status === 204) return null;
      return res.text().then(function (text) {
        var data = null;
        if (text) {
          try { data = JSON.parse(text); } catch (e) { data = null; }
        }
        if (!res.ok) {
          var errObj = data && data.error ? data.error : null;
          throw ApiError(
            (errObj && errObj.message) || ('요청이 실패했습니다. (HTTP ' + res.status + ')'),
            (errObj && errObj.code) || 'unknown_error',
            res.status,
            errObj && errObj.details
          );
        }
        return data;
      });
    });
  }

  function apiJson(path, method, body) {
    return apiRequest(path, {
      method: method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
  }

  function buildQuery(params) {
    var usp = new URLSearchParams();
    Object.keys(params || {}).forEach(function (k) {
      var v = params[k];
      if (v !== undefined && v !== null && v !== '') usp.set(k, v);
    });
    var qs = usp.toString();
    return qs ? ('?' + qs) : '';
  }

  var API = {
    presignUpload: function (filename) {
      return fetch(API_BASE + '/uploads/presign', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename: filename })
      }).then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; });
    },
    createJob: function (formData) {
      return apiRequest('/jobs', { method: 'POST', body: formData });
    },
    getJob: function (jobId) {
      return apiRequest('/jobs/' + encodeURIComponent(jobId), { method: 'GET' });
    },
    listMeetings: function (params) {
      return apiRequest('/meetings' + buildQuery(params), { method: 'GET' });
    },
    getKeywords: function () {
      return apiRequest('/keywords', { method: 'GET' });
    },
    getMe: function () {
      return apiRequest('/me', { method: 'GET' });
    },
    getUsage: function () {
      return apiRequest('/usage', { method: 'GET' });
    },
    patchSettings: function (body) {
      return apiJson('/me/settings', 'PATCH', body);
    },
    listNotifications: function (params) {
      return apiRequest('/notifications' + buildQuery(params), { method: 'GET' });
    },
    patchNotification: function (id, body) {
      /* 쓰기는 apiJson — apiRequest 에 body 를 넘기면 직렬화·Content-Type 이 안 붙어 422 가 난다. */
      return apiJson('/notifications/' + encodeURIComponent(id), 'PATCH', body);
    },
    readAllNotifications: function () {
      return apiJson('/notifications/read-all', 'POST', {});
    },
    getCalendar: function (params) {
      return apiRequest('/meetings/calendar' + buildQuery(params), { method: 'GET' });
    },
    getMeeting: function (id) {
      return apiRequest('/meetings/' + encodeURIComponent(id), { method: 'GET' });
    },
    updateMeeting: function (id, body) {
      return apiJson('/meetings/' + encodeURIComponent(id), 'PATCH', body);
    },
    deleteMeeting: function (id) {
      return apiRequest('/meetings/' + encodeURIComponent(id), { method: 'DELETE' });
    },
    listFolders: function () {
      return apiRequest('/folders', { method: 'GET' });
    },
    createFolder: function (body) {
      return apiJson('/folders', 'POST', body);
    },
    patchFolder: function (id, body) {
      return apiJson('/folders/' + encodeURIComponent(id), 'PATCH', body);
    },
    deleteFolder: function (id) {
      return apiRequest('/folders/' + encodeURIComponent(id), { method: 'DELETE' });
    },
    moveMeeting: function (id, body) {
      return apiJson('/meetings/' + encodeURIComponent(id) + '/move', 'POST', body);
    },
    restoreMeeting: function (id) {
      return apiJson('/meetings/' + encodeURIComponent(id) + '/restore', 'POST', {});
    },
    purgeMeeting: function (id) {
      return apiRequest('/meetings/' + encodeURIComponent(id) + '/purge', { method: 'DELETE' });
    },
    emptyTrash: function () {
      return apiJson('/trash/empty', 'POST', {});
    },
    getSegments: function (id) {
      return apiRequest('/meetings/' + encodeURIComponent(id) + '/segments', { method: 'GET' });
    },
    updateSegment: function (meetingId, segmentId, body) {
      return apiJson('/meetings/' + encodeURIComponent(meetingId) + '/segments/' + encodeURIComponent(segmentId), 'PATCH', body);
    },
    renameSpeaker: function (meetingId, speakerLabel, speakerName) {
      return apiJson('/meetings/' + encodeURIComponent(meetingId) + '/speakers/' + encodeURIComponent(speakerLabel), 'PATCH', { speaker_name: speakerName });
    },
    getSummary: function (id) {
      return apiRequest('/meetings/' + encodeURIComponent(id) + '/summary', { method: 'GET' }).catch(function (err) {
        if (err.status === 404) return null;
        throw err;
      });
    },
    getHighlights: function (id) {
      return apiRequest('/meetings/' + encodeURIComponent(id) + '/highlights', { method: 'GET' })
        .catch(function () { return { items: [] }; });
    },
    addHighlight: function (id, payload) {
      return apiJson('/meetings/' + encodeURIComponent(id) + '/highlights', 'POST', payload);
    },
    deleteHighlight: function (id, hlId) {
      return apiJson('/meetings/' + encodeURIComponent(id) + '/highlights/' + encodeURIComponent(hlId), 'DELETE');
    },
    createShareLink: function (id, payload) {
      return apiJson('/meetings/' + encodeURIComponent(id) + '/share-links', 'POST', payload);
    },
    listShareLinks: function (id) {
      return apiRequest('/meetings/' + encodeURIComponent(id) + '/share-links', { method: 'GET' })
        .catch(function () { return { items: [] }; });
    },
    revokeShareLink: function (id, linkId) {
      return apiJson('/meetings/' + encodeURIComponent(id) + '/share-links/' + encodeURIComponent(linkId), 'DELETE');
    },
    getBookmarks: function (id) {
      return apiRequest('/meetings/' + encodeURIComponent(id) + '/bookmarks', { method: 'GET' })
        .catch(function () { return { items: [] }; });
    },
    updateSummary: function (id, body) {
      return apiJson('/meetings/' + encodeURIComponent(id) + '/summary', 'PATCH', body);
    },
    createExport: function (id, body) {
      return apiJson('/meetings/' + encodeURIComponent(id) + '/exports', 'POST', body);
    },
    shareSlack: function (id, body) {
      return apiJson('/meetings/' + encodeURIComponent(id) + '/share/slack', 'POST', body);
    }
  };

  /* ==========================================================================
     4. 라우터 & 앱 셸
     ======================================================================= */

  var shellEl, colCenterEl, colRightEl, colRightContentEl, drawerBackdropEl;
  var currentCleanup = null;
  /* 사용자 설정 캐시 + 부팅 로드 promise. 새 회의 폼 프리필이 첫 렌더(동기) 이후에도
     한 번 더 적용될 수 있게 promise 를 들고 있는다. */
  var userSettings = {};
  var settingsReady = null;

  function parseHash() {
    var h = (location.hash || '#/new').replace(/^#/, '');
    var parts = h.split('/').filter(Boolean);
    if (parts[0] === 'meetings' && parts[1]) {
      var tab = parts[2] && TAB_SLUGS.indexOf(parts[2]) !== -1 ? parts[2] : 'transcript';
      return { name: 'detail', meetingId: decodeURIComponent(parts[1]), tab: tab };
    }
    if (parts[0] === 'meetings') return { name: 'list' };
    if (parts[0] === 'calendar') {
      var y = parseInt(parts[1], 10);
      var m = parseInt(parts[2], 10);
      return {
        name: 'calendar',
        year: (isFinite(y) && y > 1970) ? y : null,
        month: (isFinite(m) && m >= 1 && m <= 12) ? m : null
      };
    }
    // 홈 탭은 회의 목록을 재사용한다(모바일에서 목록 페인, 데스크톱에서 상시 목록 + 빈 본문).
    if (parts[0] === 'home') return { name: 'list' };
    if (parts[0] === 'folders') return { name: 'folders', key: parts[1] ? decodeURIComponent(parts[1]) : null };
    if (parts[0] === 'me') return { name: 'me' };
    if (parts[0] === 'notifications') return { name: 'notifications' };
    return { name: 'new' };
  }

  /* 녹음이 진행 중인지(서브프로젝트 G). 라우트를 떠나면 renderNewMeetingView 의 cleanup 이
     트랙을 정지시켜 녹음이 조용히 사라지므로, 이탈 전에 확인을 받는다. */
  var recordingActive = false;
  /* 새 회의 화면에 넘길 의도. parseHash 가 파라미터를 안 받으므로 라우트 스키마를 늘리지 않고
     모듈 변수로 전달하고 렌더 직후 소비한다. */
  var pendingComposeIntent = null;
  var pendingTour = false;

  function closeFabMenu(focusBack) {
    var menu = document.getElementById('fab-menu');
    var fab = document.getElementById('tab-fab');
    if (!menu || menu.hidden) return false;
    menu.hidden = true;
    if (fab) {
      fab.setAttribute('aria-expanded', 'false');
      if (focusBack) fab.focus();
    }
    return true;
  }

  function initFabMenu() {
    var fab = document.getElementById('tab-fab');
    var menu = document.getElementById('fab-menu');
    if (!fab || !menu) return;
    fab.addEventListener('click', function (e) {
      e.stopPropagation();
      if (!menu.hidden) { closeFabMenu(true); return; }
      menu.hidden = false;
      fab.setAttribute('aria-expanded', 'true');
      var first = menu.querySelector('.fab-menu-item');
      if (first) first.focus();
    });
    menu.addEventListener('click', function (e) {
      var item = e.target.closest('[data-action]');
      if (!item) return;
      closeFabMenu(false);
      /* 자동으로 녹음을 시작하거나 파일 선택창을 열지 않는다 — 권한 프롬프트가 뜨고,
         동의 체크 전에 캡처가 시작되며, hashchange 를 거치며 제스처 창을 벗어난다. */
      if (item.dataset.action === 'tt-fab-upload') pendingComposeIntent = 'upload';
      navigate('#/new');
    });
    document.addEventListener('click', function (e) {
      if (menu.hidden) return;
      if (e.target.closest('#fab-menu') || e.target.closest('#tab-fab')) return;
      closeFabMenu(false);
    });
  }

  function confirmLeaveRecording() {
    return confirmDialog('녹음이 진행 중입니다. 지금 나가면 녹음이 중단됩니다.',
                         { title: '녹음 중단', confirmLabel: '나가기', danger: true });
  }

  /* 저장하지 않은 요약 편집이 있는지(회의 상세). 녹음 가드와 같은 층에서 이탈을 막는다.
     상세 뷰의 dirty 는 클로저 변수라 navigate 에서 못 보므로 여기에 미러링한다.
     상세 cleanup 과 저장 성공 시 반드시 false 로 돌린다. */
  var summaryDirty = false;
  function confirmLeaveUnsavedSummary() {
    return confirmDialog('저장하지 않은 요약 편집이 있습니다. 지금 나가면 사라집니다.',
                         { title: '저장하지 않음', confirmLabel: '나가기', danger: true });
  }

  function navigate(hash) {
    /* 앵커뿐 아니라 JS 에서 부르는 이동(#lc-compose·#lc-bell·노트 행 등)도 여기를 지난다.
       특히 같은 해시로 부르면 hashchange 없이 renderRoute 가 바로 돌아 cleanup 이 실행되므로
       앵커만 가로채는 방식으로는 관측조차 안 된다. */
    if (recordingActive) {
      confirmLeaveRecording().then(function (ok) {
        if (!ok) return;
        recordingActive = false;
        navigate(hash);
      });
      return;
    }
    if (summaryDirty) {
      confirmLeaveUnsavedSummary().then(function (ok) {
        if (!ok) return;
        summaryDirty = false;
        navigate(hash);
      });
      return;
    }
    if (location.hash === hash) {
      renderRoute();
    } else {
      location.hash = hash;
    }
  }

  function updateNavActive(route) {
    // 레일(데스크톱)·탭바(모바일) 공용: [data-nav] 전체를 대상으로 한다.
    document.querySelectorAll('[data-nav]').forEach(function (a) { a.classList.remove('is-active'); });
    // 라우트 → 내비 키. detail 은 홈(목록)에서 진입하므로 홈을 강조. new(FAB)는 지속 탭이 없어 강조 없음.
    var map = { list: 'home', detail: 'home', calendar: 'calendar', folders: 'folders', me: 'me' };
    var key = map[route.name];
    if (!key) return;
    document.querySelectorAll('[data-nav="' + key + '"]').forEach(function (el) { el.classList.add('is-active'); });
  }

  function closeOpenDialogs() {
    document.querySelectorAll('dialog[open]').forEach(function (d) {
      try { d.close(); } catch (e) { /* noop */ }
    });
  }

  function openDrawer() {
    if (colRightEl) colRightEl.classList.add('is-open');
    if (drawerBackdropEl) drawerBackdropEl.classList.add('is-open');
  }
  function closeDrawer() {
    if (colRightEl) colRightEl.classList.remove('is-open');
    if (drawerBackdropEl) drawerBackdropEl.classList.remove('is-open');
  }

  function renderRoute() {
    if (typeof currentCleanup === 'function') {
      try { currentCleanup(); } catch (e) { /* noop */ }
    }
    currentCleanup = null;
    closeOpenDialogs();
    closeDrawer();
    var route = parseHash();
    if (shellEl) shellEl.dataset.route = route.name;
    updateNavActive(route);
    ListColumn.setActive(route.name === 'detail' ? route.meetingId : null);
    colCenterEl.innerHTML = '';
    colRightContentEl.innerHTML = '';
    if (route.name === 'new') {
      document.title = '새 회의 — 회의녹음챗';
      currentCleanup = renderNewMeetingView(colCenterEl, colRightContentEl);
      consumeComposePending(colCenterEl);
    } else if (route.name === 'list') {
      document.title = '홈 — 회의녹음챗';
      renderCenterEmpty(colCenterEl);
      renderRightTips(colRightContentEl, 'list');
    } else if (route.name === 'folders') {
      document.title = '폴더 — 회의녹음챗';
      currentCleanup = route.key
        ? renderFolderDetail(colCenterEl, route.key)
        : renderFolderTree(colCenterEl);
      renderRightTips(colRightContentEl, 'list');
    } else if (route.name === 'me') {
      document.title = '마이 — 회의녹음챗';
      currentCleanup = renderMyPageView(colCenterEl);
      renderRightTips(colRightContentEl, 'list');
    } else if (route.name === 'notifications') {
      document.title = '알림 — 회의녹음챗';
      currentCleanup = renderNotificationsView(colCenterEl);
      renderRightTips(colRightContentEl, 'list');
    } else if (route.name === 'calendar') {
      document.title = '녹음 달력 — 회의녹음챗';
      currentCleanup = renderCalendarView(colCenterEl, colRightContentEl, route.year, route.month);
    } else {
      document.title = '회의 상세 — 회의녹음챗';
      currentCleanup = renderMeetingDetailView(colCenterEl, colRightContentEl, route.meetingId, route.tab);
    }

    /* 안읽음 배지 갱신. updateNavActive 안에 두면 map 에 없는 라우트(new·notifications)에서
       조기 return 하므로 기본 라우트인 부팅 화면에서 배지가 영영 안 뜬다.
       인박스 라우트는 자기 목록 응답의 unread_count 로 세팅하므로 중복 호출하지 않는다. */
    if (route.name !== 'notifications') refreshUnreadBadge();
  }


  /* ==========================================================================
     5. 회의 목록 컬럼 (상시 마운트 — 채팅 앱의 대화 목록처럼 항상 노출)
     ======================================================================= */

  /* 노트 카드 — 상시 목록(ListColumn)과 폴더 상세가 공유. mode 로 우측 액션이 달라진다. */
  function itemChipsHtml(m) {
    var html = statusChipHtml(m.status);
    if (m.has_summary) html += '<span class="chip chip-brand">요약</span>';
    if (m.shared_count > 0) html += '<span class="chip chip-gray">공유 ' + m.shared_count + '</span>';
    return html;
  }

  function renderNoteCard(m, opts) {
    opts = opts || {};
    var title = m.title || '(제목 없음)';
    var col = colorFromString(m.meeting_id);
    var actions;
    if (opts.mode === 'trash') {
      actions =
        '<div class="card-actions">' +
          '<button type="button" class="btn btn-subtle btn-sm" data-action="restore" title="복원">복원</button>' +
          '<button type="button" class="btn btn-danger btn-sm" data-action="purge" title="영구삭제">영구삭제</button>' +
        '</div>';
    } else if (opts.mode === 'folder') {
      actions =
        '<button type="button" class="list-item-delete" data-action="move" title="폴더 이동" aria-label="폴더 이동">' + ICONS.folderMove + '</button>';
    } else {
      actions =
        '<button type="button" class="list-item-delete" data-action="delete" title="삭제" aria-label="회의 삭제">' + ICONS.trash + '</button>';
    }
    return (
      '<div class="list-item' + (m.meeting_id === opts.activeId ? ' is-active' : '') + '" data-id="' + esc(m.meeting_id) + '" tabindex="0">' +
        '<div class="list-item-avatar" style="background:' + col.bg + ';color:' + col.fg + '">' + esc(title.charAt(0) || '회') + '</div>' +
        '<div class="list-item-main">' +
          /* 검색 중이면 제목의 일치 부분도 강조한다(highlightMatch 가 내부에서 esc 함 — 이중 이스케이프 금지). */
          '<div class="list-item-top"><span class="list-item-title">' + (opts.query ? highlightMatch(title, opts.query) : esc(title)) + '</span><span class="list-item-time mono">' + esc(shortDate(m.recorded_at)) + '</span></div>' +
          '<div class="list-item-sub mono">' + esc(formatDateTime(m.recorded_at, { dateOnly: true })) + ' · ' + esc(formatDuration(m.duration_ms)) + '</div>' +
          '<div class="list-item-chips">' + itemChipsHtml(m) + '</div>' +
          ((m.matches && m.matches.length)
            ? '<div class="match-list">' + m.matches.map(function (mt) {
                return '<div class="match-row">' +
                  '<span class="match-src match-src--' + esc(mt.source) + '">' + esc(mt.label) + '</span>' +
                  (mt.start_ms != null ? '<span class="match-time mono">' + esc(formatDuration(mt.start_ms)) + '</span>' : '') +
                  '<span class="match-text">' + highlightMatch(mt.text, opts.query || '') + '</span>' +
                '</div>';
              }).join('') + '</div>'
            : '') +
        '</div>' +
        actions +
      '</div>'
    );
  }

  /* 홈 온보딩 배너 + 기능 카드 (정적). ListColumn.renderItems 가 홈 라우트에서 노트 앞에 prepend. */
  function renderHomeBanner() {
    var features = [
      ['다양한 녹음 언어', '<svg width="18" height="18" viewBox="0 0 20 20" fill="none" aria-hidden="true" focusable="false"><circle cx="10" cy="10" r="7.5" stroke="currentColor" stroke-width="1.5"/><path d="M2.5 10h15M10 2.5c2.5 2 2.5 13 0 15M10 2.5c-2.5 2-2.5 13 0 15" stroke="currentColor" stroke-width="1.5"/></svg>'],
      ['중요한 순간 북마크', '<svg width="18" height="18" viewBox="0 0 20 20" fill="none" aria-hidden="true" focusable="false"><path d="M5 3.5h10v13l-5-3.5-5 3.5v-13z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/></svg>'],
      ['강조 하이라이트', '<svg width="18" height="18" viewBox="0 0 20 20" fill="none" aria-hidden="true" focusable="false"><path d="M3 15l2-6 8-8 3 3-8 8-5 3z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/></svg>'],
      ['녹음 중 실시간 메모', '<svg width="18" height="18" viewBox="0 0 20 20" fill="none" aria-hidden="true" focusable="false"><path d="M4 3.5h9l3 3v10H4v-13z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/><path d="M6.5 8.5h7M6.5 11.5h7" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>'],
      ['이메일로 공유', '<svg width="18" height="18" viewBox="0 0 20 20" fill="none" aria-hidden="true" focusable="false"><rect x="2.5" y="4.5" width="15" height="11" rx="1.5" stroke="currentColor" stroke-width="1.5"/><path d="M3 5.5l7 5 7-5" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/></svg>']
    ];
    return (
      '<div class="home-banner">' +
        '<div class="home-banner-hero">' +
          '<div class="home-banner-title">회의녹음챗, 이렇게 써보세요!</div>' +
          '<div class="home-banner-sub">녹음하거나 파일을 올리면 전사·요약을 자동으로. 북마크·하이라이트·공유까지 한 곳에서.</div>' +
        '</div>' +
        '<div class="home-features">' +
          features.map(function (f) {
            return '<div class="home-feature"><span class="home-feature-icon">' + f[1] + '</span><span class="home-feature-label">' + esc(f[0]) + '</span></div>';
          }).join('') +
        '</div>' +
      '</div>'
    );
  }

  var ListColumn = (function () {
    var scrollEl, searchInput, filterSelect, loadMoreWrap, loadMoreBtn, countEl, chipsEl;
    var items = [];
    var nextCursor = null;
    var suggestedKeywords = [];   // GET /keywords 결과(추천 칩). 실패하면 빈 배열로 남는다.
    var RECENT_KEY = 'ln.recent-search';
    var RECENT_MAX = 5;
    var lastQuery = '';   // 검색 결과 스니펫의 강조에 쓴다(itemHtml 이 fetchList 보다 먼저 정의돼 있어 별도 보관)
    var activeId = null;
    var listSeq = seqGuard();   // 겹친 조회의 응답 역전 방지(fetchList)

    var STATUS_FILTER_OPTIONS = [
      ['', '전체 상태'],
      ['uploaded', '업로드됨'],
      ['normalizing_audio', '정규화 중'],
      ['transcribing', '전사 중'],
      ['summarizing', '요약 생성 중'],
      ['ready_for_review', '검토 대기'],
      ['failed', '실패']
    ];

    function itemHtml(m) {
      return renderNoteCard(m, { activeId: activeId, query: lastQuery, mode: 'list' });
    }

    /* 검색/필터가 없을 때 배너를 노트 앞에 prepend(함께 스크롤). 홈 라우트에서만 보이게 하는 것은
       CSS(.app-shell:not([data-route="list"]) .home-banner{display:none})가 판정한다 — 라우트 이탈 시
       상시 목록(데스크톱)에 배너가 잔존하는 문제를 JS rerender 없이 확실히 막는다(적대적 리뷰 반영). */
    function homeBannerHtml() {
      var isFiltered = !!(searchInput.value.trim() || filterSelect.value);
      return isFiltered ? '' : renderHomeBanner();
    }

    /* ---- 최근 검색어 (localStorage) ----
       프라이빗 모드 등에서 저장소가 막혀 있어도 검색 자체는 굴러가야 하므로 전부 try/catch. */
    function readRecents() {
      try {
        var v = JSON.parse(window.localStorage.getItem(RECENT_KEY) || '[]');
        return Array.isArray(v) ? v.filter(function (s) { return typeof s === 'string' && s; }) : [];
      } catch (e) { return []; }
    }
    function writeRecents(list) {
      try { window.localStorage.setItem(RECENT_KEY, JSON.stringify(list)); } catch (e) { /* 저장 불가 — 무시 */ }
    }
    /* 검색어는 '확정'된 순간에만 쌓는다(디바운스마다 저장하면 'ㄱ','가','감' 같은 조각이 남는다). */
    function commitRecent(q) {
      q = (q || '').trim();
      if (!q) return;
      var list = readRecents().filter(function (s) { return s !== q; });
      list.unshift(q);
      writeRecents(list.slice(0, RECENT_MAX));
      renderChips();
    }
    function clearRecents() {
      writeRecents([]);
      renderChips();
    }

    function chipBtnHtml(text, kind) {
      return '<button type="button" class="search-chip search-chip--' + kind + '" data-chip="' + esc(text) + '">' + esc(text) + '</button>';
    }

    /* 칩 스트립의 유일한 렌더/가시성 판정 지점. 인라인 style 은 쓰지 않는다 —
       라우트 게이팅 CSS 를 이겨버리기 때문에 is-hidden 클래스로만 토글한다. */
    function renderChips() {
      if (!chipsEl) return;
      var recents = readRecents();
      var hasQuery = !!searchInput.value.trim();
      if (hasQuery || (!recents.length && !suggestedKeywords.length)) {
        chipsEl.classList.add('is-hidden');
        chipsEl.innerHTML = '';
        return;
      }
      var html = '';
      if (recents.length) {
        html += '<div class="search-chips-group" role="group" aria-label="최근 검색">' +
          '<div class="search-chips-label">최근 검색' +
            '<button type="button" class="search-chips-clear" data-chip-clear="1" aria-label="최근 검색 전체 삭제">지우기</button>' +
          '</div>' +
          '<div class="search-chips-row">' + recents.map(function (r) { return chipBtnHtml(r, 'recent'); }).join('') + '</div>' +
        '</div>';
      }
      if (suggestedKeywords.length) {
        html += '<div class="search-chips-group" role="group" aria-label="추천 키워드">' +
          '<div class="search-chips-label">추천 키워드</div>' +
          '<div class="search-chips-row">' + suggestedKeywords.map(function (k) { return chipBtnHtml(k, 'suggest'); }).join('') + '</div>' +
        '</div>';
      }
      chipsEl.innerHTML = html;
      chipsEl.classList.remove('is-hidden');
    }

    function renderItems(loading) {
      if (countEl) countEl.textContent = items.length;
      if (loading && items.length === 0) {
        scrollEl.innerHTML = Array.from({ length: 6 }).map(function () { return '<div class="list-skeleton-row"></div>'; }).join('');
        return;
      }
      if (!loading && items.length === 0) {
        var isFiltered = !!(searchInput.value.trim() || filterSelect.value);
        scrollEl.innerHTML = isFiltered
          ? emptyStateHtml('검색 결과가 없습니다', '다른 검색어나 상태 필터를 시도해보세요.')
          : homeBannerHtml() + emptyStateHtml('아직 등록된 회의가 없습니다', '첫 회의를 녹음하거나 파일을 업로드해보세요.', '<a href="#/new" class="btn btn-primary btn-sm">새 회의 시작하기</a>');
        return;
      }
      scrollEl.innerHTML = homeBannerHtml() + items.map(itemHtml).join('');
    }

    function fetchList(reset) {
      if (reset) { items = []; nextCursor = null; renderItems(true); }
      lastQuery = searchInput.value.trim() || '';
      var params = {
        status: filterSelect.value || '',
        q: lastQuery,
        limit: 20,
        cursor: reset ? '' : (nextCursor || '')
      };
      /* 순서 토큰: 빠르게 타이핑하거나 필터를 연달아 바꾸면 조회가 겹치고, 늦게 도착한
         옛 응답이 items 를 통째로 덮어써 화면이 검색어와 어긋난 상태로 남는다.
         '더 보기' 연타의 중복 삽입(같은 커서로 두 번 concat)도 이 가드가 막는다. */
      var my = listSeq.next();
      if (loadMoreBtn) loadMoreBtn.disabled = true;
      API.listMeetings(params).then(function (res) {
        if (!listSeq.isCurrent(my)) return;   /* 더 새 조회가 이미 떠났다 */
        if (loadMoreBtn) loadMoreBtn.disabled = false;
        items = reset ? (res.items || []) : items.concat(res.items || []);
        nextCursor = res.next_cursor || null;
        loadMoreWrap.style.display = nextCursor ? '' : 'none';
        renderItems(false);
      }).catch(function (err) {
        if (!listSeq.isCurrent(my)) return;
        if (loadMoreBtn) loadMoreBtn.disabled = false;
        scrollEl.innerHTML = emptyStateHtml('회의 목록을 불러오지 못했습니다', err.message || '');
        toast(err.message || '회의 목록을 불러오지 못했습니다.', 'error');
      });
    }

    function setActive(id) {
      activeId = id;
      if (!scrollEl) return;
      scrollEl.querySelectorAll('.list-item').forEach(function (row) {
        row.classList.toggle('is-active', row.dataset.id === activeId);
      });
    }

    function init(containerEl) {
      containerEl.innerHTML =
        '<div class="list-header">' +
          '<span class="list-header-title">회의 목록</span>' +
          '<span class="list-header-count mono" id="lc-count">0</span>' +
          '<button type="button" class="list-bell-btn" id="lc-bell" title="알림" aria-label="알림">' + ICONS.bell +
            '<span class="list-bell-dot mono" id="lc-bell-dot" hidden></span></button>' +
          '<button type="button" class="list-compose-btn" id="lc-compose" title="새 회의" aria-label="새 회의">' + ICONS.plus + '</button>' +
        '</div>' +
        '<div class="list-toolbar">' +
          '<div class="list-search-wrap">' + ICONS.search + '<input type="text" class="input" id="lc-search" placeholder="제목 · 전사 · 요약 전체 검색" /></div>' +
          '<select class="select list-filter-select" id="lc-filter">' +
            STATUS_FILTER_OPTIONS.map(function (o) { return '<option value="' + esc(o[0]) + '">' + esc(o[1]) + '</option>'; }).join('') +
          '</select>' +
        '</div>' +
        /* 최근 검색 · 추천 키워드 칩. 홈(list) 라우트에서 쿼리가 비었을 때만 보인다(CSS 게이팅 + is-hidden). */
        '<div class="search-chips" id="lc-chips"></div>' +
        '<div class="list-scroll" id="lc-scroll"></div>' +
        '<div class="list-load-more" id="lc-load-more" style="display:none"><button type="button" class="btn btn-ghost btn-sm" id="lc-load-more-btn">더 보기</button></div>';

      scrollEl = containerEl.querySelector('#lc-scroll');
      searchInput = containerEl.querySelector('#lc-search');
      filterSelect = containerEl.querySelector('#lc-filter');
      loadMoreWrap = containerEl.querySelector('#lc-load-more');
      loadMoreBtn = containerEl.querySelector('#lc-load-more-btn');
      countEl = containerEl.querySelector('#lc-count');
      chipsEl = containerEl.querySelector('#lc-chips');

      containerEl.querySelector('#lc-compose').addEventListener('click', function () { navigate('#/new'); });
      containerEl.querySelector('#lc-bell').addEventListener('click', function () { navigate('#/notifications'); });

      /* 칩: 탭하면 그 말로 검색하고 최근에 올린다. 지우기는 최근 전체 삭제. */
      chipsEl.addEventListener('click', function (e) {
        if (e.target.closest('[data-chip-clear]')) { clearRecents(); return; }
        var chip = e.target.closest('[data-chip]');
        if (!chip) return;
        searchInput.value = chip.dataset.chip;
        commitRecent(chip.dataset.chip);   /* 내부에서 renderChips() → 쿼리가 찼으니 숨겨진다 */
        searchInput.focus();               /* 눌린 칩이 곧바로 사라지므로 포커스를 검색창으로 넘긴다 */
        fetchList(true);
      });

      scrollEl.addEventListener('click', function (e) {
        var delBtn = e.target.closest('[data-action="delete"]');
        var rowEl = e.target.closest('[data-id]');
        if (!rowEl) return;
        var id = rowEl.dataset.id;
        if (delBtn) {
          e.stopPropagation();
          var m = items.find(function (it) { return it.meeting_id === id; });
          confirmDialog('"' + (m ? (m.title || '제목 없음') : id) + '" 회의를 삭제하시겠습니까? 목록에서 제거되며 되돌릴 수 없습니다.', { title: '회의 삭제', confirmLabel: '삭제', danger: true }).then(function (ok) {
            if (!ok) return;
            API.deleteMeeting(id).then(function () {
              items = items.filter(function (it) { return it.meeting_id !== id; });
              /* next_cursor 는 서버가 주는 offset 이다(str(offset+limit)). 목록에서 한 건을
                 지우면 다음 페이지가 한 칸 밀려 한 건을 건너뛰므로 로컬에서 보정한다. */
              if (nextCursor) {
                var n = parseInt(nextCursor, 10);
                if (!isNaN(n)) nextCursor = String(Math.max(0, n - 1));
              }
              renderItems(false);
              toast('회의가 삭제되었습니다.', 'success');
              if (activeId === id) navigate('#/meetings');
            }).catch(function (err) {
              toast(err.message || '삭제에 실패했습니다.', 'error');
            });
          });
          return;
        }
        navigate('#/meetings/' + encodeURIComponent(id));
      });
      scrollEl.addEventListener('keydown', function (e) {
        if (e.key !== 'Enter') return;
        var rowEl = e.target.closest('[data-id]');
        if (rowEl) navigate('#/meetings/' + encodeURIComponent(rowEl.dataset.id));
      });

      var debouncedSearch = debounce(function () { fetchList(true); }, 350);
      searchInput.addEventListener('input', debouncedSearch);
      /* 칩 숨김/표시는 디바운스와 별개로 즉시 반응해야 한다(350ms 늦으면 깜빡인다). */
      searchInput.addEventListener('input', renderChips);
      /* 최근 검색 확정 시점: Enter, 그리고 포커스를 뗄 때(change). */
      searchInput.addEventListener('keydown', function (e) {
        /* 한글 조합을 확정하는 Enter 는 무시한다(isComposing) — 안 그러면 검색이 두세 번 나간다. */
        if (e.key !== 'Enter' || e.isComposing || e.keyCode === 229) return;
        e.preventDefault();
        debouncedSearch.cancel();
        commitRecent(searchInput.value);
        /* 디바운스가 이미 같은 질의를 처리했으면 다시 부르지 않는다(스켈레톤 깜빡임 방지). */
        if ((searchInput.value.trim() || '') !== lastQuery) fetchList(true);
      });
      searchInput.addEventListener('change', function () { commitRecent(searchInput.value); });
      filterSelect.addEventListener('change', function () { fetchList(true); });
      loadMoreBtn.addEventListener('click', function () { fetchList(false); });

      renderChips();
      /* 추천 키워드는 실패해도 검색에 지장이 없으므로 조용히 생략한다. */
      API.getKeywords().then(function (res) {
        suggestedKeywords = ((res && res.keywords) || []).map(function (k) { return k.text; }).filter(Boolean);
        renderChips();
      }).catch(function () { /* 추천 칩 생략 */ });

      fetchList(true);
    }

    return {
      init: init,
      refresh: function (reset) { fetchList(reset !== false); },
      setActive: setActive
    };
  })();


  /* ==========================================================================
     6. 가운데 컬럼: 새 회의 (녹음 / 업로드)
     ======================================================================= */

  function renderNewMeetingView(centerEl, rightEl) {
    renderRightTips(rightEl, 'new');

    var hasRecorder = !!(window.MediaRecorder && navigator.mediaDevices && navigator.mediaDevices.getUserMedia);

    var levelBarsHtml = Array.from({ length: 28 }).map(function () {
      return '<div class="level-meter-bar"></div>';
    }).join('');

    var recorderSectionHtml = hasRecorder ? (
      '<div class="record-stage">' +
        '<div class="record-dial" id="nm-dial">' +
          '<span class="record-dial-time mono" id="nm-timer">00:00</span>' +
          '<span class="record-dial-status" id="nm-dial-status">대기</span>' +
        '</div>' +
        '<div class="level-meter" id="nm-meter">' + levelBarsHtml + '</div>' +
        '<div class="record-controls">' +
          '<button type="button" class="btn btn-primary" id="nm-btn-start">' + ICONS.record + '<span>녹음 시작</span></button>' +
          '<button type="button" class="btn btn-ghost" id="nm-btn-pause" style="display:none">일시정지</button>' +
          '<button type="button" class="btn btn-primary" id="nm-btn-resume" style="display:none">재개</button>' +
          '<button type="button" class="btn btn-ghost" id="nm-btn-bookmark" style="display:none">' + ICONS.star + '<span>북마크</span></button>' +
          '<button type="button" class="btn btn-danger" id="nm-btn-stop" style="display:none">정지</button>' +
        '</div>' +
      '</div>'
    ) : (
      '<div class="record-unsupported">이 브라우저는 브라우저 녹음(MediaRecorder)을 지원하지 않습니다. 아래에서 녹음 파일을 업로드해주세요.</div>'
    );

    centerEl.innerHTML =
      '<div class="col-center-scroll"><div class="compose-scroll view-fade">' +
        '<div class="compose-head">' +
          '<span class="page-eyebrow">STEP 1</span>' +
          '<h1 class="page-title">새 회의 녹음 또는 업로드</h1>' +
          '<p class="page-sub">브라우저에서 바로 녹음하거나, 이미 녹음된 파일을 업로드해 전사와 요약을 자동 생성하세요.</p>' +
        '</div>' +

        '<div id="nm-form-wrap">' +
          '<div class="card card-pad">' +
            '<div class="field">' +
              '<label class="field-label" for="nm-title">회의 제목</label>' +
              '<input type="text" id="nm-title" class="input" placeholder="예: 주간 제품 회의 (비워두면 녹음 일시로 자동 생성됩니다)" />' +
            '</div>' +
            '<div class="field">' +
              '<label class="field-label" for="nm-hotwords">힌트 단어 <span class="field-hint">쉼표로 구분 · 제품명, 참석자 이름 등 (선택)</span></label>' +
              '<input type="text" id="nm-hotwords" class="input" placeholder="예: 회의녹음챗, 김민수, VibeVoice" />' +
            '</div>' +
            '<div class="field">' +
              '<label class="field-label" for="nm-language">전사 언어</label>' +
              '<select class="select" id="nm-language">' +
                '<option value="ko" selected>한국어</option>' +
                '<option value="en">English</option>' +
                '<option value="ja">日本語</option>' +
                '<option value="zh">中文</option>' +
                '<option value="auto">자동 감지</option>' +
              '</select>' +
            '</div>' +
            '<div class="field">' +
              '<label class="checkbox-row">' +
                '<input type="checkbox" id="nm-consent" />' +
                '<span class="checkbox-row-label"><strong>녹음 동의를 확인했습니다.</strong> 참석자에게 녹음 사실을 고지했으며, 업로드된 음성은 전사·요약 처리에 사용됩니다.</span>' +
              '</label>' +
            '</div>' +

            recorderSectionHtml +

            '<div class="divider-or">또는 파일 업로드</div>' +

            '<label class="dropzone" id="nm-dropzone">' +
              '<strong>클릭하거나 파일을 끌어다 놓으세요</strong>' +
              '기존에 녹음된 음성 파일 (m4a, aac, webm, wav 등)' +
              /* Android 파일 선택기는 audio/* 만으로 m4a·webm 을 못 고르는 경우가 있어
                 서버가 허용하는 확장자를 함께 준다(iOS/iPadOS 는 audio/* 로 충분). */
              '<input type="file" id="nm-file-input" ' +
                'accept="audio/*,.m4a,.aac,.mp3,.wav,.webm,.ogg,.mp4" />' +
            '</label>' +

            '<div class="preview-card" id="nm-preview" style="display:none">' +
              '<div class="preview-row">' +
                '<audio controls id="nm-preview-audio" style="flex:1;min-width:220px;height:36px"></audio>' +
              '</div>' +
              '<div class="preview-meta">' +
                '<span id="nm-preview-name" class="truncate" style="max-width:220px"></span>' +
                '<span id="nm-preview-stats"></span>' +
              '</div>' +
              '<div class="flex gap-8 mt-12">' +
                '<button type="button" class="btn btn-primary" id="nm-upload-btn">업로드</button>' +
                '<button type="button" class="btn btn-ghost" id="nm-reset-btn">다시 녹음 / 다른 파일 선택</button>' +
              '</div>' +
            '</div>' +
          '</div>' +
        '</div>' +

        '<div id="nm-stepper-wrap" style="display:none"></div>' +
      '</div></div>';

    /* ---- 엘리먼트 참조 ---- */
    var formWrap = centerEl.querySelector('#nm-form-wrap');
    var stepperWrap = centerEl.querySelector('#nm-stepper-wrap');
    var titleInput = centerEl.querySelector('#nm-title');
    var hotwordsInput = centerEl.querySelector('#nm-hotwords');
    var languageSelect = centerEl.querySelector('#nm-language');
    var consentInput = centerEl.querySelector('#nm-consent');

    /* 마이페이지에 저장한 설정으로 힌트 단어·언어를 채운다.
       빈 필드/기본값일 때만 건드려 사용자가 입력 중인 값을 덮지 않는다.
       키가 아예 없는 설정({"language":"ko"} 처럼)도 있으므로 반드시 값 존재를 먼저 본다 —
       무가드로 .join() 하면 이 화면(기본 라우트)의 이벤트 바인딩 전체가 죽는다. */
    var prefillCancelled = false;
    /* '값이 기본값이다'로는 사용자가 손댔는지 알 수 없다. 언어 기본값이 'ko' 라서,
       사용자가 일부러 '한국어'를 고른 경우와 건드리지 않은 경우가 구별되지 않는다
       → 늦게 도착한 settingsReady 가 그 선택을 저장된 언어로 되돌린다.
       그래서 값이 아니라 '손댔는지'를 따로 기록한다. */
    var prefillTouched = { lang: false, hotwords: false };
    if (languageSelect) {
      languageSelect.addEventListener('change', function () { prefillTouched.lang = true; });
    }
    if (hotwordsInput) {
      hotwordsInput.addEventListener('input', function () { prefillTouched.hotwords = true; });
    }
    function applySettingsPrefill() {
      if (prefillCancelled) return;
      var hw = userSettings && userSettings.hotwords;
      if (hw && hw.length && !prefillTouched.hotwords && !hotwordsInput.value) {
        hotwordsInput.value = hw.join(', ');
      }
      var lang = userSettings && userSettings.language;
      if (lang && languageSelect && !prefillTouched.lang && languageSelect.value === 'ko') {
        languageSelect.value = lang;
      }
    }
    applySettingsPrefill();
    if (settingsReady) settingsReady.then(applySettingsPrefill);
    var dialEl = centerEl.querySelector('#nm-dial');
    var dialTimeEl = centerEl.querySelector('#nm-timer');
    var dialStatusEl = centerEl.querySelector('#nm-dial-status');
    var meterBars = Array.from(centerEl.querySelectorAll('.level-meter-bar'));
    var startBtn = centerEl.querySelector('#nm-btn-start');
    var pauseBtn = centerEl.querySelector('#nm-btn-pause');
    var resumeBtn = centerEl.querySelector('#nm-btn-resume');
    var stopBtn = centerEl.querySelector('#nm-btn-stop');
    var bookmarkBtn = centerEl.querySelector('#nm-btn-bookmark');
    var dropzone = centerEl.querySelector('#nm-dropzone');
    var fileInput = centerEl.querySelector('#nm-file-input');
    var previewCard = centerEl.querySelector('#nm-preview');
    var previewAudio = centerEl.querySelector('#nm-preview-audio');
    var previewName = centerEl.querySelector('#nm-preview-name');
    var previewStats = centerEl.querySelector('#nm-preview-stats');
    var uploadBtn = centerEl.querySelector('#nm-upload-btn');
    var resetBtn = centerEl.querySelector('#nm-reset-btn');

    /* ---- 상태 ---- */
    var recState = 'idle'; // idle | recording | paused | stopped
    var mediaStream = null;
    var mediaRecorder = null;
    var audioCtx = null, analyser = null;
    var chunks = [];
    var startedAt = null;
    var liveBookmarks = [];   // 녹음 중 찍은 북마크(ms)
    var elapsedMs = 0;
    var segmentStartTs = 0;
    var timerRaf = null;
    var meterRaf = null;
    var resultSource = null; // 'recording' | 'file'
    var resultFile = null;
    var resultMime = null;
    var previewInfo = null; // { url, name, size, durationMs }
    /* Storage 직접 업로드가 성공한 뒤 POST /jobs 가 실패하면, 오디오 객체는 이미 올라가
       있는데 DB 행은 하나도 없다(회수 경로도 없는 고아 파일). 그 상태에서 사용자가 업로드를
       다시 누르면 또 올려서 고아를 하나 더 만든다. 그래서 성공한 업로드를 기억해 두고
       재시도 때는 /jobs 만 다시 부른다. 새 녹음/새 파일을 고르면 버린다. */
    var pendingDirect = null;
    var pollTimer = null;
    var pollAttempts = 0;
    var MAX_POLL_ATTEMPTS = 240;

    function mimeExt(mime) {
      if (!mime) return 'webm';
      if (mime.indexOf('mp4') !== -1) return 'm4a';
      if (mime.indexOf('ogg') !== -1) return 'ogg';
      return 'webm';
    }

    function setState(s) {
      recState = s;
      /* 녹음/일시정지 중에만 이탈 확인을 건다. 정지·대기로 돌아오면 즉시 해제해야
         이후 내비게이션마다 확인창이 뜨지 않는다. */
      recordingActive = (s === 'recording' || s === 'paused');
      if (dialEl) {
        dialEl.classList.remove('is-recording', 'is-paused', 'is-stopped');
        if (s === 'recording') dialEl.classList.add('is-recording');
        if (s === 'paused') dialEl.classList.add('is-paused');
        if (s === 'stopped') dialEl.classList.add('is-stopped');
        if (dialStatusEl) {
          dialStatusEl.textContent = { idle: '대기', recording: '녹음 중', paused: '일시정지', stopped: '완료' }[s] || '대기';
        }
      }
      if (startBtn) startBtn.style.display = s === 'idle' ? '' : 'none';
      if (pauseBtn) pauseBtn.style.display = s === 'recording' ? '' : 'none';
      if (resumeBtn) resumeBtn.style.display = s === 'paused' ? '' : 'none';
      if (stopBtn) stopBtn.style.display = (s === 'recording' || s === 'paused') ? '' : 'none';
      if (bookmarkBtn) bookmarkBtn.style.display = (s === 'recording' || s === 'paused') ? '' : 'none';
    }

    /* 녹음 중 북마크 — 중요한 순간을 그 자리에서 표시한다.
       전사가 끝나면 서버가 이 시각을 포함하는 세그먼트로 표시를 옮기고,
       재생 화면의 파형에도 마커로 찍힌다. */
    function currentRecordMs() {
      return recState === 'recording'
        ? elapsedMs + (performance.now() - segmentStartTs)
        : elapsedMs;
    }

    function addLiveBookmark() {
      var at = Math.round(currentRecordMs());
      // 연타로 같은 지점이 중복 기록되는 것을 막는다
      if (liveBookmarks.length && Math.abs(liveBookmarks[liveBookmarks.length - 1] - at) < 800) return;
      liveBookmarks.push(at);
      toast(formatDuration(at) + ' 북마크됨', 'success');
      var label = bookmarkBtn && bookmarkBtn.querySelector('span');
      if (label) label.textContent = '북마크 ' + liveBookmarks.length;
    }

    function tickTimer() {
      if (recState !== 'recording') return;
      var now = performance.now();
      var liveMs = elapsedMs + (now - segmentStartTs);
      if (dialTimeEl) dialTimeEl.textContent = formatDuration(liveMs);
      timerRaf = requestAnimationFrame(tickTimer);
    }

    function setupLevelMeter(stream) {
      try {
        var Ctx = window.AudioContext || window.webkitAudioContext;
        audioCtx = new Ctx();
        var source = audioCtx.createMediaStreamSource(stream);
        analyser = audioCtx.createAnalyser();
        analyser.fftSize = 64;
        source.connect(analyser);
        startLevelMeterAnim();
      } catch (e) { /* 레벨 미터는 부가 기능 — 실패해도 녹음에는 지장 없음 */ }
    }
    function startLevelMeterAnim() {
      if (!analyser) return;
      var data = new Uint8Array(analyser.frequencyBinCount);
      var n = meterBars.length;
      function loop() {
        analyser.getByteFrequencyData(data);
        for (var i = 0; i < n; i++) {
          var idx = Math.floor((i / n) * data.length);
          var v = data[idx] / 255;
          meterBars[i].style.transform = 'scaleY(' + Math.max(0.06, v) + ')';
        }
        meterRaf = requestAnimationFrame(loop);
      }
      meterRaf = requestAnimationFrame(loop);
    }
    function stopLevelMeterAnim() {
      if (meterRaf) cancelAnimationFrame(meterRaf);
      meterBars.forEach(function (b) { b.style.transform = 'scaleY(0.06)'; });
    }
    function teardownLevelMeter() {
      stopLevelMeterAnim();
      if (audioCtx) { try { audioCtx.close(); } catch (e) {} audioCtx = null; }
      analyser = null;
    }

    function startRecording() {
      navigator.mediaDevices.getUserMedia({ audio: true }).then(function (stream) {
        mediaStream = stream;
        var mimeCandidates = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4'];
        var mime = mimeCandidates.find(function (m) {
          return window.MediaRecorder.isTypeSupported && window.MediaRecorder.isTypeSupported(m);
        }) || '';
        try {
          mediaRecorder = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream);
        } catch (e) {
          mediaRecorder = new MediaRecorder(stream);
        }
        resultMime = mediaRecorder.mimeType || mime || 'audio/webm';
        chunks = [];
        mediaRecorder.ondataavailable = function (e) { if (e.data && e.data.size > 0) chunks.push(e.data); };
        mediaRecorder.onstop = onRecorderStop;
        mediaRecorder.start(250);
        startedAt = new Date();
        liveBookmarks = [];
        elapsedMs = 0;
        segmentStartTs = performance.now();
        setState('recording');
        setupLevelMeter(stream);
        timerRaf = requestAnimationFrame(tickTimer);
      }).catch(function () {
        toast('마이크 접근이 거부되었습니다. 브라우저 권한 설정을 확인해주세요.', 'error');
      });
    }

    function pauseRecording() {
      if (!mediaRecorder || recState !== 'recording') return;
      mediaRecorder.pause();
      elapsedMs += performance.now() - segmentStartTs;
      if (timerRaf) cancelAnimationFrame(timerRaf);
      setState('paused');
      stopLevelMeterAnim();
    }

    function resumeRecording() {
      if (!mediaRecorder || recState !== 'paused') return;
      mediaRecorder.resume();
      segmentStartTs = performance.now();
      setState('recording');
      startLevelMeterAnim();
      timerRaf = requestAnimationFrame(tickTimer);
    }

    function stopRecording() {
      if (!mediaRecorder || (recState !== 'recording' && recState !== 'paused')) return;
      if (recState === 'recording') elapsedMs += performance.now() - segmentStartTs;
      if (timerRaf) cancelAnimationFrame(timerRaf);
      mediaRecorder.stop();
      teardownLevelMeter();
      if (mediaStream) mediaStream.getTracks().forEach(function (t) { t.stop(); });
      setState('stopped');
    }

    function onRecorderStop() {
      var blob = new Blob(chunks, { type: resultMime });
      if (elapsedMs < 1000) {
        toast('녹음이 너무 짧습니다. 1초 이상 녹음해주세요.', 'error');
        setState('idle');
        if (dialTimeEl) dialTimeEl.textContent = '00:00';
        return;
      }
      resultSource = 'recording';
      resultFile = null;
      showPreview({
        durationMs: elapsedMs,
        size: blob.size,
        url: URL.createObjectURL(blob),
        name: 'recording-' + Date.now() + '.' + mimeExt(resultMime),
        blob: blob
      });
    }

    function handleFileSelected(file) {
      if (!file) return;
      resultSource = 'file';
      resultFile = file;
      var url = URL.createObjectURL(file);
      var probe = new Audio();
      probe.preload = 'metadata';
      probe.src = url;
      probe.onloadedmetadata = function () {
        var dur = probe.duration;
        if (!isFinite(dur) || isNaN(dur)) dur = 0;
        showPreview({ durationMs: Math.round(dur * 1000), size: file.size, url: url, name: file.name });
      };
      probe.onerror = function () {
        showPreview({ durationMs: 0, size: file.size, url: url, name: file.name });
      };
    }

    function showPreview(info) {
      previewInfo = info;
      pendingDirect = null;      // 새 파일이면 앞서 올려둔 객체는 쓸 수 없다
      previewCard.style.display = '';
      previewAudio.src = info.url;
      previewName.textContent = info.name;
      previewStats.innerHTML = '길이 <b class="mono">' + formatDuration(info.durationMs) + '</b> · 크기 <b class="mono">' + formatFileSize(info.size) + '</b>';
      previewCard.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }

    function hidePreview() {
      previewCard.style.display = 'none';
      if (previewInfo && previewInfo.url) URL.revokeObjectURL(previewInfo.url);
      previewInfo = null;
      pendingDirect = null;
    }

    function resetAll() {
      hidePreview();
      setState('idle');
      if (dialTimeEl) dialTimeEl.textContent = '00:00';
      if (fileInput) fileInput.value = '';
      resultSource = null;
      resultFile = null;
    }

    function uploadNow() {
      if (!consentInput.checked) {
        toast('녹음 동의 확인 체크박스를 선택해야 업로드할 수 있습니다.', 'error');
        consentInput.focus();
        return;
      }
    /* 브라우저 → Supabase Storage 직접 업로드.
       서버는 경로만 받으므로 Vercel 의 4.5MB 요청 본문 제한을 받지 않는다.
       presign 이 supported:false 를 주면(로컬 저장소) null 을 돌려 호출측이
       기존 multipart 로 되돌아간다. 실패해도 마찬가지 — 업로드 자체를 막지 않는다. */
    function tryDirectUpload(filePart, fileName) {
      /* 앞선 시도에서 이미 올려둔 객체가 있으면 그걸 쓴다(재업로드 = 고아 하나 더). */
      if (pendingDirect) return Promise.resolve(pendingDirect);
      return API.presignUpload(fileName).then(function (pre) {
        if (!pre || !pre.supported) return null;
        if (filePart.size > (pre.max_bytes || Infinity)) {
          throw new Error('녹음 파일이 너무 큽니다 (' +
            Math.round((pre.max_bytes || 0) / 1024 / 1024) + 'MB 이하).');
        }
        return new Promise(function (resolve, reject) {
          var xhr = new XMLHttpRequest();
          xhr.open('PUT', pre.upload_url, true);
          xhr.setRequestHeader('Content-Type', filePart.type || 'application/octet-stream');
          xhr.upload.onprogress = function (e) {
            if (!e.lengthComputable) return;
            uploadBtn.textContent = '업로드 중… ' + Math.round((e.loaded / e.total) * 100) + '%';
          };
          xhr.onload = function () {
            if (xhr.status >= 200 && xhr.status < 300) {
              uploadBtn.textContent = '처리 준비 중…';
              pendingDirect = { storage_path: pre.storage_path, meeting_id: pre.meeting_id };
              resolve(pendingDirect);
            } else {
              reject(new Error('업로드에 실패했습니다 (' + xhr.status + ').'));
            }
          };
          xhr.onerror = function () { reject(new Error('업로드 중 네트워크 오류가 발생했습니다.')); };
          xhr.send(filePart);
        });
      }).catch(function (err) {
        // presign 단계 실패는 치명적이지 않다 — 기존 경로로 넘긴다.
        if (err && /너무 큽니다/.test(err.message)) throw err;
        return null;
      });
    }

      if (!previewInfo) { toast('업로드할 녹음 또는 파일이 없습니다.', 'error'); return; }
      uploadBtn.disabled = true;
      resetBtn.disabled = true;
      uploadBtn.textContent = '업로드 중…';

      var fd = new FormData();
      var filePart = resultSource === 'recording' ? previewInfo.blob : resultFile;
      var fileName = resultSource === 'recording' ? previewInfo.name : resultFile.name;
      var title = titleInput.value.trim();
      if (title) fd.append('title', title);
      var recordedAt = resultSource === 'recording'
        ? startedAt.toISOString()
        : (resultFile.lastModified ? new Date(resultFile.lastModified).toISOString() : new Date().toISOString());
      fd.append('recorded_at', recordedAt);
      fd.append('duration_ms', String(Math.round(previewInfo.durationMs || 0)));
      fd.append('source_device', resultSource === 'recording' ? 'web_recorder' : 'file_upload');
      fd.append('language', (languageSelect && languageSelect.value) || 'ko');
      var hotwordsRaw = hotwordsInput.value.trim();
      if (hotwordsRaw) {
        var list = hotwordsRaw.split(',').map(function (s) { return s.trim(); }).filter(Boolean);
        if (list.length) fd.append('hotwords', JSON.stringify(list));
      }
      fd.append('recording_consent_confirmed', consentInput.checked ? 'true' : 'false');
      if (liveBookmarks.length) fd.append('bookmarks', JSON.stringify(liveBookmarks));

      // 파일이 API 를 통과하면 Vercel 서버리스의 요청 본문 제한(4.5MB)에 걸려
      // 2분 남짓 녹음도 못 올린다. Storage 직접 업로드가 가능하면 그쪽을 쓰고,
      // 안 되면(로컬 저장소 등) 기존 multipart 로 그대로 돌아간다.
      tryDirectUpload(filePart, fileName).then(function (direct) {
        if (direct) {
          fd.append('storage_path', direct.storage_path);
          fd.append('meeting_id', direct.meeting_id);
        } else {
          fd.append('audio_file', filePart, fileName);
        }
        return API.createJob(fd);
      }).then(function (res) {
        pendingDirect = null;          // 등록까지 끝났으니 재사용할 것이 없다
        ListColumn.refresh(true);
        startPolling(res.job_id, res.meeting_id);
      }).catch(function (err) {
        /* 파일은 이미 올라가 있고 등록만 실패한 경우가 있어, 다시 눌러도 된다고 알린다
           (재시도는 올려둔 객체를 재사용하므로 업로드가 두 번 일어나지 않는다). */
        toast((err.message || '업로드에 실패했습니다.') +
              (pendingDirect ? ' 파일은 보관돼 있으니 다시 눌러 주세요.' : ''), 'error');
        uploadBtn.disabled = false;
        resetBtn.disabled = false;
        uploadBtn.textContent = '업로드';
      });
    }

    /* ---- 처리 상태 폴링 & 스테퍼 ---- */
    /* 라우트를 떠나면 cleanup 이 pollTimer 를 지우지만, 그 순간 이미 날아간 getJob 응답은
       그대로 도착한다. 그 응답이 ready_for_review 면 toast + navigate 로 **다른 화면에 있는
       사용자를 강제로 끌고 가고**, 아니면 setTimeout 으로 루프를 되살린다.
       타이머 취소만으로는 부족해서 응답 자체를 무시할 플래그가 필요하다. */
    var viewGone = false;
    function startPolling(jobId, meetingId) {
      formWrap.style.display = 'none';
      stepperWrap.style.display = '';
      renderStepper({ status: 'uploaded', progress: 0, current_stage: null });
      pollAttempts = 0;
      poll();
      function poll() {
        pollAttempts++;
        API.getJob(jobId).then(function (job) {
          if (viewGone) return;
          renderStepper(job);
          if (job.status === 'ready_for_review') {
            ListColumn.refresh(true);
            toast('처리가 완료되었습니다. 회의 상세로 이동합니다.', 'success');
            setTimeout(function () { navigate('#/meetings/' + encodeURIComponent(meetingId)); }, 700);
            return;
          }
          if (job.status === 'failed') {
            ListColumn.refresh(true);
            renderStepperError(job);
            return;
          }
          if (pollAttempts >= MAX_POLL_ATTEMPTS) { renderStepperTimeout(); return; }
          pollTimer = setTimeout(poll, 1500);
        }).catch(function () {
          if (viewGone) return;
          if (pollAttempts >= MAX_POLL_ATTEMPTS) { renderStepperTimeout(); return; }
          pollTimer = setTimeout(poll, 2000);
        });
      }
    }

    function renderStepper(job) {
      var stageIdx = JOB_STAGES.indexOf(job.status);
      var stepsHtml = JOB_STAGES.map(function (stage, i) {
        var cls = 'stepper-step';
        var inner = '<span>' + (i + 1) + '</span>';
        if (stageIdx > i || (stageIdx === i && stage === 'ready_for_review')) {
          cls += ' is-done'; inner = ICONS.check;
        } else if (stageIdx === i) {
          cls += ' is-active'; inner = '<span class="stepper-spin"></span>';
        }
        return '<div class="' + cls + '"><div class="stepper-node">' + inner + '</div><div class="stepper-label">' + esc(STAGE_LABELS[stage]) + '</div></div>';
      }).join('');
      var pct = Math.round((job.progress || 0) * 100);
      var stageLabel = job.current_stage ? (STAGE_LABELS[job.current_stage] || job.current_stage) : (STAGE_LABELS[job.status] || job.status);
      stepperWrap.innerHTML =
        '<div class="card card-pad">' +
          '<div class="card-title">처리 진행 상황</div>' +
          '<div class="stepper-wrap"><div class="stepper">' + stepsHtml + '</div></div>' +
          '<div class="progress-track"><div class="progress-fill" style="width:' + pct + '%"></div></div>' +
          '<div class="progress-caption"><span>' + esc(stageLabel) + '</span><span class="mono">' + pct + '%</span></div>' +
        '</div>';
    }

    function renderStepperError(job) {
      renderStepper(job);
      var card = stepperWrap.querySelector('.card');
      var box = document.createElement('div');
      box.className = 'stage-error';
      box.innerHTML = '<strong>처리 실패' + (job.error_code ? (' (' + esc(job.error_code) + ')') : '') + '</strong>' + esc(job.error_message || '알 수 없는 오류가 발생했습니다.');
      card.appendChild(box);
      var retryBtn = document.createElement('button');
      retryBtn.type = 'button';
      retryBtn.className = 'btn btn-ghost mt-16';
      retryBtn.textContent = '새 회의로 다시 시도';
      retryBtn.addEventListener('click', function () { navigate('#/new'); });
      card.appendChild(retryBtn);
    }

    function renderStepperTimeout() {
      var card = stepperWrap.querySelector('.card');
      var box = document.createElement('div');
      box.className = 'stage-error';
      box.innerHTML = '<strong>응답이 지연되고 있습니다</strong>처리가 예상보다 오래 걸리고 있습니다. 잠시 후 회의 목록에서 상태를 확인해주세요.';
      card.appendChild(box);
      var goListBtn = document.createElement('button');
      goListBtn.type = 'button';
      goListBtn.className = 'btn btn-ghost mt-16';
      goListBtn.textContent = '회의 목록으로 이동';
      goListBtn.addEventListener('click', function () { navigate('#/meetings'); });
      card.appendChild(goListBtn);
    }

    /* ---- 이벤트 바인딩 ---- */
    if (startBtn) startBtn.addEventListener('click', startRecording);
    if (pauseBtn) pauseBtn.addEventListener('click', pauseRecording);
    if (resumeBtn) resumeBtn.addEventListener('click', resumeRecording);
    if (bookmarkBtn) bookmarkBtn.addEventListener('click', addLiveBookmark);
    if (stopBtn) stopBtn.addEventListener('click', stopRecording);
    uploadBtn.addEventListener('click', uploadNow);
    resetBtn.addEventListener('click', resetAll);

    dropzone.addEventListener('dragover', function (e) { e.preventDefault(); dropzone.classList.add('is-dragover'); });
    dropzone.addEventListener('dragleave', function () { dropzone.classList.remove('is-dragover'); });
    dropzone.addEventListener('drop', function (e) {
      e.preventDefault();
      dropzone.classList.remove('is-dragover');
      var f = e.dataTransfer.files && e.dataTransfer.files[0];
      if (f) handleFileSelected(f);
    });
    fileInput.addEventListener('change', function (e) {
      var f = e.target.files && e.target.files[0];
      if (f) handleFileSelected(f);
    });

    setState('idle');

    return function cleanup() {
      prefillCancelled = true;   // 늦게 도착한 설정이 사라진 폼에 쓰지 않게
      recordingActive = false;   // 이 뷰를 떠나면 확인 대상도 사라진다
      viewGone = true;           // in-flight 폴링 응답이 강제 이동시키지 못하게
      if (pollTimer) clearTimeout(pollTimer);
      if (timerRaf) cancelAnimationFrame(timerRaf);
      teardownLevelMeter();
      if (mediaStream) mediaStream.getTracks().forEach(function (t) { t.stop(); });
      if (mediaRecorder && (recState === 'recording' || recState === 'paused')) {
        try { mediaRecorder.stop(); } catch (e) {}
      }
      if (previewInfo && previewInfo.url) URL.revokeObjectURL(previewInfo.url);
    };
  }

  /* FAB '파일 업로드' 의도와 '튜토리얼 다시 보기' 요청을 렌더가 끝난 뒤에 소비한다.
     hashchange 가 비동기라 navigate() 직후에 처리하면 아직 이 화면이 없다. */
  function consumeComposePending(centerEl) {
    if (pendingComposeIntent === 'upload') {
      pendingComposeIntent = null;
      var dz = centerEl.querySelector('#nm-dropzone');
      if (dz) {
        dz.scrollIntoView({ block: 'center', behavior: 'smooth' });
        var fi = centerEl.querySelector('#nm-file-input');
        if (fi) fi.focus();   // 파일 선택창은 열지 않는다(제스처 창 이탈)
      }
    }
    if (pendingTour) {
      pendingTour = false;
      startTour();
    }
  }


  /* ==========================================================================
     7. 가운데 빈 상태 / 오른쪽 안내 팁
     ======================================================================= */

  function renderCenterEmpty(centerEl) {
    centerEl.innerHTML =
      '<div class="center-empty view-fade">' +
        '<div class="center-empty-icon">' + ICONS.empty + '</div>' +
        '<h2>회의를 선택하세요</h2>' +
        '<p>왼쪽 목록에서 회의를 클릭하면 전사와 요약을 확인할 수 있습니다.</p>' +
        '<a href="#/new" class="btn btn-primary">+ 새 회의 시작하기</a>' +
      '</div>';
  }

  function renderRightTips(rightEl, mode) {
    var heading = mode === 'new' ? '녹음 팁' : '회의녹음챗 사용법';
    rightEl.innerHTML =
      '<div class="right-section-head"><span class="right-section-title">' + esc(heading) + '</span></div>' +
      '<div class="tips-card">' +
        '<div class="tip-item"><span class="tip-num">1</span><span>녹음 시작 전 참석자에게 녹음 사실을 알리고 동의를 구하세요.</span></div>' +
        '<div class="tip-item"><span class="tip-num">2</span><span>제품명이나 참석자 이름을 힌트 단어에 적으면 전사 정확도가 올라갑니다.</span></div>' +
        '<div class="tip-item"><span class="tip-num">3</span><span>업로드 후 오디오 정규화 → 전사 → 요약 순서로 자동 처리됩니다.</span></div>' +
        '<div class="tip-item"><span class="tip-num">4</span><span>처리가 끝나면 화자 이름 수정, 북마크, 요약 편집을 진행할 수 있습니다.</span></div>' +
        '<div class="tip-item"><span class="tip-num">5</span><span>왼쪽 목록에서 회의를 선택하면 전사와 요약을 언제든 다시 검토할 수 있습니다.</span></div>' +
      '</div>';
  }


  /* ==========================================================================
     8. 가운데 + 오른쪽 컬럼: 회의 상세
     ======================================================================= */

  /* ==========================================================================
     튜토리얼 온보딩 (서브프로젝트 G) — 최초 실행 코치마크
     ======================================================================= */

  var TOUR_KEY = 'ln.tour-seen';
  /* 문구 출처는 renderRightTips 의 녹음 팁. 모바일 #/new 에선 우측 팁이 도달 불가라
     투어가 그 자리를 대신한다(데스크톱은 우측에 이미 같은 내용이 보이므로 띄우지 않는다). */
  var TOUR_STEPS = [
    { sel: '#nm-consent', title: '먼저 동의를 확인해요', body: '참석자에게 녹음을 알렸는지 체크하면 녹음을 시작할 수 있어요.' },
    { sel: '#nm-btn-start', title: '여기서 녹음을 시작해요', body: '녹음이 끝나면 전사와 요약이 자동으로 만들어져요.' },
    { sel: '#nm-hotwords', title: '힌트 단어를 넣어보세요', body: '제품명·참석자 이름을 미리 적으면 전사 정확도가 올라가요.' },
    { sel: '#nm-dropzone', title: '이미 있는 파일도 괜찮아요', body: '녹음 파일을 끌어다 놓거나 눌러서 올릴 수 있어요.' }
  ];

  var tourState = null;   // { i, steps, overlay, onScroll, onKey, prevFocus }

  function tourActive() { return !!tourState; }

  function tourVisible(el) {
    if (!el) return false;
    var r = el.getBoundingClientRect();
    /* 라우트 게이팅으로 숨겨진 요소는 null 이 아니라 0-rect 를 돌려준다. */
    return r.width > 0 && r.height > 0;
  }

  function startTour() {
    if (tourState) return;
    var steps = TOUR_STEPS.filter(function (s) { return tourVisible(document.querySelector(s.sel)); });
    if (!steps.length) return;   // MediaRecorder 미지원 등 — 조용히 넘어간다(플래그도 안 쓴다)

    var overlay = document.createElement('div');
    overlay.className = 'tour-overlay';
    overlay.setAttribute('role', 'dialog');
    overlay.innerHTML = '<div class="tour-hole"></div>' +
      '<div class="tour-bubble">' +
        '<div class="tour-step mono"></div>' +
        '<h2 class="tour-title"></h2>' +
        '<p class="tour-body"></p>' +
        '<div class="tour-actions">' +
          '<button type="button" class="btn btn-ghost btn-sm" data-action="tt-skip">건너뛰기</button>' +
          '<button type="button" class="btn btn-primary btn-sm" data-action="tt-next">다음</button>' +
        '</div>' +
      '</div>';
    document.getElementById('app-shell').appendChild(overlay);

    tourState = { i: 0, steps: steps, overlay: overlay, prevFocus: document.activeElement };

    overlay.addEventListener('click', function (e) {
      var el = e.target.closest('[data-action]');
      if (!el) return;
      if (el.dataset.action === 'tt-skip') endTour(true);
      else if (el.dataset.action === 'tt-next') nextStep();
    });
    tourState.onScroll = function () { positionTour(); };
    var scroller = document.querySelector('.col-center-scroll');
    if (scroller) scroller.addEventListener('scroll', tourState.onScroll);
    window.addEventListener('resize', tourState.onScroll);
    tourState.scroller = scroller;
    /* 라우트가 바뀌면 타깃이 사라지므로 종료. 이 경로는 '봤다'로 치지 않는다. */
    tourState.onHash = function () { endTour(false); };
    window.addEventListener('hashchange', tourState.onHash);

    paintStep();
  }

  function paintStep() {
    if (!tourState) return;
    var s = tourState.steps[tourState.i];
    var o = tourState.overlay;
    o.querySelector('.tour-step').textContent = (tourState.i + 1) + ' / ' + tourState.steps.length;
    o.querySelector('.tour-title').textContent = s.title;
    o.querySelector('.tour-body').textContent = s.body;
    o.querySelector('[data-action="tt-next"]').textContent =
      tourState.i === tourState.steps.length - 1 ? '시작하기' : '다음';
    positionTour();
    var next = o.querySelector('[data-action="tt-next"]');
    if (next) next.focus();
  }

  function positionTour() {
    if (!tourState) return;
    var s = tourState.steps[tourState.i];
    var el = document.querySelector(s.sel);
    if (!el) return;
    var r = el.getBoundingClientRect();
    var pad = 6;
    var hole = tourState.overlay.querySelector('.tour-hole');
    hole.style.top = (r.top - pad) + 'px';
    hole.style.left = (r.left - pad) + 'px';
    hole.style.width = (r.width + pad * 2) + 'px';
    hole.style.height = (r.height + pad * 2) + 'px';
    /* 말풍선은 구멍 아래, 화면을 벗어나면 위로. */
    var bubble = tourState.overlay.querySelector('.tour-bubble');
    var below = r.bottom + 12;
    var fitsBelow = below + bubble.offsetHeight < window.innerHeight - 12;
    bubble.style.top = fitsBelow ? below + 'px' : Math.max(12, r.top - bubble.offsetHeight - 12) + 'px';
  }

  function nextStep() {
    if (!tourState) return;
    if (tourState.i >= tourState.steps.length - 1) { endTour(true); return; }
    tourState.i += 1;
    var el = document.querySelector(tourState.steps[tourState.i].sel);
    if (el) el.scrollIntoView({ block: 'center', behavior: 'smooth' });
    paintStep();
  }

  /* seen=true 인 종료(건너뛰기·완료·ESC)만 플래그를 남긴다.
     라우트 이탈이나 '띄울 스텝이 없음'으로 끝난 경우까지 기록하면
     MediaRecorder 미지원 사용자가 온보딩을 영영 못 보게 된다. */
  function endTour(seen) {
    if (!tourState) return;
    var st = tourState;
    tourState = null;
    if (st.scroller && st.onScroll) st.scroller.removeEventListener('scroll', st.onScroll);
    if (st.onScroll) window.removeEventListener('resize', st.onScroll);
    if (st.onHash) window.removeEventListener('hashchange', st.onHash);
    if (st.overlay && st.overlay.parentNode) st.overlay.parentNode.removeChild(st.overlay);
    if (seen) lsSet(TOUR_KEY, '1');
    if (st.prevFocus && st.prevFocus.focus) { try { st.prevFocus.focus(); } catch (e) {} }
  }

  function maybeStartTour() {
    if (lsGet(TOUR_KEY, null)) return;
    /* 데스크톱은 우측 팁(renderRightTips)이 같은 내용을 이미 보여준다 — 중복 오버레이 금지. */
    if (window.innerWidth > 760) return;
    var shell = document.getElementById('app-shell');
    if (!shell || shell.dataset.route !== 'new') return;
    startTour();
  }

  /* 알림 인박스(서브프로젝트 F2) — 본문은 서버가 audit_logs 에서 파생해 내려준다.
     탭↔토글 매핑은 서버 _NOTIF_KINDS 의 category 열을 미러링한 것 —
     서버에 새 이벤트 종류가 생기면 여기도 같이 고쳐야 한다. */
  /* 벨 배지 — 폴링하지 않는다. 라우트가 바뀔 때와 인박스에서 상태가 바뀔 때만 갱신한다. */
  function setBadge(n) {
    var dot = document.getElementById('lc-bell-dot');
    var bell = document.getElementById('lc-bell');
    if (!dot) return;
    if (!n) {
      dot.hidden = true;
      dot.textContent = '';
    } else {
      dot.hidden = false;
      dot.textContent = n > 99 ? '99+' : String(n);
    }
    if (bell) bell.setAttribute('aria-label', n ? '알림 ' + n + '개 안 읽음' : '알림');
  }

  /* 방금 로컬에서 배지를 조정했으면 다음 라우트 갱신 1회를 건너뛴다.
     알림 행을 눌러 회의로 이동하면 PATCH 가 아직 커밋되기 전에 renderRoute 의 GET 이
     나가서 옛 값으로 되돌아가기 때문이다. */
  var skipNextBadgeRefresh = false;

  function refreshUnreadBadge() {
    if (!document.getElementById('lc-bell-dot')) return;
    if (skipNextBadgeRefresh) { skipNextBadgeRefresh = false; return; }
    API.listNotifications({ limit: 1 }).then(function (res) {
      setBadge((res && res.unread_count) || 0);
    }).catch(function () { /* 배지는 실패해도 앱에 지장 없다 */ });
  }

  var NF_TABS = [['all', '전체'], ['notice', '안내'], ['info', '정보']];
  var NF_TAB_TOGGLES = {
    all: ['summary', 'failure', 'share', 'export'],
    notice: ['share', 'export'],
    info: ['summary', 'failure']
  };

  function renderNotificationsView(centerEl) {
    var cancelled = false;
    var tab = 'all';
    var items = [];
    var notify = {};
    var unread = 0;
    var nextCursor = null;
    var loadSeq = seqGuard();   // 탭 전환 시 응답 역전 방지

    load();

    function load(cursor) {
      var append = !!cursor;
      if (!append) centerEl.innerHTML = '<div class="col-center-scroll"><div class="notif-page view-fade">' +
        '<div class="list-empty"><p>불러오는 중…</p></div></div></div>';
      /* 탭을 빠르게 바꾸면 조회가 겹친다. 순서 토큰이 없으면 옛 탭의 응답이 늦게 도착해
         현재 탭 머리글 아래에 다른 탭의 목록이 그려진다(tab 은 클로저 변수라 최신 값). */
      var my = loadSeq.next();
      API.listNotifications({ tab: tab, limit: 20, cursor: cursor || undefined }).then(function (res) {
        if (cancelled || !loadSeq.isCurrent(my)) return;
        items = append ? items.concat(res.items || []) : (res.items || []);
        notify = res.notify || {};
        unread = res.unread_count || 0;
        nextCursor = res.next_cursor ? parseInt(res.next_cursor, 10) : null;
        setBadge(unread);
        paint();
      }).catch(function (err) {
        if (cancelled || !loadSeq.isCurrent(my)) return;
        centerEl.innerHTML = '<div class="col-center-scroll"><div class="notif-page view-fade">' +
          emptyStateHtml('알림을 불러오지 못했습니다', err.message || '') + '</div></div>';
      });
    }

    function emptyHtml() {
      /* 토글로 꺼져서 빈 것과 원래 없는 것을 구분한다. data-empty 로 기계 검증도 가능하게. */
      var off = (NF_TAB_TOGGLES[tab] || []).every(function (k) { return notify[k] === false; });
      return off
        ? '<div class="notif-empty" data-empty="off">' +
            emptyStateHtml('이 알림이 꺼져 있어요', '마이 > 알림에서 다시 켤 수 있어요.',
              '<a href="#/me" class="btn btn-ghost btn-sm">알림 설정 열기</a>') + '</div>'
        : '<div class="notif-empty" data-empty="none">' +
            emptyStateHtml('알림이 없습니다', '새 소식이 생기면 여기에 표시됩니다.') + '</div>';
    }

    function rowHtml(it) {
      return '<li class="notif-row' + (it.read ? '' : ' is-unread') + '" data-id="' + esc(it.id) + '">' +
        '<button type="button" class="notif-main" data-action="nf-open" data-id="' + esc(it.id) + '" ' +
          'data-meeting="' + esc(it.meeting_id || '') + '" data-read="' + (it.read ? '1' : '0') + '">' +
          '<span class="notif-dot"' + (it.read ? ' hidden' : '') + ' aria-hidden="true"></span>' +
          '<span class="notif-body">' +
            '<span class="notif-label">' + esc(it.label) + '</span>' +
            '<span class="notif-sub">' + esc(it.title || '제목 없음') + '</span>' +
          '</span>' +
          '<span class="notif-time mono">' + esc(shortDate(it.created_at)) + '</span>' +
        '</button>' +
        '<button type="button" class="notif-x" data-action="nf-dismiss" data-id="' + esc(it.id) + '" ' +
          'aria-label="' + esc(it.label) + ' 알림 숨기기">' + ICONS.close + '</button>' +
      '</li>';
    }

    function paint() {
      centerEl.innerHTML = '<div class="col-center-scroll"><div class="notif-page view-fade">' +
        '<div class="notif-head">' +
          '<h2 class="notif-title">알림</h2>' +
          '<button type="button" class="btn btn-ghost btn-sm" data-action="nf-read-all"' +
            (unread ? '' : ' disabled') + '>모두 읽음</button>' +
        '</div>' +
        '<div class="notif-tabs" role="group" aria-label="알림 분류">' +
          NF_TABS.map(function (t) {
            return '<button type="button" class="notif-tab' + (t[0] === tab ? ' is-active' : '') + '" ' +
              'data-action="nf-tab" data-tab="' + t[0] + '"' + (t[0] === tab ? ' aria-current="true"' : '') + '>' +
              esc(t[1]) + '</button>';
          }).join('') +
        '</div>' +
        (items.length
          ? '<ul class="notif-list" role="list">' + items.map(rowHtml).join('') + '</ul>' +
            (nextCursor !== null
              ? '<div class="notif-more"><button type="button" class="btn btn-ghost btn-sm" data-action="nf-more">더 보기</button></div>'
              : '')
          : emptyHtml()) +
      '</div></div>';
    }

    /* 안읽음 수만 부분 갱신한다 — #col-center 가 aria-live 라서 전체 재렌더는 화면을 통째로 다시 읽는다. */
    function applyUnread(delta) {
      unread = Math.max(0, unread + delta);
      setBadge(unread);
      var btn = centerEl.querySelector('[data-action="nf-read-all"]');
      if (btn) btn.disabled = !unread;
    }

    function onNotifClick(e) {
      var el = e.target.closest('[data-action]');
      if (!el || !centerEl.contains(el)) return;
      var action = el.dataset.action;
      if (action === 'nf-tab') {
        if (el.dataset.tab === tab) return;
        tab = el.dataset.tab;
        nextCursor = null;
        load();
      } else if (action === 'nf-more') {
        if (nextCursor !== null) load(String(nextCursor));
      } else if (action === 'nf-open') {
        var id = el.dataset.id;
        var wasUnread = el.dataset.read === '0';
        /* PATCH 는 fire-and-forget. 완료를 기다렸다 배지를 다시 읽으면 커밋 전 값을 볼 수 있다. */
        API.patchNotification(id, { read: true }).catch(function () {});
        if (wasUnread) { applyUnread(-1); skipNextBadgeRefresh = true; }
        if (el.dataset.meeting) navigate('#/meetings/' + encodeURIComponent(el.dataset.meeting));
      } else if (action === 'nf-dismiss') {
        var did = el.dataset.id;
        var row = centerEl.querySelector('.notif-row[data-id="' + cssEscapeId(did) + '"]');
        var mainBtn = row && row.querySelector('[data-action="nf-open"]');
        var wasUnread2 = mainBtn && mainBtn.dataset.read === '0';
        API.patchNotification(did, { dismissed: true }).then(function () {
          if (cancelled) return;
          items = items.filter(function (it) { return it.id !== did; });
          if (row) row.remove();
          /* next_cursor 가 offset 이라 숨김이 생기면 결과 집합이 밀린다 → 다음 페이지가 한 건 건너뛴다. */
          if (nextCursor !== null) nextCursor = Math.max(0, nextCursor - 1);
          if (wasUnread2) applyUnread(-1);
          if (!items.length) paint();
        }).catch(function (err) {
          if (cancelled) return;
          toast(err.message || '숨기지 못했습니다.', 'error');
        });
      } else if (action === 'nf-read-all') {
        el.disabled = true;
        API.readAllNotifications().then(function (res) {
          if (cancelled) return;
          toast((res && res.marked ? res.marked + '건을 ' : '') + '읽음 처리했어요.', 'success');
          load();
        }).catch(function (err) {
          if (cancelled) return;
          el.disabled = false;
          toast(err.message || '처리하지 못했습니다.', 'error');
        });
      }
    }

    centerEl.addEventListener('click', onNotifClick);
    return function cleanup() {
      cancelled = true;
      centerEl.removeEventListener('click', onNotifClick);
    };
  }

  /* 마이페이지 — 프로필·사용량·설정(인식 언어·자주 쓰는 단어·관심 분야)·계정.
     설정 저장은 PATCH /v1/me/settings 이고 변경된 키만 보낸다(공용 계정에서 남의 저장을 덮지 않게). */

  var MP_LANGS = [['ko', '한국어'], ['en', 'English'], ['ja', '日本語'], ['zh', '中文'], ['auto', '자동 감지']];
  var NOTIFY_KEYS = [['summary', '전사·요약 완료'], ['failure', '처리 실패'],
                     ['share', '공유 활동'], ['export', '내보내기 완료']];

  /* 서버 규칙(_notify_prefs)과 동일하게 '없는 키는 켜짐'을 채운다.
     비교는 반드시 채운 값끼리 해야 한다 — 원본과 비교하면 notify 키가 없는 계정에서
     언어만 바꿔도 notify 가 함께 저장된다(설정은 키 삭제가 불가능하다). */
  function fillNotify(raw) {
    raw = raw || {};
    var out = {};
    NOTIFY_KEYS.forEach(function (kv) { out[kv[0]] = raw[kv[0]] !== false; });
    return out;
  }
  var MP_MAX_HOTWORDS = 10;
  var MP_MAX_INTERESTS = 12;

  function mpChipHtml(text, kind) {
    return '<li class="mypage-chip" data-mp-chip="' + kind + '" data-term="' + esc(text) + '">' +
      '<span>' + esc(text) + '</span>' +
      '<button type="button" class="mypage-chip-x" data-action="mp-del" data-kind="' + kind + '" ' +
        'data-term="' + esc(text) + '" aria-label="' + esc(text) + ' 삭제">' + ICONS.close + '</button>' +
    '</li>';
  }

  function mpStatHtml(key, label, raw, shown) {
    return '<div class="mypage-stat" data-usage="' + key + '" data-raw="' + esc(String(raw)) + '">' +
      '<div class="mypage-stat-label">' + esc(label) + '</div>' +
      '<div class="mypage-stat-value mono">' + esc(shown) + '</div>' +
    '</div>';
  }

  function renderMyPageView(centerEl) {
    var cancelled = false;
    var loaded = {};      // 렌더 시점 서버 설정 스냅샷 — 저장 시 변경된 키만 골라내는 기준
    var hotwords = [];
    var interests = [];
    var suggests = [];
    var notify = fillNotify(null);
    var saving = false;

    centerEl.innerHTML = '<div class="col-center-scroll"><div class="mypage-page view-fade">' +
      '<div class="list-empty"><p>불러오는 중…</p></div></div></div>';

    /* getKeywords 는 개별 catch — 이게 없으면 추천 행 하나 때문에 Promise.all 이 전체를 실패시킨다. */
    Promise.all([
      API.getMe(),
      API.getUsage(),
      API.getKeywords().catch(function () { return null; })
    ]).then(function (res) {
      if (cancelled) return;
      var me = res[0] || {};
      var usage = res[1] || {};
      loaded = me.settings || {};
      hotwords = (loaded.hotwords || []).slice();
      interests = (loaded.interests || []).slice();
      notify = fillNotify(loaded.notify);
      suggests = ((res[2] && res[2].keywords) || []).map(function (k) { return k.text; }).filter(Boolean);
      paint(me, usage);
    }).catch(function (err) {
      if (cancelled) return;
      centerEl.innerHTML = '<div class="col-center-scroll"><div class="mypage-page view-fade">' +
        emptyStateHtml('마이페이지를 불러오지 못했습니다', err.message || '') + '</div></div>';
    });

    function paint(me, usage) {
      var notes = usage.notes || {};
      var storage = usage.storage || {};
      var month = usage.this_month || {};
      var lang = loaded.language || 'ko';
      var avatar = (me.display_name || '회').charAt(0);

      centerEl.innerHTML = '<div class="col-center-scroll"><div class="mypage-page view-fade">' +
        /* 1. 프로필 — 값은 전부 서버에서 온다(이메일은 API 가 내리지 않으므로 표시하지 않는다). */
        '<section class="mypage-section" role="group" aria-labelledby="mp-h-profile">' +
          '<h2 class="mypage-h" id="mp-h-profile">프로필</h2>' +
          '<div class="mypage-profile">' +
            '<div class="mypage-avatar">' + esc(avatar) + '</div>' +
            '<div class="mypage-id">' +
              '<div class="mypage-name">' + esc(me.display_name || '-') + '</div>' +
              '<div class="mypage-mail mono">' + esc(formatDateTime(me.created_at, { dateOnly: true })) + ' 가입</div>' +
            '</div>' +
          '</div>' +
        '</section>' +

        /* 2. 사용량 — 실제 수치만. 쿼터 개념이 앱에 없어 게이지를 만들지 않는다. */
        '<section class="mypage-section" role="group" aria-labelledby="mp-h-usage">' +
          '<h2 class="mypage-h" id="mp-h-usage">사용량</h2>' +
          '<div class="mypage-stats">' +
            mpStatHtml('notes_all', '노트', notes.all || 0, String(notes.all || 0) + '개') +
            mpStatHtml('duration', '총 녹음', usage.total_duration_ms || 0, formatDuration(usage.total_duration_ms || 0)) +
            mpStatHtml('bytes', '저장 용량', storage.bytes || 0, formatFileSize(storage.bytes || 0)) +
            mpStatHtml('month', '이번 달', month.count || 0, String(month.count || 0) + '개') +
          '</div>' +
        '</section>' +

        /* 3. 인식 언어 — 선택지는 새 회의 폼과 동일해야 한다(서버 화이트리스트도 같다). */
        '<section class="mypage-section" role="group" aria-labelledby="mp-h-lang">' +
          '<h2 class="mypage-h" id="mp-h-lang">인식 언어</h2>' +
          '<label class="field-label" for="mp-language">새 회의의 기본 전사 언어</label>' +
          '<select class="select" id="mp-language">' +
            MP_LANGS.map(function (o) {
              return '<option value="' + o[0] + '"' + (o[0] === lang ? ' selected' : '') + '>' + esc(o[1]) + '</option>';
            }).join('') +
          '</select>' +
        '</section>' +

        /* 4. 자주 쓰는 단어 — 새 회의 힌트 단어로 자동 채워진다. */
        '<section class="mypage-section" role="group" aria-labelledby="mp-h-hot">' +
          '<h2 class="mypage-h" id="mp-h-hot">자주 쓰는 단어</h2>' +
          '<p class="mypage-hint" id="mp-hot-hint">새 회의의 힌트 단어로 자동 입력됩니다. 최대 ' + MP_MAX_HOTWORDS + '개 · 쉼표는 넣을 수 없어요.</p>' +
          '<ul class="mypage-chips" role="list" id="mp-hot-chips">' +
            hotwords.map(function (t) { return mpChipHtml(t, 'hotword'); }).join('') +
          '</ul>' +
          '<div class="mypage-add">' +
            '<input type="text" class="input" id="mp-hotword-input" placeholder="예: 회의녹음챗" aria-describedby="mp-hot-hint"' +
              (hotwords.length >= MP_MAX_HOTWORDS ? ' disabled' : '') + ' />' +
            '<button type="button" class="btn btn-ghost btn-sm" data-action="mp-add-hotword"' +
              (hotwords.length >= MP_MAX_HOTWORDS ? ' disabled aria-describedby="mp-hot-hint"' : '') + '>추가</button>' +
          '</div>' +
        '</section>' +

        /* 5. 관심 분야 — 요약 생성 시 힌트로 전달된다. */
        '<section class="mypage-section" role="group" aria-labelledby="mp-h-int">' +
          '<h2 class="mypage-h" id="mp-h-int">관심 분야</h2>' +
          '<p class="mypage-hint" id="mp-int-hint">요약을 만들 때 힌트로 전달됩니다. 최대 ' + MP_MAX_INTERESTS + '개.</p>' +
          '<ul class="mypage-chips" role="list" id="mp-int-chips">' +
            interests.map(function (t) { return mpChipHtml(t, 'interest'); }).join('') +
          '</ul>' +
          '<div class="mypage-add">' +
            '<input type="text" class="input" id="mp-interest-input" placeholder="예: 제품 기획" aria-describedby="mp-int-hint"' +
              (interests.length >= MP_MAX_INTERESTS ? ' disabled' : '') + ' />' +
            '<button type="button" class="btn btn-ghost btn-sm" data-action="mp-add-interest"' +
              (interests.length >= MP_MAX_INTERESTS ? ' disabled' : '') + '>추가</button>' +
          '</div>' +
          /* 추천은 있을 때만 보여준다. 프로덕션 요약은 스텁이라 비어 있는 게 정상이고,
             '내 노트에서 뽑은 키워드'라고 말하지 않는다. */
          (suggests.length
            ? '<div class="mypage-suggest"><span class="mypage-suggest-label">추천</span>' +
                suggests.map(function (t) {
                  return '<button type="button" class="search-chip search-chip--suggest" data-action="mp-suggest" data-term="' + esc(t) + '">' + esc(t) + '</button>';
                }).join('') +
              '</div>'
            : '') +
        '</section>' +

        /* 6. 알림 — 인박스 진입점 겸 토글. 모바일에서 상시 목록(=벨)이 숨는 라우트가 많아
           마이 탭이 항상 도달 가능한 진입점이 된다. */
        '<section class="mypage-section" role="group" aria-labelledby="mp-h-notify">' +
          '<h2 class="mypage-h" id="mp-h-notify">알림</h2>' +
          '<p class="mypage-hint">이 데모는 앱 안에서만 알림을 보여줍니다(푸시·이메일 발송 없음).</p>' +
          '<a href="#/notifications" class="folder-row folder-row-link mypage-notif-link">알림함 열기</a>' +
          '<button type="button" class="folder-row folder-row-link mypage-notif-link" data-action="tt-replay">튜토리얼 다시 보기</button>' +
          NOTIFY_KEYS.map(function (kv) {
            return '<label class="checkbox-row switch-row" for="mp-notify-' + kv[0] + '">' +
              '<span class="checkbox-row-label">' + esc(kv[1]) + '</span>' +
              '<input type="checkbox" id="mp-notify-' + kv[0] + '"' + (notify[kv[0]] ? ' checked' : '') + ' />' +
            '</label>';
          }).join('') +
        '</section>' +

        /* 7. 계정 · 앱 정보 */
        '<section class="mypage-section" role="group" aria-labelledby="mp-h-acc">' +
          '<h2 class="mypage-h" id="mp-h-acc">계정</h2>' +
          '<p class="mypage-hint">이 데모는 단일 공용 계정이라 저장한 설정이 모든 방문자에게 적용됩니다.</p>' +
          (me.write_protected
            ? '<p class="mypage-hint">읽기 전용 데모예요 — 회의 수정·삭제는 막혀 있지만 이 설정은 저장됩니다.</p>'
            : '') +
        '</section>' +

        '<div class="mypage-actions">' +
          '<button type="button" class="btn btn-primary" data-action="mp-save">설정 저장</button>' +
        '</div>' +
      '</div></div>';

      lastMe = me;
      lastUsage = usage;
    }

    var lastMe = {};
    var lastUsage = {};

    /* 칩 행만 부분 갱신한다 — #col-center 가 aria-live 라서 전체 재렌더는 6섹션을 다시 낭독한다. */
    function repaintChips(kind) {
      var list = kind === 'hotword' ? hotwords : interests;
      var max = kind === 'hotword' ? MP_MAX_HOTWORDS : MP_MAX_INTERESTS;
      var ul = centerEl.querySelector(kind === 'hotword' ? '#mp-hot-chips' : '#mp-int-chips');
      if (!ul) return;
      ul.innerHTML = list.map(function (t) { return mpChipHtml(t, kind); }).join('');
      var input = centerEl.querySelector(kind === 'hotword' ? '#mp-hotword-input' : '#mp-interest-input');
      var addBtn = centerEl.querySelector('[data-action="mp-add-' + (kind === 'hotword' ? 'hotword' : 'interest') + '"]');
      if (input) input.disabled = list.length >= max;
      if (addBtn) addBtn.disabled = list.length >= max;
    }

    function addTerm(kind) {
      var input = centerEl.querySelector(kind === 'hotword' ? '#mp-hotword-input' : '#mp-interest-input');
      if (!input) return;
      var term = (input.value || '').trim();
      if (!term) return;
      if (kind === 'hotword' && term.indexOf(',') !== -1) {
        toast('자주 쓰는 단어에는 쉼표를 넣을 수 없습니다.', 'error');
        return;
      }
      var list = kind === 'hotword' ? hotwords : interests;
      var max = kind === 'hotword' ? MP_MAX_HOTWORDS : MP_MAX_INTERESTS;
      if (list.length >= max) { toast('최대 ' + max + '개까지 추가할 수 있습니다.', 'error'); return; }
      if (list.indexOf(term) !== -1) { input.value = ''; return; }
      list.push(term);
      input.value = '';
      repaintChips(kind);
      input.focus();
    }

    function delTerm(kind, term) {
      var list = kind === 'hotword' ? hotwords : interests;
      var idx = list.indexOf(term);
      if (idx === -1) return;
      list.splice(idx, 1);
      repaintChips(kind);
      /* 지운 자리의 칩으로 포커스를 옮긴다(안 하면 매 삭제마다 포커스가 body 로 떨어진다). */
      var ul = centerEl.querySelector(kind === 'hotword' ? '#mp-hot-chips' : '#mp-int-chips');
      var next = ul && (ul.children[idx] || ul.children[idx - 1]);
      var btn = next && next.querySelector('.mypage-chip-x');
      if (btn) { btn.focus(); return; }
      var input = centerEl.querySelector(kind === 'hotword' ? '#mp-hotword-input' : '#mp-interest-input');
      if (input && !input.disabled) input.focus();
    }

    function save() {
      if (saving) return;
      var sel = centerEl.querySelector('#mp-language');
      var body = {};
      /* 비교용 구분자 — 단어에 들어갈 수 없는 문자여야 한다.
         공백을 쓰면 ['a b'] 와 ['a','b'] 가 같다고 판정돼 변경을 놓친다. */
      var sep = '\u0000';
      if (sel && sel.value !== (loaded.language || 'ko')) body.language = sel.value;
      if (hotwords.join(sep) !== (loaded.hotwords || []).join(sep)) body.hotwords = hotwords;
      if (interests.join(sep) !== (loaded.interests || []).join(sep)) body.interests = interests;
      /* notify 는 서버가 top-level 로만 머지하므로(부분 객체를 보내면 나머지 키가 지워져 ON 으로
         되돌아간다) 보낼 때는 4개를 전부 담는다. 비교는 채운 값끼리. */
      var baseNotify = fillNotify(loaded.notify);
      var curNotify = {};
      NOTIFY_KEYS.forEach(function (kv) {
        var cb = centerEl.querySelector('#mp-notify-' + kv[0]);
        curNotify[kv[0]] = cb ? cb.checked : baseNotify[kv[0]];
      });
      if (NOTIFY_KEYS.some(function (kv) { return curNotify[kv[0]] !== baseNotify[kv[0]]; })) {
        body.notify = curNotify;
      }
      if (!Object.keys(body).length) { toast('변경된 설정이 없습니다.'); return; }

      var btn = centerEl.querySelector('[data-action="mp-save"]');
      saving = true;
      if (btn) { btn.disabled = true; btn.setAttribute('aria-busy', 'true'); }
      /* 저장 중에도 사용자는 계속 입력할 수 있다(비활성화되는 건 저장 버튼뿐).
         응답으로 화면을 통째로 덮으면 그 사이 추가한 단어·토글이 조용히 사라지고
         '저장했습니다' 토스트만 남는다. 그래서 보낼 때의 화면 값을 기억해 두고,
         응답 시점에도 값이 그대로면(=사용자가 손대지 않았으면) 서버 값으로 갱신한다.
         손댔으면 사용자 입력을 남기고, 다음 저장의 diff 가 그 변경을 잡는다. */
      var sentLang = sel ? sel.value : null;
      var sentHot = hotwords.slice();
      var sentInt = interests.slice();
      var sentNotify = curNotify;
      API.patchSettings(body).then(function (res) {
        if (cancelled) return;
        loaded = (res && res.settings) || {};
        userSettings = loaded;          // 새 회의 폼 프리필이 즉시 최신 값을 쓰게 한다
        if (hotwords.join(sep) === sentHot.join(sep)) {
          hotwords = (loaded.hotwords || []).slice();
          repaintChips('hotword');
        }
        if (interests.join(sep) === sentInt.join(sep)) {
          interests = (loaded.interests || []).slice();
          repaintChips('interest');
        }
        if (sel && sel.value === sentLang) sel.value = loaded.language || 'ko';
        notify = fillNotify(loaded.notify);
        NOTIFY_KEYS.forEach(function (kv) {
          var cb = centerEl.querySelector('#mp-notify-' + kv[0]);
          if (cb && cb.checked === sentNotify[kv[0]]) cb.checked = notify[kv[0]];
        });
        toast('설정을 저장했습니다.', 'success');
      }).catch(function (err) {
        if (cancelled) return;
        if (err.code === 'write_disabled') toast('읽기 전용 데모라 저장할 수 없습니다.', 'error');
        else if (err.code === 'settings_unavailable') toast('설정 저장소가 아직 준비되지 않았습니다.', 'error');
        else toast(err.message || '저장에 실패했습니다.', 'error');
      }).then(function () {
        saving = false;
        var b = centerEl.querySelector('[data-action="mp-save"]');
        if (b) { b.disabled = false; b.removeAttribute('aria-busy'); }
      });
    }

    function onMyPageClick(e) {
      var el = e.target.closest('[data-action]');
      if (!el || !centerEl.contains(el)) return;
      var action = el.dataset.action;
      if (action === 'tt-replay') {
        /* 플래그를 지우고 새 회의 화면으로 간 뒤 렌더가 끝나면 시작한다.
           navigate 직후에 바로 startTour 하면 타깃이 아직 없고(전 스텝 0-rect 스킵),
           뒤늦게 도착한 hashchange 가 투어를 종료시킨다. */
        lsRemove(TOUR_KEY);
        pendingTour = true;
        navigate('#/new');
        return;
      }
      if (action === 'mp-save') save();
      else if (action === 'mp-add-hotword') addTerm('hotword');
      else if (action === 'mp-add-interest') addTerm('interest');
      else if (action === 'mp-del') delTerm(el.dataset.kind, el.dataset.term);
      else if (action === 'mp-suggest') {
        var t = el.dataset.term;
        if (interests.indexOf(t) === -1 && interests.length < MP_MAX_INTERESTS) {
          interests.push(t);
          repaintChips('interest');
        }
      }
    }

    /* 한글 조합 확정 Enter 는 무시한다(안 그러면 조합 중 문자가 칩으로 들어간다). */
    function onMyPageKeydown(e) {
      if (e.key !== 'Enter' || e.isComposing || e.keyCode === 229) return;
      var id = e.target && e.target.id;
      if (id === 'mp-hotword-input') { e.preventDefault(); addTerm('hotword'); }
      else if (id === 'mp-interest-input') { e.preventDefault(); addTerm('interest'); }
    }

    centerEl.addEventListener('click', onMyPageClick);
    centerEl.addEventListener('keydown', onMyPageKeydown);

    return function cleanup() {
      cancelled = true;
      centerEl.removeEventListener('click', onMyPageClick);
      centerEl.removeEventListener('keydown', onMyPageKeydown);
    };
  }

  /* 폴더 트리 화면 — 고정 항목(전체/기본/공유한/휴지통) + 중첩 사용자 폴더 */
  function renderFolderTree(centerEl) {
    var cancelled = false;
    function fixedRow(key, label, count, icon) {
      return '<a class="folder-row folder-fixed" href="#/folders/' + key + '">' +
        '<span class="folder-icon">' + icon + '</span>' +
        '<span class="folder-name">' + esc(label) + '</span>' +
        '<span class="folder-count mono">' + count + '</span></a>';
    }
    function userRow(f, depth) {
      return '<div class="folder-row" data-fid="' + esc(f.id) + '" style="padding-left:' + (14 + depth * 16) + 'px">' +
        '<a class="folder-row-link" href="#/folders/' + esc(f.id) + '">' +
          '<span class="folder-icon">' + ICONS.folderMove + '</span>' +
          '<span class="folder-name">' + esc(f.name) + '</span>' +
          '<span class="folder-count mono">' + f.note_count + '</span>' +
        '</a>' +
        '<button type="button" class="folder-act" data-action="rename" title="이름 변경" aria-label="이름 변경">' + ICONS.edit + '</button>' +
        '<button type="button" class="folder-act" data-action="delete-folder" title="폴더 삭제" aria-label="폴더 삭제">' + ICONS.trash + '</button>' +
      '</div>';
    }
    function treeHtml(folders, parentId, depth) {
      return folders.filter(function (f) { return (f.parent_id || null) === parentId; })
        .map(function (f) { return userRow(f, depth) + treeHtml(folders, f.id, depth + 1); }).join('');
    }
    function load() {
      centerEl.innerHTML = '<div class="folder-page"><div class="folder-loading">불러오는 중…</div></div>';
      API.listFolders().then(function (res) {
        if (cancelled) return;
        var c = res.counts || {};
        centerEl.innerHTML =
          '<div class="folder-page">' +
            '<div class="folder-head"><h2 class="folder-title">폴더</h2>' +
              '<button type="button" class="btn btn-primary btn-sm" data-action="add-folder">' + ICONS.plus + ' 폴더 추가</button></div>' +
            '<div class="folder-list">' +
              fixedRow('all', '전체 노트', c.all || 0, ICONS.folderMove) +
              fixedRow('unfiled', '기본폴더', c.unfiled || 0, ICONS.folderMove) +
              fixedRow('shared', '공유한 노트', c.shared || 0, ICONS.share) +
              fixedRow('trash', '휴지통', c.trash || 0, ICONS.trash) +
              '<div class="folder-divider"></div>' +
              (res.folders.length ? treeHtml(res.folders, null, 0)
                : '<div class="folder-empty">아직 폴더가 없어요. "폴더 추가"로 만들어보세요.</div>') +
            '</div>' +
          '</div>';
      }).catch(function (err) {
        if (cancelled) return;
        centerEl.innerHTML = '<div class="folder-page"><div class="folder-empty">폴더를 불러오지 못했습니다.</div></div>';
        toast(err.message || '폴더를 불러오지 못했습니다.', 'error');
      });
    }
    function onClick(e) {
      var addBtn = e.target.closest('[data-action="add-folder"]');
      if (addBtn) {
        var name = window.prompt('새 폴더 이름');
        if (name && name.trim()) {
          API.createFolder({ name: name.trim() }).then(function () { toast('폴더를 만들었습니다.', 'success'); load(); })
            .catch(function (err) { toast(err.message || '폴더 생성 실패', 'error'); });
        }
        return;
      }
      var row = e.target.closest('[data-fid]');
      if (!row) return;
      var fid = row.dataset.fid;
      if (e.target.closest('[data-action="rename"]')) {
        var nm = window.prompt('폴더 이름 변경');
        if (nm && nm.trim()) {
          API.patchFolder(fid, { name: nm.trim() }).then(function () { toast('이름을 변경했습니다.', 'success'); load(); })
            .catch(function (err) { toast(err.message || '변경 실패', 'error'); });
        }
        return;
      }
      if (e.target.closest('[data-action="delete-folder"]')) {
        confirmDialog('이 폴더를 삭제할까요? 폴더 안 노트는 기본폴더로, 하위 폴더는 상위로 이동합니다.', { title: '폴더 삭제', confirmLabel: '삭제', danger: true }).then(function (ok) {
          if (!ok) return;
          API.deleteFolder(fid).then(function () { toast('폴더를 삭제했습니다.', 'success'); load(); })
            .catch(function (err) { toast(err.message || '삭제 실패', 'error'); });
        });
      }
    }
    centerEl.addEventListener('click', onClick);
    load();
    return function cleanup() { cancelled = true; centerEl.removeEventListener('click', onClick); };
  }

  /* 폴더 선택 모달 — 노트 이동. onDone 은 성공 시 호출(현재 뷰 새로고침). */
  function openFolderPicker(meetingId, onDone) {
    var dlg = document.getElementById('folder-picker');
    var listEl = document.getElementById('folder-picker-list');
    var cancelBtn = document.getElementById('folder-picker-cancel');
    function rowHtml(id, name, depth) {
      return '<button type="button" class="folder-picker-row" data-folder="' + esc(id) + '" style="padding-left:' + (12 + depth * 16) + 'px">' + esc(name) + '</button>';
    }
    function treeHtml(folders, parentId, depth) {
      return folders.filter(function (f) { return (f.parent_id || null) === parentId; })
        .map(function (f) { return rowHtml(f.id, f.name, depth) + treeHtml(folders, f.id, depth + 1); }).join('');
    }
    listEl.innerHTML = '<div class="folder-loading">불러오는 중…</div>';
    API.listFolders().then(function (res) {
      listEl.innerHTML = rowHtml('__none__', '기본폴더 (미분류)', 0) + treeHtml(res.folders, null, 0);
    }).catch(function () {
      listEl.innerHTML = '<div class="folder-empty">폴더를 불러오지 못했습니다.</div>';
    });
    // confirmDialog 패턴: 리스너 정리는 dialog 'close' 이벤트에서. ESC·closeOpenDialogs 의
    // 직접 dlg.close() 도 'close' 를 발생시키므로 리스너 누적/오노트 이동을 막는다.
    var moved = false;
    var picking = inFlightLock();
    var teardownDone = false;
    /* 리스너 정리를 close 이벤트에만 맡기지 않는다. close 는 큐잉되는 비동기 이벤트라
       일부 셸 환경(Electron 기반 브라우저)에서 발화하지 않고, 그러면 listEl 의 클릭
       리스너가 남아 다음 번에 폴더를 한 번 눌러도 이동 요청이 두 번 나간다.
       (confirmDialog 에서 같은 원인으로 Promise 가 영원히 대기하던 것과 같은 문제) */
    var doneFired = false;
    function teardown() {
      if (teardownDone) return;
      teardownDone = true;
      listEl.removeEventListener('click', onPick);
      cancelBtn.removeEventListener('click', onCancel);
      dlg.removeEventListener('close', onClose);
    }
    /* onPick 성공과 onClose 양쪽에서 부를 수 있으니 한 번만 실행되게 잠근다. */
    function fireDone() {
      if (doneFired) return;
      doneFired = true;
      if (onDone) onDone();
    }
    function onPick(e) {
      var btn = e.target.closest('[data-folder]');
      if (!btn) return;
      var fid = btn.dataset.folder === '__none__' ? null : btn.dataset.folder;
      /* 연타로 다른 폴더를 두 번 고르면 이동 요청 두 개가 경합해 최종 폴더가
         응답 순서에 좌우된다. 첫 요청이 끝날 때까지 잠근다. */
      picking(function () {
        return API.moveMeeting(meetingId, { folder_id: fid }).then(function () {
          moved = true;
          toast('폴더로 이동했습니다.', 'success');
          teardown();
          dlg.close();
          fireDone();
        }).catch(function (err) { toast(err.message || '이동 실패', 'error'); });
      });
    }
    function onCancel() { teardown(); dlg.close(); }
    function onClose() {
      teardown();
      if (moved) fireDone();
    }
    listEl.addEventListener('click', onPick);
    cancelBtn.addEventListener('click', onCancel);
    dlg.addEventListener('close', onClose);
    dlg.showModal();
  }

  /* 폴더 상세 — 선택 폴더/뷰의 노트 목록(정렬·필터). key=trash 는 복원/영구삭제 모드. */
  var FOLDER_TITLES = { all: '전체 노트', unfiled: '기본폴더', shared: '공유한 노트', trash: '휴지통' };
  function renderFolderDetail(centerEl, key) {
    var cancelled = false;   // 라우트 이탈 시 in-flight 응답/토스트 억제(파일 관례)
    var isTrash = key === 'trash';
    var sort = 'recorded_at', status = '', title = FOLDER_TITLES[key] || '폴더';
    var loadSeq = seqGuard();   // 정렬/상태 필터를 연달아 바꿀 때 응답 역전 방지
    function folderParam() {
      if (key === 'all') return undefined;      // 전체(폴더 파라미터 없음)
      if (key === 'unfiled') return 'null';
      if (key === 'shared') return 'shared';
      if (key === 'trash') return 'trash';
      return key;                               // 사용자 folder_id
    }
    function load() {
      var scroll = centerEl.querySelector('#fd-scroll');
      if (scroll) scroll.innerHTML = '<div class="folder-loading">불러오는 중…</div>';
      var my = loadSeq.next();
      API.listMeetings({ folder: folderParam(), sort: sort, status: status, limit: 50 }).then(function (res) {
        if (cancelled || !loadSeq.isCurrent(my)) return;
        var s = centerEl.querySelector('#fd-scroll');
        if (!s) return;
        if (!res.items.length) { s.innerHTML = '<div class="folder-empty">' + (isTrash ? '휴지통이 비어 있어요.' : '노트가 없어요.') + '</div>'; return; }
        s.innerHTML = res.items.map(function (m) { return renderNoteCard(m, { mode: isTrash ? 'trash' : 'folder' }); }).join('');
      }).catch(function (err) {
        if (cancelled || !loadSeq.isCurrent(my)) return;
        var s = centerEl.querySelector('#fd-scroll'); if (s) s.innerHTML = '<div class="folder-empty">불러오지 못했습니다.</div>';
        toast(err.message || '불러오지 못했습니다.', 'error');
      });
    }
    centerEl.innerHTML =
      '<div class="folder-page fd-page">' +
        '<div class="fd-head">' +
          '<button type="button" class="detail-back-btn" data-action="back" aria-label="폴더로">' + ICONS.back + '</button>' +
          '<h2 class="folder-title">' + esc(title) + '</h2>' +
          (isTrash ? '<button type="button" class="btn btn-danger btn-sm" data-action="empty">휴지통 비우기</button>'
            : '<div class="fd-controls">' +
                '<select class="select" id="fd-sort">' +
                  '<option value="recorded_at">최근순</option><option value="title">제목순</option><option value="duration">길이순</option>' +
                '</select>' +
                '<select class="select" id="fd-status"><option value="">전체 상태</option>' +
                  '<option value="ready_for_review">검토 대기</option><option value="failed">실패</option></select>' +
              '</div>') +
        '</div>' +
        '<div class="list-scroll" id="fd-scroll"></div>' +
      '</div>';
    var sortSel = centerEl.querySelector('#fd-sort'), statusSel = centerEl.querySelector('#fd-status');
    if (sortSel) sortSel.addEventListener('change', function () { sort = sortSel.value; load(); });
    if (statusSel) statusSel.addEventListener('change', function () { status = statusSel.value; load(); });
    function onClick(e) {
      if (e.target.closest('[data-action="back"]')) { navigate('#/folders'); return; }
      if (e.target.closest('[data-action="empty"]')) {
        confirmDialog('휴지통을 비울까요? 모든 노트가 영구 삭제되며 되돌릴 수 없습니다.', { title: '휴지통 비우기', confirmLabel: '비우기', danger: true }).then(function (ok) {
          if (!ok) return;
          API.emptyTrash().then(function (r) { toast((r.purged || 0) + '건 영구 삭제했습니다.', 'success'); load(); })
            .catch(function (err) { toast(err.message || '실패', 'error'); });
        });
        return;
      }
      var row = e.target.closest('[data-id]');
      if (!row) return;
      var id = row.dataset.id;
      if (e.target.closest('[data-action="restore"]')) {
        API.restoreMeeting(id).then(function () { toast('복원했습니다.', 'success'); load(); ListColumn.refresh(true); }).catch(function (err) { toast(err.message || '복원 실패', 'error'); });
        return;
      }
      if (e.target.closest('[data-action="purge"]')) {
        confirmDialog('이 노트를 영구 삭제할까요? 되돌릴 수 없습니다.', { title: '영구 삭제', confirmLabel: '영구삭제', danger: true }).then(function (ok) {
          if (!ok) return;
          API.purgeMeeting(id).then(function () { toast('영구 삭제했습니다.', 'success'); load(); }).catch(function (err) { toast(err.message || '실패', 'error'); });
        });
        return;
      }
      if (e.target.closest('[data-action="move"]')) { openFolderPicker(id, load); return; }
      if (isTrash) return;   // 휴지통 카드 본문 클릭은 무동작(삭제된 회의는 상세 404)
      navigate('#/meetings/' + encodeURIComponent(id));   // 카드 본문 클릭 = 열기
    }
    centerEl.addEventListener('click', onClick);
    load();
    return function cleanup() { cancelled = true; centerEl.removeEventListener('click', onClick); };
  }

  function renderMeetingDetailView(centerEl, rightEl, meetingId, initialTab) {
    centerEl.innerHTML =
      '<div class="center-loading">' +
        '<div class="list-skeleton-row" style="height:64px"></div>' +
        '<div class="list-skeleton-row" style="height:200px"></div>' +
        '<div class="list-skeleton-row" style="height:60px"></div>' +
      '</div>';

    var cancelled = false;
    var meeting = null;
    var segmentsState = [];
    var summaryState = null;
    var bookmarksState = [];
    var highlightsState = [];

    /* 세그먼트 본문 렌더 — 사용자 하이라이트를 먼저 입히고, 검색 강조는 그 위에 얹는다.
       오프셋 기반이라 순서를 뒤집으면 <mark> 태그 길이 때문에 위치가 밀린다. */
    function renderSegmentText(raw, q, segId) {
      var hls = (highlightsState || []).filter(function (h) { return h.segment_id === segId; })
        .slice().sort(function (a, b) { return a.start_offset - b.start_offset; });
      if (!hls.length) return highlightMatch(raw, q);
      var out = '', pos = 0;
      hls.forEach(function (h) {
        if (h.start_offset < pos) return;               // 겹치면 뒤엣것은 건너뛴다
        out += highlightMatch(raw.slice(pos, h.start_offset), q);
        out += '<mark class="user-hl" data-hl="' + esc(h.id) + '">'
             + highlightMatch(raw.slice(h.start_offset, h.end_offset), q) + '</mark>';
        pos = h.end_offset;
      });
      out += highlightMatch(raw.slice(pos), q);
      return out;
    }

    /* 드래그로 고른 범위를 세그먼트 본문 기준 오프셋으로 바꾼다.
       화면에는 <mark> 등이 섞여 있으므로 DOM 위치가 아니라 텍스트 길이로 센다. */
    function selectionOffsets(textEl) {
      var sel = window.getSelection();
      if (!sel || sel.isCollapsed || !sel.rangeCount) return null;
      var range = sel.getRangeAt(0);
      if (!textEl.contains(range.commonAncestorContainer)) return null;
      var pre = range.cloneRange();
      pre.selectNodeContents(textEl);
      pre.setEnd(range.startContainer, range.startOffset);
      var start = pre.toString().length;
      var end = start + range.toString().length;
      return end > start ? { start: start, end: end } : null;
    }

    var dirty = false;
    var lastHighlightedId = null;
    var transcriptQuery = '';
    var matchIndex = 0;   /* 검색 매치 이동(1/131)의 현재 위치. 노드 참조는 렌더마다 무효라 캐시하지 않는다. */
    var sideMode = { twoSpeaker: false, order: [] };
    var detailClickHandler = null;
    var detailFieldHandler = null;
    var selectEndHandler = null;   // centerEl 의 mouseup/touchend — cleanup 에서 반드시 떼야 한다

    Promise.all([
      API.getMeeting(meetingId),
      API.getSegments(meetingId),
      API.getSummary(meetingId),
      API.getBookmarks(meetingId),
      API.getHighlights(meetingId)
    ]).then(function (results) {
      if (cancelled) return;
      meeting = results[0];
      segmentsState = (results[1] && results[1].items) || [];
      bookmarksState = (results[3] && results[3].items) || [];
      highlightsState = (results[4] && results[4].items) || [];
      var summaryRes = results[2];
      summaryState = summaryRes ? Object.assign({}, summaryRes) : {
        summary_version_id: null, version: 0, source: null,
        title: meeting.title || '', summary: '', keywords: [], sections: [],
        decisions: [], action_items: [], calendar_candidates: []
      };
      summaryState.keywords = summaryState.keywords || [];
      summaryState.sections = summaryState.sections || [];
      summaryState.decisions = summaryState.decisions || [];
      summaryState.action_items = summaryState.action_items || [];
      summaryState.calendar_candidates = summaryState.calendar_candidates || [];
      sideMode = computeSideMode(segmentsState);
      buildDetailUI();
    }).catch(function (err) {
      if (cancelled) return;
      centerEl.innerHTML =
        '<div class="center-empty view-fade">' + ICONS.empty +
        '<h2>회의를 불러오지 못했습니다</h2><p>' + esc(err.message || '') + '</p>' +
        '<a href="#/meetings" class="btn btn-ghost">회의 목록으로</a></div>';
      rightEl.innerHTML = '';
    });

    function buildDetailUI() {
      centerEl.innerHTML =
        '<div class="detail-topbar view-fade">' +
          '<button type="button" class="detail-back-btn" id="md-back-btn" aria-label="회의 목록으로">' + ICONS.back + '</button>' +
          '<div class="detail-topbar-main">' +
            '<input type="text" class="title-edit-input" id="md-title-input" value="' + esc(meeting.title || '') + '" aria-label="회의 제목" />' +
            '<div class="detail-meta">' +
              '<span id="md-status-badge">' + statusChipHtml(meeting.status) + '</span>' +
              '<span class="mono">' + esc(formatDateTime(meeting.recorded_at)) + '</span>' +
              '<span class="mono">' + esc(formatDuration(meeting.duration_ms)) + '</span>' +
            '</div>' +
          '</div>' +
          '<div class="detail-topbar-actions">' +
            '<button type="button" class="btn btn-ghost btn-icon info-toggle-btn" id="md-info-toggle" title="참석자·요약 보기" aria-label="참석자·요약 보기">' + ICONS.users + '</button>' +
            '<button type="button" class="btn btn-ghost btn-icon" id="md-move-btn" title="폴더 이동" aria-label="폴더 이동">' + ICONS.folderMove + '</button>' +
            '<button type="button" class="btn btn-ghost btn-icon" id="md-delete-btn" title="삭제" aria-label="회의 삭제">' + ICONS.trash + '</button>' +
          '</div>' +
        '</div>' +

        '<div class="msg-list-wrap">' +
          '<div class="transcript-search-row">' +
            '<div class="search-wrap">' + ICONS.search + '<input type="text" class="input" id="md-transcript-search" placeholder="발화 내용 또는 화자 검색" /></div>' +
            /* 검색 매치 이동(1/131) — 쿼리가 있을 때만 보인다. */
            '<div class="transcript-nav" id="md-match-nav">' +
              '<button type="button" class="btn btn-ghost btn-icon" id="md-match-prev" aria-label="이전 검색 결과">' + ICONS.chevronRight + '</button>' +
              '<span class="match-count mono" id="md-match-count" aria-live="polite"></span>' +
              '<button type="button" class="btn btn-ghost btn-icon" id="md-match-next" aria-label="다음 검색 결과">' + ICONS.chevronRight + '</button>' +
            '</div>' +
            '<span class="transcript-count text-sm" id="md-transcript-count"></span>' +
          '</div>' +
          '<div class="msg-list" id="md-segment-list"></div>' +
        '</div>' +

        '<div class="playback-bar">' +
          '<div class="playback-now" id="md-now-playing">재생 대기 중</div>' +
          '<div class="playback-row">' +
            '<button type="button" class="playback-btn" id="md-skip-back" title="10초 뒤로">' + ICONS.skipBack + '</button>' +
            '<button type="button" class="playback-btn playback-btn-play" id="md-play-btn" title="재생/일시정지">' + ICONS.play + '</button>' +
            '<button type="button" class="playback-btn" id="md-skip-fwd" title="10초 앞으로">' + ICONS.skipFwd + '</button>' +
            '<div class="playback-seek-wrap">' +
              '<span class="playback-time mono" id="md-cur-time">00:00</span>' +
              '<div class="wave-wrap" id="md-wave-wrap">' +
                '<canvas class="wave-canvas" id="md-wave"></canvas>' +
                '<div class="wave-markers" id="md-wave-markers"></div>' +
                '<input type="range" class="audio-seek" id="md-seek" min="0" max="100" value="0" step="0.1" />' +
              '</div>' +
              '<span class="playback-time mono" id="md-dur-time">00:00</span>' +
            '</div>' +
            '<select class="audio-rate-select" id="md-rate-select" title="재생 속도">' +
              '<option value="0.75">0.75x</option><option value="1" selected>1x</option>' +
              '<option value="1.25">1.25x</option><option value="1.5">1.5x</option><option value="2">2x</option>' +
            '</select>' +
          '</div>' +
          '<audio id="md-audio" preload="metadata" class="visually-hidden"' +
            (meeting.audio && meeting.audio.stream_url ? (' src="' + esc(meeting.audio.stream_url) + '"') : '') + '></audio>' +
        '</div>';

      rightEl.innerHTML =
        '<div class="participants-section">' +
          '<div class="right-section-head"><span class="right-section-title">참석자</span><span class="right-section-count mono" id="md-speaker-count"></span></div>' +
          '<div class="participant-list" id="md-speaker-list"></div>' +
        '</div>' +

        '<div class="rtab-bar" role="tablist">' +
          '<button type="button" class="rtab-btn" data-rtab="summary" role="tab">요약</button>' +
          '<button type="button" class="rtab-btn" data-rtab="todos" role="tab">할 일 <span class="count">' + summaryState.action_items.length + '</span></button>' +
          '<button type="button" class="rtab-btn" data-rtab="calendar" role="tab">일정 <span class="count">' + summaryState.calendar_candidates.length + '</span></button>' +
          '<button type="button" class="rtab-btn" data-rtab="export" role="tab">내보내기</button>' +
        '</div>' +

        '<div class="rtab-panel" data-rpanel="summary">' +
          '<div class="card-head"><div class="summary-version-chip" id="md-summary-version-chip"></div></div>' +
          '<div class="field"><label class="field-label" for="md-summary-title">요약 제목</label><input type="text" class="input" id="md-summary-title" value="' + esc(summaryState.title) + '" /></div>' +
          '<div class="field"><label class="field-label" for="md-summary-body">요약 본문</label><textarea class="textarea" id="md-summary-body" rows="6">' + esc(summaryState.summary) + '</textarea></div>' +
          (summaryState.keywords.length
            ? '<div class="field"><label class="field-label">주요 키워드</label><div class="kw-wrap">' +
              summaryState.keywords.map(function (k) { return '<span class="kw-chip">' + esc(k) + '</span>'; }).join('') +
              '</div></div>'
            : '') +
          (summaryState.sections.length
            ? '<div class="field"><label class="field-label">구간 요약 <span class="field-hint">시각을 누르면 그 지점부터 재생됩니다</span></label>' +
              '<ol class="sec-list">' + summaryState.sections.map(function (s) {
                return '<li class="sec-item">' +
                  '<button type="button" class="sec-time mono" data-action="seek-section" data-start="' + (s.start_ms || 0) + '">' +
                    ICONS.play + '<span>' + formatDuration(s.start_ms || 0) + '</span>' +
                  '</button>' +
                  '<div class="sec-body">' +
                    (s.heading ? '<div class="sec-heading">' + esc(s.heading) + '</div>' : '') +
                    '<div class="sec-text">' + esc(s.text) + '</div>' +
                  '</div></li>';
              }).join('') + '</ol></div>'
            : '') +
          '<div class="field"><label class="field-label">결정사항</label><div id="md-decisions-list"></div><button type="button" class="btn btn-subtle btn-sm add-row-btn" id="md-add-decision">+ 결정사항 추가</button></div>' +
          '<div class="save-bar"><button type="button" class="btn btn-primary btn-block" id="md-save-summary-1">변경사항 저장</button><span class="save-bar-status" id="md-summary-save-status"><span class="dot"></span>저장됨</span></div>' +
        '</div>' +

        '<div class="rtab-panel" data-rpanel="todos">' +
          '<div class="todo-table-wrap"><table class="todo-table"><thead><tr><th>담당자</th><th class="col-task">작업</th><th>마감일</th><th>신뢰도</th><th>상태</th><th></th></tr></thead><tbody id="md-todos-tbody"></tbody></table></div>' +
          '<button type="button" class="btn btn-subtle btn-sm add-row-btn" id="md-add-todo">+ 할 일 추가</button>' +
          '<div class="save-bar"><button type="button" class="btn btn-primary btn-block" id="md-save-summary-2">변경사항 저장</button><span class="save-bar-status" id="md-todo-save-status"><span class="dot"></span>저장됨</span></div>' +
        '</div>' +

        '<div class="rtab-panel" data-rpanel="calendar">' +
          '<p class="text-muted text-sm" style="margin-bottom:12px">AI가 추출한 일정 후보입니다. 실제 등록은 캘린더 링크에서 직접 저장하세요.</p>' +
          '<div class="candidate-list" id="md-candidates-list"></div>' +
          '<button type="button" class="btn btn-subtle btn-sm add-row-btn" id="md-add-candidate">+ 일정 후보 추가</button>' +
          '<div class="save-bar"><button type="button" class="btn btn-primary btn-block" id="md-save-summary-3">변경사항 저장</button><span class="save-bar-status" id="md-cal-save-status"><span class="dot"></span>저장됨</span></div>' +
        '</div>' +

        '<div class="rtab-panel" data-rpanel="export">' +
          '<div class="field">' +
            '<label class="field-label">링크로 공유 <span class="field-hint">링크를 가진 사람만 읽기 전용으로 봅니다</span></label>' +
            '<div class="field" style="margin-bottom:8px">' +
              '<select class="select" id="md-share-ttl">' +
                '<option value="7">7일</option><option value="30" selected>30일</option>' +
                '<option value="90">90일</option><option value="180">180일</option><option value="365">1년</option>' +
              '</select>' +
            '</div>' +
            '<input type="text" class="input" id="md-share-pw" placeholder="비밀번호 (선택)" autocomplete="new-password" />' +
            '<label class="checkbox-row" style="margin-top:8px"><input type="checkbox" id="md-share-transcript" checked /><span>전체 전사 포함</span></label>' +
            '<button type="button" class="btn btn-primary btn-sm" id="md-share-create" style="margin-top:8px">공유 링크 만들기</button>' +
            '<div id="md-share-list"></div>' +
          '</div>' +
          '<div class="export-grid">' +
            '<div class="export-option"><div class="export-option-title">' + ICONS.docEdit + '<span>Markdown 내보내기</span></div><p>요약, 결정사항, 할 일, 일정 후보, 전체 전사가 포함된 .md 파일을 생성합니다.</p><button type="button" class="btn btn-primary btn-sm" id="md-export-md">Markdown 내보내기</button></div>' +
            '<div class="export-option"><div class="export-option-title">' + ICONS.docText + '<span>TXT 내보내기</span></div><p>메신저나 이메일에 바로 붙여넣기 좋은 일반 텍스트 파일을 생성합니다.</p><button type="button" class="btn btn-primary btn-sm" id="md-export-txt">TXT 내보내기</button></div>' +
          '</div>' +
          '<div class="right-section-head"><span class="right-section-title">Slack 공유</span></div>' +
          '<div class="field"><label class="field-label" for="md-slack-channel-inline">채널 라벨 <span class="field-hint">(선택, 표시용)</span></label><input type="text" class="input" id="md-slack-channel-inline" placeholder="예: #product" /></div>' +
          '<button type="button" class="btn btn-primary btn-block" id="md-slack-preview-btn">미리보기 후 Slack 공유</button>' +
        '</div>';

      wireDetailUI();
    }


    function wireDetailUI() {
      /* ---- 공통 엘리먼트 (가운데) ---- */
      var titleInput = centerEl.querySelector('#md-title-input');
      var moveBtn = centerEl.querySelector('#md-move-btn');
      if (moveBtn) moveBtn.addEventListener('click', function () { openFolderPicker(meetingId, null); });
      var backBtn = centerEl.querySelector('#md-back-btn');
      var deleteBtn = centerEl.querySelector('#md-delete-btn');
      var infoToggleBtn = centerEl.querySelector('#md-info-toggle');
      var audioEl = centerEl.querySelector('#md-audio');
      var playBtn = centerEl.querySelector('#md-play-btn');
      var skipBackBtn = centerEl.querySelector('#md-skip-back');
      var skipFwdBtn = centerEl.querySelector('#md-skip-fwd');
      var seekRange = centerEl.querySelector('#md-seek');
      var waveCanvas = centerEl.querySelector('#md-wave');
      var waveMarkers = centerEl.querySelector('#md-wave-markers');

      /* ---- 파형 스크러버 ----
         브라우저가 오디오를 디코딩해 피크를 뽑는다. 서버(Vercel 서버리스)에서
         돌리면 대용량 파일마다 함수 실행 시간을 태우므로 클라이언트에서 한다.
         디코딩은 파일 전체를 메모리에 올리므로 큰 파일은 건너뛰고 기존 막대만 쓴다. */
      var WAVE_MAX_BYTES = 30 * 1024 * 1024;
      var wavePeaks = null;

      function drawWave() {
        if (!waveCanvas) return;
        var w = waveCanvas.clientWidth, h = waveCanvas.clientHeight;
        if (!w || !h) return;
        var dpr = window.devicePixelRatio || 1;
        waveCanvas.width = Math.round(w * dpr);
        waveCanvas.height = Math.round(h * dpr);
        var ctx = waveCanvas.getContext('2d');
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        ctx.clearRect(0, 0, w, h);
        if (!wavePeaks || !wavePeaks.length) return;
        var played = (audioEl.duration ? audioEl.currentTime / audioEl.duration : 0);
        var mid = h / 2, bw = w / wavePeaks.length;
        for (var i = 0; i < wavePeaks.length; i++) {
          var amp = Math.max(1, wavePeaks[i] * (h * 0.46));
          ctx.fillStyle = (i / wavePeaks.length) <= played
            ? 'rgba(255,199,0,0.95)' : 'rgba(255,255,255,0.28)';
          ctx.fillRect(i * bw, mid - amp, Math.max(1, bw - 0.6), amp * 2);
        }
      }

      function renderWaveMarkers(bookmarks) {
        if (!waveMarkers) return;
        var dur = audioEl.duration || 0;
        if (!dur || !bookmarks || !bookmarks.length) { waveMarkers.innerHTML = ''; return; }
        waveMarkers.innerHTML = bookmarks.map(function (b) {
          var pct = Math.max(0, Math.min(100, (b.at_ms / 1000 / dur) * 100));
          return '<button type="button" class="wave-marker" style="left:' + pct + '%"' +
                 ' data-action="seek-bookmark" data-at="' + b.at_ms + '"' +
                 ' title="' + esc(formatDuration(b.at_ms)) + ' 북마크"></button>';
        }).join('');
      }

      function loadWaveform(url) {
        if (!waveCanvas || !url || !window.AudioContext) return;
        fetch(url).then(function (r) {
          var len = parseInt(r.headers.get('Content-Length') || '0', 10);
          if (len && len > WAVE_MAX_BYTES) throw new Error('too-large');
          return r.arrayBuffer();
        }).then(function (buf) {
          var ac = new AudioContext();
          return ac.decodeAudioData(buf).then(function (audio) {
            var ch = audio.getChannelData(0);
            var N = 420, block = Math.floor(ch.length / N) || 1, peaks = [];
            for (var i = 0; i < N; i++) {
              var mx = 0, s = i * block, e = Math.min(ch.length, s + block);
              for (var j = s; j < e; j++) { var v = ch[j] < 0 ? -ch[j] : ch[j]; if (v > mx) mx = v; }
              peaks.push(mx);
            }
            var top = Math.max.apply(null, peaks) || 1;
            wavePeaks = peaks.map(function (v) { return v / top; });
            ac.close();
            drawWave();
          });
        }).catch(function () {
          // 디코딩 실패·대용량이면 파형 없이 기존 막대만 쓴다. 재생을 막지 않는다.
          wavePeaks = null;
        });
      }

      var curTimeEl = centerEl.querySelector('#md-cur-time');
      var durTimeEl = centerEl.querySelector('#md-dur-time');
      var rateSelect = centerEl.querySelector('#md-rate-select');
      var nowPlayingEl = centerEl.querySelector('#md-now-playing');

      var transcriptListEl = centerEl.querySelector('#md-segment-list');
      var transcriptSearchInput = centerEl.querySelector('#md-transcript-search');
      var transcriptCountEl = centerEl.querySelector('#md-transcript-count');
      var matchNavEl = centerEl.querySelector('#md-match-nav');
      var matchCountEl = centerEl.querySelector('#md-match-count');
      var matchPrevBtn = centerEl.querySelector('#md-match-prev');
      var matchNextBtn = centerEl.querySelector('#md-match-next');

      /* ---- 공통 엘리먼트 (오른쪽) ---- */
      var speakerListEl = rightEl.querySelector('#md-speaker-list');
      var speakerCountEl = rightEl.querySelector('#md-speaker-count');

      var summaryTitleInput = rightEl.querySelector('#md-summary-title');
      var summaryBodyInput = rightEl.querySelector('#md-summary-body');
      var decisionsListEl = rightEl.querySelector('#md-decisions-list');
      var addDecisionBtn = rightEl.querySelector('#md-add-decision');
      var todosBodyEl = rightEl.querySelector('#md-todos-tbody');
      var addTodoBtn = rightEl.querySelector('#md-add-todo');
      var candidatesListEl = rightEl.querySelector('#md-candidates-list');
      var addCandidateBtn = rightEl.querySelector('#md-add-candidate');
      var summaryVersionChip = rightEl.querySelector('#md-summary-version-chip');

      var summarySaveStatus = rightEl.querySelector('#md-summary-save-status');
      var todoSaveStatus = rightEl.querySelector('#md-todo-save-status');
      var calSaveStatus = rightEl.querySelector('#md-cal-save-status');
      var saveBtn1 = rightEl.querySelector('#md-save-summary-1');
      var saveBtn2 = rightEl.querySelector('#md-save-summary-2');
      var saveBtn3 = rightEl.querySelector('#md-save-summary-3');

      var exportMdBtn = rightEl.querySelector('#md-export-md');
      var exportTxtBtn = rightEl.querySelector('#md-export-txt');
      var slackPreviewBtn = rightEl.querySelector('#md-slack-preview-btn');
      var slackChannelInline = rightEl.querySelector('#md-slack-channel-inline');

      /* ---- 제목 수정 ---- */
      titleInput.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') { e.preventDefault(); titleInput.blur(); }
        if (e.key === 'Escape') { titleInput.value = meeting.title || ''; titleInput.blur(); }
      });
      titleInput.addEventListener('blur', function () {
        var val = titleInput.value.trim();
        if (val === (meeting.title || '')) return;
        if (!val) { titleInput.value = meeting.title || ''; toast('제목은 비워둘 수 없습니다.', 'error'); return; }
        API.updateMeeting(meetingId, { title: val }).then(function () {
          meeting.title = val;
          document.title = val + ' — 회의녹음챗';
          ListColumn.refresh(true);
          toast('제목이 저장되었습니다.', 'success');
        }).catch(function (err) {
          titleInput.value = meeting.title || '';
          toast(err.message || '제목 저장에 실패했습니다.', 'error');
        });
      });

      backBtn.addEventListener('click', function () { navigate('#/meetings'); });
      infoToggleBtn.addEventListener('click', function () { openDrawer(); });

      deleteBtn.addEventListener('click', function () {
        confirmDialog('"' + (meeting.title || '제목 없음') + '" 회의를 삭제하시겠습니까? 목록에서 제거되며 되돌릴 수 없습니다.', { title: '회의 삭제', confirmLabel: '삭제', danger: true }).then(function (ok) {
          if (!ok) return;
          API.deleteMeeting(meetingId).then(function () {
            toast('회의가 삭제되었습니다.', 'success');
            ListColumn.refresh(true);
            navigate('#/meetings');
          }).catch(function (err) { toast(err.message || '삭제에 실패했습니다.', 'error'); });
        });
      });

      /* ---- 오른쪽 패널 탭 전환 (해시는 replaceState로 조용히 갱신 — 재조회 없음) ---- */
      function switchRightTab(tabKey) {
        if (RIGHT_TAB_SLUGS.indexOf(tabKey) === -1) tabKey = 'summary';
        rightEl.querySelectorAll('.rtab-btn').forEach(function (b) { b.classList.toggle('is-active', b.dataset.rtab === tabKey); });
        rightEl.querySelectorAll('.rtab-panel').forEach(function (p) { p.classList.toggle('is-active', p.dataset.rpanel === tabKey); });
        var hash = '#/meetings/' + encodeURIComponent(meetingId) + '/' + tabKey;
        if (location.hash !== hash) history.replaceState(null, '', hash);
      }
      rightEl.querySelectorAll('.rtab-btn').forEach(function (b) {
        b.addEventListener('click', function () { switchRightTab(b.dataset.rtab); });
      });

      /* ---- 오디오 플레이어 ---- */
      function findSegmentAtTime(t) {
        for (var i = 0; i < segmentsState.length; i++) {
          var s = segmentsState[i];
          if (t >= s.start_ms && t < s.end_ms) return s;
        }
        return null;
      }
      function updatePlayIcon(playing) {
        playBtn.innerHTML = playing ? ICONS.pause : ICONS.play;
      }
      function updateNowPlayingCaption(t) {
        var seg = findSegmentAtTime(t);
        if (!seg) { nowPlayingEl.innerHTML = audioEl.paused ? '재생 대기 중' : '재생 중'; return; }
        var name = seg.speaker_name || seg.speaker_label;
        var text = seg.corrected_text || seg.text;
        nowPlayingEl.innerHTML = '<span class="np-speaker">' + esc(name) + '</span><b>' + esc(text) + '</b>';
      }
      function restoreHighlight() {
        if (!transcriptListEl) return;
        transcriptListEl.querySelectorAll('.msg-row').forEach(function (r) {
          var on = r.dataset.segmentId === lastHighlightedId;
          r.classList.toggle('is-playing', on);
        });
      }
      function updateSeekUI(fromUserSeek) {
        var dur = audioEl.duration;
        if (!isFinite(dur) || isNaN(dur)) dur = (meeting.duration_ms ? meeting.duration_ms / 1000 : 0);
        var cur = audioEl.currentTime || 0;
        var pct = dur > 0 ? (cur / dur * 100) : 0;
        if (!fromUserSeek) seekRange.value = String(pct);
        seekRange.style.setProperty('--seek-pct', pct + '%');
        drawWave();
        curTimeEl.textContent = formatDuration(cur * 1000);
        durTimeEl.textContent = formatDuration(dur * 1000);
      }
      audioEl.addEventListener('timeupdate', function () {
        var t = audioEl.currentTime * 1000;
        updateNowPlayingCaption(t);
        var current = findSegmentAtTime(t);
        var currentId = current ? current.segment_id : null;
        if (currentId !== lastHighlightedId) {
          lastHighlightedId = currentId;
          restoreHighlight();
          /* 검색 중에는 재생 따라가기 스크롤을 멈춘다 — 매치 이동으로 옮겨둔 화면을
             재생이 다시 낚아채면 1/131 네비가 무용지물이 된다. */
          if (currentId && transcriptListEl && !transcriptQuery) {
            var row = transcriptListEl.querySelector('.msg-row[data-segment-id="' + cssEscapeId(currentId) + '"]');
            if (row) row.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
          }
        }
        updateSeekUI();
      });
      audioEl.addEventListener('play', function () { updatePlayIcon(true); });
      audioEl.addEventListener('pause', function () { updatePlayIcon(false); });
      audioEl.addEventListener('ended', function () { updatePlayIcon(false); });
      /* 전사에서 텍스트를 고르면 그 자리에서 하이라이트한다.
         이미 하이라이트된 부분을 클릭하면 해제한다. */
      /* 터치 기기는 mouseup 이 안 오거나 늦게 온다. touchend 를 함께 듣되
         같은 제스처가 두 번 처리되지 않게 짧은 시간 잠근다. */
      var lastSelectAt = 0;
      function onSelectEnd(e) {
        var now = Date.now();
        if (now - lastSelectAt < 350) return;
        lastSelectAt = now;
        handleSelectionGesture(e);
      }
      selectEndHandler = onSelectEnd;
      centerEl.addEventListener('mouseup', onSelectEnd);
      centerEl.addEventListener('touchend', onSelectEnd);

      function handleSelectionGesture(e) {
        var mark = e.target.closest && e.target.closest('mark.user-hl');
        if (mark && (window.getSelection() || {}).isCollapsed !== false) {
          var hlId = mark.dataset.hl;
          API.deleteHighlight(meetingId, hlId).then(function () {
            highlightsState = highlightsState.filter(function (h) { return h.id !== hlId; });
            renderTranscriptTab();
            renderWaveHighlights();
          }).catch(function (err) { toast(err.message || '해제하지 못했습니다.', 'error'); });
          return;
        }
        var textEl = e.target.closest && e.target.closest('.msg-text');
        if (!textEl) return;
        var off = selectionOffsets(textEl);
        if (!off) return;
        var segId = textEl.dataset.seg;
        API.addHighlight(meetingId, {
          segment_id: segId, start_offset: off.start, end_offset: off.end
        }).then(function (hl) {
          highlightsState.push(hl);
          window.getSelection().removeAllRanges();
          renderTranscriptTab();
          renderWaveHighlights();
          toast('하이라이트했습니다', 'success');
        }).catch(function (err) { toast(err.message || '하이라이트하지 못했습니다.', 'error'); });
      }

      /* 하이라이트도 파형 마커로 보여준다(북마크와 색만 다르다). */
      function renderWaveHighlights() {
        if (!waveMarkers) return;
        var dur = audioEl.duration || 0;
        var segById = {};
        (segmentsState || []).forEach(function (s) { segById[s.segment_id] = s; });
        var hlMarks = (highlightsState || []).map(function (h) {
          var s = segById[h.segment_id];
          return s ? { at_ms: s.start_ms, kind: 'hl' } : null;
        }).filter(Boolean);
        var all = (bookmarksState || []).map(function (b) { return { at_ms: b.at_ms, kind: 'bm' }; })
          .concat(hlMarks);
        if (!dur || !all.length) { waveMarkers.innerHTML = ''; return; }
        waveMarkers.innerHTML = all.map(function (m) {
          var pct = Math.max(0, Math.min(100, (m.at_ms / 1000 / dur) * 100));
          return '<button type="button" class="wave-marker wave-marker--' + m.kind + '"' +
                 ' style="left:' + pct + '%" data-action="seek-bookmark" data-at="' + m.at_ms + '"' +
                 ' title="' + esc(formatDuration(m.at_ms)) + (m.kind === 'hl' ? ' 하이라이트' : ' 북마크') + '"></button>';
        }).join('');
      }

      /* ---- 공유 링크 ----
         발급 응답의 평문 토큰은 서버가 저장하지 않는다(해시만 보관). 그래서 이
         화면에서 한 번 보여주고, 목록에는 다시 나타나지 않는다. */
      var shareTtl = centerEl.querySelector('#md-share-ttl');
      var sharePw = centerEl.querySelector('#md-share-pw');
      var shareTranscript = centerEl.querySelector('#md-share-transcript');
      var shareCreate = centerEl.querySelector('#md-share-create');
      var shareList = centerEl.querySelector('#md-share-list');

      function renderShareList(items, freshUrl) {
        if (!shareList) return;
        var html = freshUrl
          ? '<div class="share-link-row"><div class="share-link-meta">' +
            '<div class="share-link-url">' + esc(freshUrl) + '</div>' +
            '<div class="share-link-sub">이 주소는 지금만 보입니다 — 복사해 두세요</div></div>' +
            '<button type="button" class="btn btn-subtle btn-sm" data-action="copy-share" data-url="' + esc(freshUrl) + '">복사</button></div>'
          : '';
        html += (items || []).map(function (s) {
          var expired = new Date(s.expires_at) < new Date() || s.revoked_at;
          return '<div class="share-link-row"><div class="share-link-meta">' +
            '<div class="share-link-url">링크 ' + esc(String(s.id).slice(-6)) + (s.has_password ? ' · 비밀번호 있음' : '') + '</div>' +
            '<div class="share-link-sub">만료 ' + esc(String(s.expires_at).slice(0, 10)) +
            ' · 열람 ' + (s.access_count || 0) + '회</div></div>' +
            '<span class="share-badge' + (expired ? ' share-badge--expired' : '') + '">' +
              (s.revoked_at ? '폐기됨' : (expired ? '만료' : '유효')) + '</span>' +
            (s.revoked_at ? '' : '<button type="button" class="btn btn-subtle btn-sm" data-action="revoke-share" data-id="' + esc(s.id) + '">폐기</button>') +
            '</div>';
        }).join('');
        shareList.innerHTML = html;
      }

      /* 발급 직후 한 번만 보이는 평문 URL. 서버는 해시만 저장하므로 이 문자열을 잃으면
         링크를 다시 알아낼 방법이 없다. 그런데 폐기 등 다른 이유로 목록을 새로 그리면
         인자 없이 호출돼 그 URL 이 화면에서 사라졌다 → 기억해 두고 계속 같이 그린다. */
      var freshShareUrl = null;
      var shareSeq = seqGuard();
      function refreshShareList(freshUrl) {
        if (freshUrl) freshShareUrl = freshUrl;
        var my = shareSeq.next();
        API.listShareLinks(meetingId).then(function (res) {
          if (!shareSeq.isCurrent(my)) return;   /* 발급·폐기 새로고침이 겹칠 때 역전 방지 */
          renderShareList((res && res.items) || [], freshShareUrl);
        });
      }

      if (shareCreate) {
        shareCreate.addEventListener('click', function () {
          shareCreate.disabled = true;
          API.createShareLink(meetingId, {
            expires_in_days: parseInt(shareTtl.value, 10),
            password: sharePw.value.trim(),
            include_transcript: !!shareTranscript.checked
          }).then(function (link) {
            sharePw.value = '';
            refreshShareList(location.origin + link.path);
            toast('공유 링크를 만들었습니다', 'success');
          }).catch(function (err) {
            toast(err.message || '링크를 만들지 못했습니다.', 'error');
          }).then(function () { shareCreate.disabled = false; });
        });
      }
      refreshShareList();

      audioEl.addEventListener('loadedmetadata', function () {
        updateSeekUI();
        renderWaveHighlights();
      });
      if (meeting.audio && meeting.audio.stream_url) loadWaveform(meeting.audio.stream_url);
      window.addEventListener('resize', drawWave);
      audioEl.addEventListener('error', function () {
        nowPlayingEl.textContent = '오디오를 불러올 수 없습니다.';
      });

      playBtn.addEventListener('click', function () {
        if (audioEl.paused) audioEl.play().catch(function () { toast('오디오 재생을 시작할 수 없습니다.', 'error'); });
        else audioEl.pause();
      });
      skipBackBtn.addEventListener('click', function () { audioEl.currentTime = Math.max(0, audioEl.currentTime - 10); });
      skipFwdBtn.addEventListener('click', function () { audioEl.currentTime = Math.min(audioEl.duration || 1e9, audioEl.currentTime + 10); });
      rateSelect.addEventListener('change', function () { audioEl.playbackRate = parseFloat(rateSelect.value); });
      seekRange.addEventListener('input', function () {
        var dur = audioEl.duration;
        if (!isFinite(dur) || isNaN(dur)) dur = (meeting.duration_ms ? meeting.duration_ms / 1000 : 0);
        audioEl.currentTime = (parseFloat(seekRange.value) / 100) * dur;
        updateSeekUI(true);
      });

      function seekAndPlay(startMs) {
        audioEl.currentTime = startMs / 1000;
        audioEl.play().catch(function () { /* 사용자 상호작용 이후이므로 대부분 성공 */ });
      }

      function jumpToSegment(segmentId) {
        closeDrawer();
        var row = transcriptListEl.querySelector('.msg-row[data-segment-id="' + cssEscapeId(segmentId) + '"]');
        if (!row) { toast('해당 발화를 찾을 수 없습니다.', 'error'); return; }
        row.scrollIntoView({ block: 'center', behavior: 'smooth' });
        row.classList.add('is-jumped');
        setTimeout(function () { row.classList.remove('is-jumped'); }, 1600);
      }

      /* ---- 전사 (채팅 버블) ---- */
      function segmentRowHtml(seg, q) {
        var displayName = seg.speaker_name || seg.speaker_label;
        var rawText = (seg.corrected_text !== null && seg.corrected_text !== undefined && seg.corrected_text !== '') ? seg.corrected_text : seg.text;
        var edited = seg.corrected_text !== null && seg.corrected_text !== undefined && seg.corrected_text !== '';
        var confPct = formatPercent(seg.confidence);
        var isRight = sideMode.twoSpeaker && sideMode.order.indexOf(seg.speaker_label) === 1;
        var side = isRight ? 'right' : 'left';
        var col = colorFromString(seg.speaker_label);
        var bubbleVariant = isRight ? 'msg-bubble--sent' : 'msg-bubble--received';
        var avatarHtml = !isRight
          ? '<div class="msg-avatar" style="background:' + col.bg + ';color:' + col.fg + '">' + esc((displayName || '?').charAt(0)) + '</div>'
          : '';
        return (
          '<div class="msg-row msg-row--' + side + '" data-segment-id="' + esc(seg.segment_id) + '" data-start-ms="' + seg.start_ms + '" data-end-ms="' + seg.end_ms + '">' +
            avatarHtml +
            '<div class="msg-col">' +
              '<div class="msg-meta">' +
                '<button type="button" class="msg-speaker" data-action="rename-speaker" style="color:' + col.fg + '">' + highlightMatch(displayName, q) + '</button>' +
                '<button type="button" class="msg-time mono" data-action="seek"><svg width="9" height="9" viewBox="0 0 10 10" fill="none"><path d="M5 1a4 4 0 100 8 4 4 0 000-8z" stroke="currentColor"/><path d="M5 2.6V5l1.6 1" stroke="currentColor" stroke-linecap="round"/></svg>' + formatDuration(seg.start_ms) + '</button>' +
              '</div>' +
              '<div class="msg-bubble ' + bubbleVariant + '">' +
                '<span class="msg-text" data-seg="' + esc(seg.segment_id) + '">' + renderSegmentText(rawText, q, seg.segment_id) + '</span>' + (edited ? '<span class="msg-edited-tag">수정됨</span>' : '') +
                '<div class="msg-edit-area" style="display:none">' +
                  '<textarea class="textarea">' + esc(rawText) + '</textarea>' +
                  '<div class="segment-edit-actions"><button type="button" class="btn btn-primary btn-sm" data-action="save-edit">저장</button><button type="button" class="btn btn-ghost btn-sm" data-action="cancel-edit">취소</button></div>' +
                '</div>' +
              '</div>' +
              (confPct !== null && confPct < 60 ? '<div class="msg-confidence-tag">신뢰도 낮음 · ' + confPct + '%</div>' : '') +
            '</div>' +
            '<div class="msg-actions">' +
              '<button type="button" class="icon-toggle' + (seg.bookmarked ? ' is-on' : '') + '" data-action="bookmark" title="북마크" aria-pressed="' + (seg.bookmarked ? 'true' : 'false') + '">' + ICONS.star + '</button>' +
              '<button type="button" class="icon-toggle" data-action="edit" title="텍스트 수정">' + ICONS.edit + '</button>' +
            '</div>' +
          '</div>'
        );
      }

      /* 검색 매치 노드 목록. innerHTML 교체마다 참조가 무효라 그때그때 새로 뽑는다.
         화자명 매치는 .msg-speaker 안이라 컨테이너로 자연히 제외되고,
         사용자 하이라이트(mark.user-hl)도 클래스로 제외한다 — 1/131 은 발화 본문 기준. */
      function matchNodes() {
        /* 화자명(.msg-speaker)도 포함한다 — 플레이스홀더가 '발화 내용 또는 화자 검색'이라
           화자명으로 찾은 결과가 0/0 으로 보이면 안 된다. querySelectorAll 은 문서 순서라
           세그먼트 순서가 그대로 유지된다. */
        return transcriptListEl ? transcriptListEl.querySelectorAll('.msg-text mark:not(.user-hl), .msg-speaker mark') : [];
      }

      /* 렌더 직후 매치/카운터/활성 표시를 DOM 기준으로 재동기화한다.
         renderTranscriptTab 꼬리에서 부르므로 사용자 하이라이트 추가·삭제로 인한
         재렌더에서도 카운터가 어긋나지 않는다. scroll 은 쿼리가 바뀐 순간에만 true. */
      function syncMatches(scroll) {
        var nodes = matchNodes();
        var n = nodes.length;
        if (!matchNavEl) return;
        if (!transcriptQuery) {
          matchNavEl.style.display = 'none';
          return;
        }
        matchNavEl.style.display = '';
        if (matchIndex > n - 1) matchIndex = n ? n - 1 : 0;
        if (matchIndex < 0) matchIndex = 0;
        matchCountEl.textContent = n ? (matchIndex + 1) + ' / ' + n : '0 / 0';
        matchPrevBtn.disabled = matchNextBtn.disabled = !n;
        matchPrevBtn.setAttribute('aria-disabled', n ? 'false' : 'true');
        matchNextBtn.setAttribute('aria-disabled', n ? 'false' : 'true');
        for (var i = 0; i < n; i++) nodes[i].classList.toggle('is-active-match', i === matchIndex);
        if (scroll && n) nodes[matchIndex].scrollIntoView({ block: 'center', behavior: 'smooth' });
      }

      /* 이전/다음 매치로 이동(랩어라운드). 재렌더 없이 클래스만 옮긴다. */
      function gotoMatch(delta) {
        var nodes = matchNodes();
        if (!nodes.length) return;   /* 0 매치에서 Enter 를 눌러도 안전해야 한다 */
        matchIndex = (matchIndex + delta + nodes.length) % nodes.length;
        syncMatches(true);
      }

      function renderTranscriptTab() {
        if (!segmentsState.length) {
          transcriptListEl.innerHTML = emptyStateHtml('전사 내용이 없습니다', '이 회의에는 아직 전사된 발화가 없습니다.');
          transcriptCountEl.textContent = '';
          if (matchNavEl) matchNavEl.style.display = 'none';
          return;
        }
        /* 검색 중에도 전체 세그먼트를 유지하고 매치만 인플레이스 하이라이트(클로바식). */
        transcriptListEl.innerHTML = segmentsState.map(function (s) { return segmentRowHtml(s, transcriptQuery); }).join('');
        transcriptCountEl.textContent = segmentsState.length + '개 발화';
        restoreHighlight();
        syncMatches(false);
      }

      function applyTranscriptSearch() {
        var q = (transcriptSearchInput.value || '').trim().toLowerCase();
        var changed = q !== transcriptQuery;
        transcriptQuery = q;
        if (!segmentsState.length) return;
        renderTranscriptTab();
        /* 쿼리가 바뀐 경우에만 첫 매치로 이동+스크롤. 편집·북마크發 재렌더는
           renderTranscriptTab 안의 syncMatches(false) 가 인덱스를 보존한다. */
        if (changed) { matchIndex = 0; syncMatches(true); }
      }
      var debouncedTranscriptSearch = debounce(applyTranscriptSearch, 200);
      transcriptSearchInput.addEventListener('input', debouncedTranscriptSearch);
      transcriptSearchInput.addEventListener('keydown', function (e) {
        /* 한글 조합 확정 Enter 는 무시한다. */
        if (e.key !== 'Enter' || e.isComposing || e.keyCode === 229) return;
        e.preventDefault();
        debouncedTranscriptSearch.cancel();
        /* 200ms 디바운스가 아직 안 돈 상태면 먼저 반영한다(첫 Enter 가 삼켜지지 않게). */
        if ((transcriptSearchInput.value || '').trim().toLowerCase() !== transcriptQuery) {
          applyTranscriptSearch();
          return;
        }
        gotoMatch(e.shiftKey ? -1 : 1);
      });
      matchPrevBtn.addEventListener('click', function () { gotoMatch(-1); });
      matchNextBtn.addEventListener('click', function () { gotoMatch(1); });

      function toggleEditArea(row, show) {
        if (!row) return;
        var bubble = row.querySelector('.msg-bubble');
        if (!bubble) return;
        var textEl = bubble.querySelector('.msg-text');
        var editedTag = bubble.querySelector('.msg-edited-tag');
        var editArea = bubble.querySelector('.msg-edit-area');
        if (textEl) textEl.style.display = show ? 'none' : '';
        if (editedTag) editedTag.style.display = show ? 'none' : '';
        if (editArea) editArea.style.display = show ? '' : 'none';
        if (show) {
          var ta = editArea && editArea.querySelector('textarea');
          if (ta) ta.focus();
        }
      }

      function saveSegmentEdit(row, seg) {
        var val = row.querySelector('.msg-edit-area textarea').value;
        API.updateSegment(meetingId, seg.segment_id, { corrected_text: val }).then(function (updated) {
          seg.corrected_text = (updated && updated.corrected_text !== undefined) ? updated.corrected_text : val;
          applyTranscriptSearch();
          toast('전사 내용이 저장되었습니다.', 'success');
        }).catch(function (err) { toast(err.message || '저장에 실패했습니다.', 'error'); });
      }

      /* 세그먼트별 in-flight 잠금. 연타하면 PATCH 두 개가 경합하고, 응답 순서가
         뒤바뀌면 서버는 켜짐인데 화면은 꺼짐으로 굳는다(응답을 버리므로 보정도 안 된다). */
      var bmLocks = {};
      function toggleBookmark(seg) {
        var key = String(seg.segment_id);
        if (bmLocks[key]) return;
        bmLocks[key] = true;
        var next = !seg.bookmarked;
        seg.bookmarked = next;
        applyTranscriptSearch();
        API.updateSegment(meetingId, seg.segment_id, { bookmarked: next }).then(function () {
          delete bmLocks[key];
        }, function (err) {
          delete bmLocks[key];
          seg.bookmarked = !next;
          applyTranscriptSearch();
          toast(err.message || '북마크 저장에 실패했습니다.', 'error');
        });
      }

      function promptRenameSpeaker(label, currentName) {
        var next = window.prompt('"' + label + '" 화자의 표시 이름을 입력하세요.', currentName || '');
        if (next === null) return;
        var trimmed = next.trim();
        if (!trimmed) { toast('화자 이름을 입력해주세요.', 'error'); return; }
        API.renameSpeaker(meetingId, label, trimmed).then(function () {
          segmentsState.forEach(function (s) { if (s.speaker_label === label) s.speaker_name = trimmed; });
          applyTranscriptSearch();
          renderSpeakerList();
          toast('화자 이름이 변경되었습니다.', 'success');
        }).catch(function (err) { toast(err.message || '화자 이름 변경에 실패했습니다.', 'error'); });
      }

      renderTranscriptTab();

      /* ---- 참석자(화자) 목록 ---- */
      function renderSpeakerList() {
        var order = sideMode.order;
        if (speakerCountEl) speakerCountEl.textContent = order.length;
        if (!order.length) { speakerListEl.innerHTML = '<p class="text-muted text-sm">참석자 정보가 없습니다.</p>'; return; }
        speakerListEl.innerHTML = order.map(function (label) {
          var seg = segmentsState.find(function (s) { return s.speaker_label === label; });
          var name = seg ? (seg.speaker_name || seg.speaker_label) : label;
          var count = segmentsState.filter(function (s) { return s.speaker_label === label; }).length;
          var col = colorFromString(label);
          return (
            '<button type="button" class="participant-chip" data-action="rename-speaker-panel" data-label="' + esc(label) + '" data-name="' + esc(name) + '">' +
              '<span class="participant-avatar" style="background:' + col.bg + ';color:' + col.fg + '">' + esc((name || '?').charAt(0)) + '</span>' +
              '<span class="participant-info"><span class="participant-name">' + esc(name) + '</span><span class="participant-sub">' + count + '개 발화</span></span>' +
            '</button>'
          );
        }).join('');
      }
      renderSpeakerList();

      /* ---- 요약 : 결정사항 ---- */
      function updateSummaryVersionChip() {
        var srcLabel = summaryState.source === 'ai' ? 'AI 생성' : (summaryState.source === 'user' ? '사용자 수정' : '초안 없음');
        summaryVersionChip.innerHTML = summaryState.version
          ? ('<span class="mono">v' + summaryState.version + '</span> · ' + esc(srcLabel))
          : '아직 저장된 요약 버전이 없습니다';
      }
      updateSummaryVersionChip();

      function renderDecisionsList() {
        if (!summaryState.decisions.length) {
          decisionsListEl.innerHTML = '<p class="text-muted text-sm">등록된 결정사항이 없습니다.</p>';
          return;
        }
        decisionsListEl.innerHTML = summaryState.decisions.map(function (d, idx) {
          return (
            '<div class="decision-row" data-array="decisions" data-idx="' + idx + '">' +
              '<div class="decision-row-main">' +
                '<textarea class="textarea" data-field="text" placeholder="결정 내용을 입력하세요">' + esc(d.text || '') + '</textarea>' +
                '<button type="button" class="btn-icon btn-ghost" data-action="remove-decision" title="삭제">' + ICONS.trash + '</button>' +
              '</div>' +
              chipsRowHtml(d.source_segment_ids) +
            '</div>'
          );
        }).join('');
      }

      /* ---- 할 일 ---- */
      function renderTodosList() {
        if (!summaryState.action_items.length) {
          todosBodyEl.innerHTML = '<tr><td colspan="6" class="text-muted text-sm">등록된 할 일이 없습니다.</td></tr>';
          return;
        }
        todosBodyEl.innerHTML = summaryState.action_items.map(function (item, idx) {
          return (
            '<tr data-array="action_items" data-idx="' + idx + '">' +
              '<td><input class="input" data-field="owner" value="' + esc(item.owner || '') + '" placeholder="담당자" /></td>' +
              '<td class="col-task"><input class="input" data-field="task" value="' + esc(item.task || '') + '" placeholder="작업 내용" />' + chipsRowHtml(item.source_segment_ids) + '</td>' +
              '<td><input type="date" class="input" data-field="due_date" value="' + esc(item.due_date ? String(item.due_date).slice(0, 10) : '') + '" /></td>' +
              '<td>' + (item.confidence !== null && item.confidence !== undefined ? confidencePillHtml(item.confidence) : '<span class="text-muted text-sm">-</span>') + '</td>' +
              '<td><select class="select" data-field="status">' + statusOptionsHtml(TODO_STATUS_OPTIONS, item.status) + '</select></td>' +
              '<td><button type="button" class="btn-icon btn-ghost" data-action="remove-todo" title="삭제">' + ICONS.trash + '</button></td>' +
            '</tr>'
          );
        }).join('');
      }

      /* ---- 일정 후보 ---- */
      function renderCandidatesList() {
        if (!summaryState.calendar_candidates.length) {
          candidatesListEl.innerHTML = '<p class="text-muted text-sm">등록된 일정 후보가 없습니다.</p>';
          return;
        }
        candidatesListEl.innerHTML = summaryState.calendar_candidates.map(function (c, idx) {
          return (
            '<div class="candidate-card" data-array="calendar_candidates" data-idx="' + idx + '">' +
              '<div class="candidate-top">' +
                '<input class="input" data-field="title" value="' + esc(c.title || '') + '" placeholder="일정 제목" style="font-weight:700" />' +
                '<button type="button" class="btn-icon btn-ghost" data-action="remove-candidate" title="삭제">' + ICONS.trash + '</button>' +
              '</div>' +
              '<div class="field-row">' +
                '<div class="field"><label class="field-label">시작</label><input type="datetime-local" class="input" data-field="start_at" value="' + toLocalInputValue(c.start_at) + '" /></div>' +
                '<div class="field"><label class="field-label">종료</label><input type="datetime-local" class="input" data-field="end_at" value="' + toLocalInputValue(c.end_at) + '" /></div>' +
              '</div>' +
              '<div class="field"><label class="field-label">참석자 <span class="field-hint">쉼표로 구분</span></label><input class="input" data-field="attendees" value="' + esc((c.attendees || []).join(', ')) + '" /></div>' +
              chipsRowHtml(c.source_segment_ids) +
              '<div class="candidate-foot">' +
                '<span class="flex gap-8" style="align-items:center">' +
                  (c.confidence !== null && c.confidence !== undefined ? confidencePillHtml(c.confidence) : '') +
                  '<select class="select" data-field="status">' + statusOptionsHtml(CAL_STATUS_OPTIONS, c.status) + '</select>' +
                '</span>' +
                '<button type="button" class="btn btn-ghost btn-sm" data-action="calendar-link">' + ICONS.calendar + '<span>캘린더 링크</span></button>' +
              '</div>' +
            '</div>'
          );
        }).join('');
      }

      renderDecisionsList();
      renderTodosList();
      renderCandidatesList();

      function buildGoogleCalendarUrl(c) {
        function fmt(iso) {
          var d = new Date(iso);
          if (isNaN(d.getTime())) return '';
          return d.toISOString().replace(/[-:]/g, '').split('.')[0] + 'Z';
        }
        var params = new URLSearchParams({
          action: 'TEMPLATE',
          text: c.title || '(제목 없음)',
          dates: fmt(c.start_at) + '/' + fmt(c.end_at),
          details: '회의녹음챗에서 자동 추출된 일정 후보입니다.'
        });
        if (c.attendees && c.attendees.length) params.set('add', c.attendees.join(','));
        return 'https://calendar.google.com/calendar/render?' + params.toString();
      }

      /* ---- 변경 감지 & 저장 ---- */
      var dirtyTick = 0;   // markDirty 호출 횟수. 저장 요청이 떠난 뒤 사용자가 또 고쳤는지 본다.
      function markDirty() {
        dirty = true;
        summaryDirty = true;   // navigate 가 볼 수 있게 모듈 레벨로 미러링
        dirtyTick += 1;   // 저장 중 수정 여부 판정용(아래 saveSummary)
        [summarySaveStatus, todoSaveStatus, calSaveStatus].forEach(function (el) {
          if (!el) return;
          el.classList.add('is-dirty');
          el.innerHTML = '<span class="dot"></span>저장되지 않은 변경사항';
        });
      }
      function markClean() {
        dirty = false;
        summaryDirty = false;
        [summarySaveStatus, todoSaveStatus, calSaveStatus].forEach(function (el) {
          if (!el) return;
          el.classList.remove('is-dirty');
          el.innerHTML = '<span class="dot"></span>저장됨';
        });
      }

      summaryTitleInput.addEventListener('input', function () { summaryState.title = summaryTitleInput.value; markDirty(); });
      summaryBodyInput.addEventListener('input', function () { summaryState.summary = summaryBodyInput.value; markDirty(); });

      function handleFieldChange(e) {
        var target = e.target;
        var field = target.dataset.field;
        if (!field) return;
        var rowEl = target.closest('[data-idx]');
        if (!rowEl) return;
        var arrName = rowEl.dataset.array;
        var idx = Number(rowEl.dataset.idx);
        var arr = summaryState[arrName];
        if (!arr || !arr[idx]) return;
        if (field === 'attendees') {
          arr[idx][field] = target.value.split(',').map(function (s) { return s.trim(); }).filter(Boolean);
        } else if (field === 'start_at' || field === 'end_at') {
          arr[idx][field] = fromLocalInputValue(target.value);
        } else if (field === 'due_date') {
          arr[idx][field] = target.value || null;
        } else {
          arr[idx][field] = target.value;
        }
        markDirty();
      }
      rightEl.addEventListener('input', handleFieldChange);
      rightEl.addEventListener('change', handleFieldChange);
      detailFieldHandler = handleFieldChange;

      function saveSummary() {
        var payload = {
          title: summaryState.title,
          summary: summaryState.summary,
          decisions: summaryState.decisions,
          action_items: summaryState.action_items,
          calendar_candidates: summaryState.calendar_candidates,
          /* 낙관적 잠금: 편집을 시작한(= 마지막으로 받은) 버전. 그 사이 다른 탭이나
             다른 방문자가 저장했으면 서버가 409 로 거부한다. 공용 계정이라 남의 편집을
             통째로 덮어쓰는 일이 실제로 생긴다. 요약이 아직 없으면 0. */
          base_version: summaryState.version || 0
        };
        [saveBtn1, saveBtn2, saveBtn3].forEach(function (b) { if (b) b.disabled = true; });
        /* 저장 중에도 입력은 막히지 않는다(비활성화되는 건 저장 버튼뿐). 그래서 응답에서
           무조건 markClean() 하면, 요청이 떠난 뒤 고친 내용은 서버에 없는데 화면은
           '저장됨' 이 된다 — 사용자가 그대로 나가면 조용히 사라진다.
           보낼 때의 수정 카운터를 기억해 두고, 그대로일 때만 깨끗하다고 표시한다. */
        var sentTick = dirtyTick;
        API.updateSummary(meetingId, payload).then(function (res) {
          summaryState.summary_version_id = res.summary_version_id;
          summaryState.version = res.version;
          summaryState.source = res.source;
          updateSummaryVersionChip();
          if (dirtyTick === sentTick) markClean();
          ListColumn.refresh(true);
          toast('요약이 저장되었습니다. (v' + res.version + ')', 'success');
        }).catch(function (err) {
          if (err && err.code === 'summary_conflict') {
            /* 사용자의 편집은 절대 버리지 않는다. 화면은 그대로 두고 충돌만 알린다.
               dirty 표시도 유지돼야 '저장됨' 으로 오해하지 않는다. */
            var cur = (err.details && err.details.current_version) || 0;
            toast('다른 곳에서 요약이 먼저 저장됐습니다(현재 v' + cur + ').' +
                  ' 내 편집은 그대로 두었어요 — 최신 내용을 확인한 뒤 다시 저장해 주세요.',
                  'error', { duration: 9000 });
            return;
          }
          toast(err.message || '요약 저장에 실패했습니다.', 'error');
        }).finally(function () {
          [saveBtn1, saveBtn2, saveBtn3].forEach(function (b) { if (b) b.disabled = false; });
        });
      }
      [saveBtn1, saveBtn2, saveBtn3].forEach(function (b) { if (b) b.addEventListener('click', saveSummary); });

      addDecisionBtn.addEventListener('click', function () {
        summaryState.decisions.push({ text: '', source_segment_ids: [] });
        markDirty(); renderDecisionsList();
      });
      addTodoBtn.addEventListener('click', function () {
        summaryState.action_items.push({ owner: '', task: '', due_date: null, source_segment_ids: [], confidence: null, status: 'open' });
        markDirty(); renderTodosList();
      });
      addCandidateBtn.addEventListener('click', function () {
        summaryState.calendar_candidates.push({ title: '', start_at: null, end_at: null, attendees: [], source_segment_ids: [], confidence: null, status: 'pending' });
        markDirty(); renderCandidatesList();
      });

      /* ---- 클릭 위임 (전사 · 참석자 · 결정사항 · 할 일 · 일정 후보 공통) ---- */
      function handleAction(e) {
        var btn = e.target.closest('[data-action]');
        if (!btn) return;
        var action = btn.dataset.action;
        var segRow, seg;
        switch (action) {
          case 'copy-share':
            navigator.clipboard.writeText(btn.dataset.url)
              .then(function () { toast('링크를 복사했습니다', 'success'); })
              .catch(function () { toast('복사하지 못했습니다.', 'error'); });
            return;
          case 'revoke-share':
            API.revokeShareLink(meetingId, btn.dataset.id).then(function () {
              refreshShareList();
              toast('링크를 폐기했습니다', 'success');
            }).catch(function (err) { toast(err.message || '폐기하지 못했습니다.', 'error'); });
            return;
          case 'seek-bookmark':
            seekAndPlay(parseInt(btn.dataset.at, 10) || 0);
            return;
          case 'seek-section':
            // 구간 요약의 시각 → 해당 지점부터 재생. 전사 말풍선의 seek 과 같은 경로를 쓴다.
            seekAndPlay(parseInt(btn.dataset.start, 10) || 0);
            return;
          case 'seek':
            segRow = btn.closest('.msg-row');
            if (segRow) seekAndPlay(Number(segRow.dataset.startMs));
            break;
          case 'rename-speaker':
            segRow = btn.closest('.msg-row');
            seg = segRow && segmentsState.find(function (s) { return s.segment_id === segRow.dataset.segmentId; });
            if (seg) promptRenameSpeaker(seg.speaker_label, seg.speaker_name);
            break;
          case 'rename-speaker-panel':
            promptRenameSpeaker(btn.dataset.label, btn.dataset.name);
            break;
          case 'bookmark':
            segRow = btn.closest('.msg-row');
            seg = segRow && segmentsState.find(function (s) { return s.segment_id === segRow.dataset.segmentId; });
            if (seg) toggleBookmark(seg);
            break;
          case 'edit':
            toggleEditArea(btn.closest('.msg-row'), true);
            break;
          case 'cancel-edit':
            toggleEditArea(btn.closest('.msg-row'), false);
            break;
          case 'save-edit':
            segRow = btn.closest('.msg-row');
            seg = segRow && segmentsState.find(function (s) { return s.segment_id === segRow.dataset.segmentId; });
            if (seg) saveSegmentEdit(segRow, seg);
            break;
          case 'jump':
            jumpToSegment(btn.dataset.seg);
            break;
          case 'remove-decision':
            removeArrayItem('decisions', btn.closest('[data-idx]'), renderDecisionsList);
            break;
          case 'remove-todo':
            removeArrayItem('action_items', btn.closest('[data-idx]'), renderTodosList);
            break;
          case 'remove-candidate':
            removeArrayItem('calendar_candidates', btn.closest('[data-idx]'), renderCandidatesList);
            break;
          case 'calendar-link':
            var wrap = btn.closest('[data-idx]');
            var idx = Number(wrap.dataset.idx);
            window.open(buildGoogleCalendarUrl(summaryState.calendar_candidates[idx]), '_blank', 'noopener');
            break;
        }
      }
      centerEl.addEventListener('click', handleAction);
      rightEl.addEventListener('click', handleAction);
      detailClickHandler = handleAction;

      function removeArrayItem(arrName, wrapEl, rerenderFn) {
        if (!wrapEl) return;
        var idx = Number(wrapEl.dataset.idx);
        summaryState[arrName].splice(idx, 1);
        markDirty();
        rerenderFn();
      }

      /* ---- 내보내기 · Slack 공유 ---- */
      function handleExport(format) {
        var btn = format === 'md' ? exportMdBtn : exportTxtBtn;
        btn.disabled = true;
        var orig = btn.textContent;
        btn.textContent = '생성 중…';
        API.createExport(meetingId, {
          format: format,
          include_transcript: true,
          summary_version_id: summaryState.summary_version_id || undefined
        }).then(function (res) {
          triggerDownload(res.download_url);
          toast(format.toUpperCase() + ' 파일을 생성했습니다. 다운로드를 확인하세요.', 'success');
        }).catch(function (err) {
          toast(err.message || '내보내기에 실패했습니다.', 'error');
        }).finally(function () {
          btn.disabled = false;
          btn.textContent = orig;
        });
      }
      exportMdBtn.addEventListener('click', function () { handleExport('md'); });
      exportTxtBtn.addEventListener('click', function () { handleExport('txt'); });

      function assembleSlackMessage() {
        var lines = [];
        lines.push('[회의 요약] ' + (summaryState.title || meeting.title || '(제목 없음)'));
        lines.push('');
        lines.push('요약:');
        lines.push('- ' + (summaryState.summary || '(요약 없음)'));
        lines.push('');
        lines.push('결정사항:');
        if (summaryState.decisions.length) summaryState.decisions.forEach(function (d) { lines.push('- ' + (d.text || '')); });
        else lines.push('- (없음)');
        lines.push('');
        lines.push('할 일:');
        if (summaryState.action_items.length) summaryState.action_items.forEach(function (a) {
          lines.push('- ' + (a.owner || '미지정') + ': ' + (a.task || '') + (a.due_date ? (' (' + a.due_date + ')') : ''));
        });
        else lines.push('- (없음)');
        lines.push('');
        lines.push('일정 후보:');
        if (summaryState.calendar_candidates.length) summaryState.calendar_candidates.forEach(function (c) {
          lines.push('- ' + (c.start_at ? formatDateTime(c.start_at) : '(미정)') + ' ' + (c.title || ''));
        });
        else lines.push('- (없음)');
        return lines.join('\n');
      }

      function openSlackPreview() {
        var dlg = document.getElementById('slack-dialog');
        var channelInput = document.getElementById('slack-channel-input');
        var previewText = document.getElementById('slack-preview-text');
        var resultArea = document.getElementById('slack-result-area');
        var sendBtn = document.getElementById('slack-dialog-send');
        var cancelBtn = document.getElementById('slack-dialog-cancel');

        channelInput.value = slackChannelInline.value || '';
        previewText.textContent = assembleSlackMessage();
        resultArea.innerHTML = '';
        sendBtn.disabled = false;
        sendBtn.textContent = 'Slack으로 전송';

        function onSend() {
          sendBtn.disabled = true;
          sendBtn.textContent = '전송 중…';
          API.shareSlack(meetingId, {
            summary_version_id: summaryState.summary_version_id || undefined,
            channel_label: channelInput.value.trim() || undefined,
            message_override: null
          }).then(function (res) {
            var ok = res.status === 'sent';
            resultArea.innerHTML = '<div class="share-result ' + (ok ? 'is-sent' : 'is-failed') + '">' +
              (ok ? '전송 완료' : '전송 실패') + ' · ' + esc(res.provider || 'slack_webhook') +
              (res.sent_at ? (' · ' + esc(formatDateTime(res.sent_at))) : '') +
              (res.detail ? (' · ' + esc(res.detail)) : '') + '</div>';
            toast(ok ? 'Slack으로 공유되었습니다.' : 'Slack 공유에 실패했습니다.', ok ? 'success' : 'error');
            if (ok) ListColumn.refresh(true);
          }).catch(function (err) {
            resultArea.innerHTML = '<div class="share-result is-failed">전송 실패 · ' + esc(err.message || '') + '</div>';
            toast(err.message || 'Slack 공유에 실패했습니다.', 'error');
          }).finally(function () {
            sendBtn.disabled = false;
            sendBtn.textContent = 'Slack으로 전송';
          });
        }
        function onCancel() { dlg.close(); }
        function onClose() {
          sendBtn.removeEventListener('click', onSend);
          cancelBtn.removeEventListener('click', onCancel);
          dlg.removeEventListener('close', onClose);
        }
        sendBtn.addEventListener('click', onSend);
        cancelBtn.addEventListener('click', onCancel);
        dlg.addEventListener('close', onClose);
        dlg.showModal();
      }
      slackPreviewBtn.addEventListener('click', openSlackPreview);

      /* ---- 초기 오른쪽 탭 적용 ---- */
      var initialRightTab = (initialTab && RIGHT_TAB_SLUGS.indexOf(initialTab) !== -1) ? initialTab : 'summary';
      switchRightTab(initialRightTab);
    }

    return function cleanup() {
      cancelled = true;
      var audioEl = centerEl.querySelector('#md-audio');
      if (audioEl) { try { audioEl.pause(); } catch (e) {} }
      if (detailClickHandler) {
        centerEl.removeEventListener('click', detailClickHandler);
        rightEl.removeEventListener('click', detailClickHandler);
      }
      if (detailFieldHandler) {
        rightEl.removeEventListener('input', detailFieldHandler);
        rightEl.removeEventListener('change', detailFieldHandler);
      }
      /* 선택 제스처 리스너도 반드시 떼야 한다. centerEl 은 라우트가 바뀌어도 살아있는
         영속 요소(innerHTML 만 갈린다)라, 안 떼면 상세를 N번 방문하면 리스너가 N쌍 붙고
         한 번 드래그에 하이라이트 POST 가 N번 나간다. 각 클로저가 자기 lastSelectAt 을
         갖기 때문에 350ms 잠금으로는 막히지 않는다. */
      if (selectEndHandler) {
        centerEl.removeEventListener('mouseup', selectEndHandler);
        centerEl.removeEventListener('touchend', selectEndHandler);
      }
      /* 이 뷰를 떠나면 가드 대상도 사라진다. 남겨두면 다른 화면에서 이동할 때마다
         '저장하지 않은 요약' 확인이 뜬다(녹음 가드의 recordingActive 와 같은 이유). */
      summaryDirty = false;
    };
  }


  /* ==========================================================================
     9. 가운데 + 오른쪽 컬럼: 녹음 달력
     ======================================================================= */

  function renderCalendarView(centerEl, rightEl, initYear, initMonth) {
    var todayD = new Date();
    var todayKey = todayD.getFullYear() + '-' + pad2(todayD.getMonth() + 1) + '-' + pad2(todayD.getDate());

    var viewYear = initYear || todayD.getFullYear();
    var viewMonth = initMonth || (todayD.getMonth() + 1);
    var selectedDate = null;
    var monthData = null;
    var cancelled = false;
    var requestToken = 0;

    function pad2(n) { return String(n).padStart(2, '0'); }

    function dateKey(y, m, d) { return y + '-' + pad2(m) + '-' + pad2(d); }
    function daysInMonth(y, m) { return new Date(y, m, 0).getDate(); }
    function firstWeekday(y, m) { return new Date(y, m - 1, 1).getDay(); }

    function formatDateHeading(dateStr) {
      var p = dateStr.split('-').map(Number);
      var d = new Date(p[0], p[1] - 1, p[2]);
      return p[0] + '.' + pad2(p[1]) + '.' + pad2(p[2]) + ' (' + DOW[d.getDay()] + ')';
    }

    function findDayInfo(dateStr) {
      var days = (monthData && monthData.days) || [];
      for (var i = 0; i < days.length; i++) { if (days[i].date === dateStr) return days[i]; }
      return null;
    }

    /* ---- 정적 셸 (한 번만 렌더링) ---- */
    centerEl.innerHTML =
      '<div class="col-center-scroll"><div class="cal-page view-fade">' +
        '<div class="cal-header-top">' +
          '<div>' +
            '<span class="page-eyebrow">CALENDAR</span>' +
            '<h1 class="page-title">녹음 달력</h1>' +
            '<p class="page-sub">날짜를 선택하면 그날 녹음한 회의를 확인할 수 있습니다.</p>' +
          '</div>' +
          '<button type="button" class="btn btn-ghost btn-icon info-toggle-btn" id="cal-info-toggle" title="이번 달 통계 보기" aria-label="이번 달 통계 보기">' + ICONS.users + '</button>' +
        '</div>' +

        '<div class="cal-nav">' +
          '<button type="button" class="cal-nav-btn" id="cal-prev" aria-label="이전 달">' + ICONS.back + '</button>' +
          '<span class="cal-nav-title" id="cal-nav-title"></span>' +
          '<button type="button" class="cal-nav-btn" id="cal-next" aria-label="다음 달">' + ICONS.chevronRight + '</button>' +
          '<button type="button" class="btn btn-subtle btn-sm" id="cal-today-btn" style="margin-left:auto">오늘</button>' +
        '</div>' +

        '<div class="card cal-grid-card">' +
          '<div class="cal-weekdays">' + DOW.map(function (d) { return '<span>' + d + '</span>'; }).join('') + '</div>' +
          '<div class="cal-grid" id="cal-grid"></div>' +
        '</div>' +

        '<div id="cal-empty-note-wrap"></div>' +

        '<div class="cal-day-detail" id="cal-day-detail"></div>' +
      '</div></div>';

    rightEl.innerHTML = '<div class="cal-right-loading text-muted text-sm">불러오는 중…</div>';

    var navTitleEl = centerEl.querySelector('#cal-nav-title');
    var gridEl = centerEl.querySelector('#cal-grid');
    var emptyNoteEl = centerEl.querySelector('#cal-empty-note-wrap');
    var dayDetailEl = centerEl.querySelector('#cal-day-detail');
    var infoToggleBtn = centerEl.querySelector('#cal-info-toggle');
    var prevBtn = centerEl.querySelector('#cal-prev');
    var nextBtn = centerEl.querySelector('#cal-next');
    var todayBtn = centerEl.querySelector('#cal-today-btn');

    /* ---- 달 이동 ---- */
    function goToMonth(y, m) {
      while (m < 1) { m += 12; y -= 1; }
      while (m > 12) { m -= 12; y += 1; }
      viewYear = y; viewMonth = m;
      selectedDate = null;
      loadMonth();
    }
    prevBtn.addEventListener('click', function () { goToMonth(viewYear, viewMonth - 1); });
    nextBtn.addEventListener('click', function () { goToMonth(viewYear, viewMonth + 1); });
    todayBtn.addEventListener('click', function () {
      viewYear = todayD.getFullYear();
      viewMonth = todayD.getMonth() + 1;
      selectedDate = null;
      loadMonth(function () { selectDate(todayKey, true); });
    });
    infoToggleBtn.addEventListener('click', function () { openDrawer(); });

    /* ---- 월간 그리드 렌더링 ---- */
    function renderGrid() {
      var map = {};
      (monthData.days || []).forEach(function (d) { map[d.date] = d; });
      var total = daysInMonth(viewYear, viewMonth);
      var lead = firstWeekday(viewYear, viewMonth);
      var cells = [];
      for (var i = 0; i < lead; i++) cells.push('<div class="cal-day cal-day--blank" aria-hidden="true"></div>');
      for (var day = 1; day <= total; day++) {
        var key = dateKey(viewYear, viewMonth, day);
        var info = map[key];
        var classes = ['cal-day'];
        if (key === todayKey) classes.push('is-today');
        if (key === selectedDate) classes.push('is-selected');
        var inner = '<span class="cal-day-num">' + day + '</span>';
        if (info && info.items && info.items.length) {
          classes.push('has-rec');
          if (info.count > 1) inner += '<span class="cal-day-count">' + info.count + '건</span>';
          var barBlocks = info.items.map(function (it) {
            var left = Math.max(0, Math.min(100, (it.start_minute / 1440) * 100));
            var width = Math.max(0, ((it.end_minute - it.start_minute) / 1440) * 100);
            return '<span class="cal-day-bar-block" style="left:' + left.toFixed(2) + '%;width:' + width.toFixed(2) + '%"></span>';
          }).join('');
          inner += '<div class="cal-day-bar">' + barBlocks + '</div>';
          var chipItems = info.items.slice(0, 2);
          var chipsHtml = chipItems.map(function (it) { return '<span class="cal-time-chip">' + esc(it.start_hm) + '</span>'; }).join('');
          if (info.items.length > 2) chipsHtml += '<span class="cal-time-chip-more">+' + (info.items.length - 2) + '</span>';
          inner += '<div class="cal-day-chips">' + chipsHtml + '</div>';
        }
        var label = info ? (key + ' 녹음 ' + info.count + '건') : (key + ' 녹음 없음');
        cells.push('<button type="button" class="' + classes.join(' ') + '" data-date="' + key + '" aria-label="' + esc(label) + '" aria-pressed="' + (key === selectedDate ? 'true' : 'false') + '">' + inner + '</button>');
      }
      var trailing = (7 - ((lead + total) % 7)) % 7;
      for (var t = 0; t < trailing; t++) cells.push('<div class="cal-day cal-day--blank" aria-hidden="true"></div>');
      gridEl.innerHTML = cells.join('');

      if (!monthData.days || !monthData.days.length) {
        emptyNoteEl.innerHTML = '<div class="cal-empty-note">' + ICONS.empty + '<span>이번 달에는 녹음된 회의가 없습니다.</span></div>';
      } else {
        emptyNoteEl.innerHTML = '';
      }
    }

    /* ---- 선택한 날짜: 24시간 타임라인 + 회의 카드 ---- */
    function renderDayDetail() {
      if (!selectedDate) {
        dayDetailEl.innerHTML = '<div class="cal-day-empty">달력에서 날짜를 선택하면 그날의 24시간 녹음 타임라인을 볼 수 있습니다.</div>';
        return;
      }
      var info = findDayInfo(selectedDate);
      var items = info ? info.items.slice().sort(function (a, b) { return a.start_minute - b.start_minute; }) : [];
      if (!items.length) {
        dayDetailEl.innerHTML =
          '<div class="cal-day-detail-head"><h2>' + esc(formatDateHeading(selectedDate)) + '</h2></div>' +
          '<div class="cal-day-empty">이 날짜에는 녹음된 회의가 없습니다.</div>';
        return;
      }
      var axisHtml = [0, 3, 6, 9, 12, 15, 18, 21, 24].map(function (h) { return '<span>' + h + '시</span>'; }).join('');
      var rowsHtml = items.map(function (it) {
        var left = Math.max(0, Math.min(100, (it.start_minute / 1440) * 100));
        var width = Math.max(0, ((it.end_minute - it.start_minute) / 1440) * 100);
        return (
          '<button type="button" class="cal-timeline-row" data-id="' + esc(it.meeting_id) + '" aria-label="' + esc(it.title || '제목 없음') + ' 회의 열기, ' + esc(it.start_hm) + '부터 ' + esc(it.end_hm) + '까지">' +
            '<div class="cal-timeline-track"><div class="cal-timeline-block" style="left:' + left.toFixed(2) + '%;width:' + width.toFixed(2) + '%"></div></div>' +
            '<div class="cal-timeline-row-label"><b>' + esc(it.title || '(제목 없음)') + '</b><span>' + esc(it.start_hm) + '~' + esc(it.end_hm) + '</span></div>' +
          '</button>'
        );
      }).join('');
      var totalDur = items.reduce(function (sum, it) { return sum + (it.duration_ms || 0); }, 0);
      var cardsHtml = items.map(function (it) {
        var chips = statusChipHtml(it.status) + (it.has_summary ? '<span class="chip chip-brand">요약</span>' : '');
        return (
          '<button type="button" class="cal-meeting-card" data-id="' + esc(it.meeting_id) + '">' +
            '<div class="cal-meeting-card-top">' +
              '<span class="cal-meeting-card-title">' + esc(it.title || '(제목 없음)') + '</span>' +
              '<span class="cal-meeting-card-time mono">' + esc(it.start_hm) + '~' + esc(it.end_hm) + '</span>' +
            '</div>' +
            '<div class="cal-meeting-card-chips">' + chips + '<span class="cal-meeting-card-dur mono">' + formatDuration(it.duration_ms) + '</span></div>' +
          '</button>'
        );
      }).join('');
      dayDetailEl.innerHTML =
        '<div class="cal-day-detail-head"><h2>' + esc(formatDateHeading(selectedDate)) + '</h2><span class="cal-day-detail-count mono">' + items.length + '건 · ' + formatDuration(totalDur) + '</span></div>' +
        '<div class="card cal-timeline"><div class="cal-timeline-axis">' + axisHtml + '</div><div class="cal-timeline-rows">' + rowsHtml + '</div></div>' +
        '<div class="cal-day-meetings">' + cardsHtml + '</div>';
    }

    /* ---- 오른쪽 컬럼: 이번 달 통계 + 선택한 날짜 요약 ---- */
    function renderRightPanel() {
      var days = monthData.days || [];
      var totalCount = monthData.total_count != null ? monthData.total_count : days.reduce(function (s, d) { return s + d.count; }, 0);
      var totalMs = days.reduce(function (s, d) { return s + (d.total_duration_ms || 0); }, 0);
      var html =
        '<div class="right-section-head"><span class="right-section-title">이번 달 통계</span></div>' +
        '<div class="cal-stats-grid">' +
          '<div class="cal-stat-card"><span class="cal-stat-label">총 녹음 건수</span><span class="cal-stat-value mono">' + totalCount + '건</span></div>' +
          '<div class="cal-stat-card"><span class="cal-stat-label">총 녹음 시간</span><span class="cal-stat-value mono">' + formatDuration(totalMs) + '</span></div>' +
          '<div class="cal-stat-card"><span class="cal-stat-label">녹음한 날짜 수</span><span class="cal-stat-value mono">' + days.length + '일</span></div>' +
        '</div>' +
        '<div class="right-section-head"><span class="right-section-title">선택한 날짜</span></div>';

      if (!selectedDate) {
        html += '<p class="text-muted text-sm">달력에서 날짜를 선택하면 그날 요약이 여기에 표시됩니다.</p>';
      } else {
        var info = findDayInfo(selectedDate);
        var items = info ? info.items.slice().sort(function (a, b) { return a.start_minute - b.start_minute; }) : [];
        var dayDur = items.reduce(function (s, it) { return s + (it.duration_ms || 0); }, 0);
        html +=
          '<div class="cal-day-summary-card">' +
            '<div class="cal-day-summary-date">' + esc(formatDateHeading(selectedDate)) + '</div>' +
            '<div class="cal-day-summary-count">' + (items.length ? (items.length + '건 · ' + formatDuration(dayDur)) : '녹음 없음') + '</div>' +
            (items.length ? ('<div class="cal-day-summary-list">' + items.map(function (it) {
              return '<button type="button" class="cal-day-summary-item" data-id="' + esc(it.meeting_id) + '"><span class="mono">' + esc(it.start_hm) + '</span><span>' + esc(it.title || '(제목 없음)') + '</span></button>';
            }).join('') + '</div>') : '') +
          '</div>';
      }
      rightEl.innerHTML = html;
    }

    /* ---- 날짜 선택 ---- */
    function selectDate(dateStr, silent) {
      selectedDate = dateStr;
      gridEl.querySelectorAll('.cal-day[data-date]').forEach(function (c) {
        var on = c.dataset.date === dateStr;
        c.classList.toggle('is-selected', on);
        c.setAttribute('aria-pressed', on ? 'true' : 'false');
      });
      renderDayDetail();
      renderRightPanel();
      if (!silent) dayDetailEl.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }

    /* ---- 월 데이터 로드 ---- */
    function loadMonth(onDone) {
      navTitleEl.textContent = viewYear + '년 ' + viewMonth + '월';
      gridEl.innerHTML = Array.from({ length: 35 }).map(function () {
        return '<div class="list-skeleton-row" style="height:74px;margin:0;border-radius:10px"></div>';
      }).join('');
      emptyNoteEl.innerHTML = '';
      dayDetailEl.innerHTML = '';
      rightEl.innerHTML = '<div class="cal-right-loading text-muted text-sm">불러오는 중…</div>';

      var myToken = ++requestToken;
      API.getCalendar({ year: viewYear, month: viewMonth }).then(function (res) {
        if (cancelled || myToken !== requestToken) return;
        monthData = res;
        var hash = '#/calendar/' + viewYear + '/' + viewMonth;
        if (location.hash !== hash) history.replaceState(null, '', hash);
        renderGrid();
        renderDayDetail();
        renderRightPanel();
        if (onDone) onDone();
      }).catch(function (err) {
        if (cancelled || myToken !== requestToken) return;
        gridEl.innerHTML = '';
        emptyNoteEl.innerHTML = emptyStateHtml('달력을 불러오지 못했습니다', err.message || '');
        rightEl.innerHTML = '<p class="text-muted text-sm">통계를 불러오지 못했습니다.</p>';
        toast(err.message || '달력을 불러오지 못했습니다.', 'error');
      });
    }

    /* ---- 클릭 위임 (날짜 셀 · 타임라인 행 · 회의 카드 · 요약 목록) ---- */
    function handleCalendarClick(e) {
      var dayCell = e.target.closest('.cal-day[data-date]');
      if (dayCell) { selectDate(dayCell.dataset.date); return; }
      var idEl = e.target.closest('[data-id]');
      if (idEl) { navigate('#/meetings/' + encodeURIComponent(idEl.dataset.id)); }
    }
    centerEl.addEventListener('click', handleCalendarClick);
    rightEl.addEventListener('click', handleCalendarClick);

    /* ---- 최초 로드: 이번 달이면 오늘 날짜가 있을 때 자동 선택 ---- */
    loadMonth(function () {
      if (!selectedDate && viewYear === todayD.getFullYear() && viewMonth === (todayD.getMonth() + 1) && findDayInfo(todayKey)) {
        selectDate(todayKey, true);
      }
    });

    return function cleanup() {
      cancelled = true;
      centerEl.removeEventListener('click', handleCalendarClick);
      rightEl.removeEventListener('click', handleCalendarClick);
    };
  }


  /* ==========================================================================
     10. 초기화
     ======================================================================= */

  document.addEventListener('DOMContentLoaded', function () {
    shellEl = document.getElementById('app-shell');
    colCenterEl = document.getElementById('col-center');
    colRightEl = document.getElementById('col-right');
    colRightContentEl = document.getElementById('col-right-content');
    drawerBackdropEl = document.getElementById('drawer-backdrop');
    var drawerCloseBtn = document.getElementById('drawer-close-btn');

    drawerBackdropEl.addEventListener('click', closeDrawer);
    drawerCloseBtn.addEventListener('click', closeDrawer);
    document.addEventListener('keydown', function (e) {
      if (e.key !== 'Escape') return;
      if (closeFabMenu(true)) return;   // 메뉴가 열려 있으면 그것만 닫는다
      /* ESC 는 사용자가 의도적으로 닫은 것이라 '봤다'로 친다(안 그러면 매 로드마다 다시 뜬다).
         반대로 라우트 이탈이나 '띄울 스텝이 없음'은 기록하지 않는다. */
      if (tourActive()) { endTour(true); return; }
      closeDrawer();
    });

    /* 해시 앵커(탭바·레일·rail-logo·폴더 행·마이 링크 등)는 기본 동작으로 이동하므로
       navigate() 를 지나지 않는다. 녹음 중일 때만 가로챈다 —
       평상시엔 즉시 return 해서 다른 위임 핸들러(C2·D·E2·F2)를 방해하지 않는다. */
    document.addEventListener('click', function (e) {
      if (!recordingActive) return;
      var a = e.target.closest && e.target.closest('a[href^="#/"]');
      if (!a) return;
      e.preventDefault();
      var href = a.getAttribute('href');
      confirmLeaveRecording().then(function (ok) {
        if (!ok) return;
        recordingActive = false;
        navigate(href);
      });
    });

    /* 사용자 설정을 부팅 시 1회 받아 새 회의 폼 프리필에 쓴다.
       await 하지 않는다 — /v1/me 가 느리거나 실패하면 앱 부팅 전체가 멈춘다.
       renderRoute() 는 동기라 첫 렌더 때는 아직 비어 있고, 그래서 promise 를 보관해
       각 뷰가 응답 후 한 번 더 프리필을 적용한다. */
    settingsReady = API.getMe().then(function (me) {
      userSettings = (me && me.settings) || {};
    }).catch(function () {
      userSettings = {};
    });

    initFabMenu();
    ListColumn.init(document.getElementById('col-list'));
    renderRoute();
    maybeStartTour();   // 최초 실행 코치마크(모바일·#/new·플래그 없음일 때만)
  });

  window.addEventListener('hashchange', renderRoute);

})();
