# Secrets — 로컬 생성 가이드

이 디렉토리의 실 secret 파일은 git 추적에서 제외됩니다 (`.gitignore`).
로컬 개발 시 본인이 직접 생성하세요. **절대 commit 하지 마세요.**

## `meili_master_key`

Meilisearch 의 master API 키. Docker compose `meilisearch` 서비스가 mount.

```bash
# 32-byte URL-safe base64 키 생성
openssl rand -base64 32 > secrets/meili_master_key
chmod 600 secrets/meili_master_key
```

## `smtp_password`

SMTP 발신 인증 비밀번호 (사내 메일 서버 또는 MailHog).

```bash
# MailHog 등 무인증 SMTP 사용 시 빈 placeholder
: > secrets/smtp_password
chmod 600 secrets/smtp_password

# 또는 실 SMTP 비밀번호
printf '%s' "<YOUR_SMTP_PASSWORD>" > secrets/smtp_password
chmod 600 secrets/smtp_password
```

## 운영 (Cloud Run) 측 secret

GCP Secret Manager 사용 권장. Cloud Run env var 의 `*_FILE` 변수가 secret 마운트 위치를 가리킵니다.

```bash
# 예: GEMINI_API_KEY 등록
echo -n "AIzaSy..." | gcloud secrets create GEMINI_API_KEY --data-file=- --project ajin-cb

# Cloud Run 에서 사용
gcloud run services update ajin-backend --region asia-northeast3 --project ajin-cb \
  --update-secrets=GEMINI_API_KEY=GEMINI_API_KEY:latest
```

## 보안 체크리스트

- [ ] `.env` / `secrets/*` 파일이 git 에 추가되지 않았는지 (`git status` 확인)
- [ ] `secrets/*.example` 만 commit, 실 값은 ignore
- [ ] secret 노출 의심 시 즉시 rotation
