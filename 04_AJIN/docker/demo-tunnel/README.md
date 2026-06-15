# AJIN Demo Tunnel — Docker 시연 환경

Mac 호스트의 Ollama 를 Cloudflare Tunnel 로 노출하여 production Cloud Run backend (`ajin-backend`) 가 호출하도록 자동화한 컨테이너.

**Production frontend**: https://ajin-ai-assistant-frontend.vercel.app

## 첫 1회 셋업 (Mac 새로 setup 시점, 5-8분)

```bash
gcloud auth login                                # GCP 권한 1회
bash scripts/demo/install_host_bridge.sh         # 호스트 launchd + Secret Manager seed (3-5분)
cd docker/demo-tunnel
docker compose build                             # Dockerfile 빌드 1회 (2-3분)
docker compose create                            # ajin-demo-tunnel 컨테이너 entity 생성
```

`install_host_bridge.sh` 가 자동 처리하는 항목:
- Homebrew 패키지 검증 (`ollama`, `cloudflared`, `jq`, `gcloud`)
- `~/Library/LaunchAgents/com.ajin.ollama.plist` — Ollama `0.0.0.0:11434` 부팅 시 자동 가동 + KeepAlive
- `~/Library/LaunchAgents/com.ajin.ollama-secure-proxy.plist` — secure_proxy.py `127.0.0.1:8434` 부팅 시 자동 가동 + KeepAlive
- `AJIN_OLLAMA_SECRET` — GCP Secret Manager (`ajin-ollama-secret`) 가 single source of truth, 미존재 시 32-byte random 생성 + Secret Manager upsert
- `secrets/.demo-tunnel.env` — compose 의 env_file 로 주입할 cache (chmod 600, .gitignore 이미 처리)

## 일상 시연 — Docker Desktop ▶ Start (60-90초)

1. Docker Desktop 앱 실행
2. 좌측 **Containers** 탭 → `ajin-demo-tunnel` 선택
3. **▶ Start** 클릭
4. **Logs** 탭에서 진행 확인:
   ```
   ▶ [1/5] Mac Ollama secure proxy 도달성 검증
     ✓ Secure proxy 도달 OK — 18개 모델
   ▶ [2/5] gcloud 인증 검증
     ✓ gcloud active account: catlife9029@gmail.com
   ▶ [3/5] Cloudflare Tunnel 시작
     ✓ Tunnel URL: https://....trycloudflare.com
   ▶ [4/5] Cloud Run env 업데이트
     ✓ Cloud Run env 적용 완료
   ▶ [5/5] Cloud Run revision 활성 대기 + 통합 진단
     ✓ overall status=ok
   ✅ 시연 환경 활성 — 모든 기능(A~F) 에 적용됨
   ```
5. https://ajin-ai-assistant-frontend.vercel.app/chat 접속 → Qwen / Gemma 모델 셀렉터 노출

## 시연 종료 — Docker Desktop ⏹ Stop (10-15초)

1. Docker Desktop → ⏹ Stop
2. SIGTERM → entrypoint cleanup trap 자동 실행:
   - cloudflared 종료
   - Cloud Run env 원복 (`OLLAMA_BASE_URL=` 비움, Gemini 단독 모드)
   - healthcheck marker 파일 삭제 → UI 즉시 `unhealthy` 표시
3. 호스트 Ollama / secure_proxy 는 launchd 가 계속 살림 → **다음 ▶ Start 가 즉시 1-클릭 활성**

## healthcheck 의미

Docker Desktop UI 의 컨테이너 상태:
- `healthy` = 3-조건 모두 충족
  1. cloudflared 프로세스 alive
  2. `/tmp/tunnel_url.txt` 존재 (Step 3 성공)
  3. `/tmp/cloudrun_applied` 존재 (Step 4 성공 = production 연동 완료)
- `unhealthy` = 1개라도 빠짐 (빨간 표시 즉시)

## CLI 사용

```bash
docker compose up -d     # 첫 생성 + 시작
docker compose stop      # 시연 종료 (보존, ⭐권장)
docker compose start     # 재가동
docker compose down      # 컨테이너 완전 제거 (이미지 재빌드 시만)
docker compose logs -f   # 로그 follow
```

### ⚠️ Stop vs Down

| 명령 | 컨테이너 | UI | 다음 시작 |
|---|---|---|---|
| `docker compose stop` (또는 ⏹ Stop) | 보존 | 표시 | ▶ Start 1-클릭 |
| `docker compose down` | **제거** | 사라짐 | `docker compose up -d` 필요 |

## 호스트 launchd 가동 해제 (시연 환경 영구 비활성)

```bash
bash scripts/demo/uninstall_host_bridge.sh           # plist 제거, secret cache 유지 (Secret Manager 보존)
bash scripts/demo/uninstall_host_bridge.sh --purge   # 위 + secrets/.demo-tunnel.env 삭제
```

Secret Manager 의 `ajin-ollama-secret` 은 항상 보존 (다음 install 시 재사용).

## 환경변수 override

`docker-compose.yml` 의 `environment:` 섹션 수정:
```yaml
environment:
  GCP_PROJECT: my-other-project
  GCP_SERVICE: my-other-service
  HOSTING_BASE: https://my-other-frontend.vercel.app
  OLLAMA_HOST_INTERNAL: host.docker.internal:8434   # 기본 (secure_proxy port)
```

## 트러블슈팅

| 증상 | 진단 / 조치 |
|---|---|
| Step 1 fail `Secure proxy 응답 없음` | 호스트 launchd 정지 → Mac terminal: `launchctl kickstart -k gui/$(id -u)/com.ajin.ollama-secure-proxy` |
| Step 1 fail (첫 setup 미완료) | `bash scripts/demo/install_host_bridge.sh` 1회 실행 |
| `AJIN_OLLAMA_SECRET` 미설정 + Secret Manager 없음 | install_host_bridge.sh 가 자동 seed — 1회 실행 |
| `gcloud 인증 없음` | 호스트에서 `gcloud auth login` + `~/.config/gcloud` 마운트 확인 |
| Step 3 `Tunnel URL 발급 실패` | Mac 인터넷 점검 + cloudflared docker image 정상 여부 |
| ⏹ Stop 후 Cloud Run env 잔여 (gcloud token 만료 시) | 호스트: `gcloud auth login` 후 entrypoint 의 warn 메시지에 안내된 명령 수동 실행 |
| `host.docker.internal` 도달 불가 (macOS Sequoia IPv6) | 테스트: `docker run --rm alpine sh -c "wget -qO- http://host.docker.internal:8434/api/tags"` — 실패 시 Docker Desktop 재시작 |
| Docker Desktop UI sleep 시 종료 | 호스트 caffeinate 별도 실행 (컨테이너에서 호스트 sleep 제어 불가) |

## 보안

- 호스트 `~/.config/gcloud` 가 RW 로 마운트 → 컨테이너가 사용자 GCP 권한 행사 가능
- `secrets/.demo-tunnel.env` chmod 600 + `.gitignore`(line 25 `secrets/`) 처리됨
- AJIN_OLLAMA_SECRET single source = GCP Secret Manager (host plist + container 모두 같은 출처)
- Cloudflare quick tunnel URL = 인증 secret 헤더로만 보호 → 시연 외 시간엔 반드시 ⏹ Stop
- 영구 URL/Access 필요 시 Cloudflare named tunnel 전환 (별도 작업)

## AJIN_OLLAMA_SECRET lifecycle

```
GCP Secret Manager (ajin-ollama-secret)  ←  single source of truth
        ↑                  ↑                ↑
   install_host_bridge   plist 환경변수   entrypoint Step 1
   (최초 1회 생성/조회)   (영구 cache)     (fallback fetch)
```
