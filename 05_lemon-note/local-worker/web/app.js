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
    calendar: '<svg width="17" height="17" viewBox="0 0 19 19" fill="none"><rect x="2.5" y="4" width="14" height="12.5" rx="2.3" stroke="currentColor" stroke-width="1.5"/><path d="M2.5 7.8h14" stroke="currentColor" stroke-width="1.5"/><path d="M6.3 2.2v3M12.7 2.2v3" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><rect x="5.6" y="10.1" width="2.7" height="2.7" rx="0.6" fill="currentColor"/></svg>'
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
    return function () {
      var args = arguments;
      clearTimeout(t);
      t = setTimeout(function () { fn.apply(null, args); }, wait);
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

  function highlightMatch(text, q) {
    var escText = esc(text);
    if (!q) return escText;
    var escQ = esc(q).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    if (!escQ) return escText;
    try {
      return escText.replace(new RegExp('(' + escQ + ')', 'ig'), '<mark>$1</mark>');
    } catch (e) {
      return escText;
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

      function onOk() { dlg.returnValue = 'ok'; dlg.close(); }
      function onCancel() { dlg.returnValue = 'cancel'; dlg.close(); }
      function onClose() {
        okBtn.removeEventListener('click', onOk);
        cancelBtn.removeEventListener('click', onCancel);
        dlg.removeEventListener('close', onClose);
        resolve(dlg.returnValue === 'ok');
      }
      okBtn.addEventListener('click', onOk);
      cancelBtn.addEventListener('click', onCancel);
      dlg.addEventListener('close', onClose);
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

  function ApiError(message, code, status) {
    var err = new Error(message);
    err.code = code;
    err.status = status;
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
            res.status
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
    if (parts[0] === 'folders') return { name: 'folders' };
    if (parts[0] === 'me') return { name: 'me' };
    return { name: 'new' };
  }

  function navigate(hash) {
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
    } else if (route.name === 'list') {
      document.title = '홈 — 회의녹음챗';
      renderCenterEmpty(colCenterEl);
      renderRightTips(colRightContentEl, 'list');
    } else if (route.name === 'folders') {
      document.title = '폴더 — 회의녹음챗';
      renderFolderPlaceholder(colCenterEl);
      renderRightTips(colRightContentEl, 'list');
    } else if (route.name === 'me') {
      document.title = '마이 — 회의녹음챗';
      renderMyPagePlaceholder(colCenterEl);
      renderRightTips(colRightContentEl, 'list');
    } else if (route.name === 'calendar') {
      document.title = '녹음 달력 — 회의녹음챗';
      currentCleanup = renderCalendarView(colCenterEl, colRightContentEl, route.year, route.month);
    } else {
      document.title = '회의 상세 — 회의녹음챗';
      currentCleanup = renderMeetingDetailView(colCenterEl, colRightContentEl, route.meetingId, route.tab);
    }
  }


  /* ==========================================================================
     5. 회의 목록 컬럼 (상시 마운트 — 채팅 앱의 대화 목록처럼 항상 노출)
     ======================================================================= */

  var ListColumn = (function () {
    var scrollEl, searchInput, filterSelect, loadMoreWrap, loadMoreBtn, countEl;
    var items = [];
    var nextCursor = null;
    var lastQuery = '';   // 검색 결과 스니펫의 강조에 쓴다(itemHtml 이 fetchList 보다 먼저 정의돼 있어 별도 보관)
    var activeId = null;

    var STATUS_FILTER_OPTIONS = [
      ['', '전체 상태'],
      ['uploaded', '업로드됨'],
      ['normalizing_audio', '정규화 중'],
      ['transcribing', '전사 중'],
      ['summarizing', '요약 생성 중'],
      ['ready_for_review', '검토 대기'],
      ['failed', '실패']
    ];

    function itemChipsHtml(m) {
      var html = statusChipHtml(m.status);
      if (m.has_summary) html += '<span class="chip chip-brand">요약</span>';
      if (m.shared_count > 0) html += '<span class="chip chip-gray">공유 ' + m.shared_count + '</span>';
      return html;
    }

    function itemHtml(m) {
      var title = m.title || '(제목 없음)';
      var col = colorFromString(m.meeting_id);
      return (
        '<div class="list-item' + (m.meeting_id === activeId ? ' is-active' : '') + '" data-id="' + esc(m.meeting_id) + '" tabindex="0">' +
          '<div class="list-item-avatar" style="background:' + col.bg + ';color:' + col.fg + '">' + esc(title.charAt(0) || '회') + '</div>' +
          '<div class="list-item-main">' +
            '<div class="list-item-top"><span class="list-item-title">' + esc(title) + '</span><span class="list-item-time mono">' + esc(shortDate(m.recorded_at)) + '</span></div>' +
            '<div class="list-item-sub mono">' + esc(formatDateTime(m.recorded_at, { dateOnly: true })) + ' · ' + esc(formatDuration(m.duration_ms)) + '</div>' +
            '<div class="list-item-chips">' + itemChipsHtml(m) + '</div>' +
            // 검색 중일 때만: 왜 이 회의가 결과에 떴는지 스니펫과 출처로 보여준다.
            ((m.matches && m.matches.length)
              ? '<div class="match-list">' + m.matches.map(function (mt) {
                  return '<div class="match-row">' +
                    '<span class="match-src match-src--' + esc(mt.source) + '">' + esc(mt.label) + '</span>' +
                    (mt.start_ms != null
                      ? '<span class="match-time mono">' + esc(formatDuration(mt.start_ms)) + '</span>' : '') +
                    '<span class="match-text">' + highlightMatch(mt.text, lastQuery) + '</span>' +
                  '</div>';
                }).join('') + '</div>'
              : '') +
          '</div>' +
          '<button type="button" class="list-item-delete" data-action="delete" title="삭제" aria-label="회의 삭제">' + ICONS.trash + '</button>' +
        '</div>'
      );
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
          : emptyStateHtml('아직 등록된 회의가 없습니다', '첫 회의를 녹음하거나 파일을 업로드해보세요.', '<a href="#/new" class="btn btn-primary btn-sm">새 회의 시작하기</a>');
        return;
      }
      scrollEl.innerHTML = items.map(itemHtml).join('');
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
      API.listMeetings(params).then(function (res) {
        items = reset ? (res.items || []) : items.concat(res.items || []);
        nextCursor = res.next_cursor || null;
        loadMoreWrap.style.display = nextCursor ? '' : 'none';
        renderItems(false);
      }).catch(function (err) {
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
          '<button type="button" class="list-compose-btn" id="lc-compose" title="새 회의" aria-label="새 회의">' + ICONS.plus + '</button>' +
        '</div>' +
        '<div class="list-toolbar">' +
          '<div class="list-search-wrap">' + ICONS.search + '<input type="text" class="input" id="lc-search" placeholder="제목 · 전사 · 요약 전체 검색" /></div>' +
          '<select class="select list-filter-select" id="lc-filter">' +
            STATUS_FILTER_OPTIONS.map(function (o) { return '<option value="' + esc(o[0]) + '">' + esc(o[1]) + '</option>'; }).join('') +
          '</select>' +
        '</div>' +
        '<div class="list-scroll" id="lc-scroll"></div>' +
        '<div class="list-load-more" id="lc-load-more" style="display:none"><button type="button" class="btn btn-ghost btn-sm" id="lc-load-more-btn">더 보기</button></div>';

      scrollEl = containerEl.querySelector('#lc-scroll');
      searchInput = containerEl.querySelector('#lc-search');
      filterSelect = containerEl.querySelector('#lc-filter');
      loadMoreWrap = containerEl.querySelector('#lc-load-more');
      loadMoreBtn = containerEl.querySelector('#lc-load-more-btn');
      countEl = containerEl.querySelector('#lc-count');

      containerEl.querySelector('#lc-compose').addEventListener('click', function () { navigate('#/new'); });

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
      filterSelect.addEventListener('change', function () { fetchList(true); });
      loadMoreBtn.addEventListener('click', function () { fetchList(false); });

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
              resolve({ storage_path: pre.storage_path, meeting_id: pre.meeting_id });
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
        ListColumn.refresh(true);
        startPolling(res.job_id, res.meeting_id);
      }).catch(function (err) {
        toast(err.message || '업로드에 실패했습니다.', 'error');
        uploadBtn.disabled = false;
        resetBtn.disabled = false;
        uploadBtn.textContent = '업로드';
      });
    }

    /* ---- 처리 상태 폴링 & 스테퍼 ---- */
    function startPolling(jobId, meetingId) {
      formWrap.style.display = 'none';
      stepperWrap.style.display = '';
      renderStepper({ status: 'uploaded', progress: 0, current_stage: null });
      pollAttempts = 0;
      poll();
      function poll() {
        pollAttempts++;
        API.getJob(jobId).then(function (job) {
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

  /* 폴더·마이 플레이스홀더 — 서브프로젝트 C·E 에서 실제 기능으로 교체된다. */
  function renderFolderPlaceholder(centerEl) {
    centerEl.innerHTML =
      '<div class="placeholder-page">' +
        '<div class="placeholder-icon"><svg width="34" height="34" viewBox="0 0 20 20" fill="none" aria-hidden="true"><path d="M2.5 6A1.5 1.5 0 014 4.5h3l1.6 2h5.9A1.5 1.5 0 0116 8v6.5a1.5 1.5 0 01-1.5 1.5h-9A1.5 1.5 0 014 14.5V6z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/></svg></div>' +
        '<h2 class="placeholder-title">폴더</h2>' +
        '<p class="placeholder-desc">전체 노트 · 기본 폴더 · 공유받은/공유한 노트 · 휴지통을 여기서 관리할 수 있게 준비하고 있어요.</p>' +
        '<span class="chip chip-gray">곧 제공</span>' +
      '</div>';
  }

  function renderMyPagePlaceholder(centerEl) {
    centerEl.innerHTML =
      '<div class="placeholder-page">' +
        '<div class="mypage-profile">' +
          '<div class="mypage-avatar">회</div>' +
          '<div class="mypage-id"><div class="mypage-name">회의녹음챗</div><div class="mypage-mail mono">demo@local</div></div>' +
        '</div>' +
        '<p class="placeholder-desc">프로필 · 사용량 · 인식 언어 · 자주 쓰는 단어 · 관심 분야 등 설정을 여기서 제공할 예정이에요.</p>' +
        '<span class="chip chip-gray">곧 제공</span>' +
      '</div>';
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
    var sideMode = { twoSpeaker: false, order: [] };
    var detailClickHandler = null;
    var detailFieldHandler = null;

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
            '<button type="button" class="btn btn-ghost btn-icon" id="md-delete-btn" title="삭제" aria-label="회의 삭제">' + ICONS.trash + '</button>' +
          '</div>' +
        '</div>' +

        '<div class="msg-list-wrap">' +
          '<div class="transcript-search-row">' +
            '<div class="search-wrap">' + ICONS.search + '<input type="text" class="input" id="md-transcript-search" placeholder="발화 내용 또는 화자 검색" /></div>' +
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
          if (currentId && transcriptListEl) {
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

      function refreshShareList(freshUrl) {
        API.listShareLinks(meetingId).then(function (res) {
          renderShareList((res && res.items) || [], freshUrl);
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

      function renderTranscriptTab() {
        if (!segmentsState.length) {
          transcriptListEl.innerHTML = emptyStateHtml('전사 내용이 없습니다', '이 회의에는 아직 전사된 발화가 없습니다.');
          transcriptCountEl.textContent = '';
          return;
        }
        transcriptListEl.innerHTML = segmentsState.map(function (s) { return segmentRowHtml(s, ''); }).join('');
        transcriptCountEl.textContent = segmentsState.length + '개 발화';
        restoreHighlight();
      }

      function applyTranscriptSearch() {
        var q = (transcriptSearchInput.value || '').trim().toLowerCase();
        transcriptQuery = q;
        if (!segmentsState.length) return;
        if (!q) { renderTranscriptTab(); return; }
        var filtered = segmentsState.filter(function (seg) {
          var name = (seg.speaker_name || seg.speaker_label || '').toLowerCase();
          var text = ((seg.corrected_text || seg.text) || '').toLowerCase();
          return name.indexOf(q) !== -1 || text.indexOf(q) !== -1;
        });
        transcriptListEl.innerHTML = filtered.length
          ? filtered.map(function (s) { return segmentRowHtml(s, q); }).join('')
          : emptyStateHtml('', '검색 결과가 없습니다.');
        transcriptCountEl.textContent = filtered.length + ' / ' + segmentsState.length + '개 발화';
        restoreHighlight();
      }
      transcriptSearchInput.addEventListener('input', debounce(applyTranscriptSearch, 200));

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

      function toggleBookmark(seg) {
        var next = !seg.bookmarked;
        seg.bookmarked = next;
        applyTranscriptSearch();
        API.updateSegment(meetingId, seg.segment_id, { bookmarked: next }).catch(function (err) {
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
      function markDirty() {
        dirty = true;
        [summarySaveStatus, todoSaveStatus, calSaveStatus].forEach(function (el) {
          if (!el) return;
          el.classList.add('is-dirty');
          el.innerHTML = '<span class="dot"></span>저장되지 않은 변경사항';
        });
      }
      function markClean() {
        dirty = false;
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
          calendar_candidates: summaryState.calendar_candidates
        };
        [saveBtn1, saveBtn2, saveBtn3].forEach(function (b) { if (b) b.disabled = true; });
        API.updateSummary(meetingId, payload).then(function (res) {
          summaryState.summary_version_id = res.summary_version_id;
          summaryState.version = res.version;
          summaryState.source = res.source;
          updateSummaryVersionChip();
          markClean();
          ListColumn.refresh(true);
          toast('요약이 저장되었습니다. (v' + res.version + ')', 'success');
        }).catch(function (err) {
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
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') closeDrawer(); });

    ListColumn.init(document.getElementById('col-list'));
    renderRoute();
  });

  window.addEventListener('hashchange', renderRoute);

})();
