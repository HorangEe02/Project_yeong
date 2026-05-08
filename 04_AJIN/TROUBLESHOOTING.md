# 문제 해결 가이드

흔한 문제와 진단·해결 방법.

## 1. 백엔드 부팅 실패

### `ModuleNotFoundError: No module named 'langchain_chroma'`
slim Docker 빌드는 chromadb 의존성 미포함입니다. 해결:
- 로컬: `pip install -r requirements.txt` (개발용 풀 의존성)
- Cloud Run prod: 정상 (Feature A 비활성 모드 — `ENABLE_FEATURE_A=false`)

### `ImportError: cannot import name 'ollama_headers' from 'config'`
`config.py` 의 `ollama_headers()` 정의가 누락된 경우. `ajin-ai-assistant-react/config.py` 의 line 27 부근 확인.

### `ModuleNotFoundError: meilisearch`
`pip install meilisearch` 또는 `pip install -r requirements.txt`. Docker 환경에서는 `requirements-cloudrun.txt` 에 포함.

## 2. LLM 호출 실패

### 응답에 `provider: gemini` 만 표시 (의도: ollama)
`LLM_ROUTER_PRIMARY` 환경변수 확인:
```bash
gcloud run services describe ajin-backend --region asia-northeast3 --project ajin-cb \
  --format='value(spec.template.spec.containers[0].env)' | tr ';' '\n' | grep LLM_ROUTER
```
- 비어있거나 `gemini` 면 → `gcloud run services update --update-env-vars LLM_ROUTER_PRIMARY=ollama`

### `Ollama HTTP 403: Forbidden — invalid or missing X-AJIN-Secret header`
Caddy 가 secret 검증 거부. 원인:
1. Cloud Run env `AJIN_OLLAMA_SECRET` ≠ `~/.config/ajin/ollama-secret` 의 값
2. 코드가 헤더 부착 안 함

검증:
```bash
# 로컬
SECRET=$(cat ~/.config/ajin/ollama-secret)
curl -sf -H "X-AJIN-Secret: $SECRET" http://127.0.0.1:8434/api/version  # 200 기대

# Cloud Run env
gcloud run services describe ajin-backend --region asia-northeast3 \
  --format='value(spec.template.spec.containers[0].env)' | grep AJIN_OLLAMA_SECRET
```

해결: 두 값 동기화 + Caddy reload + Cloud Run revision rollout.

### `OllamaHealthMiddleware: AI_UNAVAILABLE 503`
Mac Ollama 도달성 실패. 확인 순서:
1. `~/Library/LaunchAgents/com.ajin.caddy.plist` 로드 상태: `launchctl list | grep com.ajin`
2. cloudflared 살아있나: `pgrep cloudflared`
3. tunnel URL 동기화: `cat ~/.config/ajin/last_tunnel_url.txt` ↔ Cloud Run `OLLAMA_BASE_URL` 일치
4. `/api/version` direct 호출:
   ```bash
   TUNNEL=$(cat ~/.config/ajin/last_tunnel_url.txt)
   SECRET=$(cat ~/.config/ajin/ollama-secret)
   curl -sf -H "X-AJIN-Secret: $SECRET" "$TUNNEL/api/version"
   ```

## 3. cloudflared / tunnel URL

### URL 이 자주 바뀜
임시 trycloudflare URL 은 cloudflared 재시작마다 변경됩니다. Watchdog 가 자동으로 Cloud Run env 갱신:
```bash
tail -20 ~/.config/ajin/watchdog.stdout.log
```

### Watchdog 가 Cloud Run env 갱신 실패
`gcloud auth application-default print-access-token` 으로 ADC 만료 확인. 만료 시:
```bash
gcloud auth application-default login
launchctl unload ~/Library/LaunchAgents/com.ajin.tunnel-watchdog.plist
launchctl load ~/Library/LaunchAgents/com.ajin.tunnel-watchdog.plist
```

### Mac 재부팅 후 cloudflared 안 뜸
launchd 등록 확인:
```bash
launchctl list | grep com.ajin
# com.ajin.caddy / com.ajin.tunnel-watchdog 둘 다 보여야 함
```
없으면:
```bash
launchctl load ~/Library/LaunchAgents/com.ajin.caddy.plist
launchctl load ~/Library/LaunchAgents/com.ajin.tunnel-watchdog.plist
```

## 4. Frontend

### TopBar LLM 라벨이 `GEMINI · CLOUD` 로 표시 (Mac 동작 중인데)
`/api/draft/diagnose` 가 ollama.ok=false 반환. 원인 같음 — secret header 누락. 위 [Ollama HTTP 403] 절차로.

또는 frontend 가 캐시된 응답 사용 — `Cmd+Shift+R` 로 hard reload.

### `npm run build` 실패: `Cannot find module @api/client`
`tsconfig.json` / `vite.config.ts` 의 path alias 확인. `frontend/` 안에서 실행 필수:
```bash
cd frontend
npm run build
```

### Firebase deploy 실패: `HTTP Error: 401`
Firebase 인증 만료:
```bash
firebase logout
firebase login
firebase use ajin-cb
firebase deploy --only hosting
```

## 5. Docker / Cloud Build

### `COPY data/intent_ml/: file does not exist`
`.dockerignore` 또는 `.gcloudignore` 에서 ML 디렉토리 차단 + Dockerfile 의 `data/intent_ml/` COPY 가 함께 시도. 해결:
- `.gcloudignore` 의 `data/intent_ml/` 등 ML 디렉토리 줄 삭제 또는
- Dockerfile 의 해당 COPY 라인 삭제

### Cloud Build SHORT_SHA 누락 에러
`gcloud builds submit --config cloudbuild.yaml` 직접 호출 대신 `bash scripts/deploy-backend.sh` 사용. wrapper 가 SHORT_SHA 자동 처리.

### Cloud Run revision traffic 0% 받음
`gcloud run services update-traffic ajin-backend --to-latest` 또는 `--to-revisions <name>=100`.

## 6. 인증 / 세션

### 로그인 후 401 반복
JWT 만료 또는 Firebase 세션 끊김. axios interceptor 가 자동 재발급 시도하지만 실패 시 `/login` 리다이렉트. 원인:
- `AJIN_JWT_SECRET` 환경변수 변경 → 기존 토큰 invalid → 정상 (재로그인 필요)
- Firebase project mismatch — `.env` 의 `VITE_FIREBASE_*` 값 확인

### 로그인 화면 무한 루프
브라우저 localStorage 의 `auth-store` 손상. DevTools → Application → Local Storage → `https://ajin-cb.web.app` → 모두 삭제 → 재시도.

## 7. Ollama

### `Error: mkdir /Users/<user>/.ollama: file exists`
`~/.ollama` 가 깨진 심볼릭 링크. 확인:
```bash
ls -la ~/.ollama
# lrwxr-xr-x ... -> /Volumes/SomeDisk/.ollama (broken)
```
해결:
```bash
rm ~/.ollama
mkdir ~/.ollama
pkill -x ollama
ollama serve &
ollama pull qwen3.5:9b  # 등 필요한 모델 재다운로드
```

또는 외장 디스크에 모델 데이터가 있다면 rsync 로 옮기기 — `MIGRATE_OLLAMA_DATA.md` 참고.

### Ollama OOM (24GB Mac 메모리 부족)
- `OLLAMA_MAX_LOADED_MODELS=1` 으로 동시 로드 제한
- `OLLAMA_KEEP_ALIVE=10m` 으로 unload 시간 단축
- 다른 메모리 큰 앱(Xcode, Chrome 등) 종료

### `0 models` 표시
`ollama list` 결과 비어있다면:
- `ollama pull qwen3.5:9b` 등 수동 다운로드
- Caddy 경유 시 secret 헤더 미부착이면 0 models 반환 — secret 헤더 확인

## 8. 일반

### `command not found: caddy`
`brew install caddy`. brew 미설치면 https://brew.sh

### `Permission denied: secrets/ollama-secret`
```bash
chmod 600 ~/.config/ajin/ollama-secret
chmod 600 secrets/*
```

### Mac sleep 후 cloudflared 끊김
시스템 환경설정 → 잠금 화면 → "디스플레이가 꺼지면 Mac을 잠자기 모드로 두기" → **사용 안 함**.
또는 백그라운드에서:
```bash
caffeinate -d -i &
```

### gcloud / firebase 명령 결과 한글 깨짐
`export LANG=ko_KR.UTF-8` 또는 `LC_ALL=en_US.UTF-8` 으로 통일.

---

추가 문제 발생 시 [GitHub Issues](https://github.com/HorangEe02/Project_yeong/issues) 에 stacktrace + 환경 정보(`gcloud --version`, `node --version`, OS) 포함해서 보고해 주세요.
