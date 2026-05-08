// 협업 시나리오 카드 (SOP 사이드 패널 협업 탭).
// Phase 2: GET /api/scenarios 동적 로드 (사용자 부서/언어 컨텍스트). DB 비가용 시 정적 5종 fallback.
// 카드 클릭 → onPickScenario(text) → 챗 자동 전송 → 시나리오 매처 → LLM 호출 0회.

import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { fetchUserScenarios, type UserScenarioItem } from '@api/scenarios';

interface ScenarioMeta {
  id: string;
  trigger: string;
  title: string;
  tag: string;
}

const FALLBACK: ScenarioMeta[] = [
  { id: 'COLLAB-8D', trigger: '품질팀에서 8D 올려달라는데?', title: '품질팀에서 8D 올려달라는데?', tag: '8D' },
  { id: 'COLLAB-ECN', trigger: 'ECN 접수됐는데 우리 팀에 영향 있나?', title: 'ECN 접수됐는데 우리 팀에 영향 있나?', tag: 'ECN' },
  { id: 'COLLAB-SPC-DATA', trigger: '프레스 라인 SPC 데이터 보내달라는데', title: '프레스 라인 SPC 데이터 보내달라는데', tag: 'SPC' },
  { id: 'COLLAB-PPAP-PREP', trigger: '신차 PPAP 서류 우리 부서 산출물은?', title: '신차 PPAP 서류 우리 부서 산출물은?', tag: 'PPAP' },
  { id: 'COLLAB-SAFETY-AUDIT', trigger: '다음 주 안전 점검 뭐 준비?', title: '다음 주 안전 점검 뭐 준비?', tag: 'SAFETY' },
];

function deriveTag(it: UserScenarioItem): string {
  // scenario_id 의 마지막 토큰 또는 첫 트리거 키워드를 태그로
  const idTail = it.scenario_id.split('-').slice(1).join('-');
  return (idTail || it.trigger_keywords[0] || it.scenario_id).toUpperCase().slice(0, 12);
}

interface Props {
  onPickScenario?: (text: string) => void;
}

export function ScenarioPanel({ onPickScenario }: Props) {
  const { t, i18n } = useTranslation();
  const [items, setItems] = useState<ScenarioMeta[]>(FALLBACK);

  useEffect(() => {
    let cancelled = false;
    fetchUserScenarios('', i18n.language === 'en' ? 'en' : 'ko')
      .then((res) => {
        if (cancelled) return;
        if (!res.items.length) return;  // 빈 목록이면 fallback 유지
        const mapped: ScenarioMeta[] = res.items.map((it) => ({
          id: it.scenario_id,
          trigger: it.trigger_keywords[0] || it.situation || it.scenario_id,
          title: it.situation || it.scenario_id,
          tag: deriveTag(it),
        }));
        setItems(mapped);
      })
      .catch(() => {
        // 인증 실패 등 → fallback 그대로
      });
    return () => { cancelled = true; };
  }, [i18n.language]);

  return (
    <div className="scenario-panel" role="region" aria-label="협업 시나리오">
      <ul className="scenario-panel__list">
        {items.map((sc) => (
          <li key={sc.id}>
            <button
              type="button"
              className="scenario-panel__item"
              onClick={() => onPickScenario?.(sc.trigger)}
            >
              <span className="eyebrow">[{sc.tag}]</span>
              <span className="title">{sc.title}</span>
              <span className="hint">{t('chat.scenarios.eyebrow')}</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
