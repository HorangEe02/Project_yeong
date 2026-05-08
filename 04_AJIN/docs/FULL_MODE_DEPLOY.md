# Cloud Run 풀 모드 배포 런북

> ⚠️ **현 운영 모드는 슬림** (Module D + Auth만). 풀 모드 활성화 시 비용 ~$30~50/월.
> 본 문서는 **언제든 풀 모드로 전환할 준비**가 되어 있도록 작성됨.

---

## 풀 모드 vs 슬림 모드 비교

| 항목 | 슬림 (현재) | 풀 모드 |
|---|---|---|
| 활성 기능 | D + Auth | A + B + D + E |
| Dockerfile | `Dockerfile` | `Dockerfile.full` |
| requirements | `requirements-cloudrun.txt` | `requirements-cloudrun-full.txt` |
| .gcloudignore | `.gcloudignore` | `.gcloudignore-full` |
| 이미지 크기 | ~500MB | ~3GB |
| 메모리 | 1Gi | **4Gi** |
| CPU | 1 | **2** |
| Cold start | 3~5초 | 10~30초 |
| 월 비용 (min=1) | ~$5~10 | **~$30~50** |
| 임베딩 | (미사용) | Gemini text-embedding-004 (768 dims) |

---

## 코드 자산 (구현 완료, 실행 보류)

| 파일 | 역할 |
|---|---|
| `Dockerfile.full` | 풀 모드 이미지 (chromadb + langchain + 검색 자산 baking) |
| `requirements-cloudrun-full.txt` | chromadb / langchain / rank-bm25 / xgboost 등 추가 |
| `.gcloudignore-full` | data/documents, vectorstore 등을 빌드 컨텍스트에 포함 |
| `core/embedding_client.py` | `EMBEDDING_BACKEND=gemini` 시 Gemini API 사용 (Ollama → Gemini fallback) |
| `core/llm_router.py:embed()` | 동일 fallback 로직 적용 |
| `scripts/sync_vectorstore_gcs.py` | GCS 영속화 (`upload`/`download`) |
| `scripts/reembed_to_gemini.py` | bge-m3(1024) → text-embedding-004(768) 차원 변경 재인덱싱 |
| `scripts/deploy-fullmode.sh` | gcloud run deploy 자동화 (.gcloudignore 임시 교체 + 원복) |

---

## 풀 모드 활성화 절차

### 사전 준비 (1회성)

```bash
# 1. GCS 버킷 생성 (vectorstore 영속화용 — 옵션)
gcloud storage buckets create gs://ajin-cb-vectorstore \
    --location=asia-northeast3 --project=ajin-cb

# 2. Vectorstore 재인덱싱 (Ollama bge-m3 → Gemini text-embedding-004)
#    이유: 차원이 달라서 (1024 → 768) 기존 인덱스 호환 안 됨
export GEMINI_API_KEY=$(gcloud secrets versions access latest --secret=GEMINI_API_KEY --project=ajin-cb)
python scripts/reembed_to_gemini.py --dry-run     # 통계 확인
python scripts/reembed_to_gemini.py               # 실제 재인덱싱

# 3. (옵션) GCS 업로드 — 이미지 baking 대신 런타임 다운로드 시
python scripts/sync_vectorstore_gcs.py upload
```

### 배포 실행

```bash
# 가장 간단한 방법:
bash scripts/deploy-fullmode.sh

# 직접 실행 시:
cp .gcloudignore .gcloudignore.bak
cp .gcloudignore-full .gcloudignore

gcloud run deploy ajin-backend \
    --source . \
    --region asia-northeast3 \
    --memory 4Gi --cpu 2 \
    --min-instances 1 --max-instances 3 \
    --port 8080 --timeout 300 \
    --execution-environment gen2 \
    --update-env-vars "ENABLE_FEATURE_A=true,ENABLE_FEATURE_B=true,ENABLE_FEATURE_E=true,EMBEDDING_BACKEND=gemini,AUTH_BACKEND=firestore,OLLAMA_BASE_URL=" \
    --project ajin-cb

# 빌드 마치면 .gcloudignore 원복
mv .gcloudignore.bak .gcloudignore
```

### 사후 검증

```bash
URL=$(gcloud run services describe ajin-backend --region asia-northeast3 --project ajin-cb --format='value(status.url)')
TOK=$(curl -sS -X POST -H "Content-Type: application/json" -d '{"employee_id":"admin","password":"admin1234"}' $URL/api/auth/login | jq -r .access_token)

# 모듈 A 검색
curl -sS -H "Authorization: Bearer $TOK" "$URL/api/search?q=프레스+안전거리"

# 모듈 B 초안
curl -sS -X POST -H "Authorization: Bearer $TOK" -H "Content-Type: application/json" \
    -d '{"query":"PPAP 제출 일정 통보","doc_type":"general"}' \
    $URL/api/draft/generate

# 모듈 E 직원 검색
curl -sS -H "Authorization: Bearer $TOK" "$URL/api/employee/search?q=품질보증"
```

---

## 슬림 모드 복귀

비용 절감 또는 안정화 목적으로 다시 슬림 모드로 돌아가려면:

```bash
gcloud run deploy ajin-backend \
    --source . \
    --region asia-northeast3 \
    --memory 1Gi --cpu 1 \
    --min-instances 1 --max-instances 3 \
    --port 8080 --timeout 60 \
    --update-env-vars "ENABLE_FEATURE_A=false,ENABLE_FEATURE_B=false,ENABLE_FEATURE_E=false,OLLAMA_BASE_URL=,AUTH_BACKEND=firestore" \
    --project ajin-cb

# 슬림 .gcloudignore + Dockerfile (default) 사용 — 자동
```

---

## 트러블슈팅

| 증상 | 원인 | 해결 |
|---|---|---|
| Cold start > 60초 | sentence-transformers 모델 로드 (활성 시) | Gemini 임베딩 백엔드 사용 (`EMBEDDING_BACKEND=gemini`) |
| ChromaDB `dimension mismatch` 에러 | 기존 1024-dim 인덱스를 768-dim Gemini로 조회 | `python scripts/reembed_to_gemini.py` 실행 |
| 메모리 OOM | 4Gi 부족 | `--memory 8Gi --cpu 4`로 증액 |
| Gemini API 429/할당량 | 임베딩 호출 폭주 | rate-limit 추가 또는 Ollama 백엔드로 전환 |
| 빌드 타임아웃 | Cloud Build 기본 10분 초과 | `--timeout=20m` 옵션 추가 |
| 인덱스 재배포마다 사라짐 | 이미지 baking 시 매번 초기화 | GCS 영속화 (`scripts/sync_vectorstore_gcs.py`) |

---

## 관련 비용 모니터링

- Phase 3 알림 정책 (메모리 ≥85%, 인스턴스 ≥3)이 이미 활성 → 임계 도달 시 catlife9029@gmail.com 으로 메일 도착
- Cloud Run 청구: https://console.cloud.google.com/billing?project=ajin-cb
- Gemini API 사용량: https://aistudio.google.com/app/apikey
