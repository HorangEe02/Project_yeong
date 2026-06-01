import clsx from 'clsx';

interface Props {
  text?: string;
  margin?: 'sm' | 'md' | 'lg';
}

export function DottedSeparator({ text, margin = 'md' }: Props) {
  return (
    <div
      className={clsx(
        'ui-dotted-sep',
        text && 'with-text',
        margin !== 'md' && `margin-${margin}`,
      )}
    >
      {text && <span className="ui-dotted-sep-label">{text}</span>}
    </div>
  );
}
