# React + TypeScript + Vite

This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Oxc](https://oxc.rs)
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/)

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the ESLint configuration

If you are developing a production application, we recommend updating the configuration to enable type-aware lint rules:

```js
export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      // Other configs...

      // Remove tseslint.configs.recommended and replace with this
      tseslint.configs.recommendedTypeChecked,
      // Alternatively, use this for stricter rules
      tseslint.configs.strictTypeChecked,
      // Optionally, add this for stylistic rules
      tseslint.configs.stylisticTypeChecked,

      // Other configs...
    ],
    languageOptions: {
      parserOptions: {
        project: ['./tsconfig.node.json', './tsconfig.app.json'],
        tsconfigRootDir: import.meta.dirname,
      },
      // other options...
    },
  },
])
```

You can also install [eslint-plugin-react-x](https://github.com/Rel1cx/eslint-react/tree/main/packages/plugins/eslint-plugin-react-x) and [eslint-plugin-react-dom](https://github.com/Rel1cx/eslint-react/tree/main/packages/plugins/eslint-plugin-react-dom) for React-specific lint rules:

```js
// eslint.config.js
import reactX from 'eslint-plugin-react-x'
import reactDom from 'eslint-plugin-react-dom'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      // Other configs...
      // Enable lint rules for React
      reactX.configs['recommended-typescript'],
      // Enable lint rules for React DOM
      reactDom.configs.recommended,
    ],
    languageOptions: {
      parserOptions: {
        project: ['./tsconfig.node.json', './tsconfig.app.json'],
        tsconfigRootDir: import.meta.dirname,
      },
      // other options...
    },
  },
])
```

## 배포 (Deployment)

이 앱은 **Vercel** 프로젝트 `ajin-ai-assistant-frontend` 로 배포된다.
프로덕션 도메인: https://ajin-ai-assistant-frontend.vercel.app

### 정상 배포 흐름
- `main` 에 머지(또는 push)하면 **Vercel Git 연동**이 자동으로 `frontend/` 를
  **원격 빌드**해 프로덕션에 배포한다. 수동 작업 불필요.
- Vercel 프로젝트 설정의 **Root Directory = `frontend`** (레포 루트 기준).

### 주의 — 로컬 CLI 배포 함정
- ❌ repo 루트에서 `vercel build` + `vercel deploy --prebuilt` (로컬 prebuilt) 로
  올리지 말 것. 오래된 산출물이 프로덕션에 올라가 `/showcase`·`/tech` 가 사라진
  회귀 사고가 있었다.
- ❌ `vercel` 을 `frontend/` 에서 직접 실행 → 서버 설정이 Root Directory=`frontend`
  라 `frontend/frontend` 경로 중복 에러.
- ℹ️ 레포 루트에도 `ajin-ai-assistant-react` Vercel 프로젝트의 `.vercel` 링크가
  있으나 프론트 프로덕션과 무관. 프론트는 `ajin-ai-assistant-frontend` 만 쓴다.

### 웹훅 누락 시 복구
- 머지했는데 새 배포가 안 보이면(웹훅 드롭): Vercel 대시보드 → Deployments →
  최신 `main` 커밋의 ⋯ → **Redeploy**(빌드 캐시 끄기). Git 소스에서 다시 빌드된다.
- 또는 trivial 커밋을 PR 로 머지해 재트리거한다.
