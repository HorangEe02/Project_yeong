'use client';

import { useEffect, useRef, type CSSProperties, type ReactElement } from 'react';

import styles from './tech.module.css';
import {
  architecture,
  footer,
  plannedItems,
  productIntro,
  usedCategories,
  type TechItem,
} from './tech-data';

/**
 * 벤토 그리드에서 2칸(wide)으로 강조할 대표 기술 이름 집합.
 *
 * 카테고리별 대표 1개를 넓게 배치해 Apple 키노트 요약 슬라이드의 벤토 리듬을 만든다.
 * 데이터(tech-data)는 순수하게 두고, 표현(크기)만 뷰에서 결정한다.
 */
const WIDE_TILES = new Set<string>([
  'Next.js 16',
  'Flutter',
  'FastAPI',
  'Ollama (로컬 LLM)',
  'PostgreSQL (pgvector)',
  'GitHub Actions',
  'HealthKit · Health Connect',
]);

/** accent 색과 등장 stagger 인덱스를 CSS 변수로 넘기는 스타일 헬퍼. */
function tileStyle(accent: string, index: number): CSSProperties {
  return { '--accent': accent, '--i': index } as CSSProperties;
}

/** 기술 카드 한 장(Liquid Glass 타일). */
function TechCard({
  item,
  index,
  planned = false,
}: {
  item: TechItem;
  index: number;
  planned?: boolean;
}): ReactElement {
  const logos = item.logos ?? (item.logo ? [item.logo] : []);
  const wide = WIDE_TILES.has(item.name);
  const className = [styles.card, styles.reveal, wide ? styles.cardWide : '', planned ? styles.cardPlanned : '']
    .filter(Boolean)
    .join(' ');

  return (
    <article className={className} style={tileStyle(item.accent, index)}>
      <span className={styles.badge} aria-hidden="true">
        {logos.map((src) => (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            key={src}
            className={styles.badgeImg}
            src={`/tech-logos/${src}`}
            alt=""
            loading="lazy"
            decoding="async"
          />
        ))}
      </span>
      <div className={styles.cardBody}>
        <span className={styles.cardNameRow}>
          <span className={styles.cardName}>{item.name}</span>
          {item.note ? <span className={styles.cardNote}>{item.note}</span> : null}
        </span>
        <span className={styles.cardTag}>{item.tagline}</span>
      </div>
      <p className={styles.cardDesc}>{item.description}</p>
    </article>
  );
}

/**
 * /tech — WWDC26 Liquid Glass 벤토 기술 쇼케이스(클라이언트).
 *
 * Returns:
 *   포인터 반응형 specular 히어로 + 다크 글래스 벤토 카드로 정리된 기술 스택 화면.
 */
export default function TechShowcase(): ReactElement {
  const heroRef = useRef<HTMLElement>(null);

  // Liquid Glass: 포인터를 따라 움직이는 specular 스포트라이트(데스크톱 + 모션 허용 시).
  useEffect(() => {
    const el = heroRef.current;
    if (!el) {
      return;
    }
    if (
      window.matchMedia('(prefers-reduced-motion: reduce)').matches ||
      !window.matchMedia('(pointer: fine)').matches
    ) {
      return;
    }

    const onMove = (event: PointerEvent): void => {
      const rect = el.getBoundingClientRect();
      const x = ((event.clientX - rect.left) / rect.width) * 100;
      const y = ((event.clientY - rect.top) / rect.height) * 100;
      el.style.setProperty('--mx', `${x.toFixed(2)}%`);
      el.style.setProperty('--my', `${y.toFixed(2)}%`);
    };

    el.addEventListener('pointermove', onMove);
    return () => el.removeEventListener('pointermove', onMove);
  }, []);

  return (
    <main className={styles.root}>
      <div className={styles.bg} aria-hidden="true">
        <span className={`${styles.orb} ${styles.orb1}`} />
        <span className={`${styles.orb} ${styles.orb2}`} />
        <span className={`${styles.orb} ${styles.orb3}`} />
      </div>

      <div className={styles.container}>
        {/* Hero */}
        <header className={styles.hero} ref={heroRef}>
          <span className={styles.heroGlow} aria-hidden="true" />
          <span className={`${styles.eyebrow} ${styles.reveal}`}>TECH STACK · 기술 스펙</span>
          <h1 className={`${styles.heroTitle} ${styles.reveal}`} style={{ '--i': 1 } as CSSProperties}>
            {productIntro.emoji} {productIntro.name}
            <span className={styles.accentDot}>.</span>
          </h1>
          <p className={`${styles.heroSubtitle} ${styles.reveal}`} style={{ '--i': 2 } as CSSProperties}>
            {productIntro.subtitle}
          </p>
          <p className={`${styles.heroText} ${styles.reveal}`} style={{ '--i': 3 } as CSSProperties}>
            {productIntro.paragraph}
          </p>
          <div className={`${styles.heroBadges} ${styles.reveal}`} style={{ '--i': 4 } as CSSProperties}>
            {productIntro.highlights.map((h) => (
              <span key={h} className={styles.heroBadge}>
                {h}
              </span>
            ))}
          </div>
          <div className={`${styles.heroActions} ${styles.reveal}`} style={{ '--i': 5 } as CSSProperties}>
            <a className={`${styles.heroLink} ${styles.heroLinkPrimary}`} href="#stack">
              기술 스택 둘러보기 ↓
            </a>
            <a className={`${styles.heroLink} ${styles.heroLinkGhost}`} href="/keynote">
              키노트 모드 →
            </a>
          </div>
          <div className={styles.scrollCue} aria-hidden="true">
            <i />
            SCROLL
          </div>
        </header>

        {/* Architecture overview */}
        <section className={styles.arch} aria-label="아키텍처 한눈에">
          <h2 className={styles.archTitle}>아키텍처 한눈에</h2>
          <div className={styles.archRail}>
            {architecture.map((step, i) => (
              <div
                key={step.title}
                className={`${styles.archNode} ${styles.reveal}`}
                style={{ '--i': i } as CSSProperties}
              >
                <span className={styles.archIcon} aria-hidden="true">
                  {step.icon}
                </span>
                <b className={styles.archName}>{step.title}</b>
                <span className={styles.archDesc}>{step.description}</span>
              </div>
            ))}
          </div>
        </section>

        {/* Used technologies, by category */}
        <div className={styles.sections} id="stack">
          {usedCategories.map((category) => (
            <section key={category.id} className={styles.section} aria-label={category.title}>
              <div className={styles.sectionHead}>
                <span className={styles.sectionIcon} aria-hidden="true">
                  {category.icon}
                </span>
                <div>
                  <span className={styles.sectionKicker}>{category.id}</span>
                  <h2 className={styles.sectionTitle}>{category.title}</h2>
                  <p className={styles.sectionBlurb}>{category.blurb}</p>
                </div>
              </div>
              <div className={styles.bento}>
                {category.items.map((item, i) => (
                  <TechCard key={item.name} item={item} index={i} />
                ))}
              </div>
            </section>
          ))}
        </div>

        {/* Planned / roadmap */}
        <section className={styles.planned} aria-label="고도화 로드맵 도입 예정 기술">
          <div className={styles.plannedHead}>
            <h2 className={styles.plannedTitle}>🚀 고도화 로드맵 · 도입 예정</h2>
            <span className={styles.plannedPill}>ROADMAP</span>
          </div>
          <p className={styles.plannedBlurb}>
            아래는 코드·문서(optional 의존성, 모바일 목표 아키텍처)에 설계돼 있고, 고도화 단계에서 본격
            도입될 기술이에요.
          </p>
          <div className={styles.bento}>
            {plannedItems.map((item, i) => (
              <TechCard key={item.name} item={item} index={i} planned />
            ))}
          </div>
        </section>

        {/* Footer */}
        <footer className={styles.footer}>
          <span className={styles.footerNote}>{footer.note}</span>
          <div className={styles.footerLinks}>
            <a className={styles.footerLink} href="/keynote">
              키노트 모드
            </a>
            <a className={styles.footerLink} href="/">
              홈으로
            </a>
            <a
              className={styles.footerLink}
              href="https://developer.apple.com/kr/wwdc26/"
              target="_blank"
              rel="noreferrer"
            >
              디자인 영감: WWDC26
            </a>
          </div>
          <p className={styles.footerDisclaimer}>{footer.disclaimer}</p>
        </footer>
      </div>
    </main>
  );
}
