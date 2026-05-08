// ScenarioEditDrawer — 협업 시나리오 풀폼 편집 드로어 (HR_ADMIN+).
//
// 풀폼: trigger_keywords (chip) / situation / requesting_dept / my_actions
//      / hand_off_to / hand_off_items / deadline_info / related_sop_id / tips
//      / priority / scope_division (Phase 2) / lang (Phase 2)
// 액션: 저장 / Reset to default / 변경 이력 / 삭제

import { useEffect, useMemo, useState } from 'react';
import {
  createScenario,
  deleteScenario,
  resetScenario,
  updateScenario,
  type ScenarioItem,
} from '@api/admin_scenarios';
import type { DepartmentTreeResponse } from '@api/admin';

const SOP_OPTIONS = ['SOP-8D', 'SOP-ECN', 'SOP-PPAP', 'SOP-IATF', 'SOP-APQP', 'SOP-MSA', 'SOP-FMEA', 'SOP-SAFETY'];
const LANG_OPTIONS: { value: 'ko' | 'en'; label: string }[] = [
  { value: 'ko', label: '한국어' },
  { value: 'en', label: 'English' },
];

interface Props {
  mode: 'create' | 'edit';
  initial: ScenarioItem | null;
  tree: DepartmentTreeResponse | null;
  onClose: () => void;
  onSaved: (item: ScenarioItem) => void;
  onShowHistory?: (id: string) => void;
}

interface DraftState {
  scenario_id: string;
  trigger_keywords: string[];
  situation: string;
  requesting_dept: string;
  my_actions: string[];
  hand_off_to: string;
  hand_off_items: string[];
  deadline_info: string;
  related_sop_id: string;
  tips: string[];
  priority: number;
  scope_division: string;
  lang: string;
  is_active: boolean;
}

const EMPTY_DRAFT: DraftState = {
  scenario_id: '',
  trigger_keywords: [],
  situation: '',
  requesting_dept: '',
  my_actions: [],
  hand_off_to: '',
  hand_off_items: [],
  deadline_info: '',
  related_sop_id: '',
  tips: [],
  priority: 100,
  scope_division: '',
  lang: 'ko',
  is_active: true,
};

function ListEditor({
  label,
  values,
  onChange,
}: {
  label: string;
  values: string[];
  onChange: (next: string[]) => void;
}) {
  const [draft, setDraft] = useState('');
  const add = () => {
    const v = draft.trim();
    if (!v) return;
    onChange([...values, v]);
    setDraft('');
  };
  return (
    <div className="lg-field grow">
      <label>{label}</label>
      <div style={{ display: 'flex', gap: 6, marginBottom: 6 }}>
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault();
              add();
            }
          }}
          placeholder="추가 후 Enter"
          style={{ flex: 1 }}
        />
        <button type="button" className="lg-btn ghost sm" onClick={add}>
          추가
        </button>
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
        {values.map((v, i) => (
          <span
            key={`${v}-${i}`}
            className="lg-chip"
            style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}
          >
            {v}
            <button
              type="button"
              onClick={() => onChange(values.filter((_, idx) => idx !== i))}
              style={{
                background: 'transparent',
                border: 0,
                color: 'var(--hud-text-dim)',
                cursor: 'pointer',
                padding: 0,
              }}
              aria-label="삭제"
            >
              ×
            </button>
          </span>
        ))}
        {values.length === 0 && (
          <span className="dim" style={{ fontSize: 12 }}>(비어있음)</span>
        )}
      </div>
    </div>
  );
}

export function ScenarioEditDrawer({ mode, initial, tree, onClose, onSaved, onShowHistory }: Props) {
  const [draft, setDraft] = useState<DraftState>(EMPTY_DRAFT);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string>('');

  useEffect(() => {
    if (initial) {
      setDraft({
        scenario_id: initial.scenario_id,
        trigger_keywords: [...initial.trigger_keywords],
        situation: initial.situation,
        requesting_dept: initial.requesting_dept,
        my_actions: [...initial.my_actions],
        hand_off_to: initial.hand_off_to,
        hand_off_items: [...initial.hand_off_items],
        deadline_info: initial.deadline_info,
        related_sop_id: initial.related_sop_id,
        tips: [...initial.tips],
        priority: initial.priority,
        scope_division: initial.scope_division,
        lang: initial.lang,
        is_active: initial.is_active,
      });
    } else {
      setDraft({ ...EMPTY_DRAFT });
    }
    setMsg('');
  }, [initial, mode]);

  const allDepartments = useMemo(
    () => tree?.divisions.flatMap((d) => d.departments.map((x) => x.name)) ?? [],
    [tree],
  );
  const allDivisions = useMemo(() => tree?.divisions.map((d) => d.division) ?? [], [tree]);

  const isSeed = Boolean(initial?.is_system_default);

  const handleSave = async () => {
    setBusy(true);
    setMsg('');
    try {
      let saved: ScenarioItem;
      if (mode === 'create') {
        if (!draft.scenario_id.trim()) {
          throw new Error('scenario_id 가 필요합니다.');
        }
        saved = await createScenario(draft);
      } else {
        const { scenario_id: _id, ...patch } = draft;
        saved = await updateScenario(draft.scenario_id, patch);
      }
      setMsg('저장 완료');
      onSaved(saved);
    } catch (e) {
      setMsg(`저장 실패: ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  };

  const handleReset = async () => {
    if (!initial) return;
    if (!confirm(`${initial.scenario_id} 를 시스템 기본값으로 복구합니다. 계속할까요?`)) return;
    setBusy(true);
    setMsg('');
    try {
      const saved = await resetScenario(initial.scenario_id);
      setMsg('기본값 복구 완료');
      onSaved(saved);
    } catch (e) {
      setMsg(`복구 실패: ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async () => {
    if (!initial) return;
    const label = isSeed ? '비활성화' : '영구 삭제';
    if (!confirm(`${initial.scenario_id} 를 ${label} 합니다. 계속할까요?`)) return;
    setBusy(true);
    setMsg('');
    try {
      await deleteScenario(initial.scenario_id);
      setMsg(`${label} 완료`);
      onSaved({ ...initial, is_active: false });
    } catch (e) {
      setMsg(`${label} 실패: ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-label="협업 시나리오 편집"
      style={{
        position: 'fixed',
        top: 0,
        right: 0,
        bottom: 0,
        width: 'min(560px, 100vw)',
        zIndex: 60,
        background: 'color-mix(in oklab, var(--hud-surface) 92%, transparent)',
        backdropFilter: 'blur(20px) saturate(140%)',
        borderLeft: '1px solid color-mix(in oklab, var(--hud-text) 14%, transparent)',
        boxShadow: '-12px 0 40px rgba(0,0,0,0.3)',
        overflowY: 'auto',
        padding: '22px 22px 32px',
      }}
    >
      <div className="lg-card-h">
        <div>
          <div className="lg-pill">
            {mode === 'create' ? 'NEW SCENARIO' : `SCENARIO · ${initial?.scenario_id ?? ''}`}
            {isSeed && ' · 시스템 시드'}
          </div>
          <div style={{ fontSize: 18, fontWeight: 600, marginTop: 6 }}>
            {mode === 'create' ? '신규 협업 시나리오' : draft.situation || initial?.situation}
          </div>
        </div>
        <button className="lg-btn ghost sm" onClick={onClose} type="button">
          닫기
        </button>
      </div>

      <div className="lg-filter-grid" style={{ gridTemplateColumns: '1fr 1fr', marginTop: 8 }}>
        <div className="lg-field">
          <label>scenario_id</label>
          <input
            value={draft.scenario_id}
            onChange={(e) => setDraft({ ...draft, scenario_id: e.target.value })}
            disabled={mode === 'edit'}
            placeholder="COLLAB-CUSTOM-1"
          />
        </div>
        <div className="lg-field">
          <label>요청 부서</label>
          <select
            value={draft.requesting_dept}
            onChange={(e) => setDraft({ ...draft, requesting_dept: e.target.value })}
          >
            <option value="">(미지정)</option>
            {allDepartments.map((d) => (
              <option key={d}>{d}</option>
            ))}
          </select>
        </div>

        <div className="lg-field grow">
          <label>상황 (situation)</label>
          <input
            value={draft.situation}
            onChange={(e) => setDraft({ ...draft, situation: e.target.value })}
            placeholder="완성차 클레임 접수 → 8D 자료 요청"
          />
        </div>

        <div className="lg-field grow">
          <label>넘길 곳 (hand_off_to)</label>
          <input
            value={draft.hand_off_to}
            onChange={(e) => setDraft({ ...draft, hand_off_to: e.target.value })}
            placeholder="품질보증팀 8D 담당자"
          />
        </div>

        <div className="lg-field grow">
          <label>기한 (deadline_info)</label>
          <input
            value={draft.deadline_info}
            onChange={(e) => setDraft({ ...draft, deadline_info: e.target.value })}
          />
        </div>

        <div className="lg-field">
          <label>관련 SOP</label>
          <select
            value={draft.related_sop_id}
            onChange={(e) => setDraft({ ...draft, related_sop_id: e.target.value })}
          >
            <option value="">(없음)</option>
            {SOP_OPTIONS.map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        </div>

        <div className="lg-field">
          <label>우선순위 (낮을수록 우선)</label>
          <input
            type="number"
            value={draft.priority}
            onChange={(e) => setDraft({ ...draft, priority: Number(e.target.value) || 100 })}
          />
        </div>

        <div className="lg-field">
          <label>본부 한정 (Phase 2)</label>
          <select
            value={draft.scope_division}
            onChange={(e) => setDraft({ ...draft, scope_division: e.target.value })}
          >
            <option value="">전사</option>
            {allDivisions.map((d) => (
              <option key={d}>{d}</option>
            ))}
          </select>
        </div>

        <div className="lg-field">
          <label>언어 (Phase 2)</label>
          <select
            value={draft.lang}
            onChange={(e) => setDraft({ ...draft, lang: e.target.value })}
          >
            {LANG_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>

        <div className="lg-field">
          <label>활성 상태</label>
          <select
            value={draft.is_active ? '1' : '0'}
            onChange={(e) => setDraft({ ...draft, is_active: e.target.value === '1' })}
          >
            <option value="1">활성</option>
            <option value="0">비활성</option>
          </select>
        </div>
      </div>

      <div style={{ marginTop: 14, display: 'flex', flexDirection: 'column', gap: 12 }}>
        <ListEditor
          label="트리거 키워드 (매칭 키워드)"
          values={draft.trigger_keywords}
          onChange={(v) => setDraft({ ...draft, trigger_keywords: v })}
        />
        <ListEditor
          label="내가 준비할 것 (my_actions)"
          values={draft.my_actions}
          onChange={(v) => setDraft({ ...draft, my_actions: v })}
        />
        <ListEditor
          label="넘길 산출물 (hand_off_items)"
          values={draft.hand_off_items}
          onChange={(v) => setDraft({ ...draft, hand_off_items: v })}
        />
        <ListEditor
          label="신입을 위한 팁 (tips)"
          values={draft.tips}
          onChange={(v) => setDraft({ ...draft, tips: v })}
        />
      </div>

      <div style={{ marginTop: 18, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <button className="lg-btn" disabled={busy} onClick={handleSave} type="button">
          {mode === 'create' ? '추가' : '저장'}
        </button>
        {mode === 'edit' && initial?.is_system_default && (
          <button className="lg-btn ghost" disabled={busy} onClick={handleReset} type="button">
            기본값 복구
          </button>
        )}
        {mode === 'edit' && onShowHistory && (
          <button
            className="lg-btn ghost"
            disabled={busy}
            onClick={() => onShowHistory(draft.scenario_id)}
            type="button"
          >
            변경 이력
          </button>
        )}
        {mode === 'edit' && (
          <button
            className="lg-btn ghost"
            disabled={busy}
            onClick={handleDelete}
            type="button"
            style={{
              borderColor: 'color-mix(in oklab, #C0392B 50%, transparent)',
              color: '#C0392B',
            }}
          >
            {isSeed ? '비활성화' : '영구 삭제'}
          </button>
        )}
      </div>

      {msg && (
        <div
          className={msg.includes('실패') ? 'lg-state-pill crit' : 'lg-state-pill ok'}
          style={{ display: 'inline-block', marginTop: 14 }}
        >
          {msg}
        </div>
      )}
    </div>
  );
}
