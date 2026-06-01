// Day 5 Phase 4-B — 이미지 첨부 미리보기 (썸네일 + 삭제)

import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { X } from 'lucide-react';
import { UPLOAD_LIMITS } from '@api/upload';

interface Props {
  file: File;
  onRemove: () => void;
}

export function ImagePreview({ file, onRemove }: Props) {
  const { t } = useTranslation();
  const [url, setUrl] = useState<string>('');

  useEffect(() => {
    const u = URL.createObjectURL(file);
    setUrl(u);
    return () => URL.revokeObjectURL(u);
  }, [file]);

  const oversize = file.size > UPLOAD_LIMITS.imageBytes;
  const sizeKB = Math.round(file.size / 1024);

  return (
    <div className="attachment-preview image" role="region" aria-label={t('chat.attachment.image')}>
      {url && (
        <img src={url} alt={file.name} className="thumb" />
      )}
      <div className="meta">
        <span className="name" title={file.name}>{file.name}</span>
        <span className="size">{sizeKB} KB</span>
        {oversize && (
          <span className="warn" role="alert">
            {t('chat.attachment.oversize_image')}
          </span>
        )}
      </div>
      <button
        type="button"
        className="remove"
        onClick={onRemove}
        aria-label={t('chat.attachment.remove')}
        title={t('chat.attachment.remove')}
      >
        <X size={14} strokeWidth={2.5} />
      </button>
    </div>
  );
}
