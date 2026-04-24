export function Loading({ message = '로딩 중...' }: { message?: string }) {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4">
      <div className="h-10 w-10 animate-spin rounded-full border-4 border-surface-container-high border-t-primary" />
      <p className="text-sm text-on-surface-variant">{message}</p>
    </div>
  );
}
