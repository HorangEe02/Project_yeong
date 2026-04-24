#!/usr/bin/env python3
"""
T1-1a — audit_logs 를 hospital-scoped nested 구조 `/audit_logs_v2/{hid}/{pushId}` 로 마이그레이션.

용도:
- Legacy flat `/audit_logs/{pushId}` 에 누적된 audit 엔트리를 hospital 별로 분류.
- bucket 분류 규칙:
    1) meta.hospitalId 존재 → 그 값 사용
    2) meta.claims.hospitalId 존재 → 그 값 사용
    3) action 이 'chatbot.*' 또는 'wait_queue.*' 이고 target 가 string → target 을 hospitalId 로 간주
    4) 그 외 → 'platform' bucket (platformAdmin 시스템 액션)
- pushId 는 원본 그대로 유지 → 시계열/추적 보존.
- 기존 /audit_logs 는 삭제하지 않음 (T1-1b dual-write 기간 유지).

사용:
    python3 scripts/migrate-audit-logs-to-v2.py --dry-run        # 분석만, 쓰기 안 함
    python3 scripts/migrate-audit-logs-to-v2.py --apply           # 백업 + v2 write
    python3 scripts/migrate-audit-logs-to-v2.py --rollback TS     # audit_logs_backup_{TS} 로 /audit_logs 복원

전제: gcloud auth application-default 또는 `print-access-token` 로 토큰 발급 가능.
"""
import argparse
import json
import subprocess
import sys
import time
import urllib.request

DB = 'https://mediway-demo-default-rtdb.firebaseio.com'


def token() -> str:
    return subprocess.run(
        ['gcloud', 'auth', 'print-access-token'],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def api(method: str, path: str, body=None):
    p = path if path.startswith('/') else f'/{path}'
    url = f'{DB}{p}.json?access_token={token()}'
    data = json.dumps(body).encode() if body is not None else None
    headers = {'Content-Type': 'application/json'} if body is not None else {}
    req = urllib.request.Request(url, method=method, data=data, headers=headers)
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read() or b'null')


def bucket_for(entry: dict) -> str:
    meta = entry.get('meta') or {}
    if isinstance(meta, dict):
        if meta.get('hospitalId'):
            return str(meta['hospitalId'])
        cl = meta.get('claims')
        if isinstance(cl, dict) and cl.get('hospitalId'):
            return str(cl['hospitalId'])
    tgt = entry.get('target')
    action = entry.get('action', '')
    if isinstance(tgt, str) and action.startswith(('chatbot.', 'wait_queue.')):
        return tgt
    return 'platform'


def dry_run() -> None:
    src = api('GET', '/audit_logs') or {}
    buckets: dict = {}
    for k, v in src.items():
        buckets.setdefault(bucket_for(v), []).append(k)
    print(f'source /audit_logs: {len(src)} entries')
    for b, keys in sorted(buckets.items(), key=lambda x: -len(x[1])):
        print(f'  → {b}: {len(keys)} entries')
    print('no writes performed (dry-run)')


def apply() -> None:
    src = api('GET', '/audit_logs') or {}
    if not src:
        print('source is empty — nothing to migrate')
        return

    ts = int(time.time() * 1000)
    backup_path = f'/audit_logs_backup_{ts}'
    api('PUT', backup_path, src)
    print(f'✓ backup: {backup_path} ({len(src)} entries)')

    payload: dict = {}
    for k, entry in src.items():
        payload[f'audit_logs_v2/{bucket_for(entry)}/{k}'] = entry
    api('PATCH', '/', payload)
    print(f'✓ v2 write: {len(payload)} entries')

    v2 = api('GET', '/audit_logs_v2') or {}
    total = sum(len(b) for b in v2.values())
    for b, items in v2.items():
        print(f'  audit_logs_v2/{b}: {len(items)}')
    print(f'  total v2: {total} / source: {len(src)} / match: {total == len(src)}')


def rollback(ts: str) -> None:
    backup_path = f'/audit_logs_backup_{ts}'
    data = api('GET', backup_path)
    if not data:
        print(f'backup not found at {backup_path}', file=sys.stderr)
        sys.exit(1)
    api('PUT', '/audit_logs', data)
    print(f'✓ restored /audit_logs from {backup_path} ({len(data)} entries)')
    print('NOTE: /audit_logs_v2 is NOT removed by this command — remove manually if needed.')


def main() -> None:
    p = argparse.ArgumentParser()
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument('--dry-run', action='store_true')
    g.add_argument('--apply', action='store_true')
    g.add_argument('--rollback', metavar='TIMESTAMP', help='timestamp suffix of audit_logs_backup_{TS}')
    args = p.parse_args()

    if args.dry_run:
        dry_run()
    elif args.apply:
        apply()
    elif args.rollback:
        rollback(args.rollback)


if __name__ == '__main__':
    main()
