// Day 5 Phase 4-B — 일반 파일 첨부 미리보기 (filename + size + 삭제)
// v3.3 Phase G-4 — CAD/HWP 확장자별 아이콘 + 양식 라벨 + lg-attachment-cad 변형.

import { useTranslation } from 'react-i18next';
import { X, FileText, Boxes, FileImage, ScanLine } from 'lucide-react';
import { UPLOAD_LIMITS } from '@api/upload';

interface Props {
  file: File;
  onRemove: () => void;
}

type CategoryKey = 'cad-text' | 'cad-binary' | 'hwp' | 'doc';

interface Category {
  kind: CategoryKey;
  label: string;
  icon: React.ReactNode;
}

function categorize(filename: string): Category {
  const ext = filename.toLowerCase().split('.').pop() ?? '';
  if (['dxf', 'step', 'stp', 'igs', 'iges'].includes(ext)) {
    return { kind: 'cad-text', label: `${ext.toUpperCase()} (도면)`, icon: <ScanLine size={20} strokeWidth={1.5} aria-hidden /> };
  }
  if (['sldprt', 'sldasm', 'prt', 'catpart', 'catproduct'].includes(ext)) {
    return { kind: 'cad-binary', label: `${ext.toUpperCase()} (3D 부품)`, icon: <Boxes size={20} strokeWidth={1.5} aria-hidden /> };
  }
  if (['hwp', 'hwpx'].includes(ext)) {
    return { kind: 'hwp', label: `${ext.toUpperCase()} (한글 문서)`, icon: <FileImage size={20} strokeWidth={1.5} aria-hidden /> };
  }
  return { kind: 'doc', label: ext ? ext.toUpperCase() : '문서', icon: <FileText size={20} strokeWidth={1.5} aria-hidden /> };
}

export function AttachmentPreview({ file, onRemove }: Props) {
  const { t } = useTranslation();
  const oversize = file.size > UPLOAD_LIMITS.fileBytes;
  const sizeKB = Math.round(file.size / 1024);
  const category = categorize(file.name);

  // CAD 변형: lg-attachment-cad 클래스 (Phase 0 추가) + 양식 라벨
  const wrapperClass =
    category.kind === 'cad-text' || category.kind === 'cad-binary'
      ? 'attachment-preview file lg-attachment-cad'
      : 'attachment-preview file';

  return (
    <div className={wrapperClass} role="region" aria-label={t('chat.attachment.file')} data-kind={category.kind}>
      {category.icon}
      <div className="meta">
        <span className="name" title={file.name}>{file.name}</span>
        <span className="size">
          {category.label} · {sizeKB} KB
        </span>
        {oversize && (
          <span className="warn" role="alert">
            {t('chat.attachment.oversize_file')}
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
