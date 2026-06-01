// HWP/HWPX/DOCX/PDF 다운로드용 Markdown 빌더.
// DownloadActions content prop 으로 전달된다.

import type {
  ErrResultDisplay,
  InspectionRow,
  MaintCostDisplay,
  MarkovBranchDisplay,
  MoldDisplay,
  ProcessHealthDisplay,
} from './types';

export function buildInspectionMarkdown(rows: InspectionRow[]): string {
  const lines: string[] = ['# 점검 체크리스트 (9 템플릿)', ''];
  lines.push(`총 ${rows.length}건 — 3장비(프레스/용접/CNC) × 3주기(일간/주간/월간)`, '');
  lines.push('| 장비 | 주기 | 최근 점검 | 완료율 | 미달 항목 |');
  lines.push('|---|---|---|---:|---|');
  for (const r of rows) {
    lines.push(`| ${r.eq} | ${r.cycle} | ${r.date} | ${r.rate}% | ${r.miss} |`);
  }
  return lines.join('\n');
}

export function buildMtbfMarkdown(items: MaintCostDisplay[], machinesAttention?: number): string {
  const lines: string[] = ['# MTBF 예측 정비 보고서', ''];
  if (machinesAttention !== undefined) lines.push(`점검 필요 설비: **${machinesAttention}대**`, '');
  lines.push('## 수리 비용 TOP 5', '');
  lines.push('| 설비 | 누적 비용 (만원) | 건수 | 다음 정비 |');
  lines.push('|---|---:|---:|---|');
  for (const m of items) {
    lines.push(`| ${m.eq} | ${m.cost.toLocaleString()} | ${m.jobs} | ${m.next} |`);
  }
  return lines.join('\n');
}

export function buildMoldMarkdown(molds: MoldDisplay[], total: number): string {
  const lines: string[] = ['# XGBoost 금형 잔여 수명 보고서', ''];
  lines.push(`표시 ${molds.length}/${total}기`, '');
  lines.push('| 금형 ID | 부품 | 누적 (k) | 최대 (k) | 사용률 | 잔여 (k) | 리스크 |');
  lines.push('|---|---|---:|---:|---:|---:|---|');
  for (const m of molds) {
    const pct = ((m.shots / m.max) * 100).toFixed(0);
    const rem = ((m.max - m.shots) / 1000).toFixed(0);
    lines.push(`| ${m.id} | ${m.part} | ${(m.shots / 1000).toFixed(0)} | ${(m.max / 1000).toFixed(0)} | ${pct}% | ${rem} | ${m.risk} |`);
  }
  return lines.join('\n');
}

export function buildSpcMarkdown(processes: ProcessHealthDisplay[], chartProcessName?: string): string {
  const lines: string[] = ['# SPC · Nelson 8 Rules 위반 보고서', ''];
  lines.push(`대상 공정: ${chartProcessName ?? '5공정 (CCH/OBC/범퍼빔/도어/볼시트)'}`, '');
  lines.push('## 5공정 건강 카드', '');
  lines.push('| 공정 | 상태 | Cpk | 위반 건수 | 위반 Rule |');
  lines.push('|---|---|---:|---:|---|');
  for (const p of processes) {
    lines.push(`| ${p.name} | ${p.state.toUpperCase()} | ${p.cpk.toFixed(2)} | ${p.viol} | ${p.rules.length ? p.rules.join(' · ') : '—'} |`);
  }
  return lines.join('\n');
}

export function buildErrSearchMarkdown(
  query: string,
  equipFilter: string,
  symptom: string,
  results: ErrResultDisplay[],
  markov: MarkovBranchDisplay[],
): string {
  const lines: string[] = ['# 에러 검색 결과 보고서 (TF-IDF + Markov)', ''];
  lines.push(`- 입력 질의: "${query}"`);
  lines.push(`- 장비: ${equipFilter}`);
  lines.push(`- 증상 카테고리: ${symptom}`, '');
  lines.push('## 매칭 에러 코드 (코사인 유사도 TOP 5)', '');
  lines.push('| 코드 | 명칭 | 코사인 | 심각도 | 12개월 이력 | 평균 복구 | 주요 원인 |');
  lines.push('|---|---|---:|---|---:|---|---|');
  for (const r of results) {
    lines.push(`| ${r.code} | ${r.name} | ${r.sim.toFixed(2)} | ${r.sev} | ${r.count > 0 ? r.count + '건' : '—'} | ${r.mttr} | ${r.cause} |`);
  }
  if (markov.length > 0) {
    lines.push('', '## Markov 후속 고장 예측', '');
    for (const m of markov) {
      lines.push(`- ${m.code} ${m.name} (확률 ${m.prob.toFixed(2)})`);
    }
  }
  return lines.join('\n');
}
