# 2026-06-01 다음 섹션 인계 프롬프트

> 작성 기준: 2026-06-01
> 목적: 다음 Codex 섹션에서 Android/iOS 재설치 상태, 갤러리 샘플, Vercel `project-yeong` 연동을 이어서 작업하기 위한 handoff

---

## 이어서 사용할 프롬프트

아래 내용을 다음 섹션 첫 메시지로 사용한다.

```text
Lemon-Aid repo에서 이어서 작업해줘.

Repo root:
/Volumes/Corsair EX400U Media/yeong_offload/99_me/00_github/03_lemon_healthcare/Lemon-Aid

현재 브랜치:
docs/docs-2026-05-31-backend-ocr-security

현재 주요 작업 상태:
1. Android Pixel 10 Pro Emulator
   - `Pictures/LemonAID-Readable-Labels` 앨범에 영양제 성분표/라벨 이미지 20장 추가 완료
   - MediaStore 기준 20장 인덱싱 확인
   - `com.example.lemon_aid_mobile.dev` 삭제 후 `app-dev-debug.apk` 재설치 완료

2. iOS Simulator
   - `iPhone 17 Pro` UDID `7B2E1A72-B3C9-4102-8E3C-0009CCBFB4FB` 부팅 확인
   - Flutter Runner bundle `com.example.lemonAidMobile` 삭제 후 재설치/실행 완료
   - 중복으로 남아 있던 예전 native bundle `yeongs.Lemon-Aid` 제거 완료
   - 현재 촬영 화면의 `Mac camera bridge 8755` 오류는 bridge 프로세스 미실행 상태로 분류

3. Vercel
   - `frontend` 로컬 디렉터리를 `yeong0202-s-projects/project-yeong`에 연결 완료
   - Vercel 프로젝트 설정:
     - Root Directory: `03_lemon_healthcare/Lemon-Aid/frontend`
     - Framework: Next.js
     - Node.js: 24.x
     - Build Command: `npm run build`
   - `npm run typecheck`, `npm run build`, `vercel pull --environment=preview --yes` 통과
   - Preview env는 아직 0개라 OCR/YOLO/Supabase 원격 smoke는 미완료

4. 모바일 분석 결과 검토 UI
   - 분석 결과 요약 카드 클릭 시 OCR 근거 텍스트 표 표시 완료
   - 상세 성분 및 함량 표에 성분별 체크박스 추가 완료
   - 체크된 성분이 1개이면 해당 성분만 수정하는 단건 편집 흐름 추가 완료
   - 섭취 방법/주의사항이 이미지에 없으면 `해당 이미지에는 해당하는 내용이 없습니다` 표시
   - 다중 영양제 분석 결과는 상단 탭으로 개별 결과 전환 가능
   - 검증:
     - `flutter test test/widget/analysis_result_screen_test.dart` 통과
     - `flutter analyze lib/screens/analysis_result_screen.dart test/widget/analysis_result_screen_test.dart` 통과
   - `git diff --check` 통과

5. Backend taxonomy/API filter
   - 영양제 category catalog와 음식 cuisine/course/item catalog 모델/마이그레이션 추가
   - `GET /api/v1/supplements/categories`
   - `GET /api/v1/meals/cuisines`
   - `GET /api/v1/meals/foods`
   - `GET /api/v1/supplements` category/q filter
   - `GET /api/v1/meals` cuisine/course/catalog item/date filter
   - `meal:read` scope 추가, 기존 식단 분석/확정은 `meal:write` 유지
   - stale taxonomy filter는 `422 taxonomy_filter_not_found` 반환
   - 검증:
     - `.venv/bin/python -m ruff check Nutrition-backend/src` 통과
     - targeted pytest 42개 통과

6. 모바일 background analysis / chat handoff
   - 새 분석 시작 시 이전 preview/result를 즉시 비워 stale result 오인을 줄임
   - 분석 완료 notice에서 `결과 보기` action으로 결과 화면 이동 가능
   - local LLM/impact check가 실패해도 저장된 supplement 결과는 유지
   - chat 탭으로 사용자 안전 설명 draft를 1회성 전달 가능
   - 검증:
     - targeted `flutter test` 통과
     - targeted `flutter analyze` 통과

남은 blocker:
- Vercel Preview에 아래 필수 env가 없다.
  - `LEMON_API_BASE_URL`
  - `NEXT_PUBLIC_SUPABASE_URL`
  - `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`
- `LEMON_API_BASE_URL`은 Vercel serverless runtime에서 접근 가능한 public HTTPS `/api/v1` URL이어야 한다.
- 로컬 `.env.local`의 loopback/private URL은 Vercel Preview에 넣으면 안 된다.
- 실제 물리 iPhone `박준영의 iPhone`은 아직 `flutter devices`에서 연결되지 않는다.
- 실제 기기에서 OCR 근거 표/성분 체크박스/다중 영양제 탭 수동 QA는 아직 별도 실행하지 않았다.
- 다중 사진을 여러 영양제로 자동 그룹핑하는 UX는 per-image preview/tab과 backend merged preview 계약이 섞일 수 있으므로, 실제 4장/3영양제 시나리오에서 추가 확인이 필요하다.

다음 작업 우선순위:
1. 사용자가 Vercel Preview env 값을 제공하거나, public HTTPS backend가 준비되면 값 노출 없이 `vercel env add <KEY> preview`로 등록한다.
2. `vercel pull --environment=preview --yes` 후 `npm run vercel:check-env`를 실행한다.
3. 통과하면 `npm run vercel:preflight`를 실행한다.
4. 명시 승인을 받은 뒤 Preview deploy를 진행한다.
5. Preview URL이 나오면 `LEMON_WEB_SMOKE_URL=<preview-url> npm run smoke:remote`를 실행한다.
6. iOS Simulator camera preview가 필요하면 Mac camera bridge 8755 프로세스를 먼저 실행한다.
7. taxonomy 모바일 필터 UI 연결은 다음 단계로 분리한다.
8. 여러 영양제 이미지를 한 번에 업로드하는 경우, backend batch 계약이 `한 영양제 보강 세션`인지 `여러 영양제 그룹`인지 먼저 확정한 뒤 UI grouping을 보완한다.

규칙:
- raw OCR text, provider payload, image 원문, Supabase key, env secret, ngrok token은 출력하거나 stage하지 않는다.
- `.env`, `.env.local`, `.vercel/.env.*.local`, `.vercel/output`, raw screenshots, private dataset은 stage 금지다.
- 기존 mobile/iOS/backend dirty changes는 사용자 변경일 수 있으므로 임의로 되돌리지 않는다.
- todo-list 문서는 repo-local `outputs/todo-list/YYYY-MM-DD/` 안에 작성한다.
- 커밋 메시지는 Conventional Commits 형식으로 작성하고, body에는 왜 필요한 변경인지 적는다.
- 작업 전 `git status --short --branch`로 repo 상태를 확인한다.
```

---

## Git/GitHub 규칙

- true repo root는 `/Volumes/Corsair EX400U Media/yeong_offload/99_me/00_github/03_lemon_healthcare/Lemon-Aid`다.
- team remote와 personal remote를 혼동하지 않는다.
  - `origin`: `https://github.com/Lemon-Aid-KDT/Lemon-sin.git`
  - `personal`: `https://github.com/HorangEe02/Project_yeong.git`
- stage는 요청 범위 파일만 제한적으로 진행한다.
- commit message는 Conventional Commits를 사용한다.
- push는 사용자가 명시적으로 요청한 경우에만 진행한다.

예상 commit scope:

```text
docs(todo): record 2026-06-01 mobile reinstall and Vercel link status

Document the emulator gallery sample setup, Android/iOS reinstall verification,
and project-yeong Vercel link state so the next section can continue from
confirmed environment facts without exposing secrets or raw OCR data.
```
