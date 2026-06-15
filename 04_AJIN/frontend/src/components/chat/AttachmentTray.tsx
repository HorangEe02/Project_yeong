// Day 5 Phase 4-B — 첨부 트레이
// 클립 아이콘 + 이미지/파일 picker. 단일 첨부 슬롯 정책 — 기존 첨부가 있으면 교체.

import { useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { Paperclip, Image as ImageIcon } from 'lucide-react';
import { useToastStore } from '@store/toast';
import { validateImageFile, validateGenericFile } from '@api/upload';
import { useFeatureCFlags } from '@lib/featureFlags';

interface Props {
  disabled?: boolean;
  onAttachImage: (file: File) => void;
  onAttachFile: (file: File) => void;
}

export function AttachmentTray({ disabled, onAttachImage, onAttachFile }: Props) {
  const { t } = useTranslation();
  const flags = useFeatureCFlags();
  const imageInputRef = useRef<HTMLInputElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const addToast = useToastStore((s) => s.addToast);
  const acceptedFiles = [
    '.pdf', '.txt', '.md', '.log', '.docx', '.doc', '.xlsx', '.xls',
    '.csv', '.hwp', '.hwpx',
    ...(flags.cad_upload
      ? [
          '.dxf', '.step', '.stp', '.igs', '.iges',
          '.sldprt', '.sldasm', '.prt', '.catpart', '.catproduct',
        ]
      : []),
  ].join(',');

  const handleImagePick = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = ''; // 같은 파일 재선택 허용
    if (!file) return;
    const err = validateImageFile(file);
    if (err) {
      addToast({ type: 'error', message: err });
      return;
    }
    onAttachImage(file);
  };

  const handleFilePick = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    const err = validateGenericFile(file);
    if (err) {
      addToast({ type: 'error', message: err });
      return;
    }
    onAttachFile(file);
  };

  return (
    <div className="attachment-tray" role="group" aria-label={t('chat.attachment.tray')}>
      <button
        type="button"
        className="attach-btn"
        disabled={disabled}
        onClick={() => imageInputRef.current?.click()}
        aria-label={t('chat.attachment.image')}
        title={t('chat.attachment.image')}
      >
        <ImageIcon size={16} strokeWidth={2} />
      </button>
      <button
        type="button"
        className="attach-btn"
        disabled={disabled}
        onClick={() => fileInputRef.current?.click()}
        aria-label={t('chat.attachment.file')}
        title={t('chat.attachment.file')}
      >
        <Paperclip size={16} strokeWidth={2} />
      </button>

      <input
        ref={imageInputRef}
        type="file"
        accept="image/*"
        hidden
        onChange={handleImagePick}
      />
      <input
        ref={fileInputRef}
        type="file"
        accept={acceptedFiles}
        hidden
        onChange={handleFilePick}
      />
    </div>
  );
}
