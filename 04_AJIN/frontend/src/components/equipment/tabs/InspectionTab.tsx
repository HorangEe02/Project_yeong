// InspectionTab — F-inspection 메인 탭 (점검 체크리스트).

import { DownloadActions } from '@components/common/DownloadActions';
import type { InspectionChecklistResponse } from '@/types/equipment';
import type { InspectionRow } from '../types';
import { buildInspectionMarkdown } from '../markdownBuilders';

interface Props {
  checklist: InspectionChecklistResponse | null;
  inspectionRows: InspectionRow[];
}

export function InspectionTab({ checklist, inspectionRows }: Props) {
  return (
    <section className="lg-card">
      <div className="lg-card-h">
        <div>
          <div className="lg-eyebrow">INSPECTION · 점검 체크리스트</div>
          <h2 className="lg-h2">{checklist?.total ?? 9} 템플릿 (3장비 × 3주기)</h2>
        </div>
      </div>
      <div className="lg-table-wrap">
        <table className="lg-table">
          <thead>
            <tr>
              <th>장비</th>
              <th>주기</th>
              <th>최근 점검</th>
              <th>완료율</th>
              <th>미달 항목</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {inspectionRows.map((row, i) => (
              <tr key={i}>
                <td>{row.eq}</td>
                <td>{row.cycle}</td>
                <td className="mono dim">{row.date}</td>
                <td>
                  <span className={row.lvl === 'warn' ? 'lg-warn' : 'lg-ok'}>{row.rate}%</span>
                </td>
                <td className="dim">{row.miss}</td>
                <td>
                  <button className="lg-btn ghost sm">보기</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <DownloadActions
        content={() => buildInspectionMarkdown(inspectionRows)}
        basename={`equipment_inspection_${new Date().toISOString().slice(0, 10)}`}
        source="equipment"
        metadata={{
          title: '점검 체크리스트 (9 템플릿)',
          doc_type: 'equipment_inspection',
        }}
      />
    </section>
  );
}
