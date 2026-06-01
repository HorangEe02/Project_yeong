# 08. Docker 복구 + 컨테이너 정리

> 브랜치 성격: ops/infra
> 대응 커밋: 없음 (운영 작업)

---

## 1. 사건: backend 컨테이너 시작 불가

재빌드 후 `docker compose up -d backend`로 컨테이너를 **재생성**하자, 새 컨테이너가 시작 불가(`Created`) 상태에 빠졌다.

```
Error response from daemon: error while creating mount source path
'/host_mnt/Volumes/Corsair EX400U Media/.../data/nutrition_reference':
mkdir /host_mnt/Volumes/Corsair EX400U Media: file exists
```

- 원인: **Docker Desktop의 stale bind-mount 버그** — 볼륨 경로의 **공백**(`Corsair EX400U Media`)으로 Docker VM 내 `/host_mnt` 상태가 꼬임.
- `docker start` 3회·`rm`+`up` 모두 동일 버그로 실패. 호스트 Docker 이슈(코드 무관).
- db·redis·ajin·supabase 11개는 정상(먼저 마운트를 확립한 상태라 영향 없음).

---

## 2. 코드 검증 (마운트 없이)

서비스 복구와 별개로, 코드는 **no-mount 일회용 컨테이너**로 검증(버그 우회):

- `docker run --rm --entrypoint sh <image>` + pytest
- **374 tests, 368 passed, 6 failed** — 실패 6건은 전부 `/data`·`/config` 마운트 경로 의존 테스트(handoff §12.5 클래스), 코드 무관

---

## 3. 복구 (사용자 승인 후)

Docker Desktop 재시작으로 stale 마운트 초기화:

- `osascript`로 Docker Desktop quit → `open -a Docker` → 데몬 대기(daemon up, server 29.5.2)
- stale `Created` backend 컨테이너 `rm` → `docker compose up -d backend`
- 결과: **backend Started, health=200, healthy**
- 라이브 컨테이너에서 전체 스위트 재실행: **374 tests, 372 passed, 2 failed**
  - 마운트 복구로 registration 4건 통과(368→372)
  - 잔여 2건은 `/config/implementation-readiness.settings.json` env 의존(pre-existing, 코드 무관)

---

## 4. 잔여 컨테이너 정리

Docker 재시작 잔여물 2개(크래시 아님):

| 컨테이너 | 상태 | 조치 |
|---|---|---|
| `lemon-aid-backend-webtest` | Exited(143=SIGTERM) | executor 테스트 임시 인스턴스 → **docker rm 삭제** |
| `supabase_edge_runtime_...` | Exited(137=SIGKILL, OOM 아님) | RestartPolicy=no라 자동복구 안 됨 → **docker start 재기동** |

- 둘 다 정리 완료: webtest `REMOVED_OK`, edge_runtime `state=running`
- 최종: lemon 관련 비정상 컨테이너 **0개**, backend health=200

---

## 5. 교훈

- 공백 포함 경로 + Docker Desktop bind-mount는 컨테이너 **재생성** 시 취약. 가능하면 재생성 대신 재시작 사용.
- 서비스 다운을 유발하는 `up -d`(재생성)는 코드 검증과 분리하고, 복구가 다른 프로젝트를 건드릴 땐 승인 게이트.
