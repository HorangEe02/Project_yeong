# 운영 배포 가이드

> Cloud Run + Firebase Hosting + Mac Ollama (Plan A 변형) 배포 절차.

## 1. 사전 준비 (1회)

### 1.1 GCP 프로젝트
```bash
# 프로젝트 생성 + billing 연결
gcloud projects create ajin-cb
gcloud config set project ajin-cb

# 필요한 API 활성화
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  firestore.googleapis.com \
  secretmanager.googleapis.com \
  firebase.googleapis.com

# Artifact Registry 생성 (백엔드 이미지 저장)
gcloud artifacts repositories create ajin-backend \
  --repository-format=docker \
  --location=asia-northeast3
```

### 1.2 Firebase 프로젝트
- https://console.firebase.google.com/project/ajin-cb 에서 Hosting 활성화
- Authentication → Sign-in method → Google 활성화
- Firestore Database 생성 (asia-northeast3)
- `firebase login` + `firebase use ajin-cb`

### 1.3 Secrets (GCP Secret Manager)
```bash
# Gemini API key
echo -n "AIzaSy..." | gcloud secrets create GEMINI_API_KEY --data-file=-

# JWT 서명 키
openssl rand -hex 32 | gcloud secrets create AJIN_JWT_SECRET --data-file=-

# Cloud Run 가 이 secret 들을 read 할 수 있도록 IAM
gcloud secrets add-iam-policy-binding GEMINI_API_KEY \
  --member=serviceAccount:$(gcloud projects describe ajin-cb --format='value(projectNumber)')-compute@developer.gserviceaccount.com \
  --role=roles/secretmanager.secretAccessor
```

## 2. 백엔드 첫 배포

### 2.1 환경변수 + secret 박기
```bash
gcloud run services update ajin-backend \
  --region asia-northeast3 --project ajin-cb \
  --set-env-vars \
"ENABLE_FEATURE_A=true,\
ENABLE_FEATURE_B=true,\
ENABLE_FEATURE_E=true,\
EMBEDDING_BACKEND=gemini,\
LLM_ROUTER_PRIMARY=ollama,\
LLM_ROUTER_FALLBACK_ENABLED=false,\
AUTH_BACKEND=firestore,\
CORS_ORIGINS=https://ajin-cb.web.app,\
FEATURE_C_INLINE_ACTIONS=true,\
FEATURE_C_MULTI_LLM=true" \
  --update-secrets \
"GEMINI_API_KEY=GEMINI_API_KEY:latest,\
AJIN_JWT_SECRET=AJIN_JWT_SECRET:latest"
```

### 2.2 코드 deploy (canary + smoke test 자동)
```bash
bash scripts/deploy-backend.sh --mode slim
```

옵션:
- `--mode full` — vectorstore + ML 자산 포함 (이미지 ~3GB)
- `--skip-canary` — canary 없이 즉시 100%
- `--rollback` — 이전 revision 으로 traffic 100% 환원

## 3. Frontend 첫 배포

### 3.1 빌드 + Firebase Hosting
```bash
cd frontend
npm install
npm run build
cd ..

firebase deploy --only hosting --project ajin-cb
# → Hosting URL: https://ajin-cb.web.app
```

### 3.2 Firestore rules + indexes
```bash
firebase deploy --only firestore:rules,firestore:indexes
firebase deploy --only storage  # storage rules
firebase deploy --only database  # realtime DB rules (있다면)
```

## 4. Mac 호스트 셋업 (Ollama 자가 호스팅)

### 4.1 launchd 영속화
```bash
bash scripts/setup-host.sh
# Step 6 — Caddy + Watchdog 영속화 동의
```

### 4.2 Ollama 모델 다운로드
```bash
ollama pull qwen3.5:9b qwen3.5:4b gemma4:e4b gemma4:e2b bge-m3
ollama list  # 5개 모두 표시 확인
```

### 4.3 Cloud Run env 의 `AJIN_OLLAMA_SECRET` 동기화
```bash
NEW_SECRET=$(cat ~/.config/ajin/ollama-secret)
gcloud run services update ajin-backend --region asia-northeast3 \
  --update-env-vars "AJIN_OLLAMA_SECRET=$NEW_SECRET"
```

### 4.4 Watchdog 기동
```bash
launchctl load ~/Library/LaunchAgents/com.ajin.tunnel-watchdog.plist
sleep 30
tail -20 ~/.config/ajin/watchdog.stdout.log
# tunnel URL 추출 + Cloud Run env 자동 update 확인
```

## 5. 검증 (E2E)

```bash
# 1. /api/health
curl -sf https://ajin-cb.web.app/api/health
# {"llm_connected": true, "models_loaded": [...7개...]}

# 2. /api/draft/diagnose — TopBar 가 사용
curl -sf https://ajin-cb.web.app/api/draft/diagnose | python3 -m json.tool
# ollama.ok=true, base_url=https://*.trycloudflare.com

# 3. 채팅 endpoint smoke
curl -X POST https://ajin-cb.web.app/api/onboarding/chat \
  -H "Content-Type: application/json" \
  -d '{"query":"안녕","conversation_id":"prod-1"}'
# data: {"type":"metadata", "metadata":{"provider":"ollama", ...}}
```

## 6. 일상 운영

### 6.1 자동 deploy (GitHub Actions)
`main` 브랜치에 push 시 자동:
- `04_AJIN/backend/`, `core/`, `features/`, `Dockerfile` 변경 → Cloud Run 자동 deploy
- `04_AJIN/frontend/`, `firebase.json` 변경 → Firebase Hosting 자동 deploy

수동 deploy 가 필요한 경우 위 Step 2-3 명령 그대로.

### 6.2 모니터링
- Cloud Run logs: https://console.cloud.google.com/run/detail/asia-northeast3/ajin-backend/logs
- Firebase Hosting analytics: Firebase Console
- Mac 측 cloudflared/Caddy: `tail -f ~/.config/ajin/{caddy,watchdog}.stderr.log`

### 6.3 Secret rotation (90일 권장)
```bash
NEW=$(openssl rand -hex 32)
echo "$NEW" > ~/.config/ajin/ollama-secret
chmod 600 ~/.config/ajin/ollama-secret
launchctl setenv AJIN_OLLAMA_SECRET "$NEW"
launchctl unload ~/Library/LaunchAgents/com.ajin.caddy.plist
launchctl load ~/Library/LaunchAgents/com.ajin.caddy.plist

gcloud run services update ajin-backend --region asia-northeast3 \
  --update-env-vars "AJIN_OLLAMA_SECRET=$NEW"
gcloud run services update-traffic ajin-backend --region asia-northeast3 --to-latest
```

### 6.4 사고 시 빠른 환원 (Gemini-only)
```bash
gcloud run services update ajin-backend --region asia-northeast3 \
  --update-env-vars "LLM_ROUTER_PRIMARY=gemini,LLM_ROUTER_FALLBACK_ENABLED=true,OLLAMA_BASE_URL="
```
즉시 Gemini-only 모드 (Mac 무관). 나중에 다시 ollama 우선으로:
```bash
NEW_TUNNEL=$(cat ~/.config/ajin/last_tunnel_url.txt)
gcloud run services update ajin-backend --region asia-northeast3 \
  --update-env-vars "LLM_ROUTER_PRIMARY=ollama,LLM_ROUTER_FALLBACK_ENABLED=false,OLLAMA_BASE_URL=$NEW_TUNNEL"
```

## 7. Plan B 이행 (미래 GPU 서버)

`ARCHITECTURE.md` 의 Section 8 참고. 같은 Caddy + secret + watchdog 패턴 그대로 GPU 서버에 복제 → Mac 측 watchdog 정지 → 다운타임 < 5분.

## 8. 참고 — Cloud Run 사양

- Region: `asia-northeast3` (서울)
- CPU: 2 / Memory: 2 GiB
- Min instances: 0 (cold start 허용)
- Max instances: 10
- Timeout: 300s
- Concurrency: 80
- Service URL: https://ajin-backend-ncsnraqdaa-du.a.run.app

자원 부족 시 `gcloud run services update --memory=4Gi --cpu=4`.
