// P4 D15 — 신입 학습경로 panel.
// 신입 본인이 자기 진도 + 주차별 변경 + 퀴즈 응시 + 사수 평가 요청.
// 디스클레이머: AI 자문은 참고용 — 최종 판단은 담당자.

import { useEffect, useState } from 'react';
import {
 fetchLearningQuizPreview,
 fetchMyLearning,
 requestLearningReview,
 takeLearningQuiz,
 type LearningPathDetail,
 type LearningProgressItem } from '@api/compliance';

interface QuizUiState {
 // P4.1 §6 — preview 먼저, 사용자가 선택 후 submit
 question?: string;
 choices?: string[];
 selected?: number | null;
 feedback?: string;
}

export function LearningPathPanel() {
 const [paths, setPaths] = useState<LearningPathDetail[]>([]);
 const [busy, setBusy] = useState(false);
 const [error, setError] = useState<string | null>(null);
 const [quizState, setQuizState] = useState<Record<number, QuizUiState>>({});

 const reload = () => {
 setBusy(true);
 fetchMyLearning()
 .then((r) => setPaths(r.paths))
 .catch((e) => setError((e as Error).message))
 .finally(() => setBusy(false));
 };

 useEffect(() => {
 reload();
 }, []);

 // P4.1 §6 — preview 먼저: question/choices 받아 사용자 선택 대기. answer_index 미반환.
 const startQuiz = async (prog: LearningProgressItem) => {
 try {
 const preview = await fetchLearningQuizPreview(prog.id);
 setQuizState((s) => ({
 ...s,
 [prog.id]: {
 question: preview.question,
 choices: preview.choices,
 selected: null,
 feedback: undefined } }));
 } catch (e) {
 setError((e as Error).message);
 }
 };

 const selectChoice = (progId: number, idx: number) => {
 setQuizState((s) => ({
 ...s,
 [progId]: { ...s[progId], selected: idx, feedback: undefined } }));
 };

 const submitQuiz = async (prog: LearningProgressItem) => {
 const qs = quizState[prog.id];
 if (!qs || qs.selected == null) return;
 try {
 const out = await takeLearningQuiz(prog.id, qs.selected);
 setQuizState((s) => ({
 ...s,
 [prog.id]: {
 ...s[prog.id],
 feedback: out.correct
 ? `✓ 정답 (점수 ${out.score})`
 : `✗ 오답 — 정답은 보기 ${out.answer_index + 1}번` } }));
 reload();
 } catch (e) {
 setError((e as Error).message);
 }
 };

 const askReview = async (prog: LearningProgressItem) => {
 try {
 await requestLearningReview(prog.id);
 setError(null);
 } catch (e) {
 setError((e as Error).message);
 }
 };

 if (busy && paths.length === 0) {
 return <div className="lg-card">불러오는 중…</div>;
 }
 if (paths.length === 0) {
 return (
 <div className="lg-card">
 <div className="lg-pill">P4 D15 · LEARNING PATH</div>
 <p style={{ marginTop: 8 }}>아직 할당된 학습 경로가 없습니다. 사수에게 큐레이션을 요청하세요.</p>
 </div>
 );
 }

 return (
 <>
 {error && (
 <div className="lg-card">
 <div className="lg-state-pill crit">{error}</div>
 </div>
 )}
 {paths.map((p) => (
 <div key={p.id} className="lg-card" style={{ marginBottom: 12 }}>
 <div className="lg-card-h">
 <div>
 <div className="lg-pill">LEARNING PATH #{p.id}</div>
 <h3 style={{ marginTop: 6 }}>{p.name}</h3>
 <div style={{ fontSize: 12, color: 'var(--hud-text-dim)' }}>
 사수: {p.owner_employee_id} · {p.week_count}주차 · {p.status}
 </div>
 </div>
 </div>
 <p style={{ fontSize: 12, color: 'var(--hud-text-dim)' }}>
 AI 자문은 참고용 — 최종 판단은 담당자입니다.
 </p>

 {p.curriculum.map((week) => {
 const weekProgress = p.progress.filter((pr) => pr.week === week.week);
 const done = weekProgress.filter(
 (pr) => pr.mentor_review === 'pass' || pr.mentor_review === 'pass_with_comment',
 ).length;
 return (
 <div key={week.week} style={{ marginTop: 14, paddingTop: 10, borderTop: '1px solid var(--hud-line)' }}>
 <strong>Week {week.week}</strong>
 <span style={{ fontSize: 12, color: 'var(--hud-text-dim)', marginLeft: 8 }}>
 ({done}/{weekProgress.length} 완료)
 </span>
 <ul style={{ listStyle: 'none', padding: 0, marginTop: 6 }}>
 {weekProgress.map((pr) => {
 const qs = quizState[pr.id] ?? {};
 return (
 <li
 key={pr.id}
 style={{
 padding: 8,
 marginBottom: 4,
 borderRadius: 4,
 background: 'var(--hud-surface)' }}
 >
 <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
 <span>change #{pr.change_id}</span>
 <span style={{ fontSize: 11, color: 'var(--hud-text-dim)' }}>
 점수 {pr.quiz_score >= 0 ? pr.quiz_score : '-'} · 시도 {pr.quiz_attempts} · {pr.mentor_review}
 </span>
 </div>
 {qs.question && (
 <div style={{ fontSize: 12, marginTop: 6 }}>
 <div>Q. {qs.question}</div>
 <ul style={{ listStyle: 'none', padding: 0, margin: '6px 0' }}>
 {(qs.choices ?? []).map((ch, idx) => (
 <li key={idx} style={{ marginBottom: 3 }}>
 <label>
 <input
 type="radio"
 name={`quiz-${pr.id}`}
 checked={qs.selected === idx}
 onChange={() => selectChoice(pr.id, idx)}
 disabled={busy || !!qs.feedback}
 />{' '}
 {idx + 1}. {ch}
 </label>
 </li>
 ))}
 </ul>
 {qs.feedback && (
 <div style={{ marginTop: 4 }}>{qs.feedback}</div>
 )}
 </div>
 )}
 <div style={{ marginTop: 6, display: 'flex', gap: 6 }}>
 {!qs.question && (
 <button
 type="button"
 className="lg-btn"
 onClick={() => startQuiz(pr)}
 disabled={busy}
 >
 퀴즈 응시
 </button>
 )}
 {qs.question && !qs.feedback && (
 <button
 type="button"
 className="lg-btn primary"
 onClick={() => submitQuiz(pr)}
 disabled={busy || qs.selected == null}
 >
 ✓ 제출
 </button>
 )}
 {pr.quiz_score >= 0 && pr.mentor_review === 'pending' && (
 <button
 type="button"
 className="lg-btn primary"
 onClick={() => askReview(pr)}
 disabled={busy}
 >
 사수에게 평가 요청
 </button>
 )}
 </div>
 </li>
 );
 })}
 </ul>
 </div>
 );
 })}
 </div>
 ))}
 </>
 );
}
