import { Link, useSearchParams } from 'react-router-dom';
import { ShieldAlert } from 'lucide-react';

export function ForbiddenPage() {
  const [params] = useSearchParams();
  const reason = params.get('reason');

  const message =
    reason === 'suspended'
      ? '계정이 비활성화되었습니다. 관리자에게 문의하세요.'
      : reason === 'role'
        ? '이 페이지에 접근할 권한이 없습니다.'
        : '접근이 허용되지 않았습니다.';

  return (
    <main className="flex min-h-[calc(100vh-60px)] flex-col items-center justify-center px-4">
      <div className="flex flex-col items-center gap-4 text-center">
        <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-red-50">
          <ShieldAlert className="h-8 w-8 text-red-500" />
        </div>
        <h1 className="text-2xl font-bold text-on-surface">접근 제한</h1>
        <p className="max-w-md text-on-surface-variant">{message}</p>
        <Link
          to="/"
          className="mt-4 rounded-lg bg-primary px-5 py-2.5 text-sm font-medium text-on-primary no-underline"
        >
          홈으로 돌아가기
        </Link>
      </div>
    </main>
  );
}
