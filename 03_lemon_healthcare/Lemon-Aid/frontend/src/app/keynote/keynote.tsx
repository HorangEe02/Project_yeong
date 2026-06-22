'use client';

import { Fragment, useEffect, useRef, useState } from 'react';

import styles from './keynote.module.css';

/** 하단 파이프라인 레일에 표시할 AI 4단계. */
const STAGES = [
  { num: '01', kr: '본다', logo: 'yolo.svg' },
  { num: '02', kr: '읽는다', logo: 'paddlepaddle.svg' },
  { num: '03', kr: '이해한다', logo: 'ollama-mono.svg' },
  { num: '04', kr: '판단한다', logo: 'kdris.svg' },
];

/** "Built with" 몽타주 로고. */
const STACK = [
  'fastapi.svg',
  'python.svg',
  'nextdotjs.svg',
  'react.svg',
  'flutter.svg',
  'postgresql.svg',
  'redis.svg',
  'docker.svg',
  'supabase.svg',
  'vercel.svg',
];

/**
 * WWDC 스타일 스크롤 키노트.
 *
 * Returns:
 *   순수 블랙 배경에 한 슬라이드 한 메시지로 AI 파이프라인을 시연하는 화면.
 */
export default function Keynote() {
  const deckRef = useRef<HTMLDivElement>(null);
  const [activeStage, setActiveStage] = useState(-1);
  const [railShown, setRailShown] = useState(false);

  useEffect(() => {
    const root = deckRef.current;
    if (!root) {
      return;
    }

    // 스크롤 진입 시 페이드업 reveal.
    const revealObs = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            entry.target.classList.add(styles.inview);
          }
        }
      },
      { root, threshold: 0.25 },
    );
    root.querySelectorAll<HTMLElement>('[data-reveal]').forEach((el) => revealObs.observe(el));

    // AI 단계 슬라이드 → 활성 단계 + 레일 표시.
    const stageObs = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setActiveStage(Number((entry.target as HTMLElement).dataset.stage));
            setRailShown(true);
          }
        }
      },
      { root, threshold: 0.55 },
    );
    root.querySelectorAll<HTMLElement>('[data-stage]').forEach((el) => stageObs.observe(el));

    // 단계 구간을 벗어나면 레일 숨김.
    const edgeObs = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setRailShown(false);
          }
        }
      },
      { root, threshold: 0.5 },
    );
    root.querySelectorAll<HTMLElement>('[data-edge]').forEach((el) => edgeObs.observe(el));

    return () => {
      revealObs.disconnect();
      stageObs.disconnect();
      edgeObs.disconnect();
    };
  }, []);

  return (
    <div className={styles.deck} ref={deckRef}>
      {/* 01 — Cover */}
      <section className={`${styles.slide} ${styles.slideTint}`}>
        <p className={`${styles.kicker} ${styles.kickerLemon} ${styles.reveal}`} data-reveal>
          KDT 레몬헬스케어 기업 프로젝트
        </p>
        <h1 className={`${styles.headline} ${styles.reveal}`} data-reveal data-d="1">
          <span className={styles.accent}>Lemon AID</span>
        </h1>
        <p className={`${styles.sub} ${styles.reveal}`} data-reveal data-d="2">
          사진 한 장으로, 영양제를 이해하다.
        </p>
        <div className={styles.scrollHint} aria-hidden="true">
          <span />
          SCROLL
        </div>
      </section>

      {/* 02 — Problem */}
      <section className={styles.slide}>
        <h2 className={`${styles.headline} ${styles.reveal}`} data-reveal>
          {'영양제 라벨,\n누가 다 읽을 수 있을까요?'}
        </h2>
        <p className={`${styles.sub} ${styles.subTight} ${styles.reveal}`} data-reveal data-d="2">
          성분 · 함량 · 섭취법 · 주의사항 — 너무 작고, 너무 많습니다.
        </p>
      </section>

      {/* 03 — Divider: AI */}
      <section className={`${styles.slide} ${styles.slideDark}`}>
        <h2 className={`${styles.giant} ${styles.accentAi} ${styles.reveal}`} data-reveal>
          AI.
        </h2>
        <p className={`${styles.sub} ${styles.reveal}`} data-reveal data-d="2">
          그래서 우리는, 보고 · 읽고 · 이해하는 AI를 만들었습니다.
        </p>
      </section>

      {/* 04 — Pipeline overview (edge: before stages) */}
      <section className={styles.slide} data-edge>
        <p className={`${styles.kicker} ${styles.reveal}`} data-reveal>
          ONE PHOTO. FOUR STEPS.
        </p>
        <h2 className={`${styles.headline} ${styles.reveal}`} data-reveal data-d="1">
          사진 한 장이 지나는 길
        </h2>
        <div className={`${styles.flow} ${styles.reveal}`} data-reveal data-d="2">
          {STAGES.map((s, i) => (
            <Fragment key={s.num}>
              {i > 0 && <div className={styles.flowArrow}>→</div>}
              <div className={styles.flowNode}>
                <span className={styles.flowNum}>{s.num}</span>
                <span className={styles.flowKr}>{s.kr}</span>
                <span className={styles.flowTech}>
                  {['음식·라벨 인식', 'OCR 글자 인식', '로컬 LLM 구조화', '영양 기준 판단'][i]}
                </span>
              </div>
            </Fragment>
          ))}
        </div>
      </section>

      {/* 05 — Stage 01: YOLO (본다) */}
      <section className={styles.slide} data-stage="0">
        <div className={`${styles.stageTop} ${styles.reveal}`} data-reveal>
          <span className={styles.stageNum}>01</span>
          <span className={styles.stageLogo}>
            <img src="/tech-logos/yolo.svg" alt="" />
          </span>
        </div>
        <h2 className={`${styles.headline} ${styles.reveal}`} data-reveal data-d="1">
          <span className={styles.accent}>본다.</span>
        </h2>
        <p className={`${styles.sub} ${styles.subTight} ${styles.reveal}`} data-reveal data-d="2">
          음식과 영양제 라벨이 사진 어디에 있는지 찾아냅니다.
        </p>
        <div className={`${styles.io} ${styles.reveal}`} data-reveal data-d="2">
          <div className={styles.ioBox}>
            <span className={styles.ioLabel}>INPUT</span>
            <span
              style={{
                width: '64%',
                height: '64%',
                borderRadius: 14,
                background: 'radial-gradient(circle at 60% 40%, #4a4a2a, #1a1a1c)',
              }}
            />
          </div>
          <div className={styles.ioArrow}>→</div>
          <div className={styles.ioBox}>
            <span className={styles.ioLabel}>YOLO</span>
            <span
              style={{
                width: '64%',
                height: '64%',
                borderRadius: 14,
                background: 'radial-gradient(circle at 60% 40%, #4a4a2a, #1a1a1c)',
              }}
            />
            <i className={styles.bbox} data-tag="영양제" style={{ top: '30%', left: '24%', width: '38%', height: '34%' }} />
            <i className={styles.bbox} data-tag="음식" style={{ top: '52%', left: '50%', width: '30%', height: '26%' }} />
          </div>
        </div>
        <span className={`${styles.credit} ${styles.reveal}`} data-reveal data-d="3">
          <span className={styles.creditDot} />
          YOLOv8 · Ultralytics · 로컬
        </span>
      </section>

      {/* 06 — Stage 02: OCR (읽는다) */}
      <section className={styles.slide} data-stage="1">
        <div className={`${styles.stageTop} ${styles.reveal}`} data-reveal>
          <span className={styles.stageNum}>02</span>
          <span className={styles.stageLogo}>
            <img src="/tech-logos/paddlepaddle.svg" alt="" />
          </span>
        </div>
        <h2 className={`${styles.headline} ${styles.reveal}`} data-reveal data-d="1">
          <span className={styles.accent}>읽는다.</span>
        </h2>
        <p className={`${styles.sub} ${styles.subTight} ${styles.reveal}`} data-reveal data-d="2">
          라벨의 한글·숫자를 한 글자씩 텍스트로 읽어냅니다.
        </p>
        <div className={`${styles.io} ${styles.reveal}`} data-reveal data-d="2">
          <div className={styles.ioBox}>
            <span className={styles.ioLabel}>라벨</span>
            <div className={styles.mockLabel}>
              <i />
              <i />
              <i />
              <i />
            </div>
          </div>
          <div className={styles.ioArrow}>→</div>
          <div className={styles.ioBox}>
            <span className={styles.ioLabel}>TEXT</span>
            <div className={styles.ocrOut}>
              <div>비타민 D 1000 IU</div>
              <div>칼슘 200 mg</div>
              <div>1일 1정 섭취</div>
              <div>식후 30분</div>
            </div>
          </div>
        </div>
        <span className={`${styles.credit} ${styles.reveal}`} data-reveal data-d="3">
          <span className={styles.creditDot} />
          PaddleOCR 기본·로컬 · NAVER CLOVA / Google Vision 선택
        </span>
      </section>

      {/* 07 — Stage 03: Ollama · Gemma4 (이해한다) — HERO */}
      <section className={`${styles.slide} ${styles.slideDark}`} data-stage="2">
        <div className={`${styles.stageTop} ${styles.reveal}`} data-reveal>
          <span className={styles.stageNum}>03</span>
          <span className={styles.stageLogo}>
            <img src="/tech-logos/ollama-mono.svg" alt="" />
          </span>
        </div>
        <h2 className={`${styles.headline} ${styles.reveal}`} data-reveal data-d="1">
          <span className={styles.accent}>이해한다.</span>
        </h2>
        <p className={`${styles.sub} ${styles.subTight} ${styles.reveal}`} data-reveal data-d="2">
          {'로컬 LLM이 읽은 글자를 의미로 바꿉니다.\n성분 · 함량 · 섭취법으로 구조화.'}
        </p>
        <div className={`${styles.io} ${styles.reveal}`} data-reveal data-d="2">
          <div className={styles.ioBox}>
            <span className={styles.ioLabel}>TEXT</span>
            <div className={styles.ocrOut}>
              <div>비타민 D 1000 IU</div>
              <div>1일 1정 식후</div>
            </div>
          </div>
          <div className={styles.ioArrow}>→</div>
          <div className={styles.ioBox}>
            <span className={styles.ioLabel}>Gemma4</span>
            <div className={styles.jsonOut}>
              {'{'}
              <br />
              &nbsp;&nbsp;<b>성분</b>: &quot;비타민 D&quot;,
              <br />
              &nbsp;&nbsp;<b>함량</b>: &quot;1000 IU&quot;,
              <br />
              &nbsp;&nbsp;<b>섭취</b>: &quot;1일 1정&quot;
              <br />
              {'}'}
            </div>
          </div>
        </div>
        <span className={`${styles.credit} ${styles.reveal}`} data-reveal data-d="3">
          <span className={styles.creditDot} />
          Ollama · Gemma4 (비전) · qwen3.5 (텍스트) · 100% 로컬
        </span>
      </section>

      {/* 08 — Stage 04: KDRIs (판단한다) */}
      <section className={styles.slide} data-stage="3">
        <div className={`${styles.stageTop} ${styles.reveal}`} data-reveal>
          <span className={styles.stageNum}>04</span>
          <span className={styles.stageLogo}>
            <img src="/tech-logos/kdris.svg" alt="" />
          </span>
        </div>
        <h2 className={`${styles.headline} ${styles.reveal}`} data-reveal data-d="1">
          <span className={styles.accent}>판단한다.</span>
        </h2>
        <p className={`${styles.sub} ${styles.subTight} ${styles.reveal}`} data-reveal data-d="2">
          한국인 영양섭취기준(KDRIs 2025)과 비교해, 나에게 맞는지 알려줍니다.
        </p>
        <div className={`${styles.io} ${styles.reveal}`} data-reveal data-d="2">
          <div className={styles.ioBox}>
            <span className={styles.ioLabel}>성분</span>
            <div className={styles.jsonOut}>
              <b>비타민 D</b>
              <br />
              1000 IU / 일
            </div>
          </div>
          <div className={styles.ioArrow}>→</div>
          <div className={styles.ioBox}>
            <span className={styles.ioLabel}>KDRIs</span>
            <div style={{ display: 'grid', gap: 10, width: '78%', textAlign: 'left' }}>
              <span className={`${styles.mtag} ${styles.mok}`}>권장 범위 ✓</span>
              <span style={{ color: 'var(--muted)', fontSize: 12, fontWeight: 600 }}>
                상한(4000 IU) 이내
              </span>
            </div>
          </div>
        </div>
        <span className={`${styles.credit} ${styles.reveal}`} data-reveal data-d="3">
          <span className={styles.creditDot} />
          KDRIs 2025 · 룰 매칭
        </span>
      </section>

      {/* 09 — Result / demo (edge: after stages) */}
      <section className={`${styles.slide} ${styles.slideTint}`} data-edge>
        <p className={`${styles.kicker} ${styles.reveal}`} data-reveal>
          그리고, 결과.
        </p>
        <h2 className={`${styles.headline} ${styles.reveal}`} data-reveal data-d="1">
          한눈에 보이는 판단
        </h2>
        <div className={`${styles.phoneWrap} ${styles.reveal}`} data-reveal data-d="2">
          <div className={styles.phone}>
            <div className={styles.phoneScreen}>
              <div className={styles.phoneNotch} />
              <div className={styles.scoreRing}>
                <div>
                  <b>82</b>
                  <span>건강 점수</span>
                </div>
              </div>
              <div className={styles.mrow}>
                비타민 D<span className={`${styles.mtag} ${styles.mok}`}>적정</span>
              </div>
              <div className={styles.mrow}>
                칼슘<span className={`${styles.mtag} ${styles.mok}`}>적정</span>
              </div>
              <div className={styles.mrow}>
                철분<span className={`${styles.mtag} ${styles.mwarn}`}>주의</span>
              </div>
            </div>
          </div>
        </div>
        <p className={`${styles.sub} ${styles.reveal}`} data-reveal data-d="3">
          복용 이력 · 건강 상태와 연결되는 맞춤 판단.
        </p>
      </section>

      {/* 10 — Built with (stack montage) */}
      <section className={styles.slide}>
        <p className={`${styles.kicker} ${styles.reveal}`} data-reveal>
          BUILT WITH
        </p>
        <h2 className={`${styles.headline} ${styles.reveal}`} data-reveal data-d="1">
          탄탄한 스택 위에서
        </h2>
        <div className={`${styles.stackGrid} ${styles.reveal}`} data-reveal data-d="2">
          {STACK.map((logo) => (
            <span key={logo} className={styles.stackChip}>
              <img src={`/tech-logos/${logo}`} alt="" loading="lazy" />
            </span>
          ))}
        </div>
        <a className={`${styles.techLink} ${styles.reveal}`} data-reveal data-d="3" href="/tech">
          전체 기술 스택 보기 →
        </a>
      </section>

      {/* 11 — One more thing */}
      <section className={`${styles.slide} ${styles.slideDark}`}>
        <p className={`${styles.otmt} ${styles.reveal}`} data-reveal>
          one more thing…
        </p>
        <h2 className={`${styles.giant} ${styles.accent} ${styles.reveal}`} data-reveal data-d="1">
          Private.
        </h2>
        <p className={`${styles.sub} ${styles.reveal}`} data-reveal data-d="2">
          {'사진은 당신의 서버 밖으로 나가지 않습니다.\n로컬 AI 우선 · 외부 OCR 기본 차단(fail-closed).'}
        </p>
      </section>

      {/* 12 — Closer */}
      <section className={`${styles.slide} ${styles.slideTint}`}>
        <h2 className={`${styles.wordmark} ${styles.accent} ${styles.reveal}`} data-reveal>
          Lemon AID
        </h2>
        <p className={`${styles.sub} ${styles.reveal}`} data-reveal data-d="1">
          건강의신 AI · 만성질환자 중심 헬스케어 보조
        </p>
        <p className={`${styles.disclaimer} ${styles.reveal}`} data-reveal data-d="2">
          본 화면의 정보는 일반적인 이해를 돕기 위한 기술 소개이며, 의료적 진단·처방을 대체하지 않습니다.
        </p>
      </section>

      {/* Sticky pipeline rail */}
      <div
        className={`${styles.railWrap} ${railShown ? styles.railShown : ''}`}
        aria-hidden="true"
      >
        {STAGES.map((s, i) => (
          <Fragment key={s.num}>
            {i > 0 && <span className={styles.railArrow}>›</span>}
            <div
              className={`${styles.railStage} ${activeStage === i ? styles.railStageActive : ''}`}
            >
              <b>{s.num}</b>
              <span>{s.kr}</span>
            </div>
          </Fragment>
        ))}
      </div>
    </div>
  );
}
