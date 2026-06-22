/**
 * Lemon Healthcare 기술 스택 쇼케이스 데이터.
 *
 * 비전공자도 이해할 수 있도록 각 기술을 "이게 뭐예요? / 우리 앱에선 이렇게 써요"
 * 관점으로 정리한다. 실제 코드에서 확인된 기술(used)과 문서·구조상 도입 예정인
 * 선택 기술(planned)을 구분한다.
 *
 * 뱃지는 `public/tech-logos/`의 실제 로고(SVG/PNG)를 사용하고, 로고가 없는 기술은
 * 같은 폴더의 직접 제작한 SVG 아이콘을 사용한다(기본 이모지 미사용).
 *
 * 근거 경로 예시:
 *   - frontend/package.json, frontend/vercel.json
 *   - mobile/pubspec.yaml
 *   - backend/requirements.txt, backend/pyproject.toml
 *   - docker-compose.yml, supabase/, .github/workflows/*
 */

/** 개별 기술 항목. */
export interface TechItem {
  /** 영문 기술 이름(카드 제목). */
  name: string;
  /** 한 줄 요약(무슨 도구인지). */
  tagline: string;
  /** 비전공자용 쉬운 설명(무엇이고 우리 앱에서 어떻게 쓰는지). */
  description: string;
  /** public/tech-logos/ 안의 로고 또는 커스텀 SVG 파일명. */
  logo?: string;
  /** 로고가 2개인 경우(예: iOS · Android). logo 대신 사용. */
  logos?: string[];
  /** 뱃지 강조 색(브랜드 컬러) — 카드 악센트. */
  accent: string;
  /** 선택적 상태 태그(예: "기본", "선택 · 외부", "선택 · 로컬"). */
  note?: string;
}

/** 기술 카테고리(섹션). */
export interface TechCategory {
  id: string;
  /** 카테고리 이모지 아이콘. */
  icon: string;
  /** 한국어 카테고리 제목. */
  title: string;
  /** 카테고리 한 줄 소개. */
  blurb: string;
  items: TechItem[];
}

/** 아키텍처 흐름 단계. */
export interface ArchStep {
  icon: string;
  title: string;
  description: string;
}

/** 서비스 한 줄 소개. */
export const productIntro = {
  emoji: '🍋',
  name: 'Lemon Healthcare',
  subtitle: '건강의신 AI · 만성질환자 중심 헬스케어 보조 서비스',
  paragraph:
    '영양제 라벨과 식단 사진을 찍으면, OCR(글자 인식)과 AI가 성분을 읽어 ' +
    '한국인 영양섭취기준(KDRIs)과 비교하고 활동·체중 관리를 돕습니다. ' +
    '진단·처방이 아니라 "건강관리 보조"를 목표로 하며, 사진을 외부로 보내지 않는 ' +
    '로컬 AI를 기본값으로 둔 프라이버시 우선 서비스입니다.',
  highlights: ['Local-first AI', 'Privacy by default', 'Next.js 16', 'FastAPI', 'Flutter'],
};

/** "아키텍처 한눈에" 흐름. */
export const architecture: ArchStep[] = [
  {
    icon: '📱',
    title: '모바일 · 웹 앱',
    description: '사용자가 영양제·식단 사진을 찍고 결과를 봅니다.',
  },
  {
    icon: '⚙️',
    title: '백엔드 API',
    description: 'FastAPI 서버가 요청을 받아 분석 과정을 지휘합니다.',
  },
  {
    icon: '🤖',
    title: 'AI · OCR 엔진',
    description: '로컬 LLM·OCR·음식 인식이 사진을 해석합니다.',
  },
  {
    icon: '🗃️',
    title: '데이터베이스',
    description: '결과와 영양 기준을 PostgreSQL·Redis에 저장·조회합니다.',
  },
];

/** 실제 사용 중인 기술(카테고리별). */
export const usedCategories: TechCategory[] = [
  {
    id: 'frontend',
    icon: '🖥️',
    title: '프론트엔드 (웹)',
    blurb: '사용자가 브라우저에서 보는 웹 화면을 만드는 기술이에요.',
    items: [
      {
        name: 'Next.js 16',
        tagline: 'React 기반 웹 프레임워크',
        description:
          '웹사이트의 화면과 주소(페이지)를 만들고 서버에서 빠르게 그려주는 도구예요. ' +
          '지금 보고 계신 이 페이지도 Next.js로 만들었어요.',
        logo: 'nextdotjs.svg',
        accent: '#e5e7eb',
      },
      {
        name: 'React 19',
        tagline: '화면 조립 라이브러리',
        description:
          '버튼·카드 같은 화면 조각을 레고처럼 조립해 만드는 도구. ' +
          '사용자의 동작에 맞춰 화면이 즉시 바뀌게 해줘요.',
        logo: 'react.svg',
        accent: '#61dafb',
      },
      {
        name: 'TypeScript',
        tagline: '안전한 자바스크립트',
        description:
          '"이 값은 숫자, 저 값은 글자"라고 미리 정해 두어 실수를 줄여주는 언어. ' +
          '버그를 배포 전에 잡아줘요.',
        logo: 'typescript.svg',
        accent: '#3178c6',
      },
      {
        name: 'Supabase JS',
        tagline: '로그인 · 데이터 연결',
        description:
          '회원 로그인 상태를 확인하고 데이터베이스와 안전하게 연결해주는 연결선이에요.',
        logo: 'supabase.svg',
        accent: '#3ecf8e',
      },
      {
        name: 'Vercel',
        tagline: '웹 자동 배포 · 호스팅',
        description:
          '코드를 올리면 자동으로 전 세계에 빠른 웹사이트로 띄워주는 호스팅 서비스. ' +
          '이 사이트가 떠 있는 곳이에요.',
        logo: 'vercel.svg',
        accent: '#e5e7eb',
      },
    ],
  },
  {
    id: 'mobile',
    icon: '📱',
    title: '모바일 앱',
    blurb: '아이폰·안드로이드에서 돌아가는 휴대폰 앱을 만드는 기술이에요.',
    items: [
      {
        name: 'Flutter',
        tagline: '하나의 코드로 iOS · Android',
        description:
          '코드를 한 번만 짜면 아이폰과 안드로이드 앱을 동시에 만들 수 있는 ' +
          '구글의 앱 제작 도구예요.',
        logo: 'flutter.svg',
        accent: '#54c5f8',
      },
      {
        name: 'Riverpod',
        tagline: '앱 상태 관리',
        description:
          '앱이 기억해야 할 정보(로그인·점수 등)를 깔끔하게 보관하고 화면에 전달하는 도구.',
        logo: 'riverpod.svg',
        accent: '#5b8def',
      },
      {
        name: 'go_router',
        tagline: '화면 이동(라우팅)',
        description:
          '홈 → 카메라 → 결과처럼 앱 안에서 화면을 옮겨 다니는 길을 정해줘요.',
        logo: 'go-router.svg',
        accent: '#2bb3a3',
      },
      {
        name: 'camera · image_picker',
        tagline: '사진 촬영 · 선택',
        description:
          '영양제 라벨이나 식단 사진을 카메라로 찍거나 앨범에서 고를 수 있게 해줘요.',
        logo: 'camera.svg',
        accent: '#f6b900',
      },
      {
        name: 'flutter_secure_storage',
        tagline: '민감정보 안전 보관',
        description:
          '로그인 토큰 같은 민감한 정보를 휴대폰 보안 영역(키체인)에 암호화해 저장해요.',
        logo: 'secure-storage.svg',
        accent: '#9aa0aa',
      },
      {
        name: '네이티브 iOS · Android',
        tagline: 'Xcode · Kotlin 빌드',
        description:
          '앱을 실제 아이폰(Xcode)과 안드로이드(Kotlin)에서 돌아가게 빌드·설정하는 부분. ' +
          '사진 자르기(image_cropper) 같은 기능도 여기서 연결해요.',
        logos: ['ios.svg', 'android.svg'],
        accent: '#a3e635',
      },
    ],
  },
  {
    id: 'backend',
    icon: '⚙️',
    title: '백엔드 (서버)',
    blurb: '화면 뒤에서 계산·저장·판단을 담당하는 "서버 두뇌"예요.',
    items: [
      {
        name: 'Python 3.13',
        tagline: '백엔드 주력 언어',
        description:
          '읽기 쉽고 AI·데이터 처리에 강한 프로그래밍 언어. ' +
          '서버 로직 대부분을 파이썬으로 작성했어요.',
        logo: 'python.svg',
        accent: '#4b8bbe',
      },
      {
        name: 'FastAPI',
        tagline: '빠른 웹 API 서버',
        description:
          '앱과 서버가 데이터를 주고받는 통로(API)를 빠르고 안전하게 만들어주는 도구.',
        logo: 'fastapi.svg',
        accent: '#009688',
      },
      {
        name: 'Uvicorn',
        tagline: 'ASGI 실행 엔진',
        description:
          'FastAPI로 만든 서버를 실제로 켜서 동시에 많은 요청을 처리하게 돌려주는 엔진.',
        logo: 'Uvicorn.png',
        accent: '#2d9d78',
      },
      {
        name: 'Pydantic v2',
        tagline: '데이터 검증',
        description:
          '들어오는 데이터가 형식에 맞는지(예: 나이는 숫자) 자동으로 확인해 ' +
          '잘못된 값을 걸러내요.',
        logo: 'pydantic.svg',
        accent: '#e92063',
      },
      {
        name: 'SQLAlchemy + asyncpg',
        tagline: '데이터베이스 연결(ORM)',
        description:
          '파이썬 코드로 데이터베이스를 다루게 해주는 번역기. ' +
          'asyncpg로 PostgreSQL과 빠르게 통신해요.',
        logo: 'sqlalchemy.svg',
        accent: '#c0563f',
      },
      {
        name: 'Alembic',
        tagline: 'DB 구조 버전관리',
        description:
          '데이터베이스 표(table) 구조가 바뀔 때 이력을 관리하고 안전하게 반영해줘요.',
        logo: 'alembic.svg',
        accent: '#6ba539',
      },
      {
        name: 'PyJWT',
        tagline: '로그인 토큰',
        description:
          '로그인한 사용자에게 위조 불가능한 "출입증(토큰)"을 발급·검증해 본인 확인을 해요.',
        logo: 'pyjwt.svg',
        accent: '#a855f7',
      },
      {
        name: 'httpx',
        tagline: '외부 통신',
        description: '서버가 다른 서비스(예: AI 엔진)에 요청을 보낼 때 쓰는 통신 도구.',
        logo: 'httpx.svg',
        accent: '#2a6df4',
      },
      {
        name: 'Pillow',
        tagline: '이미지 처리',
        description:
          '업로드된 사진의 크기·형식을 다듬어 OCR/AI가 잘 읽도록 전처리해요.',
        logo: 'pillow.svg',
        accent: '#6c7b8b',
      },
      {
        name: 'RapidFuzz',
        tagline: '글자 정확도 측정',
        description:
          'OCR이 읽은 글자가 실제와 얼마나 비슷한지(오차율)를 계산해 품질을 점검해요.',
        logo: 'rapidfuzz.svg',
        accent: '#f59e0b',
      },
    ],
  },
  {
    id: 'ai',
    icon: '🤖',
    title: 'AI · OCR',
    blurb: '사진 속 글자와 음식을 알아보고 영양 정보를 해석하는 똑똑한 부분이에요.',
    items: [
      {
        name: 'Ollama (로컬 LLM)',
        tagline: '내 서버 안에서 돌아가는 AI',
        description:
          '사진을 외부 회사로 보내지 않고 우리 서버 안에서 직접 돌리는 AI예요. ' +
          'qwen3.5(글)·gemma(이미지) 모델로 영양제 정보를 정리하고, 개인정보 보호가 기본값이에요.',
        logo: 'ollama-mono.svg',
        accent: '#e5e7eb',
        note: '기본',
      },
      {
        name: 'PaddleOCR',
        tagline: '한글 글자 인식(OCR)',
        description:
          '영양제 라벨 사진에서 한글·숫자 글자를 읽어내는 무료 오픈소스 OCR 엔진. ' +
          '사진을 외부로 보내지 않는 기본 OCR이에요.',
        logo: 'paddlepaddle.svg',
        accent: '#5b6cff',
        note: '기본 · 로컬',
      },
      {
        name: 'NAVER CLOVA OCR',
        tagline: '한글 특화 OCR',
        description:
          '네이버 클라우드의 한글 특화 OCR. 어댑터가 구현돼 있어 더 높은 정확도가 ' +
          '필요할 때 켤 수 있어요(프라이버시 위해 외부 전송은 기본 차단).',
        logo: 'naver.svg',
        accent: '#03c75a',
        note: '선택 · 외부',
      },
      {
        name: 'Google Cloud Vision',
        tagline: '고정밀 OCR',
        description:
          '더 정확한 글자 인식이 필요할 때 켤 수 있는 구글의 OCR 어댑터. ' +
          '기본은 꺼져 있어요(사진 외부 전송 차단).',
        logo: 'google-cloud.svg',
        accent: '#4285f4',
        note: '선택 · 외부',
      },
      {
        name: 'YOLOv8 · Ultralytics',
        tagline: '음식 · 라벨 인식',
        description:
          '식단 사진에서 음식을, 영양제 라벨에서 글자 영역(ROI)을 찾아내는 이미지 인식 모델. ' +
          '학습된 음식 인식 모델이 포함돼 있어요.',
        logo: 'yolo.svg',
        accent: '#19c37d',
        note: '선택 · 로컬',
      },
      {
        name: 'KDRIs 2025',
        tagline: '한국인 영양 기준 데이터',
        description:
          '한국인 영양소 섭취 기준 데이터. OCR로 읽은 성분을 이 기준과 비교해 ' +
          '과다·부족을 알려줘요.',
        logo: 'kdris.svg',
        accent: '#f59e0b',
      },
    ],
  },
  {
    id: 'infra',
    icon: '🗃️',
    title: '데이터 · 인프라',
    blurb: '정보를 저장하고 서비스를 인터넷에 띄우는 토대예요.',
    items: [
      {
        name: 'PostgreSQL (pgvector)',
        tagline: '메인 데이터베이스',
        description:
          '사용자·영양 정보를 표로 저장하는 핵심 데이터베이스. ' +
          'pgvector로 AI 검색용 벡터도 보관할 수 있어요.',
        logo: 'postgresql.svg',
        accent: '#4f86b3',
      },
      {
        name: 'Redis',
        tagline: '빠른 임시 저장(캐시)',
        description:
          '자주 쓰는 데이터를 잠깐 메모리에 담아두어 응답을 빠르게 해주는 초고속 저장소.',
        logo: 'redis.svg',
        accent: '#e2493f',
      },
      {
        name: 'Supabase',
        tagline: '로그인 · DB 클라우드',
        description: '회원 로그인(Auth)과 데이터베이스를 손쉽게 제공하는 클라우드 서비스.',
        logo: 'supabase.svg',
        accent: '#3ecf8e',
      },
      {
        name: 'Docker Compose',
        tagline: '실행환경 한 번에',
        description:
          '서버·DB·캐시를 똑같은 환경으로 한 번에 켜고 끌 수 있게 포장해주는 도구. ' +
          '"내 컴퓨터에선 됐는데" 문제를 없애요.',
        logo: 'docker.svg',
        accent: '#2496ed',
      },
      {
        name: 'Google Cloud Platform',
        tagline: '클라우드 인프라',
        description: '구글의 클라우드. Vision OCR과 서버 배포 등에 활용해요.',
        logo: 'google-cloud.svg',
        accent: '#4285f4',
      },
    ],
  },
  {
    id: 'quality',
    icon: '🛡️',
    title: '개발 · 품질 · CI/CD',
    blurb: '코드 품질을 자동으로 점검하고 안전하게 배포하는 안전장치예요.',
    items: [
      {
        name: 'GitHub Actions',
        tagline: '자동 검사 · 배포(CI/CD)',
        description:
          '코드를 올릴 때마다 자동으로 검사·테스트를 돌려주는 로봇. ' +
          '백엔드·모바일·문서용 검사가 따로 있어요.',
        logo: 'github.svg',
        accent: '#e5e7eb',
      },
      {
        name: 'Black + Ruff',
        tagline: '코드 정리 · 검사',
        description: '코드 모양을 통일(Black)하고 흔한 실수를 잡아내는(Ruff) 자동 도구.',
        logo: 'ruff.svg',
        accent: '#d7ff64',
      },
      {
        name: 'mypy (strict)',
        tagline: '타입 정적 검사',
        description: '코드의 자료형이 안 맞는 부분을 실행 전에 엄격하게 잡아내요.',
        logo: 'mypy.svg',
        accent: '#2a6df4',
      },
      {
        name: 'pytest (+coverage)',
        tagline: '자동 테스트',
        description:
          '기능이 의도대로 동작하는지 자동으로 확인. 코드의 80% 이상을 ' +
          '테스트로 덮도록 강제해요.',
        logo: 'pytest.svg',
        accent: '#0a9edc',
      },
      {
        name: 'Codecov',
        tagline: '테스트 커버리지 리포트',
        description: '테스트가 코드를 얼마나 검사했는지 시각화해 보여줘요.',
        logo: 'codecov.svg',
        accent: '#f01f7a',
      },
      {
        name: 'pre-commit · detect-secrets',
        tagline: '커밋 전 점검 · 비밀유출 방지',
        description:
          '코드를 저장(commit)하기 전 자동 점검하고, 비밀번호·키가 ' +
          '실수로 올라가는 걸 막아요.',
        logo: 'pre-commit.svg',
        accent: '#fab040',
      },
    ],
  },
];

/**
 * 고도화 로드맵(도입 예정) 기술.
 *
 * 코드·문서(pyproject optional-dependencies, mobile 목표 아키텍처, config 플래그)에
 * 설계돼 있고 고도화 단계에서 본격 도입될 기술. 현재 런타임 기본값에는 포함되지 않는다.
 */
export const plannedItems: TechItem[] = [
  {
    name: 'HealthKit · Health Connect',
    tagline: '건강 데이터 자동 연동',
    description:
      '아이폰·안드로이드의 건강 데이터(걸음수·심박수·체중)를 사용자 동의 후 ' +
      '자동으로 받아오는 연동. 모바일 설계 문서에 정의돼 있어요.',
    logo: 'healthkit.svg',
    accent: '#ff5a5f',
    note: '모바일 고도화',
  },
  {
    name: 'dio · retrofit · freezed',
    tagline: '모바일 목표 아키텍처',
    description:
      '모바일의 네트워크·데이터모델 표준 도구. 앱 규모가 커질 때 도입할 ' +
      '구조로 설계돼 있어요(현재는 가벼운 http 사용).',
    logo: 'mobile-arch.svg',
    accent: '#5b8def',
    note: '모바일 고도화',
  },
  {
    name: 'fl_chart',
    tagline: '모바일 차트',
    description:
      '모바일에서 활동·체중 변화를 그래프로 보여주기 위한 차트 라이브러리(목표 디자인).',
    logo: 'flchart.svg',
    accent: '#54c5f8',
    note: '모바일 고도화',
  },
  {
    name: 'sentence-transformers + pgvector',
    tagline: '의미 검색 · 내부 학습',
    description:
      '문장을 숫자(벡터)로 바꿔 비슷한 의미를 찾는 내부 학습·검색 파이프라인. ' +
      '백엔드 learning 모듈과 pgvector DB가 준비돼 있고, 게이트 통과 시 본격 설치돼요.',
    logo: 'embeddings.svg',
    accent: '#a855f7',
    note: '학습 파이프라인',
  },
  {
    name: 'boto3 · S3',
    tagline: '대용량 클라우드 저장',
    description:
      '대용량 이미지·학습 모델 파일을 클라우드 저장소에 보관하기 위한 도구(학습 단계용).',
    logo: 's3.svg',
    accent: '#ff9900',
    note: '학습 파이프라인',
  },
  {
    name: 'torch · Ultralytics 본격화',
    tagline: '비전 모델 학습 · 확장',
    description:
      '음식·라벨 인식 모델을 직접 학습·고도화하기 위한 딥러닝 스택. ' +
      '어댑터는 구현돼 있고 무거운 학습 의존성은 고도화 단계에서 설치돼요.',
    logo: 'torch.svg',
    accent: '#ee4c2c',
    note: '비전 고도화',
  },
  {
    name: '멀티모달 LLM 교차검증',
    tagline: 'OCR 정확도 고도화',
    description:
      '이미지+텍스트를 함께 보는 AI로 OCR 결과를 교차 검증하는 기능. ' +
      '어댑터가 구현돼 있고 기본 비활성(실험)이며, 정확도 고도화 시 켜요.',
    logo: 'multimodal.svg',
    accent: '#ffc400',
    note: '정확도 고도화',
  },
];

/** 푸터 고지 문구. */
export const footer = {
  disclaimer:
    '본 페이지의 정보는 일반적인 이해를 돕기 위한 기술 소개이며, 의료적 진단·처방을 대체하지 않습니다.',
  note: '🔒 프라이버시 우선 · 로컬 AI 기본값 · 외부 OCR 기본 차단(fail-closed)',
};
