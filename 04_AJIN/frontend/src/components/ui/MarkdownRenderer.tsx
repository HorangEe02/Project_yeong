import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import clsx from 'clsx';

interface Props {
  content: string;
  variant?: 'chat' | 'document';
  className?: string;
}

export function MarkdownRenderer({ content, variant = 'document', className }: Props) {
  return (
    <div className={clsx('ui-md', `variant-${variant}`, className)}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        // react-markdown 은 기본적으로 HTML 비활성 + script 차단 (XSS 안전)
        components={{
          a: ({ href, children, ...rest }) => (
            <a href={href} target="_blank" rel="noopener noreferrer" {...rest}>
              {children}
            </a>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
