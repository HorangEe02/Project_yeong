import { Link } from 'react-router-dom';
import { Stethoscope, User, Mail } from 'lucide-react';
import { AuthCard } from '@/components/auth/AuthCard';

export function SignupChoicePage() {
  return (
    <AuthCard
      title="회원가입"
      subtitle="어떤 유형으로 가입하시나요?"
      footer={
        <span>
          이미 계정이 있으신가요?{' '}
          <Link to="/login" className="font-medium text-primary">
            로그인
          </Link>
        </span>
      }
    >
      <div className="flex flex-col gap-3">
        <Link
          to="/signup/staff"
          className="group flex items-center gap-4 rounded-xl border border-surface-container-high p-4 no-underline transition-colors hover:border-primary"
        >
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary/10">
            <Stethoscope className="h-5 w-5 text-primary" />
          </div>
          <div className="flex-1">
            <p className="text-sm font-semibold text-on-surface">의료진</p>
            <p className="text-xs text-on-surface-variant">
              의료진 ID 코드가 필요합니다
            </p>
          </div>
        </Link>

        <Link
          to="/signup/patient"
          className="group flex items-center gap-4 rounded-xl border border-surface-container-high p-4 no-underline transition-colors hover:border-primary"
        >
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary/10">
            <User className="h-5 w-5 text-primary" />
          </div>
          <div className="flex-1">
            <p className="text-sm font-semibold text-on-surface">환자 · 보호자</p>
            <p className="text-xs text-on-surface-variant">
              주차 위치 저장, 동선 이력 등 선택 기능을 이용
            </p>
          </div>
        </Link>
      </div>

      <div className="mt-5 flex items-start gap-2 rounded-lg bg-primary/5 p-3 text-xs text-primary">
        <Mail className="mt-0.5 h-3.5 w-3.5 shrink-0" />
        <p>
          <span className="font-semibold">초대 링크를 받으셨나요?</span> 링크를 직접 클릭하면 의료진 가입 절차가 안내됩니다 (코드 불필요).
        </p>
      </div>

      <p className="mt-3 rounded-lg bg-surface-container-low p-3 text-xs text-on-surface-variant">
        회원가입 없이도 QR 코드만으로 동선 안내를 받을 수 있습니다.
      </p>
    </AuthCard>
  );
}
