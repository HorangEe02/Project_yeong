// tech.tsx — 백엔드 기술 스택 설명 페이지 (비전공자용).
// /showcase 와 동일한 양식(풀스크린 · HUD · 다크/라이트 토글)으로, 이 서비스가
// "무엇을 · 왜" 썼는지 쉬운 말로 설명한다. 내용은 실제 requirements/코드 기준.
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Server, Cloud, RadioTower, Database, HardDrive, Flame, BarChart3,
  BrainCircuit, Library, Boxes, Eye, TrendingUp, Search, Layers,
  Clock, Bot, FileText, IdCard, Lock, Cable, Rocket, GitBranch,
  type LucideIcon,
} from 'lucide-react';
import { useThemeStore } from '@store/theme';

type ShowTheme = 'dark' | 'light';

interface TechItem {
  icon: LucideIcon;
  name: string;
  tag: string;
  what: string; // 무엇인가요 (쉬운 비유)
  use: string; // 어디에 썼나요 (이 앱에서의 역할)
}
interface TechSection {
  id: string;
  title: string;
  sub: string;
  items: TechItem[];
}

const SECTIONS: TechSection[] = [
  {
    id: 'core',
    title: '1 · 웹 서비스의 뼈대',
    sub: '사용자의 요청을 받아 처리하고 답을 돌려주는 기본 구조',
    items: [
      {
        icon: Server, name: 'FastAPI', tag: '파이썬 웹 서버',
        what: '주문을 받아 요리해 내보내는 식당 주방 같은 역할. 사용자의 요청을 받아 데이터를 처리하고 결과를 돌려줍니다.',
        use: '검색·문서작성·챗봇·법규·설비 등 모든 기능의 요청을 처리하는 중심 서버입니다.',
      },
      {
        icon: Cloud, name: 'Cloud Run (Google)', tag: '클라우드 실행 환경',
        what: '우리 서버를 인터넷에 띄워 24시간 돌아가게 해주는 구글 클라우드. 쓰는 만큼만 자동으로 켜지고 꺼져 비용을 아낍니다.',
        use: '백엔드 전체가 여기서 구동됩니다. 평소엔 1대만 돌려 효율적으로 운영합니다.',
      },
      {
        icon: RadioTower, name: 'SSE 실시간 스트리밍', tag: '실시간 응답',
        what: 'AI가 답을 한 글자씩 타이핑하듯 실시간으로 보내주는 방식입니다(ChatGPT처럼 글자가 차례로 나타남).',
        use: 'AI 도우미 채팅에서 답변이 끊김 없이 흐르듯 표시됩니다.',
      },
    ],
  },
  {
    id: 'data',
    title: '2 · 데이터 보관',
    sub: '정보를 안전하게 저장하는 여러 종류의 창고',
    items: [
      {
        icon: Database, name: 'PostgreSQL (Supabase)', tag: '메인 데이터베이스',
        what: '여러 사람이 동시에 써도 안전한 정식 대형 창고. 정보의 "원본(진실의 원천)"을 보관합니다.',
        use: '사원 정보, 로그인 계정 등 핵심 데이터의 원본을 저장합니다.',
      },
      {
        icon: HardDrive, name: 'SQLite', tag: '내장 초고속 DB',
        what: '서버 안에 들어있는 작고 빠른 수첩. 자주 보는 정보를 즉시 꺼내 쓰기 좋습니다.',
        use: '로그인 검증·검색 인덱스 등 빠른 응답이 필요한 곳에서 원본의 사본을 두고 즉시 조회합니다.',
      },
      {
        icon: Flame, name: 'Firebase', tag: '실시간 DB · 파일 저장',
        what: '변화가 생기면 즉시 화면에 반영해주는 구글의 실시간 도구이자 파일 보관소입니다.',
        use: '보안 감사 기록(누가 언제 로그인), 설비 실시간 알람, 업로드 파일 저장에 사용합니다.',
      },
      {
        icon: BarChart3, name: 'BigQuery (Google)', tag: '대용량 분석 창고',
        what: '엄청난 양의 기록을 모아 빠르게 분석하는 구글의 대형 데이터 창고입니다.',
        use: '모든 활동·감사 로그를 쌓아 사후 분석과 감사 추적에 활용합니다.',
      },
    ],
  },
  {
    id: 'ai',
    title: '3 · AI 두뇌',
    sub: '직접 생각하고 답을 만들어내는 인공지능 부분',
    items: [
      {
        icon: BrainCircuit, name: 'Ollama (자체 호스팅 LLM)', tag: '사내 AI 언어모델',
        what: '회사 내부에서 직접 돌리는 AI 언어모델입니다. 데이터를 외부로 보내지 않아 보안에 유리합니다.',
        use: '챗봇 답변·문서 초안 작성·질의응답의 "두뇌". 사내 PC에서 구동하고 안전 터널로 클라우드와 연결합니다.',
      },
      {
        icon: Library, name: 'RAG (검색증강생성)', tag: '근거 기반 답변',
        what: 'AI가 답하기 전에 회사 자료를 먼저 찾아보고 그 근거로 답하는 방식. 추측이 아니라 "출처 있는 답"을 만듭니다.',
        use: '법규·SOP·문서 질문에서 실제 자료를 인용해 정확하게 답하고 출처를 함께 보여줍니다.',
      },
      {
        icon: Boxes, name: 'ChromaDB (벡터 검색)', tag: '의미 기반 저장소',
        what: '문장을 "의미"로 저장해 뜻이 비슷한 내용을 찾아줍니다. 단어가 달라도 의미가 통하면 찾아냅니다.',
        use: '의미 기반 검색과 RAG에서 질문과 관련된 문서를 빠르게 골라냅니다.',
      },
      {
        icon: Eye, name: 'Vision AI (Gemini)', tag: '이미지 이해 · OCR',
        what: '사진·도면·문서 이미지를 "보고" 그 안의 글자와 내용을 읽어 이해하는 AI입니다.',
        use: '도면·부품 사진 Q&A, 명함·MSDS·영수증 등 이미지에서 텍스트와 정보를 자동 추출합니다.',
      },
      {
        icon: TrendingUp, name: '머신러닝 (scikit-learn)', tag: '예측 · 분류',
        what: '과거 데이터에서 패턴을 학습해 미래를 예측하거나 자동 분류하는 전통 머신러닝입니다.',
        use: '설비 잔여수명 예측, 공정 이상 감지(SPC Nelson 규칙), 검색 의도 자동 분류에 사용합니다.',
      },
    ],
  },
  {
    id: 'search',
    title: '4 · 똑똑한 검색',
    sub: '원하는 정보를 정확하고 빠르게 찾는 기술',
    items: [
      {
        icon: Search, name: 'FTS5 전문 검색', tag: '초고속 키워드 검색',
        what: '키워드가 들어간 자료를 즉시 찾아주는 빠른 검색 엔진(SQLite 내장)입니다.',
        use: '인원·문서 키워드 검색의 1차 빠른 매칭을 담당합니다.',
      },
      {
        icon: Layers, name: '하이브리드 검색', tag: 'BM25 + 의미 + 한국어',
        what: '키워드 일치(BM25) + 의미 유사도(벡터) + 한국어 형태소 분석(Kiwi)을 합쳐 가장 알맞은 결과를 고릅니다.',
        use: '인원 검색·법규 검색에서 오타·동의어·줄임말에도 정확히 찾도록 해줍니다.',
      },
    ],
  },
  {
    id: 'auto',
    title: '5 · 자동화 · 백그라운드',
    sub: '사람이 시키지 않아도 알아서 도는 작업들',
    items: [
      {
        icon: Clock, name: 'Celery + Redis', tag: '예약 작업 · 작업 큐',
        what: '정해진 시간에 자동으로 일을 시키는 "알람 비서"와, 밀린 일감을 차례로 처리하는 대기열입니다.',
        use: '매일 새벽 법규 사이트를 자동 점검하고, 변경을 감지해 일일 요약을 발송합니다.',
      },
      {
        icon: Bot, name: '9종 법규 크롤러', tag: '자동 수집 로봇',
        what: '정부·해외 규제 사이트를 자동으로 돌며 새 규정과 변경 사항을 모아오는 로봇입니다.',
        use: '법규 모니터(D)의 변경 알림 데이터를 매일 자동으로 수집합니다.',
      },
    ],
  },
  {
    id: 'docs',
    title: '6 · 문서 자동 생성',
    sub: 'AI 초안을 실제 업무 파일로 바꿔주는 기술',
    items: [
      {
        icon: FileText, name: '다포맷 문서 변환', tag: 'Word · PDF · Excel · 한글',
        what: 'AI가 만든 초안을 실제 업무에서 쓰는 파일(워드·PDF·엑셀·한글 HWPX)로 자동 변환합니다.',
        use: '문서 작성(B)에서 작성한 초안을 여러 포맷으로 즉시 다운로드할 수 있습니다.',
      },
    ],
  },
  {
    id: 'security',
    title: '7 · 보안 · 인증',
    sub: '권한을 확인하고 정보를 안전하게 지키는 장치',
    items: [
      {
        icon: IdCard, name: 'JWT + RBAC', tag: '토큰 인증 · 6단계 권한',
        what: '출입증(JWT)으로 신원을 확인하고, 직급(L1~L6)에 따라 볼 수 있는 메뉴를 제한합니다.',
        use: '로그인과 권한별 화면 접근 제어(예: 관리 기능은 관리자만 접근)에 사용합니다.',
      },
      {
        icon: Lock, name: 'bcrypt 암호화', tag: '비밀번호 보호',
        what: '비밀번호를 되돌릴 수 없게 암호화해 저장합니다. 설령 유출돼도 원래 비밀번호를 알 수 없습니다.',
        use: '모든 계정 비밀번호 저장과 강력한 비밀번호 정책에 적용됩니다.',
      },
    ],
  },
  {
    id: 'ops',
    title: '8 · 운영 · 인프라',
    sub: '서비스를 안정적으로 띄우고 안전하게 업데이트하는 기반',
    items: [
      {
        icon: Cable, name: 'Cloudflare Tunnel', tag: '보안 연결 통로',
        what: '사내 PC의 AI를 외부에 직접 노출하지 않고, 안전한 통로로만 클라우드와 연결합니다.',
        use: '자체 호스팅 Ollama와 클라우드 백엔드를 안전하게 이어줍니다.',
      },
      {
        icon: Rocket, name: '카나리 배포 + 자동 롤백', tag: '안전한 업데이트',
        what: '새 버전을 먼저 일부에만 시험 노출하고, 문제없으면 전체 적용·문제 시 자동으로 되돌립니다.',
        use: '백엔드 업데이트 시 장애 위험을 최소화하며 배포합니다.',
      },
      {
        icon: GitBranch, name: 'Alembic 마이그레이션', tag: 'DB 구조 버전관리',
        what: '데이터베이스 구조 변경을 버전 관리하듯 안전하게 적용하고 필요하면 되돌립니다.',
        use: '스키마(표 구조) 변경 이력을 안전하게 관리합니다.',
      },
    ],
  },
];

export function TechStack() {
  const resolved = useThemeStore((s) => s.resolved());
  // 앱의 현재 테마로 시작 → 토글 표시와 실제 화면이 항상 일치.
  // (App.tsx 전역 테마 효과가 child effect 이후 실행돼 'dark' 하드코딩을 덮어쓰던 문제 방지.)
  const [theme, setTheme] = useState<ShowTheme>(resolved);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    return () => {
      document.documentElement.setAttribute('data-theme', resolved);
    };
  }, [theme, resolved]);

  return (
    <div
      data-screen-label="Tech Stack"
      style={{ minHeight: '100vh', background: 'var(--hud-bg)', color: 'var(--hud-text)', display: 'flex', flexDirection: 'column' }}
    >
      <header
        style={{
          position: 'sticky', top: 0, zIndex: 10,
          display: 'flex', alignItems: 'center', gap: 16, padding: '16px 28px',
          borderBottom: '1px solid color-mix(in oklab, var(--hud-text) 10%, transparent)',
          background: 'color-mix(in oklab, var(--hud-surface) 72%, transparent)',
          backdropFilter: 'blur(20px) saturate(140%)',
          WebkitBackdropFilter: 'blur(20px) saturate(140%)',
        }}
      >
        <div>
          <div style={{ fontSize: 11, letterSpacing: '0.14em', color: 'var(--hud-text-dim)', fontFamily: 'var(--hud-font-mono)' }}>
            AJIN AI ASSISTANT · TECH STACK
          </div>
          <div style={{ fontSize: 20, fontWeight: 700, marginTop: 2 }}>백엔드 기술 한눈에 보기</div>
          <div style={{ fontSize: 12, color: 'var(--hud-text-dim)', marginTop: 2 }}>
            비전공자도 이해하는 — 어떤 기술을, 무엇을 위해 썼는지
          </div>
        </div>
        <div style={{ flex: 1 }} />
        <div style={{ display: 'inline-flex', border: '1px solid var(--hud-border)', borderRadius: 999, overflow: 'hidden' }}>
          {(['dark', 'light'] as ShowTheme[]).map((t) => (
            <button
              key={t}
              onClick={() => setTheme(t)}
              style={{
                padding: '8px 18px', border: 0, cursor: 'pointer', fontSize: 12, fontWeight: 600,
                background: theme === t ? 'var(--hud-primary)' : 'transparent',
                color: theme === t ? 'var(--hud-bg)' : 'var(--hud-text-dim)',
                transition: 'background 120ms ease',
              }}
            >
              {t === 'dark' ? '다크 모드' : '라이트 모드'}
            </button>
          ))}
        </div>
        <Link
          to="/"
          style={{ padding: '8px 16px', borderRadius: 999, border: '1px solid var(--hud-border)', color: 'var(--hud-text)', textDecoration: 'none', fontSize: 12 }}
        >
          ← 앱으로
        </Link>
      </header>

      <div style={{ padding: 28, maxWidth: 1320, width: '100%', margin: '0 auto' }}>
        {/* 한 줄 요약 */}
        <div
          style={{
            marginBottom: 28, padding: '18px 22px', borderRadius: 16,
            border: '1px solid color-mix(in oklab, var(--hud-primary) 28%, transparent)',
            background: 'color-mix(in oklab, var(--hud-primary) 7%, transparent)', fontSize: 14, lineHeight: 1.7,
          }}
        >
          이 서비스는 <b>사내에서 직접 돌리는 AI(Ollama)</b>를 중심으로, <b>회사 자료를 근거로 답하는 방식(RAG)</b>과
          <b> 똑똑한 검색</b>을 결합한 <b>온프레미스(사내 보안) AI 업무 도우미</b>입니다. 아래는 그 뒤에서 일하는 백엔드 기술들을 쉬운 말로 정리한 것입니다.
        </div>

        {SECTIONS.map((sec) => (
          <section key={sec.id} style={{ marginBottom: 34 }}>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 14 }}>
              <h2 style={{ fontSize: 17, fontWeight: 700, margin: 0 }}>{sec.title}</h2>
              <span style={{ fontSize: 12, color: 'var(--hud-text-dim)' }}>{sec.sub}</span>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 16 }}>
              {sec.items.map((it) => (
                <article
                  key={it.name}
                  style={{
                    padding: 18, borderRadius: 16,
                    border: '1px solid color-mix(in oklab, var(--hud-text) 10%, transparent)',
                    background: 'color-mix(in oklab, var(--hud-surface) 70%, transparent)',
                    display: 'flex', flexDirection: 'column', gap: 10,
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <div
                      style={{
                        width: 38, height: 38, borderRadius: 10, flexShrink: 0,
                        background: 'color-mix(in oklab, var(--hud-primary) 14%, transparent)',
                        display: 'grid', placeItems: 'center',
                      }}
                    >
                      <it.icon size={20} color="var(--hud-primary)" strokeWidth={2} />
                    </div>
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontSize: 15, fontWeight: 700 }}>{it.name}</div>
                      <div style={{ fontSize: 10, letterSpacing: '0.06em', color: 'var(--hud-primary)', fontFamily: 'var(--hud-font-mono)', marginTop: 1 }}>
                        {it.tag}
                      </div>
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.08em', color: 'var(--hud-text-dim)', fontFamily: 'var(--hud-font-mono)' }}>
                      무엇인가요?
                    </div>
                    <div style={{ fontSize: 13, lineHeight: 1.6, marginTop: 3 }}>{it.what}</div>
                  </div>
                  <div>
                    <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.08em', color: 'var(--hud-primary)', fontFamily: 'var(--hud-font-mono)' }}>
                      어디에 썼나요?
                    </div>
                    <div style={{ fontSize: 13, lineHeight: 1.6, marginTop: 3, color: 'var(--hud-text)' }}>{it.use}</div>
                  </div>
                </article>
              ))}
            </div>
          </section>
        ))}

        <div style={{ padding: '16px 0 8px', fontSize: 11, color: 'var(--hud-text-dim)', textAlign: 'center', fontFamily: 'var(--hud-font-mono)' }}>
          AJIN AI ASSISTANT · ON-PREMISE · FastAPI · Ollama · Supabase · Firebase · KNU SILLI 2026
        </div>
      </div>
    </div>
  );
}
