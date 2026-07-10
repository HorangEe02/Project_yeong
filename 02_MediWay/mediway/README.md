# MediWay — 앱 루트

병원 동선 안내 + 고령자 접근성 웹앱의 애플리케이션 본체입니다.
프로젝트 소개·아키텍처·브랜치 전략은 상위 [02_MediWay/README.md](../README.md)를 참고하세요.

## 빠른 시작

```bash
npm install
cp .env.local.example .env.local   # Firebase 설정 입력
npm run dev                        # 개발 서버
npm run test                       # Vitest 단위 테스트
npm run build                      # 프로덕션 빌드
```

## 구성

- `src/` — pages · components · services · hooks · stores · types · utils · config
- `functions/` — Firebase Cloud Functions (Kakao·Naver OAuth), 별도 `npm install` 필요
- `docs/` — 단계별 구현 스펙 (PHASE_A ~ PHASE_G)
- `e2e/` — 보안 규칙 E2E 테스트 하네스 (배포 자산에서 제외)
