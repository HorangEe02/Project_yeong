# CAD Vision React 전환 — 상세 구현 계획

> **목표**: Streamlit UI → React(Next.js) SPA로 전환하여 Stitch 프로토타입 1:1 재현
> **백엔드**: FastAPI + Core Pipeline 100% 재사용 (변경 없음)
> **예상 기간**: 14일 (Phase 0~6)
>
> **현황 (2026-04-06)**: v5.6 완료. Phase 0~5 완료, Phase 6(Docker) 미착수.
> - Dashboard, Registration, Search, Analysis, DXF Viewer, 3D Viewer, Tools 전체 구현
> - 다크/라이트 모드, Settings/User 패널, 3D 뷰어(Three.js), DXF SVG 뷰어
> - Gemma 4 + Qwen3.5 모델 선택, 카테고리 드롭다운, DXF Diff 상세 결과
> - v5.6: AI 응답 언어 선택(EN/KO/Both), IGES 2D 와이어프레임 감지, 글씨 크기 최소 12px

---

## Phase 0: 백엔드 API 갭 해결 (1일)

### 목표
React에서 필요하지만 현재 없는 3개 엔드포인트를 FastAPI에 추가

### 작업

| # | 엔드포인트 | 용도 | 시간 |
|---|-----------|------|------|
| 0-1 | `GET /api/v1/drawings/{id}/image` | 도면 이미지 파일 서빙 (PNG/JPG) | 2h |
| 0-2 | `GET /api/v1/drawings/{id}/thumbnail` | 썸네일 (256px, 캐시) | 1h |
| 0-3 | `POST /api/v1/drawings/register-batch` | 다중 파일 배치 등록 | 2h |

### 상세

#### 0-1: 이미지 파일 서빙
```python
# app/api/routers/drawings.py에 추가
from fastapi.responses import FileResponse

@router.get("/drawings/{drawing_id}/image")
async def get_drawing_image(drawing_id: str, pipeline=Depends(get_pipeline)):
    record = pipeline.get_record(drawing_id)
    if not record:
        raise HTTPException(404, "도면을 찾을 수 없습니다.")
    file_path = _resolve_image_path(record)
    if not file_path or not Path(file_path).exists():
        raise HTTPException(404, "이미지 파일을 찾을 수 없습니다.")
    return FileResponse(file_path, media_type="image/png")
```

#### 0-2: 썸네일 서빙
```python
@router.get("/drawings/{drawing_id}/thumbnail")
async def get_drawing_thumbnail(drawing_id: str, pipeline=Depends(get_pipeline)):
    # UniversalRenderer.render_thumbnail() 활용
    record = pipeline.get_record(drawing_id)
    thumb = pipeline.renderer.render_thumbnail(record.file_path)
    return FileResponse(thumb, media_type="image/png")
```

#### 0-3: 배치 등록
```python
@router.post("/drawings/register-batch")
async def register_batch(
    files: list[UploadFile] = File(...),
    category: str = Query(""),
    pipeline=Depends(get_pipeline),
):
    results = []
    for file in files:
        tmp = save_upload(file)
        try:
            record = pipeline.register_drawing(tmp, category=category, use_llm=False)
            results.append({"status": "ok", "drawing_id": record.drawing_id})
        except Exception as e:
            results.append({"status": "error", "file": file.filename, "error": str(e)})
        finally:
            tmp.unlink(missing_ok=True)
    return results
```

### 완료 기준
- `curl http://localhost:8000/api/v1/drawings/{id}/image` → 이미지 바이너리
- `curl http://localhost:8000/api/v1/drawings/{id}/thumbnail` → 썸네일 바이너리
- 기존 857 테스트 + 신규 6개 = 863 통과

---

## Phase 1: 프로젝트 초기 설정 (0.5일)

### 목표
Next.js + TypeScript + Tailwind 프로젝트 생성 및 API 타입 자동 생성

### 작업

| # | 작업 | 시간 |
|---|------|------|
| 1-1 | Next.js 14 App Router 프로젝트 생성 | 0.5h |
| 1-2 | Tailwind CSS + 디자인 토큰 설정 | 1h |
| 1-3 | OpenAPI → TypeScript 타입 자동 생성 | 1h |
| 1-4 | API 클라이언트 모듈 설정 | 1h |

### 상세

#### 1-1: 프로젝트 생성
```bash
cd "<EXTERNAL_DRIVE>/00_work_out/01_complete/me/01_CAD"
npx create-next-app@latest web --typescript --tailwind --eslint --app --src-dir
```

#### 1-2: Tailwind 디자인 토큰
```typescript
// web/tailwind.config.ts
const config = {
  theme: {
    extend: {
      colors: {
        background: '#0e0e0e',
        'surface-1': '#131313',
        'surface-2': '#1a1a1a',
        'surface-3': '#262626',
        outline: '#484847',
        primary: '#5eb4ff',
        'primary-dark': '#2aa7ff',
        secondary: '#ff8a00',
        tertiary: '#bca2ff',
        error: '#ff716c',
        success: '#4ade80',
      },
      fontFamily: {
        heading: ['Space Grotesk', 'sans-serif'],
        body: ['Inter', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
    },
  },
};
```

#### 1-3: OpenAPI → TypeScript
```bash
# FastAPI가 실행 중이어야 함
npx openapi-typescript http://localhost:8000/openapi.json -o web/src/lib/api-types.ts
```

#### 1-4: API 클라이언트
```typescript
// web/src/lib/api.ts
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000/api/v1';

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  });
  if (!res.ok) throw new Error(`API Error: ${res.status}`);
  return res.json();
}

export function apiStreamSSE(path: string, body: FormData, onToken: (t: string) => void) {
  // SSE 스트리밍 구현
}
```

### 완료 기준
- `npm run dev` → http://localhost:3000 정상 접속
- TypeScript 타입 파일 자동 생성 완료
- `apiFetch('/health')` 호출 성공

---

## Phase 2: 레이아웃 쉘 (1일)

### 목표
TopNav + Sidebar + StatusFooter + 페이지 라우팅 구조 완성

### 작업

| # | 작업 | Stitch 대응 | 시간 |
|---|------|------------|------|
| 2-1 | TopNav 컴포넌트 | 글로벌 검색 바 + Ollama 모델 + Connected 뱃지 | 2h |
| 2-2 | Sidebar 컴포넌트 | ENGINEERING TERMINAL + 7페이지 네비 + NEW PROJECT | 2h |
| 2-3 | StatusFooter 컴포넌트 | 레이턴시 + 인덱스 + GIN + VECTOR SYNC | 1h |
| 2-4 | Layout 조합 + 라우팅 | App Router layout.tsx | 1h |

### 파일 구조
```
web/src/
├── app/
│   └── layout.tsx           # TopNav + Sidebar + Footer + {children}
├── components/
│   └── layout/
│       ├── TopNav.tsx
│       ├── Sidebar.tsx
│       └── StatusFooter.tsx
```

### 완료 기준
- 모든 페이지에서 TopNav/Sidebar/Footer가 고정 표시
- 7개 페이지 라우트 (`/`, `/register`, `/search`, `/analysis`, `/viewer/dxf`, `/viewer/stl`, `/tools`)
- Sidebar 네비게이션 클릭 → 페이지 전환

---

## Phase 3: Dashboard 페이지 (1일)

### 목표
Stitch Dashboard 프로토타입 1:1 재현

### 작업

| # | 컴포넌트 | Stitch 요소 | 시간 |
|---|---------|------------|------|
| 3-1 | KPICard | 4열 카드 (68,649 +12% / 81 / 3 IMAGE TEXT GNN / 0.104s Fast) | 1.5h |
| 3-2 | CategoryChart | 수평 바 (SHAFTS & ROTORS 32,410 UNITS) + BAR/TREND 토글 | 2h |
| 3-3 | OllamaStatus | Connected 점 + Qwen3.5 9b + RAM 바 + Restart 버튼 | 1.5h |
| 3-4 | ActivityTable | 6열 테이블 (FILE PREVIEW / ID / FORMAT / CATEGORY / YOLO / TIMESTAMP) | 2h |

### API 호출
```typescript
// useStats.ts
const { data: stats } = useQuery({
  queryKey: ['stats'],
  queryFn: () => apiFetch<StatsResponse>('/stats'),
  refetchInterval: 30000, // 30초 폴링
});

// useDrawings.ts
const { data: drawings } = useQuery({
  queryKey: ['drawings', page],
  queryFn: () => apiFetch<PaginatedResponse>(`/drawings?page=${page}&page_size=10`),
});
```

### 완료 기준
- KPI 카드 4열 실제 데이터 표시
- 카테고리 분포 차트 애니메이션 바
- Ollama 상태 실시간 반영
- Activity 테이블 최근 10건 + FILE PREVIEW 열 (썸네일 API)

---

## Phase 4: Search 페이지 (2일)

### 목표
Stitch Multi-channel Search 프로토타입 1:1 재현

### 작업

| # | 컴포넌트 | Stitch 요소 | 시간 |
|---|---------|------------|------|
| 4-1 | SearchBar | 전폭 입력 + IMAGE UPLOAD + DXF UPLOAD + EXECUTE SEARCH | 2h |
| 4-2 | FilterPanel | FILE FORMAT 체크박스 + CATEGORY 리스트(81 TOTAL) + MATERIAL 칩 + DATE RANGE | 3h |
| 4-3 | ResultCard | 3열 그리드, 썸네일(그레이스케일+블루 틴트), ★ 98.4% MATCH 뱃지, 제목+카테고리+부품번호+크기+수정일 | 4h |
| 4-4 | VectorPreview | 우하단 플로팅 패널 (Embedding Model: CLIP-ViT-L/14, Similarity: 0.9982, 92% Confidence) | 2h |
| 4-5 | SemanticBadges | 시맨틱 확장 뱃지 (보라색) | 1h |
| 4-6 | SortDropdown | SORT BY: SIMILARITY SCORE ∨ | 0.5h |

### API 호출
```typescript
// useSearch.ts
const searchMutation = useMutation({
  mutationFn: (query: UnifiedSearchRequest) =>
    apiFetch<UnifiedSearchResultResponse[]>('/drawings/search/unified', {
      method: 'POST',
      body: JSON.stringify(query),
    }),
});
```

### Stitch 특수 요소
- **검색 바**: 단일 입력 필드 + 인라인 IMAGE/DXF 업로드 버튼 (탭 분리 아님)
- **필터 패널**: 좌측 고정 사이드바 (현재 Streamlit의 탭 내부 필터와 다름)
- **결과 카드 호버**: 이미지 opacity 0.6→1.0 + scale(1.05) 트랜지션
- **하단 상태 바**: 서버 레이턴시 실시간 갱신

### 완료 기준
- 텍스트 검색 → 3열 카드 그리드 결과
- 이미지 파일 드래그앤드롭 → 이미지 검색
- Material 칩 필터 동작
- Vector Preview 패널 결과 카드 클릭 시 표시

---

## Phase 5: Analysis 페이지 (2일)

### 목표
Stitch Drawing Analysis 프로토타입 1:1 재현

### 작업

| # | 컴포넌트 | Stitch 요소 | 시간 |
|---|---------|------------|------|
| 5-1 | DrawingViewer | Canvas 기반 줌/팬/회전 + 4버튼 툴바 + CURSOR POSITION + LAYER STATUS | 4h |
| 5-2 | AnalysisSidebar | Analysis Overview + LIVE AI FEED 뱃지 + SYSTEM NARRATIVE + EXTRACTED METADATA 테이블 + CLASS PREDICTION 바 | 4h |
| 5-3 | QAPanel | TECHNICAL ASSISTANT + Terminal Session: Active + 채팅 (SSE 스트리밍) + 입력 바 + 전송 버튼 | 4h |
| 5-4 | 6:4 레이아웃 | CSS Grid `grid-template-columns: 1fr 380px` | 1h |

### SSE 스트리밍 구현
```typescript
// useAnalysisStream.ts
export function useAnalysisStream() {
  const [tokens, setTokens] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);

  const startStream = async (file: File, question: string) => {
    setIsStreaming(true);
    setTokens('');
    const formData = new FormData();
    formData.append('file', file);

    const res = await fetch(`${API_BASE}/drawings/analyze/stream?question=${encodeURIComponent(question)}`, {
      method: 'POST',
      body: formData,
    });

    const reader = res.body?.getReader();
    const decoder = new TextDecoder();

    while (reader) {
      const { done, value } = await reader.read();
      if (done) break;
      const chunk = decoder.decode(value);
      // SSE 형식: "data: {"token": "..."}\n\n"
      for (const line of chunk.split('\n')) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6);
          if (data === '[DONE]') { setIsStreaming(false); break; }
          try {
            const { token } = JSON.parse(data);
            setTokens(prev => prev + token);
          } catch {}
        }
      }
    }
  };

  return { tokens, isStreaming, startStream };
}
```

### 완료 기준
- 이미지 업로드 → 6:4 분할 (좌: DrawingViewer, 우: Analysis Overview)
- YOLO 분류 → CLASS PREDICTION 바 실시간 표시
- 설명 생성 버튼 → SSE 스트리밍으로 SYSTEM NARRATIVE에 토큰 순차 표시
- Q&A 입력 → 스트리밍 응답 + 채팅 히스토리

---

## Phase 6: 나머지 페이지 + Docker (3.5일)

### 6-A: Registration 페이지 (1일)

| # | 컴포넌트 | 시간 |
|---|---------|------|
| 6A-1 | UploadZone | 드래그앤드롭 (react-dropzone), 12종 포맷 | 2h |
| 6A-2 | PipelineConfig | GNN/AI Analysis 토글 + Active Model 표시 | 1h |
| 6A-3 | ProcessingQueue | 3개 상태(PROCESSING/INDEXED/QUEUED), 4단계 바, 실시간 업데이트 | 3h |
| 6A-4 | BatchUpload | Folder Bulk Upload 버튼 + Clear Queue + Start Indexing | 1h |

### 6-B: DXF Viewer (1일)

| # | 컴포넌트 | 시간 |
|---|---------|------|
| 6B-1 | SVGRenderer | API `/viewer/dxf` → SVG 렌더링 | 3h |
| 6B-2 | LayerPanel | 레이어 토글 체크박스 + 엔티티 통계 | 2h |
| 6B-3 | EntityTable | 엔티티 타입별 건수 테이블 | 1h |

### 6-C: 3D Viewer (1일)

| # | 컴포넌트 | 시간 |
|---|---------|------|
| 6C-1 | STLViewer | React Three Fiber + OrbitControls | 4h |
| 6C-2 | MeshInfo | 삼각형 수, 꼭짓점 수, BBox, 파일 크기 | 1h |
| 6C-3 | WireframeToggle | 와이어프레임/솔리드 토글 | 1h |

### 6-D: Tools 페이지 (0.5일)

| # | 컴포넌트 | 시간 |
|---|---------|------|
| 6D-1 | BOMExtractor | 도면 선택 + BOM 테이블 | 1h |
| 6D-2 | DimensionCompare | 양쪽 도면 선택 + 비교 결과 | 1h |
| 6D-3 | DXFDiff | 2파일 업로드 + diff 결과 | 1h |
| 6D-4 | VersionHistory + FeedbackStats | 버전 타임라인 + 피드백 통계 | 1h |

---

## Phase 7: Docker + 배포 (1일)

### 작업

| # | 작업 | 시간 |
|---|------|------|
| 7-1 | React Dockerfile (multi-stage build) | 1h |
| 7-2 | docker-compose.yml 업데이트 (cad-web 서비스 추가) | 1h |
| 7-3 | Nginx 리버스 프록시 (API + React 통합) | 1h |
| 7-4 | 환경변수 + 빌드 최적화 | 1h |
| 7-5 | E2E 테스트 (Playwright) | 2h |

### Docker 구성
```yaml
# docker-compose.yml
services:
  cad-api:
    build: ./app
    ports: ["8000:8000"]
    # ... (기존 유지)

  cad-web:  # NEW (Streamlit 대체)
    build: ./web
    ports: ["3000:3000"]
    environment:
      - NEXT_PUBLIC_API_BASE_URL=http://cad-api:8000/api/v1
    depends_on:
      cad-api:
        condition: service_healthy

  cad-chromadb:
    # ... (기존 유지)
```

### React Dockerfile
```dockerfile
# web/Dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./
EXPOSE 3000
CMD ["npm", "start"]
```

---

## 전체 타임라인

```
Day 1:   Phase 0 (API 갭) + Phase 1 (프로젝트 설정)
Day 2:   Phase 2 (레이아웃 쉘)
Day 3:   Phase 3 (Dashboard)
Day 4-5: Phase 4 (Search)
Day 6-7: Phase 5 (Analysis + SSE)
Day 8:   Phase 6-A (Registration)
Day 9:   Phase 6-B (DXF Viewer)
Day 10:  Phase 6-C (3D Viewer)
Day 11:  Phase 6-D (Tools)
Day 12:  Phase 7 (Docker + 배포)
Day 13:  전체 통합 테스트 + 버그 수정
Day 14:  최종 QA + 문서 업데이트
```

---

## 리스크 및 완화 전략

| 리스크 | 영향 | 완화 |
|--------|------|------|
| SSE 스트리밍 React 통합 복잡 | Phase 5 지연 | fetch + ReadableStream 먼저, EventSource 폴백 |
| Three.js 3D 뷰어 성능 | Phase 6-C 지연 | react-three-fiber/drei 사용, LOD 적용 |
| 이미지 서빙 CORS 이슈 | Phase 0에서 발견 | FastAPI FileResponse에 CORS 헤더 추가 |
| TypeScript 타입 수동 작업 | Phase 1 지연 | openapi-typescript 자동 생성 + 수동 보정 |
| Streamlit 병행 운영 필요 | 전환 중 서비스 중단 | React 완성까지 Streamlit 유지 (포트 8501) |

---

## 의존성

```json
{
  "dependencies": {
    "next": "^14.2",
    "react": "^18.3",
    "react-dom": "^18.3",
    "@tanstack/react-query": "^5.0",
    "recharts": "^2.10",
    "@react-three/fiber": "^8.15",
    "@react-three/drei": "^9.88",
    "three": "^0.159",
    "react-dropzone": "^14.2",
    "lucide-react": "^0.300"
  },
  "devDependencies": {
    "typescript": "^5.3",
    "tailwindcss": "^3.4",
    "openapi-typescript": "^6.7",
    "@playwright/test": "^1.40"
  }
}
```
