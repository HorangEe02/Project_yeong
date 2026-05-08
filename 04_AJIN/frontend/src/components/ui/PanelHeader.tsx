import type { ReactNode } from 'react';

interface Props {
  labelEn: string;
  labelKo?: string;
  badge?: ReactNode;
  action?: ReactNode;
}

export function PanelHeader({ labelEn, labelKo, badge, action }: Props) {
  return (
    <div className="ui-panel-header">
      <div className="ui-panel-header-text">
        <span className="label-en">{labelEn}</span>
        {labelKo && <span className="label-ko">{labelKo}</span>}
      </div>
      {badge !== undefined && <span>{badge}</span>}
      {action !== undefined && <span>{action}</span>}
    </div>
  );
}
