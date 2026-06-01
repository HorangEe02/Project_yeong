// G7: 글로서리 용어 hover Tooltip.
//
// 단일 용어에 대해 hover 시 정의 팝오버를 표시한다.
// data 는 GlossaryProvider 의 컨텍스트 또는 props 로 받음.

import { useEffect, useRef, useState } from 'react';
import type { GlossaryTermData } from './GlossaryProvider';

interface Props {
  term: string;                     // 화면에 표시할 텍스트
  data: GlossaryTermData;           // 정의 + alias
  className?: string;
  highlighted?: boolean;            // <mark> 등 외부 강조 동시 적용
}

export function GlossaryTerm({ term, data, className, highlighted }: Props) {
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState<'below' | 'above'>('below');
  const ref = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (!open || !ref.current) return;
    const r = ref.current.getBoundingClientRect();
    const spaceBelow = window.innerHeight - r.bottom;
    setPosition(spaceBelow < 200 ? 'above' : 'below');
  }, [open]);

  return (
    <span
      ref={ref}
      className={[
        'lg-glossary-term',
        highlighted ? 'highlighted' : '',
        className ?? '',
      ].filter(Boolean).join(' ')}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
      tabIndex={0}
      role="button"
      aria-describedby={open ? `glossary-${data.term}` : undefined}
    >
      {term}
      {open && (
        <span
          id={`glossary-${data.term}`}
          role="tooltip"
          className={`lg-glossary-popover lg-glossary-popover-${position}`}
        >
          <span className="lg-glossary-pop-eyebrow">
            <span className="label-en">{data.en || '—'}</span>
          </span>
          <strong className="lg-glossary-pop-title">{data.term}</strong>
          {data.ko && <span className="lg-glossary-pop-ko">{data.ko}</span>}
          <p className="lg-glossary-pop-def">{data.definition}</p>
          {data.category && (
            <span className="lg-glossary-pop-cat">{data.category}</span>
          )}
        </span>
      )}
    </span>
  );
}
