# AJIN Demo Tunnel — Docker 시연 환경

Mac 의 Ollama 를 Cloudflare Tunnel 로 외부에 노출시켜 Cloud Run(`ajin-backend`)이 호출하도록 자동화한 컨테이너.

## 첫 1회 셋업

```bash
# 1. 호스트 Ollama 0.0.0.0 바인딩 (영구 — launchd 등록)
cat > ~/Library/LaunchAgents/com.ajin.ollama.plist <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<plist version="1.0"><dict>
  <key>Label</key><string>com.ajin.ollama</string>
  <key>ProgramArguments</key>
  <array><string>/usr/local/bin/ollama</string><string>serve</string></array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>OLLAMA_HOST</key><string>0.0.0.0:11434</string>
    <key>OLLAMA_ORIGINS</key><string>*</string>
    <key>OLLAMA_NUM_PARALLEL</key><string>4</string>
    <key>OLLAMA_KEEP_ALIVE</key><string>30m</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
</dict></plist>
EOF
launchctl load ~/Library/LaunchAgents/com.ajin.ollama.plist

# 2. 컨테이너 빌드 (3-5분, 1회만)
cd docker/demo-tunnel
docker compose build
```

## 시연 시작 — Docker Desktop UI

1. **Docker Desktop** 앱 실행
2. 좌측 **Containers** 탭 → `ajin-demo-tunnel` 컨테이너 선택
3. **▶ Start** 버튼 클릭
4. **Logs** 탭에서 진행 확인:
   ```
   ✓ Ollama 도달 OK — 15개 모델
   ✓ gcloud 인증 OK (catlife9029@gmail.com)
   ✓ Tunnel URL: https://...trycloudflare.com
   ✓ Cloud Run env 적용 완료
   ✓ summary_ok=true
   ✅ 시연 환경 활성
   ```
5. https://ajin-cb.web.app/draft 접속 → Qwen/Gemma 셀렉터 노출

## 시연 종료

Docker Desktop → **⏹ Stop** 버튼 클릭

→ entrypoint 의 trap 이 자동 실행:
- cloudflared 종료
- Cloud Run env 원복 (OLLAMA_BASE_URL 비움)
- Frontend 는 자동으로 Gemini 단독 모드로 전환

## CLI 사용도 가능

```bash
docker compose up -d     # 첫 생성 + 시작 (백그라운드)
docker compose stop      # 시연 종료 (컨테이너 보존 — Docker Desktop UI에 남음 ⭐권장)
docker compose start     # 다시 시작 (보존된 컨테이너 재가동)
docker compose down      # 컨테이너 완전 제거 (UI에서 사라짐 — 이미지 재빌드 시만 사용)
docker compose logs -f   # 로그 follow
```

### ⚠️ Stop vs Down 차이

| 명령 | 컨테이너 | Docker Desktop UI | 다음 시작 |
|---|---|---|---|
| `docker compose stop` (또는 UI ⏹ Stop) | 보존 | 그대로 표시 | UI ▶ Start 1-클릭 |
| `docker compose down` | **제거** | 사라짐 | `docker compose up -d` 다시 필요 |

→ **시연 종료 시 ⏹ Stop 사용 권장**. 다음 시연 시 ▶ Start 만으로 재활성화 가능.

## 환경변수 오버라이드

`docker-compose.yml` 의 `environment:` 섹션 수정:
```yaml
environment:
  GCP_PROJECT: my-other-project
  GCP_SERVICE: my-other-service
```

## 트러블슈팅

| 증상 | 원인 / 조치 |
|---|---|
| `Ollama 응답 없음` | 호스트에서 `lsof -i :11434` 로 0.0.0.0 바인딩 확인 |
| `gcloud 인증 없음` | 호스트에서 `gcloud auth login` 후 `~/.config/gcloud` 가 마운트되는지 확인 |
| `Tunnel URL 발급 실패` | Mac 인터넷 점검 → 컨테이너 재시작 |
| Stop 버튼 후 Cloud Run env 잔여 | `gcloud run services update ajin-backend --update-env-vars OLLAMA_BASE_URL= --region asia-northeast3` 수동 실행 |
| Docker Desktop UI 가 sleep 시 종료 | 호스트 caffeinate 별도 실행 필요 (컨테이너 안에서는 호스트 sleep 제어 불가) |

## 보안 주의

- 호스트 `~/.config/gcloud` 가 `:ro` 로 마운트되어 컨테이너가 사용자 GCP 계정 권한 행사 가능
- Cloudflare quick tunnel URL 은 인증 없이 누구나 접근 → 시연 외 시간엔 반드시 ⏹ Stop
- 영구 URL/인증 게이트가 필요하면 Cloudflare named tunnel + Access 적용 (별도 설정)
