#!/usr/bin/env bash
# Supabase 연결 점검 — .env 의 SUPABASE_URL / SUPABASE_ANON_KEY 로 REST 도달성 확인.
# (RLS가 켜져 있어 데이터는 비어 보이지만 200이면 연결·인증 정상)
set -e
cd "$(dirname "$0")/.."

# .env 로드
[ -f .env ] && set -a && . ./.env && set +a

if [ -z "$SUPABASE_URL" ] || [ -z "$SUPABASE_ANON_KEY" ]; then
  echo "SUPABASE_URL / SUPABASE_ANON_KEY 가 .env 에 없습니다."; exit 1
fi

echo "URL: $SUPABASE_URL"
code=$(curl -s -o /tmp/_sb.txt -w '%{http_code}' \
  "$SUPABASE_URL/rest/v1/meetings?select=id&limit=1" \
  -H "apikey: $SUPABASE_ANON_KEY" -H "Authorization: Bearer $SUPABASE_ANON_KEY")
echo "REST /meetings: HTTP $code  body=$(cat /tmp/_sb.txt)"
authcode=$(curl -s -o /dev/null -w '%{http_code}' "$SUPABASE_URL/auth/v1/health" -H "apikey: $SUPABASE_ANON_KEY")
echo "auth health: HTTP $authcode"
[ "$code" = "200" ] && echo "✅ 연결 정상 (RLS로 데이터는 서버 role 에서만 조회)" || echo "⚠️ 연결 확인 필요"
